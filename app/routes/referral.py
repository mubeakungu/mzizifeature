from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models.referral import ReferralCode, Referral, ReferralSettings

referral_bp = Blueprint("referral", __name__, url_prefix="/referrals")


@referral_bp.route("/")
@login_required
def dashboard():
    code_row = ReferralCode.get_or_create(current_user)
    referrals = (
        Referral.query.filter_by(referrer_id=current_user.id)
        .order_by(Referral.created_at.desc())
        .all()
    )
    settings = ReferralSettings.get()

    total_earned = sum(
        float(b.amount) for r in referrals for b in r.bonuses
    )

    return render_template(
        "referral/dashboard.html",
        code=code_row.code,
        referrals=referrals,
        settings=settings,
        total_earned=total_earned,
    )
