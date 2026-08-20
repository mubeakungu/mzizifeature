from datetime import datetime, date
from urllib.parse import urlparse

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.casino import Game

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _get_showcase_games():
    return Game.query.filter_by(is_active=True).order_by(Game.display_order).limit(12).all()


def _safe_next_url():
    """Read `next` from the query string or POSTed form and only return it
    if it's a safe same-site relative path — never redirect to an
    attacker-supplied absolute/external URL. Falls back to the casino
    lobby if `next` is missing or looks unsafe."""
    next_url = request.args.get("next") or request.form.get("next")
    if not next_url:
        return url_for("casino.lobby")

    parsed = urlparse(next_url)
    # A safe relative path has no scheme and no network location
    # (rules out "https://evil.com/..." and protocol-relative "//evil.com/...").
    if parsed.scheme or parsed.netloc or not next_url.startswith("/"):
        return url_for("casino.lobby")

    return next_url


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    next_url = _safe_next_url()

    if current_user.is_authenticated:
        return redirect(next_url)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        password = request.form.get("password", "")
        dob_raw = request.form.get("date_of_birth", "")

        if not all([full_name, phone_number, password, dob_raw]):
            flash("All fields are required.", "error")
            return render_template("auth/register.html", showcase_games=_get_showcase_games(), next=next_url)

        try:
            dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Enter a valid date of birth.", "error")
            return render_template("auth/register.html", showcase_games=_get_showcase_games(), next=next_url)

        age = date.today().year - dob.year - ((date.today().month, date.today().day) < (dob.month, dob.day))
        if age < 18:
            flash("You must be 18 or older to register.", "error")
            return render_template("auth/register.html", showcase_games=_get_showcase_games(), next=next_url)

        if User.query.filter_by(phone_number=phone_number).first():
            flash("An account with that phone number already exists.", "error")
            return render_template("auth/register.html", showcase_games=_get_showcase_games(), next=next_url)

        user = User(full_name=full_name, phone_number=phone_number, date_of_birth=dob)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get user.id before commit
        wallet = Wallet(user_id=user.id, balance=0)
        db.session.add(wallet)
        db.session.commit()

        login_user(user)
        flash("Welcome to Mzizibet. Verify your ID to unlock withdrawals.", "success")
        return redirect(next_url)

    return render_template("auth/register.html", showcase_games=_get_showcase_games(), next=next_url)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = _safe_next_url()

    if current_user.is_authenticated:
        return redirect(next_url)

    if request.method == "POST":
        phone_number = request.form.get("phone_number", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(phone_number=phone_number).first()

        if user and user.check_password(password):
            can_play, reason = user.can_play()
            login_user(user)
            if not can_play:
                flash(reason, "warning")
            # Redirect to next_url regardless of can_play — if it points at
            # /casino/play/<slug>, play() re-checks can_play() itself and
            # shows casino_blocked.html there. No need to duplicate that
            # logic here.
            return redirect(next_url)

        flash("Invalid phone number or password.", "error")

    return render_template("auth/login.html", showcase_games=_get_showcase_games(), next=next_url)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))
