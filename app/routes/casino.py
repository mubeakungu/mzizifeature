"""Casino catalog and canonical game launcher.

Important architecture rule:
- The catalog owns discovery.
- app.games.registry owns game routing.
- Each game has exactly one canonical implementation.
- casino_play.html is provider-only and contains no local game logic.
"""

from flask import Blueprint, render_template, request, redirect, abort
from flask_login import login_required, current_user

from app.models.casino import Game, GameCategory
from app.games.registry import get_game_definition

casino_bp = Blueprint("casino", __name__)


@casino_bp.route("/casino")
def lobby():
    """Public casino lobby; authentication is required only to play."""
    category_slug = request.args.get("category", "all")
    search = request.args.get("q", "").strip()

    categories = GameCategory.query.order_by(GameCategory.display_order).all()

    query = Game.query.filter_by(is_active=True)
    if category_slug != "all":
        query = query.join(GameCategory).filter(GameCategory.slug == category_slug)
    if search:
        query = query.filter(Game.name.ilike(f"%{search}%"))
    games = query.order_by(Game.display_order).all()

    featured_games = (
        Game.query.filter_by(is_active=True)
        .filter(Game.badge.in_(["HOT", "POPULAR"]))
        .order_by(Game.display_order)
        .limit(8)
        .all()
    )

    return render_template(
        "casino_lobby.html",
        categories=categories,
        games=games,
        featured_games=featured_games,
        active_category=category_slug,
        search=search,
    )


@casino_bp.route("/casino/play/<slug>")
@login_required
def play(slug):
    """Launch the one canonical implementation for a catalog game."""
    game = Game.query.filter_by(slug=slug, is_active=True).first_or_404()

    can_play, reason = current_user.can_play()
    if not can_play:
        return render_template("casino_blocked.html", reason=reason)

    definition = get_game_definition(slug)
    if definition is None:
        # Do not silently run a fake/demo game. If a catalog row has no
        # canonical implementation, fail explicitly until it is wired up.
        abort(503, description=f"Game '{slug}' has no canonical implementation configured.")

    if definition.kind == "redirect":
        return redirect(definition.route)

    if definition.template:
        wallet = current_user.wallet
        return render_template(
            definition.template,
            game=game,
            balance=float(wallet.balance) if wallet else 0,
        )

    # Provider games are intentionally kept separate from local game logic.
    return render_template("casino_play.html", game=game)
