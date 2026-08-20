"""
JetX Blueprint - FIXED VERSION
Key fixes:
1. App context moved INSIDE the while loop (not wrapping the entire loop)
2. Removed broadcast=True parameter (not supported in Flask-SocketIO 5.3.6)
3. Better error handling with logging
"""

import hashlib
import secrets
import time
import traceback
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.wallet import Wallet, Transaction
from app.models.jetx_models import JetXGame, JetXBet, JetXStats

_loop_started = False

class JetXEngine:
    MIN_MULTIPLIER = Decimal("1.01")
    MAX_MULTIPLIER = Decimal("100.00")
    BETTING_WINDOW = 5
    GAME_DURATION = 45
    MIN_BET = Decimal("10")
    MAX_BET = Decimal("100000")

    @staticmethod
    def get_game_flavor():
        return {
            "theme": "rocket",
            "emoji": "🚀",
            "crash_reason": "System overload",
            "sounds": ["launch", "accelerating", "explosion"],
            "display_metric": "fuel_percentage",
        }

class GameState:
    def __init__(self):
        self.current_round = None
        self.round_number = 0
        self.is_betting = False
        self.crash_point = None
        self.live_multiplier = 1.0
        self.players = {}

game_state = GameState()

class CrashEngine:
    @staticmethod
    def generate_crash_point(server_seed, client_nonce=None):
        if client_nonce is None:
            client_nonce = secrets.token_hex(16)
        combined = f"{server_seed}{client_nonce}"
        hash_result = hashlib.sha256(combined.encode()).hexdigest()
        hash_int = int(hash_result[:8], 16)
        rand_val = hash_int / 0xffffffff
        rand_val = max(0.00001, min(0.99999, rand_val))
        
        import math
        multiplier = 100.0 * math.exp(-math.log(100.0) * rand_val)
        multiplier = max(JetXEngine.MIN_MULTIPLIER, min(JetXEngine.MAX_MULTIPLIER, multiplier))
        return Decimal(str(round(multiplier, 2))), client_nonce

    @staticmethod
    def generate_server_seed():
        return secrets.token_hex(32)

def place_bet(user_id, amount):
    """Place a bet on the current JetX round"""
    try:
        amount = Decimal(str(amount))
        
        if amount < JetXEngine.MIN_BET or amount > JetXEngine.MAX_BET:
            return {"success": False, "error": "Invalid bet amount"}
        
        if not game_state.is_betting or not game_state.current_round:
            return {"success": False, "error": "Betting window closed"}
        
        if user_id in game_state.players:
            return {"success": False, "error": "You already have a bet this round"}
        
        wallet = Wallet.query.filter_by(user_id=user_id).first()
        if not wallet or wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}
        
        # Debit wallet
        wallet.balance -= amount
        
        # Create transaction log
        tx = Transaction(
            user_id=user_id,
            type="stake",
            amount=-amount,
            reference_type="jetx_game",
            reference_id=game_state.current_round.id,
            description=f"JetX bet - Round {game_state.round_number}"
        )
        
        # Create bet record
        bet = JetXBet(
            user_id=user_id,
            game_id=game_state.current_round.id,
            bet_amount=amount,
            status="active"
        )
        
        db.session.add(tx)
        db.session.add(bet)
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
    """Cash out the current bet"""
    try:
        player = game_state.players.get(user_id)
        if not player or player["status"] != "active":
            return {"success": False, "error": "No active bet"}
        
        if not game_state.current_round or game_state.current_round.status != "live":
            return {"success": False, "error": "Round not live"}
        
        multiplier = Decimal(str(game_state.live_multiplier))
        if multiplier <= Decimal("1.0"):
            return {"success": False, "error": "Cannot cashout at 1.00x"}
        
        bet = JetXBet.query.get(player["bet_id"])
        if not bet or bet.status != "active":
            return {"success": False, "error": "Bet not found"}
        
        payout = bet.bet_amount * multiplier
        
        bet.status = "cashed_out"
        bet.cashout_at = float(multiplier)
        bet.payout_amount = payout
        bet.cashed_out_at = datetime.utcnow()
        
        wallet = Wallet.query.filter_by(user_id=user_id).first()
        wallet.balance += payout
        
        tx = Transaction(
            user_id=user_id,
            type="payout",
            amount=payout,
            reference_type="jetx_game",
            reference_id=game_state.current_round.id,
            description=f"JetX cashout at {multiplier}x"
        )
        
        if not wallet.jetx_stats:
            wallet.jetx_stats = JetXStats(user_id=user_id)
        
        wallet.jetx_stats.total_winnings = (wallet.jetx_stats.total_winnings or 0) + payout - bet.bet_amount
        wallet.jetx_stats.win_count = (wallet.jetx_stats.win_count or 0) + 1
        wallet.jetx_stats.best_multiplier = max(wallet.jetx_stats.best_multiplier or 0, float(multiplier))
        
        db.session.add(tx)
        db.session.commit()
        
        player["status"] = "cashed_out"
        
        return {
            "success": True,
            "payout": float(payout),
            "profit": float(payout - bet.bet_amount),
            "balance": float(wallet.balance)
        }
    except Exception as e:
        db.session.rollback()
        print(f"Cashout error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def resolve_round(crash_point):
    """Resolve all active bets"""
    try:
        active_bets = JetXBet.query.filter_by(game_id=game_state.current_round.id, status="active").all()
        
        for bet in active_bets:
            bet.status = "lost"
            
            if not bet.user.jetx_stats:
                bet.user.jetx_stats = JetXStats(user_id=bet.user_id)
            
            bet.user.jetx_stats.total_losses = (bet.user.jetx_stats.total_losses or 0) + bet.bet_amount
            bet.user.jetx_stats.loss_count = (bet.user.jetx_stats.loss_count or 0) + 1
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Resolve round error: {e}")

def game_loop(sio, app):
    """Main game loop - FIXED: app_context moved INSIDE the while loop"""
    print("🚀 JetX game loop started")
    
    while True:
        # ✅ FIXED: Move app_context INSIDE the loop
        try:
            with app.app_context():
                game_state.round_number += 1
                server_seed = CrashEngine.generate_server_seed()
                crash_point, _ = CrashEngine.generate_crash_point(server_seed)
                
                new_game = JetXGame(
                    round_number=game_state.round_number,
                    crash_point=crash_point,
                    status="pending",
                    seed=server_seed,
                )
                db.session.add(new_game)
                db.session.commit()
                
                game_state.current_round = new_game
                game_state.is_betting = True
                game_state.players = {}
                game_state.crash_point = float(crash_point)
                game_state.live_multiplier = 1.0
                
                # ✅ FIXED: Removed broadcast=True
                sio.emit("new_round", {
                    "round_number": game_state.round_number,
                    "betting_window": JetXEngine.BETTING_WINDOW,
                }, namespace="/jetx")
                
                sio.sleep(JetXEngine.BETTING_WINDOW)
                
                game_state.is_betting = False
                game_state.current_round.status = "live"
                game_state.current_round.game_start_time = datetime.utcnow()
                db.session.commit()
                
                # ✅ FIXED: Removed broadcast=True
                sio.emit("game_start", {}, namespace="/jetx")
                
                start_time = time.time()
                while time.time() - start_time < JetXEngine.GAME_DURATION:
                    elapsed = time.time() - start_time
                    progress = elapsed / JetXEngine.GAME_DURATION
                    
                    multiplier = 1.0 + (game_state.crash_point - 1.0) * progress
                    multiplier = min(multiplier, game_state.crash_point)
                    game_state.live_multiplier = multiplier
                    
                    # ✅ FIXED: Removed broadcast=True
                    sio.emit("multiplier_update", {
                        "multiplier": round(multiplier, 2),
                        "elapsed": round(elapsed, 2),
                    }, namespace="/jetx")
                    
                    sio.sleep(0.1)
                
                game_state.live_multiplier = game_state.crash_point
                resolve_round(game_state.crash_point)
                
                # ✅ FIXED: Removed broadcast=True
                sio.emit("game_crashed", {
                    "crash_point": game_state.crash_point,
                    "round_number": game_state.round_number,
                }, namespace="/jetx")
                
                sio.sleep(3)
        
        except Exception as e:
            print(f"❌ JetX game loop error: {e}")
            traceback.print_exc()
            sio.sleep(1)

def get_jetx_blueprint(sio, app):
    """Factory function to create and register blueprint"""
    global _loop_started
    
    jetx_bp = Blueprint("jetx", __name__, url_prefix="/jetx")
    
    @jetx_bp.route("/", methods=["GET"])
    @login_required
    def index():
        wallet = Wallet.query.filter_by(user_id=current_user.id).first()
        balance = float(wallet.balance) if wallet else 0.0
        return render_template("games/jetx.html", balance=balance)
    
    @jetx_bp.route("/api/status", methods=["GET"])
    @login_required
    def api_status():
        if not game_state.current_round:
            return jsonify({"status": "initializing"})
        return jsonify({
            "round_number": game_state.round_number,
            "status": game_state.current_round.status,
            "is_betting": game_state.is_betting,
            "players_count": len(game_state.players)
        })
    
    @jetx_bp.route("/api/bet", methods=["POST"])
    @login_required
    def api_place_bet():
        data = request.get_json()
        return jsonify(place_bet(current_user.id, data.get("amount")))
    
    @jetx_bp.route("/api/cashout", methods=["POST"])
    @login_required
    def api_cashout():
        return jsonify(cashout_bet(current_user.id))
    
    @jetx_bp.route("/api/history", methods=["GET"])
    @login_required
    def api_history():
        limit = request.args.get("limit", 20, type=int)
        bets = JetXBet.query.filter_by(user_id=current_user.id).order_by(JetXBet.created_at.desc()).limit(limit).all()
        return jsonify([{
            "id": b.id,
            "amount": float(b.bet_amount),
            "cashout_at": float(b.cashout_at) if b.cashout_at else None,
            "payout": float(b.payout_amount) if b.payout_amount else None,
            "status": b.status,
        } for b in bets])
    
    @jetx_bp.route("/api/stats", methods=["GET"])
    @login_required
    def api_stats():
        try:
            stats = getattr(current_user, 'jetx_stats', None)
            if not stats:
                stats = JetXStats(user_id=current_user.id)
                db.session.add(stats)
                db.session.commit()
            
            return jsonify({
                "total_wagered": float(stats.total_wagered or 0),
                "total_won": float(stats.total_winnings or 0),
                "win_count": stats.win_count or 0,
                "loss_count": stats.loss_count or 0,
                "best_multiplier": float(stats.best_multiplier or 0)
            })
        except Exception as e:
            print(f"Stats error: {e}")
            return jsonify({
                "total_wagered": 0,
                "total_won": 0,
                "win_count": 0,
                "loss_count": 0,
                "best_multiplier": 0
            })
    
    # ✅ START GAME LOOP ONLY ONCE
    if not _loop_started:
        print("✅ Starting JetX game loop background task")
        sio.start_background_task(game_loop, sio, app)
        _loop_started = True
    
    return jetx_bp
