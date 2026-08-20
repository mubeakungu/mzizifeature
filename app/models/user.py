from datetime import datetime, date
from flask_login import UserMixin
from app.extensions import db, bcrypt


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    date_of_birth = db.Column(db.Date, nullable=False)  # MIN_AGE enforced at registration
    national_id = db.Column(db.String(20), unique=True, nullable=True)  # KYC
    kyc_verified = db.Column(db.Boolean, default=False)

    role = db.Column(db.String(20), default="player")  # player, admin, ceo, support
    is_active = db.Column(db.Boolean, default=True)
    is_self_excluded = db.Column(db.Boolean, default=False)
    self_exclusion_until = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    wallet = db.relationship("Wallet", backref="user", uselist=False, cascade="all, delete-orphan")
    bets = db.relationship("Bet", backref="user", lazy="dynamic")

    def set_password(self, raw_password):
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def can_play(self):
        """Central gate: age, KYC, self-exclusion all checked here."""
        if not self.is_active:
            return False, "Account is disabled."
        if self.is_self_excluded:
            if self.self_exclusion_until and self.self_exclusion_until < date.today():
                self.is_self_excluded = False
            else:
                return False, "Self-exclusion is active on this account."
        if self.age < 18:
            return False, "Must be 18 or older to play."
        return True, None

    def __repr__(self):
        return f"<User {self.phone_number} ({self.role})>"
