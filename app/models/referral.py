import secrets
from datetime import datetime
from app.extensions import db


class ReferralSettings(db.Model):
    """Single-row config the admin can edit — no code redeploy needed to
    change bonus amounts."""

    __tablename__ = "referral_settings"

    id = db.Column(db.Integer, primary_key=True)
    signup_bonus = db.Column(db.Numeric(12, 2), default=0)      # paid to referrer when referee registers
    deposit_bonus_pct = db.Column(db.Numeric(5, 2), default=0)  # % of referee's first deposit
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls(signup_bonus=0, deposit_bonus_pct=0, is_active=False)
            db.session.add(settings)
            db.session.commit()
        return settings


class ReferralCode(db.Model):
    """Kept as its own table (not a users.column) so this ships without any
    ALTER TABLE on the existing users table — db.create_all() only creates
    missing tables, it won't add columns to one that already exists."""

    __tablename__ = "referral_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("referral_code_row", uselist=False))

    @classmethod
    def get_or_create(cls, user):
        row = cls.query.filter_by(user_id=user.id).first()
        if not row:
            code = generate_referral_code(user)
            while cls.query.filter_by(code=code).first():
                code = generate_referral_code(user)
            row = cls(user_id=user.id, code=code)
            db.session.add(row)
            db.session.commit()
        return row


class Referral(db.Model):
    __tablename__ = "referrals"

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    referee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    referrer = db.relationship("User", foreign_keys=[referrer_id], backref="referrals_made")
    referee = db.relationship("User", foreign_keys=[referee_id], backref="referred_by")
    bonuses = db.relationship("ReferralBonus", backref="referral", lazy=True, cascade="all, delete-orphan")


class ReferralBonus(db.Model):
    __tablename__ = "referral_bonuses"

    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey("referrals.id"), nullable=False)
    bonus_type = db.Column(db.String(20), nullable=False)  # signup, first_deposit
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def generate_referral_code(user) -> str:
    """Short, human-shareable code derived from the user id + random suffix."""
    return f"MZB{user.id:04d}{secrets.token_hex(2).upper()}"
