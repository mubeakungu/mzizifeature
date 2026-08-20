# UPDATED app/routes/sports.py with live fixtures support
# This matches your actual SportsEvent schema (event_time, status='upcoming'/'live', etc.)
#
# FIX: added get_betslip_summary() — app/__init__.py's inject_globals
# context processor imports this and runs on EVERY template render, so
# its absence was crashing /casino too, not just sports pages.

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.sports import SportsEvent, SportsMarket, SportsSelection, Bet, BetSlip, BetSlipLeg
from datetime import datetime, timedelta

sports_bp = Blueprint("sports", __name__, url_prefix="/sports")


# ==================== BETSLIP SUMMARY (used by inject_globals) ====================

def get_betslip_summary():
    """
    Return (betslip_items, betslip_total_odds) for the current user's open
    bet slip. Called by app/__init__.py's inject_globals context processor
    on every single page render, so it must never raise — anonymous users
    or users with no open slip just get an empty summary.
    """
    if not current_user.is_authenticated:
        return [], 0

    open_slip = (
        BetSlip.query
        .filter_by(user_id=current_user.id, status="open")
        .order_by(BetSlip.id.desc())
        .first()
    )

    if not open_slip:
        return [], 0

    legs = BetSlipLeg.query.filter_by(bet_slip_id=open_slip.id).all()

    betslip_items = []
    total_odds = 1.0

    for leg in legs:
        selection = SportsSelection.query.get(leg.selection_id)
        event = SportsEvent.query.get(leg.event_id)

        betslip_items.append({
            "leg_id": leg.id,
            "event_id": leg.event_id,
            "selection_id": leg.selection_id,
            "selection_name": selection.name if selection else None,
            "home_team": event.home_team if event else None,
            "away_team": event.away_team if event else None,
            "odds": float(leg.odds),
            "status": leg.status,
        })

        total_odds *= float(leg.odds)

    if not betslip_items:
        total_odds = 0

    return betslip_items, total_odds


# ==================== LIVE FIXTURES ROUTES ====================

@sports_bp.route("/live")
def live_fixtures():
    """Display live and recently finished games."""

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(minutes=30)

    # Get live games + recently finished (last 30 mins)
    live_games = SportsEvent.query.filter(
        db.or_(
            db.and_(
                SportsEvent.status == 'live',
                SportsEvent.is_live == True
            ),
            db.and_(
                SportsEvent.status == 'finished',
                SportsEvent.updated_at >= recent_cutoff
            )
        )
    ).order_by(SportsEvent.updated_at.desc()).all()

    return render_template("sports_live.html", live_games=live_games)


@sports_bp.route("/api/live/<int:event_id>")
def get_live_event(event_id):
    """API endpoint for live game data — used for auto-refresh."""
    event = SportsEvent.query.get_or_404(event_id)

    return jsonify({
        'id': event.id,
        'homeTeam': event.home_team,
        'awayTeam': event.away_team,
        'homeScore': event.home_score,
        'awayScore': event.away_score,
        'status': event.status,
        'isLive': event.is_live,
        'updatedAt': event.updated_at.isoformat() if event.updated_at else None,
        'displayScore': event.display_score
    })


@sports_bp.route("/api/live-markets/<int:event_id>")
def get_live_markets(event_id):
    """Get current odds for a live event."""
    event = SportsEvent.query.get_or_404(event_id)
    markets = SportsMarket.query.filter_by(event_id=event_id).all()

    markets_data = []
    for market in markets:
        selections = SportsSelection.query.filter_by(market_id=market.id).all()
        selections_data = [
            {
                'id': s.id,
                'name': s.name,
                'odds': float(s.odds)
            }
            for s in selections
        ]
        markets_data.append({
            'id': market.id,
            'name': market.name,
            'selections': selections_data
        })

    return jsonify({
        'event': {
            'id': event.id,
            'homeTeam': event.home_team,
            'awayTeam': event.away_team,
            'status': event.status,
            'displayScore': event.display_score
        },
        'markets': markets_data
    })


# ==================== EXISTING LOBBY (UPDATED) ====================

@sports_bp.route("/")
@sports_bp.route("/lobby")
def lobby():
    """Display upcoming sports fixtures for betting."""

    # Get filter parameters
    active_sport = request.args.get("sport", "all")
    search = request.args.get("q", "").strip()
    show_live = request.args.get("live", "false").lower() == "true"

    # Query upcoming events or live events
    if show_live:
        # Show LIVE games only
        query = SportsEvent.query.filter(
            SportsEvent.status == 'live',
            SportsEvent.is_live == True
        )
    else:
        # Show UPCOMING games (default)
        query = SportsEvent.query.filter(
            SportsEvent.event_time >= datetime.utcnow(),
            SportsEvent.event_time <= datetime.utcnow() + timedelta(days=7),
            SportsEvent.status == "upcoming"
        )

    # Filter by sport
    if active_sport != "all":
        query = query.filter_by(sport=active_sport)

    # Search by team name
    if search:
        query = query.filter(
            db.or_(
                SportsEvent.home_team.ilike(f"%{search}%"),
                SportsEvent.away_team.ilike(f"%{search}%")
            )
        )

    # Order by event time (or updated time for live)
    if show_live:
        upcoming_events = query.order_by(SportsEvent.updated_at.desc()).all()
    else:
        upcoming_events = query.order_by(SportsEvent.event_time.asc()).all()

    # Get unique sports for filter tabs
    all_sports = db.session.query(SportsEvent.sport).filter(
        SportsEvent.event_time >= datetime.utcnow()
    ).distinct().all()
    sports = [s[0] for s in all_sports]

    # Count live games for badge
    live_count = SportsEvent.query.filter(
        SportsEvent.status == 'live',
        SportsEvent.is_live == True
    ).count()

    return render_template(
        "sports_lobby.html",
        upcoming_events=upcoming_events,
        active_sport=active_sport,
        sports=sports,
        search=search,
        show_live=show_live,
        live_count=live_count
    )


@sports_bp.route("/event/<int:event_id>")
def event_detail(event_id):
    """Show detailed view of an event with all available markets."""
    event = SportsEvent.query.get_or_404(event_id)

    return render_template(
        "sports_event_detail.html",
        event=event,
        is_live=event.is_live_now  # ← Add this so template knows if live
    )


@sports_bp.route("/place-bet/<int:event_id>", methods=["GET", "POST"])
@login_required
def place_bet(event_id):
    """Handle bet placement."""
    event = SportsEvent.query.get_or_404(event_id)
    selection_id = request.args.get("selection_id", type=int)

    if request.method == "POST":
        try:
            # Check if event can be bet on
            if event.status not in ['upcoming', 'live']:
                return jsonify({"error": f"Cannot bet on {event.status} events"}), 403

            amount = float(request.form.get("amount", 0))
            selection_id = int(request.form.get("selection_id", 0))

            if amount <= 0 or amount > current_user.wallet.balance:
                return jsonify({"error": "Invalid amount"}), 400

            selection = SportsSelection.query.get_or_404(selection_id)
            market = SportsMarket.query.get(selection.market_id)

            # Create bet slip
            bet_slip = BetSlip(
                user_id=current_user.id,
                status="open",
                potential_return=amount * selection.odds
            )
            db.session.add(bet_slip)
            db.session.flush()

            # Add leg to bet slip (using your actual schema)
            leg = BetSlipLeg(
                bet_slip_id=bet_slip.id,
                event_id=event_id,
                market_id=market.id,
                selection_id=selection_id,
                odds=selection.odds,
                status="pending"
            )
            db.session.add(leg)

            # Create bet
            bet = Bet(
                user_id=current_user.id,
                bet_slip_id=bet_slip.id,
                amount=amount,
                potential_return=amount * selection.odds,
                status="pending"
            )
            db.session.add(bet)

            # Deduct from wallet
            current_user.wallet.balance -= amount

            db.session.commit()

            return redirect(url_for("sports.bet_confirmation", bet_id=bet.id))

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 400

    # GET: Show bet placement form
    return render_template(
        "sports_place_bet.html",
        event=event,
        selection_id=selection_id
    )


@sports_bp.route("/bet-confirmation/<int:bet_id>")
@login_required
def bet_confirmation(bet_id):
    """Show bet confirmation page."""
    bet = Bet.query.get_or_404(bet_id)

    # Only show own bets
    if bet.user_id != current_user.id:
        return redirect(url_for("sports.lobby"))

    return render_template(
        "sports_bet_confirmation.html",
        bet=bet
    )


@sports_bp.route("/my-bets")
@login_required
def my_bets():
    """Show user's active and settled bets."""
    page = request.args.get("page", 1, type=int)

    bets = Bet.query.filter_by(user_id=current_user.id).order_by(
        Bet.created_at.desc()
    ).paginate(page=page, per_page=20)

    return render_template(
        "sports_my_bets.html",
        bets=bets
    )


@sports_bp.route("/api/odds/<int:selection_id>")
def get_odds(selection_id):
    """API endpoint to get real-time odds (for dynamic updates)."""
    selection = SportsSelection.query.get_or_404(selection_id)

    return jsonify({
        "name": selection.name,
        "odds": float(selection.odds),
        "status": selection.status
    })
