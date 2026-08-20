"""
Plinko Mzizi - Ball Drop Physics Game

Ball drops through pegs and lands in slots
Each slot has different multiplier
Central slots = higher payouts
Edge slots = lower payouts

FIXED: socketio event handlers moved OUT of module level (they referenced
       `socketio = None` at import time, which crashed the import and is
       why this blueprint was never registered in app/__init__.py).
FIXED: added get_plinkomzizi_blueprint(sio, app) factory function, matching
       the pattern used by mzizicrash_blueprint.py, so app/__init__.py
       has something to call and register.
FIXED: round_number seeded from DB max on loop start to avoid unique
       constraint collisions after restarts.
FIXED: render_template path corrected to games/plinkomzizi.html to match
       the actual template file location.
FIXED: resolve_round() now marks sub-1.0x outcomes as losses and tracks
       total_lost / loss_count on PlinkoStats (previously every round was
       recorded as a "win" regardless of multiplier).
"""

import random
import traceback
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db

# ============================================================================
# MODELS
# ============================================================================

class PlinkoRound(db.Model):
    __tablename__ = 'plinko_rounds'
    
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, nullable=False, unique=True)
    landed_slot = db.Column(db.Integer, nullable=False)  # 0-8 (9 slots)
    multiplier = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlinkoBet(db.Model):
    __tablename__ = 'plinko_bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('plinko_rounds.id'))
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    landed_slot = db.Column(db.Integer)
    multiplier = db.Column(db.Float)
    payout_amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlinkoStats(db.Model):
    __tablename__ = 'plinko_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    total_wagered = db.Column(db.Numeric(10, 2), default=0)
    total_won = db.Column(db.Numeric(10, 2), default=0)
    total_lost = db.Column(db.Numeric(10, 2), default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref='plinko_stats')

# ============================================================================
# BLUEPRINT
# ============================================================================

plinko_bp = Blueprint('plinko', __name__, url_prefix='/plinko-mzizi', template_folder='templates')

socketio = None
_loop_started = False
game_state = {
    'round_number': 0,
    'current_round': None,
    'is_betting': True,
    'landed_slot': None,
    'players': {},
}

# Plinko slot multipliers (0-8, center is highest)
SLOT_MULTIPLIERS = [0.5, 1.2, 1.8, 2.5, 5.0, 2.5, 1.8, 1.2, 0.5]

# ============================================================================
# GAME LOGIC
# ============================================================================

def place_bet(user_id, amount):
    """Place Plinko bet"""
    try:
        amount = Decimal(str(amount))
        
        if amount <= 0 or amount > Decimal("10000"):
            return {"success": False, "error": "Invalid bet (10-10000 KES)"}
        
        if not game_state['current_round'] or not game_state['is_betting']:
            return {"success": False, "error": "Betting closed"}
        
        if user_id in game_state['players']:
            return {"success": False, "error": "Already bet this round"}
        
        from app.models import User
        user = User.query.get(user_id)
        
        if not user or not hasattr(user, 'wallet'):
            return {"success": False, "error": "User/wallet not found"}
        
        if user.wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}
        
        user.wallet.balance -= amount
        
        bet = PlinkoBet(
            user_id=user_id,
            round_id=game_state['current_round'].id,
            bet_amount=amount,
            status='pending'
        )
        db.session.add(bet)
        db.session.commit()
        
        game_state['players'][user_id] = {
            'bet_id': bet.id,
            'amount': float(amount)
        }
        
        return {
            'success': True,
            'bet_id': bet.id,
            'balance': float(user.wallet.balance)
        }
    
    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}

def resolve_round():
    """Determine all payouts based on landed slot.
    FIXED: a multiplier below 1.0x now counts as a loss (total_lost /
    loss_count), not a win. Previously every bet was recorded as won
    regardless of whether the payout was below the stake."""
    try:
        game = game_state['current_round']
        game.status = 'resolved'
        game.landed_slot = game_state['landed_slot']
        game.multiplier = SLOT_MULTIPLIERS[game_state['landed_slot']]
        
        bets = PlinkoBet.query.filter_by(round_id=game.id, status='pending').all()
        
        for bet in bets:
            multiplier = game.multiplier
            payout = bet.bet_amount * Decimal(str(multiplier))
            
            bet.landed_slot = game_state['landed_slot']
            bet.multiplier = multiplier
            bet.payout_amount = payout
            
            # Add to wallet regardless of win/loss (payout can be partial, e.g. 0.5x)
            bet.user.wallet.balance += payout
            
            if not bet.user.plinko_stats:
                bet.user.plinko_stats = PlinkoStats(user_id=bet.user_id)
            
            profit = payout - bet.bet_amount
            
            if multiplier >= Decimal('1.0'):
                bet.status = 'won'
                bet.user.plinko_stats.total_won = (bet.user.plinko_stats.total_won or Decimal('0')) + profit
                bet.user.plinko_stats.win_count = (bet.user.plinko_stats.win_count or 0) + 1
            else:
                bet.status = 'lost'
                bet.user.plinko_stats.total_lost = (bet.user.plinko_stats.total_lost or Decimal('0')) + (bet.bet_amount - payout)
                bet.user.plinko_stats.loss_count = (bet.user.plinko_stats.loss_count or 0) + 1
        
        db.session.commit()
    
    except Exception as e:
        db.session.rollback()
        print(f"Error resolving: {e}")

# ============================================================================
# ROUTES
# ============================================================================

@plinko_bp.route('/', methods=['GET'])
@login_required
def index():
    wallet = current_user.wallet if hasattr(current_user, 'wallet') else None
    balance = float(wallet.balance) if wallet else 0.0
    return render_template('games/plinkomzizi.html', balance=balance, multipliers=SLOT_MULTIPLIERS)

@plinko_bp.route('/api/bet', methods=['POST'])
@login_required
def api_bet():
    data = request.get_json()
    result = place_bet(current_user.id, data.get('amount'))
    return jsonify(result)

@plinko_bp.route('/api/history', methods=['GET'])
@login_required
def api_history():
    limit = request.args.get('limit', 20, type=int)
    bets = PlinkoBet.query.filter_by(user_id=current_user.id)\
        .order_by(PlinkoBet.created_at.desc())\
        .limit(limit).all()
    
    return jsonify([{
        'amount': float(b.bet_amount),
        'slot': b.landed_slot,
        'multiplier': b.multiplier or 0,
        'payout': float(b.payout_amount) if b.payout_amount else None,
        'status': b.status
    } for b in bets])

@plinko_bp.route('/api/stats', methods=['GET'])
@login_required
def api_stats():
    stats = current_user.plinko_stats
    if not stats:
        stats = PlinkoStats(user_id=current_user.id)
        db.session.add(stats)
        db.session.commit()
    
    return jsonify({
        'total_wagered': float(stats.total_wagered or 0),
        'total_won': float(stats.total_won or 0),
        'total_lost': float(stats.total_lost or 0),
        'win_count': stats.win_count or 0,
        'loss_count': stats.loss_count or 0
    })

# ============================================================================
# WEBSOCKET + GAME LOOP
# ============================================================================

def init_socketio(sio, app=None):
    """Register SocketIO handlers and start the game loop.
    FIXED: handlers are registered here, at call time (after `sio` is a
    real SocketIO instance), instead of as module-level decorators against
    `socketio = None`, which crashed on import."""
    global socketio, _loop_started
    socketio = sio

    @sio.on('connect', namespace='/plinko-mzizi')
    def on_connect():
        socketio.emit('connection_response', {'data': 'Connected to Plinko'}, namespace='/plinko-mzizi')

    @sio.on('join_game', namespace='/plinko-mzizi')
    def on_join():
        socketio.emit('player_joined', {'players': len(game_state['players'])}, namespace='/plinko-mzizi', skip_sid=request.sid)

    if not _loop_started:
        if app:
            socketio.start_background_task(game_loop, app)
        _loop_started = True

def game_loop(app):
    """Plinko game loop"""
    print("✅ Plinko game loop started")

    # Seed the in-memory round counter from the DB's current max round_number
    # on startup so restarts don't collide with rows already in plinko_rounds.
    with app.app_context():
        try:
            last_round = PlinkoRound.query.order_by(PlinkoRound.round_number.desc()).first()
            game_state['round_number'] = last_round.round_number if last_round else 0
            print(f"✅ Resuming Plinko round counter from {game_state['round_number']}")
        except Exception as e:
            print(f"⚠️ Could not read last Plinko round_number, defaulting to 0: {e}")
            game_state['round_number'] = 0

    while True:
        try:
            with app.app_context():
                # New round
                game_state['round_number'] += 1
                game_state['landed_slot'] = random.randint(0, 8)
                
                new_game = PlinkoRound(
                    round_number=game_state['round_number'],
                    landed_slot=game_state['landed_slot'],
                    multiplier=SLOT_MULTIPLIERS[game_state['landed_slot']],
                    status='pending'
                )
                db.session.add(new_game)
                db.session.commit()
                
                game_state['current_round'] = new_game
                game_state['is_betting'] = True
                game_state['players'] = {}
                
                socketio.emit('new_round', {
                    'round_number': game_state['round_number'],
                    'betting_window': 6
                }, namespace='/plinko-mzizi')
                
                socketio.sleep(6)
                
                # Ball drops
                game_state['is_betting'] = False
                socketio.emit('ball_drop', {
                    'round_number': game_state['round_number']
                }, namespace='/plinko-mzizi')
                
                socketio.sleep(3)
                
                # Ball lands
                resolve_round()
                socketio.emit('ball_landed', {
                    'slot': game_state['landed_slot'],
                    'multiplier': SLOT_MULTIPLIERS[game_state['landed_slot']],
                    'round_number': game_state['round_number']
                }, namespace='/plinko-mzizi')
                
                socketio.sleep(3)
        
        except Exception as e:
            print(f"❌ Plinko game loop error: {e}")
            traceback.print_exc()
            socketio.sleep(1)

# ============================================================================
# FACTORY
# ============================================================================

def get_plinkomzizi_blueprint(sio, app):
    """Factory function to create the blueprint and start the game loop.
    Matches the pattern used by get_mzizicrash_blueprint() so app/__init__.py
    can register this the same way."""
    init_socketio(sio, app)
    return plinko_bp
