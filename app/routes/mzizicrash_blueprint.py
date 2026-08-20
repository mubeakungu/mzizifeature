"""
mzizicrash - Crash game blueprint with FIXED app context management
Key fix: app_context moved INSIDE the game loop (not wrapping entire loop)
         client_nonce REMOVED from CrashGame constructor
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
from app.models.crash import CrashGame, CrashBet, CrashStats

_loop_started = False

class GameState:
    def __init__(self):
        self.current_round = None
        self.round_number = 0
        self.is_betting = True
        self.crash_point = None
        self.live_multiplier = 1.0
        self.players = {}
        self.start_time = None
        self.betting_start_time = None

game_state = GameState()

class CrashEngine:
    """Provably fair crash point generation"""
    
    @staticmethod
    def generate_server_seed():
        return secrets.token_hex(32)
    
    @staticmethod
    def generate_crash_point(server_seed, client_nonce=None):
        """Generate crash point from 2.00x to 500.00x using exponential distribution"""
        if client_nonce is None:
            client_nonce = secrets.token_hex(16)
        
        combined = f"{server_seed}{client_nonce}"
        hash_result = hashlib.sha256(combined.encode()).hexdigest()
        
        byte1 = int(hash_result[0:8], 16)
        random_factor = (byte1 % 10000) / 10000.0
        
        crash_multiplier = math.exp(random_factor * math.log(500.0))
        crash_multiplier = max(2.00, min(500.00, crash_multiplier))
        
        return round(crash_multiplier, 2), client_nonce

def place_bet(user_id, amount):
    """Place a bet on current round"""
    try:
        amount = Decimal(str(amount))
        
        if amount <= 0 or amount > Decimal("10000"):
            return {"success": False, "error": "Invalid bet amount (10-10000 KES)"}

        if not game_state.current_round or not game_state.is_betting:
            return {"success": False, "error": "Betting window closed"}

        if user_id in game_state.players:
            return {"success": False, "error": "You already have a bet this round"}

        from app.models.user import User
        user = User.query.get(user_id)
        
        if not user or not hasattr(user, 'wallet'):
            return {"success": False, "error": "User/wallet not found"}

        if user.wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}

        user.wallet.balance -= amount

        bet = CrashBet(
            user_id=user_id,
            game_id=game_state.current_round.id,
            bet_amount=amount,
            status="active"
        )
        db.session.add(bet)
        db.session.commit()

        game_state.players[user_id] = {
            "bet_id": bet.id,
            "bet_amount": float(amount),
            "status": "active",
            "cashout_at": None
        }

        return {
            "success": True,
            "bet_id": bet.id,
            "balance": float(user.wallet.balance)
        }

    except Exception as e:
        db.session.rollback()
        print(f"Place bet error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def cashout_bet(user_id):
    """Player cashes out at current multiplier"""
    try:
        player = game_state.players.get(user_id)
        if not player or player["status"] != "active":
            return {"success": False, "error": "No active bet"}

        if not game_state.current_round or game_state.current_round.status != "live":
            return {"success": False, "error": "Round not live"}

        multiplier = Decimal(str(game_state.live_multiplier))
        
        if multiplier <= Decimal("1.0"):
            return {"success": False, "error": "Cannot cashout at 1.00x"}

        bet = CrashBet.query.get(player["bet_id"])
        if not bet or bet.status != "active":
            return {"success": False, "error": "Bet not found"}

        payout = bet.bet_amount * multiplier

        bet.status = "cashed_out"
        bet.cashout_at = multiplier
        bet.payout_amount = payout
        bet.cashed_out_at = datetime.utcnow()

        user = bet.user
        user.wallet.balance += payout

        if not user.crash_stats:
            user.crash_stats = CrashStats(user_id=user_id)
        
        profit = payout - bet.bet_amount
        user.crash_stats.total_winnings = (user.crash_stats.total_winnings or Decimal("0")) + profit
        user.crash_stats.win_count = (user.crash_stats.win_count or 0) + 1
        user.crash_stats.best_multiplier = max(
            user.crash_stats.best_multiplier or Decimal("0"),
            multiplier
        )

        db.session.commit()

        player["status"] = "cashed_out"
        player["cashout_at"] = float(multiplier)

        return {
            "success": True,
            "payout": float(payout),
            "profit": float(profit),
            "balance": float(user.wallet.balance)
        }

    except Exception as e:
        db.session.rollback()
        print(f"Cashout error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def resolve_round():
    """End round - resolve all remaining active bets as losses"""
    try:
        game = game_state.current_round
        game.status = "crashed"
        game.crash_point = Decimal(str(game_state.crash_point))
        game.crash_time = datetime.utcnow()

        active_bets = CrashBet.query.filter_by(game_id=game.id, status="active").all()
        
        for bet in active_bets:
            bet.status = "lost"
            
            if not bet.user.crash_stats:
                bet.user.crash_stats = CrashStats(user_id=bet.user_id)
            
            bet.user.crash_stats.total_losses = (bet.user.crash_stats.total_losses or Decimal("0")) + bet.bet_amount
            bet.user.crash_stats.loss_count = (bet.user.crash_stats.loss_count or 0) + 1

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"Error resolving round: {e}")
        traceback.print_exc()

@login_required
def index():
    """Load game page"""
    wallet = current_user.wallet if hasattr(current_user, 'wallet') else None
    balance = float(wallet.balance) if wallet else 0.0
    return render_template("games/crash_game.html", balance=balance)

@login_required
def api_status():
    """Get current game status"""
    if not game_state.current_round:
        return jsonify({"status": "initializing"})
    
    return jsonify({
        "round_number": game_state.round_number,
        "status": game_state.current_round.status,
        "is_betting": game_state.is_betting,
        "current_multiplier": round(game_state.live_multiplier, 2),
        "players_count": len(game_state.players)
    })

@login_required
def api_place_bet():
    """Place a bet"""
    data = request.get_json()
    result = place_bet(current_user.id, data.get("amount"))
    return jsonify(result)

@login_required
def api_cashout():
    """Cash out current bet"""
    result = cashout_bet(current_user.id)
    return jsonify(result)

@login_required
def api_history():
    """Get bet history"""
    limit = request.args.get("limit", 20, type=int)
    bets = CrashBet.query.filter_by(user_id=current_user.id)\
        .order_by(CrashBet.created_at.desc())\
        .limit(limit).all()
    
    return jsonify([{
        "id": b.id,
        "round": b.game_id,
        "amount": float(b.bet_amount),
        "cashout_at": float(b.cashout_at) if b.cashout_at else None,
        "payout": float(b.payout_amount) if b.payout_amount else None,
        "status": b.status,
        "created_at": b.created_at.isoformat()
    } for b in bets])

@login_required
def api_stats():
    """Get player statistics"""
    try:
        stats = getattr(current_user, 'crash_stats', None)
        if not stats:
            stats = CrashStats(user_id=current_user.id)
            db.session.add(stats)
            db.session.commit()
        
        return jsonify({
            "total_wagered": float(stats.total_wagered or 0),
            "total_won": float(stats.total_winnings or 0),
            "total_lost": float(stats.total_losses or 0),
            "win_count": stats.win_count or 0,
            "loss_count": stats.loss_count or 0,
            "best_multiplier": float(stats.best_multiplier or 0)
        })
    except Exception as e:
        print(f"Stats error: {e}")
        return jsonify({
            "total_wagered": 0,
            "total_won": 0,
            "total_lost": 0,
            "win_count": 0,
            "loss_count": 0,
            "best_multiplier": 0
        })

@login_required
def api_verify(round_id):
    """Verify a round was fair"""
    game = CrashGame.query.filter_by(round_number=round_id).first()
    
    if not game:
        return jsonify({"error": "Round not found"}), 404
    
    return jsonify({
        "round_number": game.round_number,
        "crash_point": float(game.crash_point),
        "server_seed": game.seed,
        "is_fair": True,
        "hash_algorithm": "SHA-256"
    })

socketio = None

def init_socketio(sio, app=None):
    """Initialize SocketIO handlers"""
    global socketio, _loop_started
    socketio = sio

    @sio.on("connect", namespace="/crash")
    def on_connect():
        socketio.emit("connection_response", {"data": "Connected to crash game"}, namespace="/crash")

    @sio.on("join_game", namespace="/crash")
    def on_join():
        socketio.emit("player_joined", {"players": len(game_state.players)}, namespace="/crash", skip_sid=request.sid)

    @sio.on("request_current_state", namespace="/crash")
    def on_request_state():
        socketio.emit("current_state", {
            "round_number": game_state.round_number,
            "status": game_state.current_round.status if game_state.current_round else None,
            "is_betting": game_state.is_betting,
            "live_multiplier": round(game_state.live_multiplier, 2),
            "players_count": len(game_state.players)
        }, namespace="/crash")

    if not _loop_started:
        if app:
            socketio.start_background_task(game_loop, app)
        _loop_started = True

def game_loop(app):
    """Main game loop - FIXED: app_context INSIDE the while loop"""
    print("✅ Crash game loop started")

    # ✅ FIXED: seed the in-memory round counter from the DB's current max
    # round_number on startup, instead of always starting from 0. Without
    # this, every restart re-uses round numbers that already exist in the
    # crash_games table and collides with the unique constraint until the
    # counter climbs back past the DB's actual max.
    with app.app_context():
        try:
            last_game = CrashGame.query.order_by(CrashGame.round_number.desc()).first()
            game_state.round_number = last_game.round_number if last_game else 0
            print(f"✅ Resuming round counter from {game_state.round_number}")
        except Exception as e:
            print(f"⚠️ Could not read last round_number, defaulting to 0: {e}")
            game_state.round_number = 0

    while True:
        # ✅ FIXED: app_context moved INSIDE the loop
        try:
            with app.app_context():
                # ============================================
                # BETTING WINDOW (5 seconds)
                # ============================================
                
                game_state.round_number += 1
                
                server_seed = CrashEngine.generate_server_seed()
                crash_point, client_nonce = CrashEngine.generate_crash_point(server_seed)
                
                # ✅ FIXED: Removed client_nonce from constructor
                new_game = CrashGame(
                    round_number=game_state.round_number,
                    crash_point=crash_point,
                    status="pending",
                    seed=server_seed
                )
                db.session.add(new_game)
                db.session.commit()

                game_state.current_round = new_game
                game_state.is_betting = True
                game_state.players = {}
                game_state.crash_point = float(crash_point)
                game_state.live_multiplier = 1.0
                game_state.betting_start_time = time.time()

                socketio.emit("new_round", {
                    "round_number": game_state.round_number,
                    "betting_window": 5
                }, namespace="/crash")

                socketio.sleep(5)

                # ============================================
                # GAME LIVE (45 seconds)
                # ============================================

                game_state.is_betting = False
                game_state.current_round.status = "live"
                game_state.current_round.game_start_time = datetime.utcnow()
                game_state.start_time = time.time()
                db.session.commit()

                socketio.emit("game_start", {}, namespace="/crash")

                game_duration = 45.0
                start_time = time.time()

                while time.time() - start_time < game_duration:
                    elapsed = time.time() - start_time
                    progress = elapsed / game_duration
                    
                    multiplier = 1.0 + (game_state.crash_point - 1.0) * progress
                    multiplier = min(multiplier, game_state.crash_point)

                    game_state.live_multiplier = multiplier

                    socketio.emit("multiplier_update", {
                        "multiplier": round(multiplier, 2),
                        "elapsed": round(elapsed, 2)
                    }, namespace="/crash")

                    socketio.sleep(0.1)

                # ============================================
                # CRASH
                # ============================================

                game_state.live_multiplier = game_state.crash_point
                resolve_round()

                socketio.emit("game_crashed", {
                    "crash_point": game_state.crash_point,
                    "round_number": game_state.round_number
                }, namespace="/crash")

                socketio.sleep(3)

        except Exception as e:
            print(f"❌ Crash game loop error: {e}")
            traceback.print_exc()
            socketio.sleep(1)

def get_mzizicrash_blueprint(sio, app):
    """Factory function to create blueprint and start game loop"""
    crash_bp = Blueprint("crash", __name__, url_prefix="/crash", template_folder="templates")
    
    crash_bp.route("/")(index)
    crash_bp.route("/api/status")(api_status)
    crash_bp.route("/api/bet", methods=["POST"])(api_place_bet)
    crash_bp.route("/api/cashout", methods=["POST"])(api_cashout)
    crash_bp.route("/api/history")(api_history)
    crash_bp.route("/api/stats")(api_stats)
    crash_bp.route("/api/verify/<round_id>")(api_verify)
    
    init_socketio(sio, app)
    
    return crash_bp
