from datetime import datetime
from app.extensions import db


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    balance = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    bonus_balance = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    currency = db.Column(db.String(3), default="KES")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = db.relationship("Transaction", backref="wallet", lazy="dynamic")


class Transaction(db.Model):
    """Every credit/debit against a wallet — deposits, withdrawals, bet stakes, payouts."""

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id"), nullable=False)

    type = db.Column(db.String(20), nullable=False)
    # deposit, withdrawal, stake, payout, bonus, reversal

    amount = db.Column(db.Numeric(12, 2), nullable=False)
    balance_after = db.Column(db.Numeric(12, 2), nullable=False)

    reference = db.Column(db.String(64), unique=True, nullable=False)  # M-Pesa receipt / internal ref
    mpesa_receipt = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), default="pending")  # pending, completed, failed, reversed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Transaction {self.type} {self.amount} ({self.status})>"
