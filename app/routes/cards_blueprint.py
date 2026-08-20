"""
cards Blueprint - self-hosted Blackjack engine.
Aligns with seed.py: slug="cards", category="table", name="Cards", RTP 99.5.

Rules implemented (chosen to match seed.py's 99.5% RTP claim under basic
strategy — change these if you intended a different ruleset):
  - Single 52-card deck, reshuffled every round (not a multi-deck shoe)
  - Dealer stands on soft 17
  - Blackjack (natural 21 on the first two cards) pays 3:2
  - Regular win pays 1:1, push returns the stake, no surrender
  - Double down allowed on the first decision only (no split, v1)

Ledger: same pattern as mzizicrash_blueprint.py and casino_games_bp — all
stake/payout movement goes through Wallet.balance + a logged Transaction
row. Nothing here writes to a separate table.

Fairness: the deck is shuffled deterministically from a per-round
server_seed using an HMAC-SHA256-driven Fisher-Yates shuffle. The SHA-256
hash of server_seed is sent to the player at bet time (commit); the raw
server_seed is only revealed after the round settles (reveal), so a player
can verify after the fact that the deck wasn't altered mid-round.

Nothing about hand outcomes is ever trusted from the client — hit/stand/
double are the only inputs the client sends; all card dealing and hand
evaluation happens server-side against the round row in the database.
"""

import hashlib
import hmac
import secrets
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.wallet import Wallet, Transaction
from app.models.cards_models import BlackjackRound, BlackjackStats

cards_bp = Blueprint("cards", __name__, url_prefix="/cards", template_folder="templates")

MAX_STAKE = Decimal("10000")
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["H", "D", "C", "S"]


# ============================================================================
# PROVABLY-FAIR DECK
# ============================================================================

def _build_shuffled_deck(server_seed: str):
    """Deterministic Fisher-Yates shuffle driven by HMAC-SHA256(server_seed, i).
    Same server_seed always produces the same deck order — this is what
    makes it verifiable after reveal."""
    deck = [{"rank": r, "suit": s} for s in SUITS for r in RANKS]
    for i in range(len(deck) - 1, 0, -1):
        digest = hmac.new(server_seed.encode(), f"shuffle:{i}".encode(), hashlib.sha256).hexdigest()
        j = int(digest, 16) % (i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    return deck


def _card_value(card):
    if card["rank"] == "A":
        return 11
    if card["rank"] in ("J", "Q", "K"):
        return 10
    return int(card["rank"])


def _hand_value(cards):
    """Best blackjack value, treating Aces as 11 unless that busts the hand."""
    total = sum(_card_value(c) for c in cards)
    aces = sum(1 for c in cards if c["rank"] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _is_blackjack(cards):
    return len(cards) == 2 and _hand_value(cards) == 21


# ============================================================================
# ROUND LOGIC (real wallet ledger)
# ============================================================================

def start_round(user_id, amount):
    try:
        amount = Decimal(str(amount))
        if amount <= 0 or amount > MAX_STAKE:
            return {"success": False, "error": "Invalid bet amount"}

        wallet = Wallet.query.filter_by(user_id=user_id).first()
        if not wallet or wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}

        server_seed = secrets.token_hex(32)
        server_seed_hash = hashlib.sha256(server_seed.encode()).hexdigest()
        deck = _build_shuffled_deck(server_seed)

        player_cards = [deck[0], deck[2]]
        dealer_cards = [deck[1], deck[3]]

        wallet.balance -= amount
        db.session.add(Transaction(
            wallet_id=wallet.id,
            type="stake",
            amount=amount,
            balance_after=wallet.balance,
            reference=f"cards:pending:{user_id}:stake",
            status="completed",
        ))

        round_row = BlackjackRound(
            user_id=user_id,
            bet_amount=amount,
            status="active",
            server_seed=server_seed,
            server_seed_hash=server_seed_hash,
            player_cards=player_cards,
            dealer_cards=dealer_cards,
            deck_position=4,
        )
        db.session.add(round_row)
        db.session.commit()

        result = {
            "success": True,
            "round_id": round_row.id,
            "player_cards": player_cards,
            "dealer_upcard": dealer_cards[0],  # only the up-card is shown until stand/blackjack
            "server_seed_hash": server_seed_hash,
            "balance": float(wallet.balance),
        }

        # Natural blackjack resolves immediately (standard house rule)
        if _is_blackjack(player_cards):
            settle = _settle(round_row, wallet, force_dealer_reveal=True)
            result.update(settle)

        return result

    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}


def hit(user_id, round_id):
    try:
        round_row = BlackjackRound.query.filter_by(id=round_id, user_id=user_id, status="active").first()
        if not round_row:
            return {"success": False, "error": "No active round"}

        deck = _build_shuffled_deck(round_row.server_seed)
        card = deck[round_row.deck_position]
        round_row.deck_position += 1
        round_row.player_cards = round_row.player_cards + [card]

        player_total = _hand_value(round_row.player_cards)

        if player_total > 21:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            settle = _settle(round_row, wallet, force_dealer_reveal=True, bust=True)
            return {"success": True, "player_cards": round_row.player_cards, **settle}

        db.session.commit()
        return {
            "success": True,
            "player_cards": round_row.player_cards,
            "player_total": player_total,
            "status": "active",
        }

    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}


def double_down(user_id, round_id):
    try:
        round_row = BlackjackRound.query.filter_by(id=round_id, user_id=user_id, status="active").first()
        if not round_row:
            return {"success": False, "error": "No active round"}
        if len(round_row.player_cards) != 2 or round_row.doubled:
            return {"success": False, "error": "Double down only allowed on your first decision"}

        wallet = Wallet.query.filter_by(user_id=user_id).first()
        if not wallet or wallet.balance < round_row.bet_amount:
            return {"success": False, "error": "Insufficient balance to double down"}

        # Match the original stake
        wallet.balance -= round_row.bet_amount
        db.session.add(Transaction(
            wallet_id=wallet.id,
            type="stake",
            amount=round_row.bet_amount,
            balance_after=wallet.balance,
            reference=f"cards:{round_row.id}:{user_id}:double",
            status="completed",
        ))
        round_row.bet_amount = round_row.bet_amount * 2
        round_row.doubled = True

        deck = _build_shuffled_deck(round_row.server_seed)
        card = deck[round_row.deck_position]
        round_row.deck_position += 1
        round_row.player_cards = round_row.player_cards + [card]

        bust = _hand_value(round_row.player_cards) > 21
        settle = _settle(round_row, wallet, force_dealer_reveal=True, bust=bust)
        return {"success": True, "player_cards": round_row.player_cards, **settle}

    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}


def stand(user_id, round_id):
    try:
        round_row = BlackjackRound.query.filter_by(id=round_id, user_id=user_id, status="active").first()
        if not round_row:
            return {"success": False, "error": "No active round"}

        wallet = Wallet.query.filter_by(user_id=user_id).first()
        settle = _settle(round_row, wallet, force_dealer_reveal=True)
        return {"success": True, **settle}

    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}


def _settle(round_row, wallet, force_dealer_reveal=False, bust=False):
    """Resolve the round: draw for the dealer if needed, determine outcome,
    credit the wallet, log the payout Transaction, update stats. This is the
    ONLY place payout is decided — always from server state, never client
    input."""
    deck = _build_shuffled_deck(round_row.server_seed)
    player_total = _hand_value(round_row.player_cards)

    if not bust and force_dealer_reveal:
        # Dealer draws to 17+, standing on soft 17
        while _hand_value(round_row.dealer_cards) < 17:
            card = deck[round_row.deck_position]
            round_row.deck_position += 1
            round_row.dealer_cards = round_row.dealer_cards + [card]

    dealer_total = _hand_value(round_row.dealer_cards)
    player_bj = _is_blackjack(round_row.player_cards)
    dealer_bj = _is_blackjack(round_row.dealer_cards) and len(round_row.player_cards) == 2

    if bust:
        outcome, payout = "lose", Decimal("0")
    elif player_bj and dealer_bj:
        outcome, payout = "push", round_row.bet_amount
    elif player_bj:
        outcome, payout = "blackjack", round_row.bet_amount * Decimal("2.5")
    elif dealer_bj:
        outcome, payout = "lose", Decimal("0")
    elif dealer_total > 21:
        outcome, payout = "win", round_row.bet_amount * Decimal("2")
    elif player_total > dealer_total:
        outcome, payout = "win", round_row.bet_amount * Decimal("2")
    elif player_total < dealer_total:
        outcome, payout = "lose", Decimal("0")
    else:
        outcome, payout = "push", round_row.bet_amount

    round_row.status = "settled"
    round_row.outcome = outcome
    round_row.payout = payout
    round_row.settled_at = datetime.utcnow()

    if payout > 0:
        wallet.balance += payout
        db.session.add(Transaction(
            wallet_id=wallet.id,
            type="payout",
            amount=payout,
            balance_after=wallet.balance,
            reference=f"cards:{round_row.id}:{round_row.user_id}:payout",
            status="completed",
        ))

    stats = BlackjackStats.query.filter_by(user_id=round_row.user_id).first()
    if not stats:
        stats = BlackjackStats(user_id=round_row.user_id)
        db.session.add(stats)
    stats.hands_played += 1
    stats.total_wagered += round_row.bet_amount
    stats.total_winnings += (payout - round_row.bet_amount)
    if outcome == "push":
        stats.hands_pushed += 1
    elif outcome in ("win", "blackjack"):
        stats.hands_won += 1
        if outcome == "blackjack":
            stats.blackjacks_hit += 1
    else:
        stats.hands_lost += 1

    db.session.commit()

    return {
        "status": "settled",
        "dealer_cards": round_row.dealer_cards,
        "player_total": player_total,
        "dealer_total": dealer_total,
        "outcome": outcome,
        "payout": float(payout),
        "server_seed": round_row.server_seed,  # reveal — player can now verify the shuffle
        "balance": float(wallet.balance),
    }


# ============================================================================
# HTTP ROUTES
# ============================================================================

@cards_bp.route("/", methods=["GET"])
@login_required
def index():
    wallet = current_user.wallet
    return render_template("games/cards.html", balance=float(wallet.balance) if wallet else 0)


@cards_bp.route("/api/bet", methods=["POST"])
@login_required
def api_start_round():
    data = request.get_json()
    return jsonify(start_round(current_user.id, data.get("amount")))


@cards_bp.route("/api/hit", methods=["POST"])
@login_required
def api_hit():
    data = request.get_json()
    return jsonify(hit(current_user.id, data.get("round_id")))


@cards_bp.route("/api/double", methods=["POST"])
@login_required
def api_double():
    data = request.get_json()
    return jsonify(double_down(current_user.id, data.get("round_id")))


@cards_bp.route("/api/stand", methods=["POST"])
@login_required
def api_stand():
    data = request.get_json()
    return jsonify(stand(current_user.id, data.get("round_id")))


@cards_bp.route("/api/history", methods=["GET"])
@login_required
def api_history():
    limit = request.args.get("limit", 20, type=int)
    rounds = BlackjackRound.query.filter_by(
        user_id=current_user.id, status="settled"
    ).order_by(BlackjackRound.settled_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rounds])


@cards_bp.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    stats = BlackjackStats.query.filter_by(user_id=current_user.id).first()
    if not stats:
        stats = BlackjackStats(user_id=current_user.id)
        db.session.add(stats)
        db.session.commit()
    return jsonify(stats.to_dict())


# ============================================================================
# FACTORY - matches app/__init__.py's get_cards_blueprint(socketio) call
# ============================================================================

def get_cards_blueprint(sio):
    """Blackjack doesn't need a shared broadcast loop the way crash does —
    each player's hand is independent — so this factory mainly exists to
    match the get_*_blueprint(socketio) shape app/__init__.py expects. If
    you want live dealing animation pushed over the socket rather than
    plain HTTP responses, socket event handlers can be registered here the
    same way mzizicrash_blueprint.py does (sio.on_event(...) — never
    @sio.on(...) at import time)."""
    return cards_bp
