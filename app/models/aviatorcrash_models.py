"""Models for AviatorCrash — the Unity-driven crash game that now backs both
/aviator-mzizi/ and /jetx/. Replaces the old inline AviatorRound/AviatorBet/
AviatorStats models and app/models/jetx_models.py.
"""

from datetime import datetime

from app.extensions import db


class AviatorCrashRound(db.Model):
    __tablename__ = "aviatorcrash_rounds"

    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, nullable=False, unique=True)
    crash_point = db.Column(db.Numeric(10, 2), nullable=False)
    seed = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, betting, live, crashed
    started_at = db.Column(db.DateTime)
    crashed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AviatorCrashBet(db.Model):
    __tablename__ = "aviatorcrash_bets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey("aviatorcrash_rounds.id"), nullable=False)

    slot = db.Column(db.String(1), nullable=False)  # "f" (first bet) or "s" (second bet)
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    target = db.Column(db.Numeric(10, 2))            # auto-cashout multiplier, if set
    auto = db.Column(db.Boolean, default=False)       # client re-arms this bet automatically each round

    cashout_at = db.Column(db.Numeric(10, 2))
    payout_amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default="active")  # active, cashed_out, lost

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cashed_out_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="aviatorcrash_bets")
    round = db.relationship("AviatorCrashRound", backref="bets")


class AviatorCrashStats(db.Model):
    __tablename__ = "aviatorcrash_stats"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    total_wagered = db.Column(db.Numeric(12, 2), default=0)
    total_won = db.Column(db.Numeric(12, 2), default=0)
    total_lost = db.Column(db.Numeric(12, 2), default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)
    best_multiplier = db.Column(db.Numeric(10, 2), default=0)

    user = db.relationship("User", backref="aviatorcrash_stats")
