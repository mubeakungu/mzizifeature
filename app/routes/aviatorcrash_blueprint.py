"""
AviatorCrash — real backend for the Unity WebGL "aviator-crash-main" game.

This replaces the old demo aviatormzizi_blueprint.py and jetx_blueprint.py.
Both /aviator-mzizi/ and /jetx/ now serve the exact same built game
(app/static/aviatorcrash/), backed by ONE shared provably-fair game engine
and your real wallet/DB — the frontend itself has no backend of its own.

--------------------------------------------------------------------------
Frontend protocol (reverse-engineered from src/context.tsx and
src/components/crash/index.tsx in the built bundle — do not change these
event names/shapes without rebuilding the React app):

  socket namespace: /aviatorcrash   (same-origin; auth via the Flask
                                      session cookie, exactly like every
                                      other game in this app)

  client -> server:
    enterRoom  { token }                       -- token is unused; session
                                                   cookie is the real auth
    playBet    { betAmount, target, type, auto }  -- type: "f" | "s"
    cashOut    { type, endTarget }              -- endTarget is NOT trusted;
                                                   payout is computed here
                                                   from server-side elapsed
                                                   time on the same curve

  server -> client:
    myInfo, myBetState, bettedUserInfo, gameState, previousHand,
    history, finishGame, getBetLimits, error, success

  REST (the built JS calls these as ABSOLUTE paths — "/api/..." — not
  relative to whichever of the two mounts served the page, so they are
  registered at the app root, not under /aviator-mzizi or /jetx):
    POST /api/my-info
    GET  /api/get-day-history
    GET  /api/get-month-history
    GET  /api/get-year-history
--------------------------------------------------------------------------

The multiplier curve below is copied exactly from the client's own
crash/index.tsx so that a server-computed payout always matches what the
Unity plane animation is showing the player at that instant:

    currentNum = 1 + 0.06t + (0.06t)^2 - (0.04t)^3 + (0.04t)^4

The client only ever tells us how it FEELS about the multiplier
(endTarget); we never trust that number for money. Every payout here is
recomputed from elapsed server time against this same formula.
"""

import hashlib
import os
import secrets
import time
import traceback
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, send_from_directory
from flask_login import current_user, login_required
from flask_socketio import emit, join_room

from app.extensions import db
from app.models.user import User
from app.models.wallet import Wallet, Transaction
from app.models.aviatorcrash_models import AviatorCrashRound, AviatorCrashBet, AviatorCrashStats

NAMESPACE = "/aviatorcrash"
BUILD_DIR = "../static/aviatorcrash"  # -> app/static/aviatorcrash, relative to this file

BETTING_WINDOW = 5     # seconds
GAMEEND_PAUSE = 3      # seconds, showing the final multiplier before next round

MIN_BET = Decimal("10")
MAX_BET = Decimal("100000")

AVATARS = [
    "/avatars/av-15.png", "/avatars/av-4.png", "/avatars/av-39.png",
    "/avatars/av-14.png", "/avatars/av-5.png", "/avatars/av-12.png",
    "/avatars/av-3.png", "/avatars/av-45.png", "/avatars/av-13.png",
]

_loop_started = False


def avatar_for(user_id):
    return AVATARS[user_id % len(AVATARS)]


def mask_username(user):
    name = getattr(user, "username", None) or getattr(user, "phone", None) or f"user{user.id}"
    name = str(name)
    if len(name) <= 2:
        return (name[0] if name else "u") + "***"
    return name[0] + "***" + name[-1]


# ---------------------------------------------------------------------------
# Multiplier curve (must match the client exactly) + provably-fair crash point
# ---------------------------------------------------------------------------

def multiplier_at(t):
    """Multiplier at elapsed seconds t. Mirrors crash/index.tsx precisely."""
    if t <= 0:
        return 1.0
    return 1 + 0.06 * t + (0.06 * t) ** 2 - (0.04 * t) ** 3 + (0.04 * t) ** 4


def time_for_multiplier(target):
    """Invert multiplier_at via bisection: how many seconds until we reach `target`?"""
    if target <= 1.0:
        return 0.0
    lo, hi = 0.0, 200.0
    while multiplier_at(hi) < target and hi < 1e6:
        hi *= 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if multiplier_at(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class CrashEngine:
    """SHA-256 provably-fair crash point, same family of algorithm as
    mzizicrash's engine, tuned to a ~3% house edge."""

    HOUSE_EDGE = 0.03
    MIN_MULTIPLIER = Decimal("1.00")
    MAX_MULTIPLIER = Decimal("500.00")  # keeps max round length to ~100s

    @staticmethod
    def generate_server_seed():
        return secrets.token_hex(32)

    @staticmethod
    def generate_crash_point(server_seed, nonce):
        combined = f"{server_seed}:{nonce}"
        h = hashlib.sha256(combined.encode()).hexdigest()
        r = int(h[:13], 16) / float(0xFFFFFFFFFFFFF)  # ~52 bits of entropy in [0, 1)

        if r < CrashEngine.HOUSE_EDGE:
            crash = Decimal("1.00")
        else:
            crash = Decimal(str(round((1 - CrashEngine.HOUSE_EDGE) / (1 - r), 2)))

        return max(CrashEngine.MIN_MULTIPLIER, min(CrashEngine.MAX_MULTIPLIER, crash))


# ---------------------------------------------------------------------------
# In-memory round state (mirrors the pattern used by mzizicrash/aviatormzizi)
# ---------------------------------------------------------------------------

class RoundState:
    def __init__(self):
        self.round_number = 0
        self.round_id = None
        self.phase = "BET"  # BET, PLAYING, GAMEEND
        self.phase_start = time.time()
        self.crash_point = 0.0
        self.crash_time = 0.0
        self.bets = {}            # (user_id, slot) -> dict
        self.history = []         # most-recent-first crash points
        self.connected_users = set()

    def elapsed(self):
        return time.time() - self.phase_start


state = RoundState()
socketio = None


def _get_wallet(user_id):
    return Wallet.query.filter_by(user_id=user_id).first()


def _get_stats(user_id):
    stats = AviatorCrashStats.query.filter_by(user_id=user_id).first()
    if not stats:
        stats = AviatorCrashStats(user_id=user_id)
        db.session.add(stats)
    return stats


def _betted_user_info():
    out = []
    for (_uid, _slot), b in state.bets.items():
        out.append({
            "name": b["name"],
            "betAmount": b["amount"],
            "cashOut": b["cashout_at"] or 0,
            "cashouted": b["cashouted"],
            "target": b["target"] or 0,
            "img": b["img"],
            "bot": False,
        })
    return out


def _empty_slot():
    return {"auto": False, "betted": False, "cashouted": False, "betAmount": 0, "cashAmount": 0, "target": 2}


def _slot_payload(b, betted):
    slot = _empty_slot()
    if b:
        slot.update({
            "auto": b["auto"], "betted": betted, "cashouted": b["cashouted"],
            "betAmount": b["amount"], "cashAmount": b["cashout_at"] or 0,
            "target": b["target"] or 2,
        })
    return slot


def _user_type_payload(user_id, balance, username=""):
    fb = state.bets.get((user_id, "f"))
    sb = state.bets.get((user_id, "s"))
    return {
        "balance": float(balance), "userType": False, "img": avatar_for(user_id), "userName": username,
        "f": _slot_payload(fb, betted=True),
        "s": _slot_payload(sb, betted=True),
    }


def _finish_game_payload(user_id, balance, username=""):
    fb = state.bets.get((user_id, "f"))
    sb = state.bets.get((user_id, "s"))
    return {
        "balance": float(balance), "userType": False, "img": avatar_for(user_id), "userName": username,
        "f": _slot_payload(fb, betted=False),
        "s": _slot_payload(sb, betted=False),
    }


def _settle_cashout(user_id, slot, b, multiplier, reference_suffix):
    """Shared by manual cashOut and auto-cashout — credits wallet, updates stats,
    marks the in-memory + DB bet as cashed out, and notifies the player."""
    bet = AviatorCrashBet.query.get(b["bet_id"])
    wallet = _get_wallet(user_id)
    payout = (bet.bet_amount * Decimal(str(multiplier))).quantize(Decimal("0.01"))

    bet.status = "cashed_out"
    bet.cashout_at = Decimal(str(multiplier))
    bet.payout_amount = payout
    bet.cashed_out_at = datetime.utcnow()
    wallet.balance += payout

    db.session.add(Transaction(
        wallet_id=wallet.id, type="payout", amount=payout, balance_after=wallet.balance,
        reference=f"aviatorcrash:{state.round_id}:{slot}:{reference_suffix}:{user_id}:{state.round_number}",
        status="completed",
    ))

    stats = _get_stats(user_id)
    profit = payout - bet.bet_amount
    stats.total_won = (stats.total_won or Decimal("0")) + profit
    stats.win_count = (stats.win_count or 0) + 1
    stats.best_multiplier = max(stats.best_multiplier or Decimal("0"), Decimal(str(multiplier)))
    db.session.commit()

    b["cashouted"] = True
    b["cashout_at"] = multiplier

    user = User.query.get(user_id)
    username = mask_username(user) if user else ""
    payload = _user_type_payload(user_id, wallet.balance, username)
    socketio.emit("myInfo", payload, room=str(user_id), namespace=NAMESPACE)
    socketio.emit("myBetState", payload, room=str(user_id), namespace=NAMESPACE)
    socketio.emit("bettedUserInfo", _betted_user_info(), namespace=NAMESPACE)


# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

def game_loop(app):
    print("✈️  AviatorCrash game loop started")

    with app.app_context():
        try:
            last = AviatorCrashRound.query.order_by(AviatorCrashRound.round_number.desc()).first()
            state.round_number = last.round_number if last else 0
            print(f"✈️  Resuming round counter from {state.round_number}")
        except Exception as e:
            print(f"⚠️  Could not read last AviatorCrash round_number, defaulting to 0: {e}")
            state.round_number = 0

    while True:
        try:
            with app.app_context():
                _run_betting_phase()
                _run_playing_phase()
                _run_gameend_phase()
        except Exception as e:
            print(f"❌ AviatorCrash loop error: {e}")
            traceback.print_exc()
            socketio.sleep(1)


def _run_betting_phase():
    state.round_number += 1
    server_seed = CrashEngine.generate_server_seed()
    crash_point = CrashEngine.generate_crash_point(server_seed, state.round_number)

    round_row = AviatorCrashRound(
        round_number=state.round_number, crash_point=crash_point, seed=server_seed, status="betting",
    )
    db.session.add(round_row)
    db.session.commit()

    state.round_id = round_row.id
    state.crash_point = float(crash_point)
    state.crash_time = time_for_multiplier(state.crash_point)
    state.bets = {}
    state.phase = "BET"
    state.phase_start = time.time()

    socketio.emit("gameState", {
        "currentNum": 1, "currentSecondNum": 1, "GameState": "BET", "time": 0,
    }, namespace=NAMESPACE)
    socketio.emit("bettedUserInfo", [], namespace=NAMESPACE)

    socketio.sleep(BETTING_WINDOW)


def _run_playing_phase():
    round_row = AviatorCrashRound.query.get(state.round_id)
    round_row.status = "live"
    round_row.started_at = datetime.utcnow()
    db.session.commit()

    state.phase = "PLAYING"
    state.phase_start = time.time()

    socketio.emit("gameState", {
        "currentNum": 1, "currentSecondNum": 1, "GameState": "PLAYING", "time": 0,
    }, namespace=NAMESPACE)

    while state.elapsed() < state.crash_time:
        socketio.sleep(0.2)
        _check_auto_cashouts()


def _check_auto_cashouts():
    elapsed = state.elapsed()
    live_multiplier = round(min(multiplier_at(elapsed), state.crash_point), 2)

    for (user_id, slot), b in list(state.bets.items()):
        if b["cashouted"] or not b["target"]:
            continue
        if live_multiplier >= b["target"]:
            try:
                _settle_cashout(user_id, slot, b, min(b["target"], live_multiplier), "autopayout")
            except Exception as e:
                db.session.rollback()
                print(f"AviatorCrash auto-cashout error: {e}")
                traceback.print_exc()


def _run_gameend_phase():
    round_row = AviatorCrashRound.query.get(state.round_id)
    round_row.status = "crashed"
    round_row.crashed_at = datetime.utcnow()

    for (_user_id, _slot), b in state.bets.items():
        if not b["cashouted"]:
            bet = AviatorCrashBet.query.get(b["bet_id"])
            bet.status = "lost"
            stats = _get_stats(_user_id)
            stats.total_lost = (stats.total_lost or Decimal("0")) + bet.bet_amount
            stats.loss_count = (stats.loss_count or 0) + 1
    db.session.commit()

    state.phase = "GAMEEND"
    state.phase_start = time.time()

    previous_hand = _betted_user_info()
    state.history.insert(0, state.crash_point)
    state.history = state.history[:25]

    socketio.emit("gameState", {
        "currentNum": state.crash_point, "currentSecondNum": state.crash_point,
        "GameState": "GAMEEND", "time": 0,
    }, namespace=NAMESPACE)
    socketio.emit("previousHand", previous_hand, namespace=NAMESPACE)
    socketio.emit("history", state.history, namespace=NAMESPACE)

    for user_id in list(state.connected_users):
        wallet = _get_wallet(user_id)
        balance = float(wallet.balance) if wallet else 0.0
        payload = _finish_game_payload(user_id, balance)
        socketio.emit("finishGame", payload, room=str(user_id), namespace=NAMESPACE)

    socketio.sleep(GAMEEND_PAUSE)


# ---------------------------------------------------------------------------
# Socket.IO handlers
# ---------------------------------------------------------------------------

def init_socketio(sio, app):
    global socketio, _loop_started
    socketio = sio

    @sio.on("connect", namespace=NAMESPACE)
    def on_connect(auth=None):
        if not current_user.is_authenticated:
            return False  # reject the connection

    @sio.on("disconnect", namespace=NAMESPACE)
    def on_disconnect():
        # Best-effort: if this was the player's only tab, stop sending them
        # personalized events. Harmless if they still have another tab open —
        # the next enterRoom re-adds them.
        if current_user.is_authenticated:
            state.connected_users.discard(current_user.id)

    @sio.on("enterRoom", namespace=NAMESPACE)
    def on_enter_room(_data):
        if not current_user.is_authenticated:
            emit("error", {"message": "Please log in to play.", "index": "f"})
            return

        join_room(str(current_user.id))
        state.connected_users.add(current_user.id)

        wallet = _get_wallet(current_user.id)
        balance = float(wallet.balance) if wallet else 0.0
        username = mask_username(current_user)

        payload = _user_type_payload(current_user.id, balance, username)
        emit("myInfo", payload)
        emit("myBetState", payload)
        emit("getBetLimits", {"max": float(MAX_BET), "min": float(MIN_BET)})
        emit("history", state.history)
        emit("bettedUserInfo", _betted_user_info())

        current_num = state.crash_point if state.phase == "GAMEEND" else 1
        emit("gameState", {
            "currentNum": current_num,
            "currentSecondNum": current_num,
            "GameState": state.phase,
            "time": int(state.elapsed() * 1000),
        })

    @sio.on("playBet", namespace=NAMESPACE)
    def on_play_bet(data):
        if not current_user.is_authenticated:
            return
        slot = (data or {}).get("type")
        try:
            if slot not in ("f", "s"):
                emit("error", {"message": "Invalid bet slot", "index": slot or "f"})
                return
            if state.phase != "BET":
                emit("error", {"message": "Betting window is closed", "index": slot})
                return
            if (current_user.id, slot) in state.bets:
                emit("error", {"message": "You already have a bet this round", "index": slot})
                return

            amount = Decimal(str(data.get("betAmount", 0)))
            if amount < MIN_BET or amount > MAX_BET:
                emit("error", {"message": f"Bet must be between {MIN_BET} and {MAX_BET} KES", "index": slot})
                return

            wallet = _get_wallet(current_user.id)
            if not wallet or wallet.balance < amount:
                emit("error", {"message": "Insufficient balance", "index": slot})
                return

            wallet.balance -= amount

            target_raw = data.get("target")
            target = Decimal(str(target_raw)) if target_raw else None

            bet = AviatorCrashBet(
                user_id=current_user.id, round_id=state.round_id, slot=slot,
                bet_amount=amount, target=target, auto=bool(data.get("auto")), status="active",
            )
            db.session.add(bet)
            db.session.add(Transaction(
                wallet_id=wallet.id, type="stake", amount=-amount, balance_after=wallet.balance,
                reference=f"aviatorcrash:{state.round_id}:{slot}:stake:{current_user.id}:{state.round_number}",
                status="completed",
            ))
            stats = _get_stats(current_user.id)
            stats.total_wagered = (stats.total_wagered or Decimal("0")) + amount
            db.session.commit()

            state.bets[(current_user.id, slot)] = {
                "bet_id": bet.id, "amount": float(amount),
                "target": float(target) if target else None, "auto": bool(data.get("auto")),
                "cashouted": False, "cashout_at": None,
                "name": mask_username(current_user), "img": avatar_for(current_user.id),
            }

            payload = _user_type_payload(current_user.id, wallet.balance, mask_username(current_user))
            socketio.emit("myInfo", payload, room=str(current_user.id), namespace=NAMESPACE)
            socketio.emit("myBetState", payload, room=str(current_user.id), namespace=NAMESPACE)
            socketio.emit("bettedUserInfo", _betted_user_info(), namespace=NAMESPACE)
        except Exception as e:
            db.session.rollback()
            print(f"AviatorCrash playBet error: {e}")
            traceback.print_exc()
            emit("error", {"message": "Something went wrong placing your bet", "index": slot or "f"})

    @sio.on("cashOut", namespace=NAMESPACE)
    def on_cash_out(data):
        if not current_user.is_authenticated:
            return
        slot = (data or {}).get("type")
        try:
            key = (current_user.id, slot)
            b = state.bets.get(key)
            if not b or b["cashouted"]:
                emit("error", {"message": "No active bet to cash out", "index": slot or "f"})
                return
            if state.phase != "PLAYING":
                emit("error", {"message": "Round is not live", "index": slot})
                return

            multiplier = round(min(multiplier_at(state.elapsed()), state.crash_point), 2)
            if multiplier <= 1.0:
                emit("error", {"message": "Cannot cash out at 1.00x", "index": slot})
                return

            _settle_cashout(current_user.id, slot, b, multiplier, "payout")
        except Exception as e:
            db.session.rollback()
            print(f"AviatorCrash cashOut error: {e}")
            traceback.print_exc()
            emit("error", {"message": "Something went wrong cashing out", "index": slot or "f"})

    if not _loop_started:
        sio.start_background_task(game_loop, app)
        _loop_started = True


# ---------------------------------------------------------------------------
# REST endpoints (absolute /api/* paths, baked into the built JS bundle)
# ---------------------------------------------------------------------------

api_bp = Blueprint("aviatorcrash_api", __name__)


@api_bp.route("/api/my-info", methods=["POST"])
@login_required
def my_info():
    bets = (AviatorCrashBet.query.filter_by(user_id=current_user.id)
            .order_by(AviatorCrashBet.created_at.desc()).limit(20).all())
    data = [{
        "_id": b.id,
        "name": mask_username(current_user),
        "betAmount": float(b.bet_amount),
        "cashoutAt": float(b.cashout_at) if b.cashout_at else 0,
        "cashouted": b.status == "cashed_out",
        "date": int(b.created_at.timestamp() * 1000),
    } for b in bets]
    return jsonify({"status": True, "data": data})


def _top_history(since):
    rows = (AviatorCrashBet.query
            .filter(AviatorCrashBet.status == "cashed_out", AviatorCrashBet.created_at >= since)
            .order_by(AviatorCrashBet.payout_amount.desc())
            .limit(20).all())
    return [{
        "name": mask_username(b.user),
        "img": avatar_for(b.user_id),
        "betAmount": float(b.bet_amount),
        "cashoutAt": float(b.cashout_at) if b.cashout_at else 0,
    } for b in rows]


@api_bp.route("/api/get-day-history")
@login_required
def get_day_history():
    return jsonify({"status": True, "data": _top_history(datetime.utcnow() - timedelta(days=1))})


@api_bp.route("/api/get-month-history")
@login_required
def get_month_history():
    return jsonify({"status": True, "data": _top_history(datetime.utcnow() - timedelta(days=30))})


@api_bp.route("/api/get-year-history")
@login_required
def get_year_history():
    return jsonify({"status": True, "data": _top_history(datetime.utcnow() - timedelta(days=365))})


# ---------------------------------------------------------------------------
# Static game blueprints — /aviator-mzizi/ and /jetx/ both serve the same
# built Unity/React bundle out of app/static/aviatorcrash/
# ---------------------------------------------------------------------------

def _make_game_blueprint(name, url_prefix):
    bp = Blueprint(name, __name__, static_folder=BUILD_DIR, static_url_path="", url_prefix=url_prefix)

    @bp.route("/")
    @login_required
    def index():
        return send_from_directory(os.path.join(bp.root_path, BUILD_DIR), "index.html")

    return bp


def get_aviatorcrash_blueprints(sio, app):
    """Factory — call once from create_app(). Returns (aviator_bp, jetx_bp, api_bp)."""
    init_socketio(sio, app)
    aviator_bp = _make_game_blueprint("aviatorcrash_aviator", "/aviator-mzizi")
    jetx_bp = _make_game_blueprint("aviatorcrash_jetx", "/jetx")
    return aviator_bp, jetx_bp, api_bp
