"""
Hi-Lo Card - Predict Higher or Lower

Player is shown a card (2-14, Ace high)
Must predict if next card is Higher or Lower
Quick 30-second rounds
Multiplier based on prediction difficulty

FIXED: socketio event handlers moved OUT of module level (they referenced
       `socketio = None` at import time, which crashed the import and is
       why this blueprint was never registered in app/__init__.py).
FIXED: added get_hilocard_blueprint(sio, app) factory function, matching
       the pattern used by mzizicrash_blueprint.py, so app/__init__.py
       has something to call and register.
FIXED: round_number seeded from DB max on loop start (same fix as the
       crash game) to avoid unique constraint collisions after restarts.
FIXED: render_template path corrected to games/hilocard.html to match the
       actual template file location.
"""

import random
import traceback
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user

from app.extensions import db

# ============================================================================
# MODELS
# ============================================================================

class HiLoRound(db.Model):
    __tablename__ = 'hilo_rounds'
    
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, nullable=False, unique=True)
    current_card = db.Column(db.Integer, nullable=False)  # 2-14
    next_card = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HiloBet(db.Model):
    __tablename__ = 'hilo_bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('hilo_rounds.id'))
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    prediction = db.Column(db.String(10))  # 'higher' or 'lower'
    multiplier = db.Column(db.Float)
    payout_amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HiLoStats(db.Model):
    __tablename__ = 'hilo_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    total_wagered = db.Column(db.Numeric(10, 2), default=0)
    total_won = db.Column(db.Numeric(10, 2), default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)

# ============================================================================
# BLUEPRINT
# ============================================================================

hilo_bp = Blueprint('hilo', __name__, url_prefix='/hi-lo-card', template_folder='templates')

socketio = None
_loop_started = False
game_state = {
    'round_number': 0,
    'current_round': None,
    'is_betting': True,
    'players': {},
}

# ============================================================================
# GAME LOGIC
# ============================================================================

def place_bet(user_id, amount, prediction):
    """Place Hi-Lo bet"""
    try:
        amount = Decimal(str(amount))
        
        if amount <= 0 or amount > Decimal("10000"):
            return {"success": False, "error": "Invalid bet (10-10000 KES)"}
        
        if prediction not in ['higher', 'lower']:
            return {"success": False, "error": "Invalid prediction"}
        
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
        
        bet = HiloBet(
            user_id=user_id,
            round_id=game_state['current_round'].id,
            bet_amount=amount,
            prediction=prediction,
            status='pending'
        )
        db.session.add(bet)
        db.session.commit()
        
        game_state['players'][user_id] = {
            'bet_id': bet.id,
            'amount': float(amount),
            'prediction': prediction
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
    """Determine winners/losers"""
    try:
        game = game_state['current_round']
        game.status = 'resolved'
        
        bets = HiloBet.query.filter_by(round_id=game.id, status='pending').all()
        
        for bet in bets:
            current = game.current_card
            next_card = game.next_card
            
            # Calculate multiplier based on difficulty
            diff = abs(next_card - current)
            base_multiplier = 2.0 + (diff / 12.0)  # 2.0x to 3.0x
            
            # Check prediction
            is_correct = False
            if bet.prediction == 'higher' and next_card > current:
                is_correct = True
            elif bet.prediction == 'lower' and next_card < current:
                is_correct = True
            elif next_card == current:
                # Tie = big payout!
                is_correct = True
                base_multiplier = 11.0
            
            if is_correct:
                bet.status = 'won'
                payout = bet.bet_amount * Decimal(str(base_multiplier))
                bet.multiplier = base_multiplier
                bet.payout_amount = payout
                
                bet.user.wallet.balance += payout
                
                if not bet.user.hilo_stats:
                    bet.user.hilo_stats = HiLoStats(user_id=bet.user_id)
                
                profit = payout - bet.bet_amount
                bet.user.hilo_stats.total_won = (bet.user.hilo_stats.total_won or Decimal('0')) + profit
                bet.user.hilo_stats.win_count = (bet.user.hilo_stats.win_count or 0) + 1
            else:
                bet.status = 'lost'
                bet.multiplier = 0
                
                if not bet.user.hilo_stats:
                    bet.user.hilo_stats = HiLoStats(user_id=bet.user_id)
                
                bet.user.hilo_stats.total_lost = (bet.user.hilo_stats.total_lost or Decimal('0')) + bet.bet_amount
                bet.user.hilo_stats.loss_count = (bet.user.hilo_stats.loss_count or 0) + 1
        
        db.session.commit()
    
    except Exception as e:
        db.session.rollback()
        print(f"Error resolving: {e}")

# ============================================================================
# ROUTES
# ============================================================================

@hilo_bp.route('/', methods=['GET'])
@login_required
def index():
    wallet = current_user.wallet if hasattr(current_user, 'wallet') else None
    balance = float(wallet.balance) if wallet else 0.0
    return render_template('games/hilocard.html', balance=balance)

@hilo_bp.route('/api/status', methods=['GET'])
@login_required
def api_status():
    if not game_state['current_round']:
        return jsonify({'status': 'initializing'})
    
    return jsonify({
        'round_number': game_state['round_number'],
        'status': game_state['current_round'].status,
        'is_betting': game_state['is_betting'],
        'current_card': game_state['current_round'].current_card,
        'players_count': len(game_state['players'])
    })

@hilo_bp.route('/api/bet', methods=['POST'])
@login_required
def api_bet():
    data = request.get_json()
    result = place_bet(current_user.id, data.get('amount'), data.get('prediction'))
    return jsonify(result)

@hilo_bp.route('/api/history', methods=['GET'])
@login_required
def api_history():
    limit = request.args.get('limit', 20, type=int)
    bets = HiloBet.query.filter_by(user_id=current_user.id)\
        .order_by(HiloBet.created_at.desc())\
        .limit(limit).all()
    
    return jsonify([{
        'prediction': b.prediction,
        'amount': float(b.bet_amount),
        'multiplier': b.multiplier or 0,
        'payout': float(b.payout_amount) if b.payout_amount else None,
        'status': b.status
    } for b in bets])

@hilo_bp.route('/api/stats', methods=['GET'])
@login_required
def api_stats():
    stats = current_user.hilo_stats
    if not stats:
        stats = HiLoStats(user_id=current_user.id)
        db.session.add(stats)
        db.session.commit()
    
    return jsonify({
        'total_wagered': float(stats.total_wagered or 0),
        'total_won': float(stats.total_won or 0),
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

    @sio.on('connect', namespace='/hi-lo-card')
    def on_connect():
        socketio.emit('connection_response', {'data': 'Connected to Hi-Lo'}, namespace='/hi-lo-card')

    @sio.on('join_game', namespace='/hi-lo-card')
    def on_join():
        socketio.emit('player_joined', {'players': len(game_state['players'])}, namespace='/hi-lo-card', skip_sid=request.sid)

    if not _loop_started:
        if app:
            socketio.start_background_task(game_loop, app)
        _loop_started = True

def game_loop(app):
    """Hi-Lo game loop"""
    print("✅ Hi-Lo game loop started")

    # Seed the in-memory round counter from the DB's current max round_number
    # on startup so restarts don't collide with rows already in hilo_rounds.
    with app.app_context():
        try:
            last_round = HiLoRound.query.order_by(HiLoRound.round_number.desc()).first()
            game_state['round_number'] = last_round.round_number if last_round else 0
            print(f"✅ Resuming Hi-Lo round counter from {game_state['round_number']}")
        except Exception as e:
            print(f"⚠️ Could not read last Hi-Lo round_number, defaulting to 0: {e}")
            game_state['round_number'] = 0

    while True:
        try:
            with app.app_context():
                # New round
                game_state['round_number'] += 1
                current_card = random.randint(2, 14)
                next_card = random.randint(2, 14)
                
                new_game = HiLoRound(
                    round_number=game_state['round_number'],
                    current_card=current_card,
                    next_card=next_card,
                    status='pending'
                )
                db.session.add(new_game)
                db.session.commit()
                
                game_state['current_round'] = new_game
                game_state['is_betting'] = True
                game_state['players'] = {}
                
                socketio.emit('new_round', {
                    'round_number': game_state['round_number'],
                    'current_card': current_card,
                    'betting_window': 8
                }, namespace='/hi-lo-card')
                
                socketio.sleep(8)
                
                # Reveal card
                game_state['is_betting'] = False
                resolve_round()
                
                socketio.emit('card_revealed', {
                    'next_card': next_card,
                    'round_number': game_state['round_number']
                }, namespace='/hi-lo-card')
                
                socketio.sleep(3)
        
        except Exception as e:
            print(f"❌ Hi-Lo game loop error: {e}")
            traceback.print_exc()
            socketio.sleep(1)

# ============================================================================
# FACTORY
# ============================================================================

def get_hilocard_blueprint(sio, app):
    """Factory function to create the blueprint and start the game loop.
    Matches the pattern used by get_mzizicrash_blueprint() so app/__init__.py
    can register this the same way."""
    init_socketio(sio, app)
    return hilo_bp
