"""
Models for the JetX crash engine (app/routes/jetx_blueprint.py). Structurally
identical to crash_models.py's CrashGame/CrashBet/CrashStats, but kept as
separate tables/round numbering so JetX and mzizicrash rounds never collide
or get mixed up in each other's history/stats.
"""

from datetime import datetime
from app.extensions import db


class JetXGame(db.Model):
    __tablename__ = "jetx_games"

    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending -> live -> crashed -> completed
    seed = db.Column(db.String(64), nullable=False)
    crash_point = db.Column(db.Numeric(10, 2), nullable=True)
    game_start_time = db.Column(db.DateTime, nullable=True)
    crash_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class JetXBet(db.Model):
    __tablename__ = "jetx_bets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("jetx_games.id"), nullable=False, index=True)
    bet_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # active | cashed_out | lost
    cashout_at = db.Column(db.Numeric(10, 2), nullable=True)
    payout_amount = db.Column(db.Numeric(12, 2), nullable=True)
    cashed_out_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "bet_id": self.id,
            "game_id": self.game_id,
            "bet_amount": float(self.bet_amount),
            "status": self.status,
            "cashout_at": float(self.cashout_at) if self.cashout_at is not None else None,
            "payout_amount": float(self.payout_amount) if self.payout_amount is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class JetXStats(db.Model):
    __tablename__ = "jetx_stats"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    win_count = db.Column(db.Integer, nullable=False, default=0)
    loss_count = db.Column(db.Integer, nullable=False, default=0)
    total_winnings = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_losses = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    best_multiplier = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    def to_dict(self):
        return {
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "total_winnings": float(self.total_winnings),
            "total_losses": float(self.total_losses),
            "best_multiplier": float(self.best_multiplier),
        }
