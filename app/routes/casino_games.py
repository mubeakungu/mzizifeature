"""
Casino Game Routes - Self-contained game server for the self-hosted
provably-fair games (Aviator, Dice, Mines, Plinko, Roulette, Slots).

Wallet debits/credits go through the real Wallet + Transaction models
(app/models/wallet.py) — the same ledger your M-Pesa deposit flow writes
to — so game balance and deposit balance never diverge.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import datetime

from app.models.casino import Game, CasinoRound
from app.models.wallet import Wallet, Transaction  # noqa: F401 (Wallet kept for typing/clarity)
from app.extensions import db
from app.game_engine import GameEngine, PayoutCalculator  # noqa: F401

casino_games_bp = Blueprint("casino_games", __name__, url_prefix="/api/casino")


@casino_games_bp.route("/init-round", methods=["POST"])
@login_required
def init_round():
    """
    Initialize a game round:
    - Validate stake
    - Reserve funds (debit wallet, log a 'stake' transaction)
    - Generate server seed & round ID
    """
    data = request.get_json()
    game_id = data.get("game_id")
    stake = Decimal(str(data.get("stake", 0)))
    client_seed = data.get("client_seed", "")

    if stake <= 0 or stake > Decimal("10000"):
        return jsonify({"error": "Invalid stake amount"}), 400

    game = Game.query.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404

    wallet = current_user.wallet
    if not wallet or wallet.balance < stake:
        return jsonify({"error": "Insufficient balance"}), 402

    round_id = GameEngine.generate_round_id()
    server_seed = GameEngine.generate_server_seed()

    # Debit stake
    wallet.balance -= stake
    stake_txn = Transaction(
        wallet_id=wallet.id,
        type="stake",
        amount=stake,
        balance_after=wallet.balance,
        reference=f"casino:{round_id}:stake",
        status="completed",
    )
    db.session.add(stake_txn)

    casino_round = CasinoRound(
        user_id=current_user.id,
        game_id=game_id,
        stake=stake,
        status="pending",
        provider_round_id=round_id,
        provider_result={
            "server_seed": server_seed,
            "client_seed": client_seed,
            "round_id": round_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
    db.session.add(casino_round)
    db.session.commit()

    return jsonify({
        "round_id": round_id,
        "server_seed": server_seed,
        "client_seed": client_seed,
        "nonce": 1,
        "balance": float(wallet.balance),
    }), 200


@casino_games_bp.route("/settle-round", methods=["POST"])
@login_required
def settle_round():
    """
    Process game outcome and settle round:
    - Validate game result / payout
    - Credit wallet (log a 'payout' transaction), or void + reverse the stake
    """
    data = request.get_json()
    round_id = data.get("round_id")
    game_id = data.get("game_id")
    payout = Decimal(str(data.get("payout", 0)))
    game_result = data.get("game_result", {})

    casino_round = CasinoRound.query.filter_by(
        provider_round_id=round_id,
        user_id=current_user.id,
        status="pending",
    ).first_or_404()

    game = Game.query.get(game_id)
    if not game or game.id != casino_round.game_id:
        return jsonify({"error": "Game mismatch"}), 400

    wallet = current_user.wallet

    # Payout can't exceed 100x stake — anything past that is a fraud attempt
    max_payout = casino_round.stake * Decimal("100")
    if payout < 0 or payout > max_payout:
        casino_round.status = "void"
        casino_round.payout = Decimal("0.00")

        wallet.balance += casino_round.stake
        reversal_txn = Transaction(
            wallet_id=wallet.id,
            type="reversal",
            amount=casino_round.stake,
            balance_after=wallet.balance,
            reference=f"casino:{round_id}:reversal",
            status="completed",
        )
        db.session.add(reversal_txn)
        db.session.commit()

        return jsonify({"error": "Invalid payout amount"}), 400

    casino_round.status = "settled"
    casino_round.payout = payout
    casino_round.settled_at = datetime.utcnow()

    result_data = dict(casino_round.provider_result or {})
    result_data["game_result"] = game_result
    result_data["payout"] = float(payout)
    casino_round.provider_result = result_data

    net_result = payout - casino_round.stake

    if payout > 0:
        wallet.balance += payout
        payout_txn = Transaction(
            wallet_id=wallet.id,
            type="payout",
            amount=payout,
            balance_after=wallet.balance,
            reference=f"casino:{round_id}:payout",
            status="completed",
        )
        db.session.add(payout_txn)

    db.session.add(casino_round)
    db.session.commit()

    return jsonify({
        "status": "settled",
        "payout": float(payout),
        "net_result": float(net_result),
        "balance": float(wallet.balance),
        "round_id": round_id,
    }), 200


@casino_games_bp.route("/get-balance", methods=["GET"])
@login_required
def get_balance():
    """Get current balance."""
    wallet = current_user.wallet
    return jsonify({
        "balance": float(wallet.balance) if wallet else 0,
        "currency": wallet.currency if wallet else "KES",
    }), 200


@casino_games_bp.route("/game-seeds/<round_id>", methods=["GET"])
@login_required
def get_game_seeds(round_id):
    """Get seeds for verification (provably fair)."""
    casino_round = CasinoRound.query.filter_by(
        provider_round_id=round_id,
        user_id=current_user.id,
    ).first_or_404()

    result_data = casino_round.provider_result or {}

    return jsonify({
        "round_id": round_id,
        "server_seed": result_data.get("server_seed"),
        "client_seed": result_data.get("client_seed"),
        "game_result": result_data.get("game_result"),
        "payout": result_data.get("payout"),
        "stake": float(casino_round.stake),
    }), 200


@casino_games_bp.route("/round-history", methods=["GET"])
@login_required
def round_history():
    """Get user's recent round history."""
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)

    rounds = CasinoRound.query.filter_by(
        user_id=current_user.id,
        status="settled",
    ).order_by(CasinoRound.created_at.desc()).limit(limit).offset(offset).all()

    # CasinoRound has a raw game_id FK, no ORM relationship to Game (see
    # app/models/casino.py), so batch-fetch names/slugs instead of an
    # N+1 round_obj.game.* access pattern.
    game_ids = {r.game_id for r in rounds}
    games_by_id = {g.id: g for g in Game.query.filter(Game.id.in_(game_ids)).all()}

    history = []
    for round_obj in rounds:
        game = games_by_id.get(round_obj.game_id)
        history.append({
            "round_id": round_obj.provider_round_id,
            "game_name": game.name if game else "Unknown",
            "game_slug": game.slug if game else "unknown",
            "stake": float(round_obj.stake),
            "payout": float(round_obj.payout),
            "net": float(round_obj.payout - round_obj.stake),
            "status": round_obj.status,
            "settled_at": round_obj.settled_at.isoformat() if round_obj.settled_at else None,
        })

    return jsonify({
        "history": history,
        "count": len(history),
    }), 200
