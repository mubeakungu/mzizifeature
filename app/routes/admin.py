from functools import wraps
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from app.models.user import User
from app.models.wallet import Transaction

admin_bp = Blueprint("admin", __name__)


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_user.role.lower() not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


@admin_bp.route("/")
@login_required
@roles_required("admin", "ceo")
def dashboard():
    total_users = User.query.count()
    pending_kyc = User.query.filter_by(kyc_verified=False).count()
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(20).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        pending_kyc=pending_kyc,
        recent_transactions=recent_transactions,
    )
