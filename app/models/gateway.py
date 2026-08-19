from datetime import datetime
from app.extensions import db


class PaymentGateway(db.Model):
    """Admin-manageable limits/toggle for each payment rail. Credentials
    (Daraja keys, etc.) stay in environment variables / config — this table
    only controls what the admin should be able to change without a
    redeploy: whether it's enabled, and the min/max/fee rules.
    """

    __tablename__ = "payment_gateways"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)  # mpesa_stk, mpesa_b2c
    display_name = db.Column(db.String(60), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # deposit, withdrawal
    is_active = db.Column(db.Boolean, default=True)
    min_amount = db.Column(db.Numeric(12, 2), default=10)
    max_amount = db.Column(db.Numeric(12, 2), default=150000)
    fee_flat = db.Column(db.Numeric(12, 2), default=0)
    fee_pct = db.Column(db.Numeric(5, 2), default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def fee_for(self, amount) -> float:
        amount = float(amount)
        return round(float(self.fee_flat) + amount * float(self.fee_pct) / 100, 2)

    def in_range(self, amount) -> bool:
        return float(self.min_amount) <= float(amount) <= float(self.max_amount)


def seed_default_gateways():
    defaults = [
        dict(code="mpesa_stk", display_name="M-Pesa (STK Push)", direction="deposit",
             min_amount=10, max_amount=150000, fee_flat=0, fee_pct=0),
        dict(code="mpesa_b2c", display_name="M-Pesa (B2C Payout)", direction="withdrawal",
             min_amount=50, max_amount=150000, fee_flat=0, fee_pct=0),
    ]
    for gw in defaults:
        if not PaymentGateway.query.filter_by(code=gw["code"]).first():
            db.session.add(PaymentGateway(**gw))
    db.session.commit()
