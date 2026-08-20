from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from decimal import Decimal

from app.extensions import db
from app.models.wallet import Transaction

wallet_bp = Blueprint("wallet", __name__)


@wallet_bp.route("/")
@login_required
def overview():
    transactions = (
        current_user.wallet.transactions.order_by(Transaction.created_at.desc()).limit(50).all()
    )
    return render_template("wallet/overview.html", wallet=current_user.wallet, transactions=transactions)


@wallet_bp.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        amount = Decimal(request.form.get("amount", "0"))
        daily_limit = current_app.config["DEFAULT_DAILY_DEPOSIT_LIMIT"]

        if amount <= 0:
            return render_template("wallet/deposit.html", error="Enter a valid amount.")
        if amount > daily_limit:
            return render_template(
                "wallet/deposit.html",
                error=f"Deposits are capped at KES {daily_limit:,} per day. "
                      f"Reach out to support to adjust your limit.",
            )

        # Trigger STK Push here using the same Daraja flow as Ufanisi Sacco:
        # build password from shortcode+passkey+timestamp, POST to
        # /mpesa/stkpush/v1/processrequest, then handle the callback at
        # MPESA_CALLBACK_URL to credit the wallet only on a successful receipt.
        # Left as an integration point pending your Daraja go-live credentials.

        return render_template("wallet/deposit_pending.html", amount=amount)

    return render_template("wallet/deposit.html")


@wallet_bp.route("/mpesa/callback", methods=["POST"])
def mpesa_callback():
    """
    Daraja hits this after an STK Push attempt. Verify the payload signature/
    shared-secret pattern you use in your other projects before crediting
    anything — never trust ResultCode == 0 without matching it to a pending
    Transaction row by CheckoutRequestID.
    """
    payload = request.get_json(silent=True) or {}
    # TODO: match payload to a pending Transaction, credit wallet.balance,
    # mark transaction.status = "completed", store mpesa_receipt.
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
