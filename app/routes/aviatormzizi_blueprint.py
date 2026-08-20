"""
Aviator Mzizi - FIXED VERSION with corrected app context
Key fixes: 
1. app_context moved INSIDE the game loop
2. Removed broadcast=True parameter (not supported in Flask-SocketIO 5.3.6)
"""

import hashlib
import secrets
import time
import traceback
import math
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.wallet import Wallet, Transaction

_loop_started = False

# ============================================================================
# MODELS - Embedded here for simplicity
# ============================================================================

class AviatorRound(db.Model):
    __tablename__ = 'aviator_rounds'
    
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, nullable=False, unique=True)
    crash_point = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    started_at = db.Column(db.DateTime)
    crashed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AviatorBet(db.Model):
    __tablename__ = 'aviator_bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('aviator_rounds.id'))
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    cashout_at = db.Column(db.Float)
    payout_amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='aviator_bets')

class AviatorStats(db.Model):
    __tablename__ = 'aviator_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    total_wagered = db.Column(db.Numeric(10, 2), default=0)
    total_won = db.Column(db.Numeric(10, 2), default=0)
    total_lost = db.Column(db.Numeric(10, 2), default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)
    best_multiplier = db.Column(db.Float, default=0)
    user = db.relationship('User', backref='aviator_stats_rel')

# ============================================================================
# GAME STATE
# ============================================================================

class GameState:
    def __init__(self):
        self.current_round = None
        self.round_number = 0
        self.is_betting = True
        self.crash_point = None
        self.live_multiplier = 1.0
        self.players = {}

game_state = GameState()

# ============================================================================
# CRASH ENGINE
# ============================================================================

class CrashEngine:
    @staticmethod
    def generate_server_seed():
        return secrets.token_hex(32)

    @staticmethod
    def generate_crash_point(server_seed, client_nonce=None):
        """Generate crash point from 1.01x to 100.00x"""
        if client_nonce is None:
            client_nonce = secrets.token_hex(16)

        combined = f"{server_seed}{client_nonce}"
        hash_result = hashlib.sha256(combined.encode()).hexdigest()
        hash_int = int(hash_result[:8], 16)
        rand_val = hash_int / 0xffffffff
        rand_val = max(0.00001, min(0.99999, rand_val))

        multiplier = 100.0 * math.exp(-math.log(100.0) * rand_val)
        multiplier = max(Decimal("1.01"), min(Decimal("100.00"), Decimal(str(round(multiplier, 2)))))

        return float(multiplier), client_nonce

# ============================================================================
# GAME LOGIC
# ============================================================================

def place_bet(user_id, amount):
    """Place a bet"""
    try:
        amount = Decimal(str(amount))
        
        if amount <= 0 or amount > Decimal("100000"):
            return {"success": False, "error": "Invalid bet amount"}

        if not game_state.current_round or not game_state.is_betting:
            return {"success": False, "error": "Betting window closed"}

        if user_id in game_state.players:
            return {"success": False, "error": "Already have a bet"}

        from app.models.user import User
        user = User.query.get(user_id)
        
        if not user or not hasattr(user, 'wallet'):
            return {"success": False, "error": "User not found"}

        if user.wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}

        wallet = user.wallet
        wallet.balance -= amount

        bet = AviatorBet(
            user_id=user_id,
            round_id=game_state.current_round.id,
            bet_amount=amount,
            status='active'
        )
        db.session.add(bet)

        # Keep the same wallet ledger used by the rest of the application.
        # The amount is negative because this transaction debits the wallet.
        db.session.add(Transaction(
            wallet_id=wallet.id,
            type="stake",
            amount=-amount,
            balance_after=wallet.balance,
            reference=f"aviator:{game_state.current_round.id}:stake:{bet.id}",
            status="completed",
        ))

        stats = getattr(user, "aviator_stats_rel", None)
        if not stats:
            stats = AviatorStats(user_id=user_id)
            db.session.add(stats)
        stats.total_wagered = (stats.total_wagered or Decimal("0")) + amount
        db.session.commit()

        game_state.players[user_id] = {
            "bet_id": bet.id,
            "bet_amount": float(amount),
            "status": "active"
        }

        return {
            "success": True,
            "bet_id": bet.id,
            "balance": float(wallet.balance)
        }

    except Exception as e:
        db.session.rollback()
        print(f"Place bet error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def cashout_bet(user_id):
    """Cash out current bet"""
    try:
        player = game_state.players.get(user_id)
        if not player or player["status"] != "active":
            return {"success": False, "error": "No active bet"}

        if not game_state.current_round or game_state.current_round.status != "live":
            return {"success": False, "error": "Not live"}

        multiplier = Decimal(str(game_state.live_multiplier))
        
        bet = AviatorBet.query.get(player["bet_id"])
        if not bet:
            return {"success": False, "error": "Bet not found"}

        payout = bet.bet_amount * multiplier

        bet.status = "cashed_out"
        bet.cashout_at = float(multiplier)
        bet.payout_amount = payout

        user = bet.user
        wallet = user.wallet
        wallet.balance += payout

        stats = getattr(user, "aviator_stats_rel", None)
        if not stats:
            stats = AviatorStats(user_id=user_id)
            db.session.add(stats)

        profit = payout - bet.bet_amount
        stats.total_won = (stats.total_won or Decimal("0")) + profit
        stats.win_count = (stats.win_count or 0) + 1
        stats.best_multiplier = max(stats.best_multiplier or 0, float(multiplier))

        db.session.add(Transaction(
            wallet_id=wallet.id,
            type="payout",
            amount=payout,
            balance_after=wallet.balance,
            reference=f"aviator:{game_state.current_round.id}:payout:{bet.id}",
            status="completed",
        ))
        db.session.commit()

        player["status"] = "cashed_out"

        return {
            "success": True,
            "payout": float(payout),
            "profit": float(profit),
            "balance": float(wallet.balance)
        }

    except Exception as e:
        db.session.rollback()
        print(f"Cashout error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def resolve_round():
    """Resolve round"""
    try:
        round_obj = game_state.current_round
        round_obj.status = "crashed"
        round_obj.crashed_at = datetime.utcnow()

        active_bets = AviatorBet.query.filter_by(round_id=round_obj.id, status='active').all()
        
        for bet in active_bets:
            bet.status = "lost"
            if not bet.user.aviator_stats_rel:
                bet.user.aviator_stats_rel = AviatorStats(user_id=bet.user_id)
            bet.user.aviator_stats_rel.total_lost = (bet.user.aviator_stats_rel.total_lost or 0) + bet.bet_amount
            bet.user.aviator_stats_rel.loss_count = (bet.user.aviator_stats_rel.loss_count or 0) + 1

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Resolve error: {e}")
        traceback.print_exc()

# ============================================================================
# ROUTES
# ============================================================================

@login_required
def index():
    wallet = current_user.wallet if hasattr(current_user, 'wallet') else None
    balance = float(wallet.balance) if wallet else 0.0
    return render_template("games/aviatormzizi.html", balance=balance)

@login_required
def api_status():
    if not game_state.current_round:
        return jsonify({"status": "initializing"})
    return jsonify({
        "round_number": game_state.round_number,
        "status": game_state.current_round.status,
        "is_betting": game_state.is_betting,
        "multiplier": round(game_state.live_multiplier, 2),
        "players": len(game_state.players)
    })

@login_required
def api_bet():
    data = request.get_json(silent=True) or {}
    if "amount" not in data:
        return jsonify({"success": False, "error": "Bet amount is required"}), 400
    return jsonify(place_bet(current_user.id, data.get("amount")))

@login_required
def api_cashout():
    return jsonify(cashout_bet(current_user.id))

@login_required
def api_history():
    limit = request.args.get("limit", 20, type=int)
    bets = AviatorBet.query.filter_by(user_id=current_user.id).order_by(AviatorBet.created_at.desc()).limit(limit).all()
    return jsonify([{
        "id": b.id,
        "amount": float(b.bet_amount),
        "cashout": float(b.cashout_at) if b.cashout_at else None,
        "payout": float(b.payout_amount) if b.payout_amount else None,
        "status": b.status
    } for b in bets])

@login_required
def api_stats():
    try:
        stats = getattr(current_user, 'aviator_stats_rel', None)
        if not stats:
            stats = AviatorStats(user_id=current_user.id)
            db.session.add(stats)
            db.session.commit()
        return jsonify({
            "total_won": float(stats.total_won or 0),
            "total_lost": float(stats.total_lost or 0),
            "wins": stats.win_count or 0,
            "losses": stats.loss_count or 0,
            "best": float(stats.best_multiplier or 0)
        })
    except Exception as e:
        print(f"Stats error: {e}")
        return jsonify({"total_won": 0, "total_lost": 0, "wins": 0, "losses": 0, "best": 0})

socketio = None

def init_socketio(sio, app=None):
    """Initialize SocketIO"""
    global socketio, _loop_started
    socketio = sio

    @sio.on("connect", namespace="/aviator-mzizi")
    def on_connect():
        socketio.emit("connection_response", {"data": "Connected"}, namespace="/aviator-mzizi")

    @sio.on("join_game", namespace="/aviator-mzizi")
    def on_join():
        # ✅ FIXED: Removed broadcast=True
        socketio.emit("player_joined", {"players": len(game_state.players)}, namespace="/aviator-mzizi", skip_sid=request.sid)

    @sio.on("request_current_state", namespace="/aviator-mzizi")
    def on_request_state():
        socketio.emit("current_state", {
            "round_number": game_state.round_number,
            "status": game_state.current_round.status if game_state.current_round else None,
            "is_betting": game_state.is_betting,
            "multiplier": round(game_state.live_multiplier, 2),
            "players": len(game_state.players)
        }, namespace="/aviator-mzizi")

    if not _loop_started:
        if app:
            socketio.start_background_task(game_loop, app)
        _loop_started = True

def game_loop(app):
    """Main game loop - FIXED: app_context INSIDE the while loop"""
    print("✅ Aviator game loop started")
    
    while True:
        # ✅ FIXED: app_context moved INSIDE the loop
        try:
            with app.app_context():
                game_state.round_number += 1
                
                server_seed = CrashEngine.generate_server_seed()
                crash_point, _ = CrashEngine.generate_crash_point(server_seed)
                
                new_round = AviatorRound(
                    round_number=game_state.round_number,
                    crash_point=crash_point,
                    status='pending'
                )
                db.session.add(new_round)
                db.session.commit()

                game_state.current_round = new_round
                game_state.is_betting = True
                game_state.players = {}
                game_state.crash_point = float(crash_point)
                game_state.live_multiplier = 1.0

                # ✅ FIXED: Removed broadcast=True
                socketio.emit("new_round", {
                    "round_number": game_state.round_number,
                    "betting_window": 5
                }, namespace="/aviator-mzizi")

                socketio.sleep(5)

                game_state.is_betting = False
                game_state.current_round.status = "live"
                game_state.current_round.started_at = datetime.utcnow()
                db.session.commit()

                # ✅ FIXED: Removed broadcast=True
                socketio.emit("game_start", {}, namespace="/aviator-mzizi")

                start_time = time.time()
                while time.time() - start_time < 45.0:
                    elapsed = time.time() - start_time
                    progress = elapsed / 45.0
                    
                    multiplier = 1.0 + (game_state.crash_point - 1.0) * progress
                    multiplier = min(multiplier, game_state.crash_point)
                    game_state.live_multiplier = multiplier

                    # ✅ FIXED: Removed broadcast=True
                    socketio.emit("multiplier_update", {
                        "multiplier": round(multiplier, 2),
                        "elapsed": round(elapsed, 2)
                    }, namespace="/aviator-mzizi")

                    socketio.sleep(0.1)

                game_state.live_multiplier = game_state.crash_point
                resolve_round()

                # ✅ FIXED: Removed broadcast=True
                socketio.emit("game_crashed", {
                    "crash_point": game_state.crash_point,
                    "round_number": game_state.round_number
                }, namespace="/aviator-mzizi")

                socketio.sleep(3)

        except Exception as e:
            print(f"❌ Aviator game loop error: {e}")
            traceback.print_exc()
            socketio.sleep(1)

def get_aviator_blueprint(sio, app):
    """Factory function"""
    av_bp = Blueprint("aviator", __name__, url_prefix="/aviator-mzizi", template_folder="templates")
    
    av_bp.route("/")(index)
    av_bp.route("/api/status")(api_status)
    av_bp.route("/api/bet", methods=["POST"])(api_bet)
    av_bp.route("/api/cashout", methods=["POST"])(api_cashout)
    av_bp.route("/api/history")(api_history)
    av_bp.route("/api/stats")(api_stats)
    
    init_socketio(sio, app)
    
    return av_bp
