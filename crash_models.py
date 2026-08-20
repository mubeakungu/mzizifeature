"""
SQLAlchemy models for mzizicrash game
Integrates with existing mzizibet user & wallet models
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from decimal import Decimal
import enum

db = SQLAlchemy()


class CrashGameStatus(enum.Enum):
    PENDING = "pending"
    LIVE = "live"
    CRASHED = "crashed"
    COMPLETED = "completed"


class CrashBetStatus(enum.Enum):
    ACTIVE = "active"
    CASHED_OUT = "cashed_out"
    LOST = "lost"
    WON = "won"


class CrashGame(db.Model):
    __tablename__ = "crash_games"

    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    crash_point = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default="pending", index=True)
    betting_window_start = db.Column(db.DateTime, default=datetime.utcnow)
    betting_window_end = db.Column(db.DateTime)
    game_start_time = db.Column(db.DateTime)
    crash_time = db.Column(db.DateTime)
    seed = db.Column(db.String(255))  # For provable fairness
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bets = db.relationship("CrashBet", backref="game", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "round_number": self.round_number,
            "crash_point": float(self.crash_point),
            "status": self.status,
            "game_start_time": self.game_start_time.isoformat() if self.game_start_time else None,
            "crash_time": self.crash_time.isoformat() if self.crash_time else None,
        }

    def __repr__(self):
        return f"<CrashGame {self.round_number} @ {self.crash_point}x>"


class CrashBet(db.Model):
    __tablename__ = "crash_bets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("crash_games.id", ondelete="CASCADE"), nullable=False, index=True)
    bet_amount = db.Column(db.Numeric(12, 2), nullable=False)
    cashout_multiplier = db.Column(db.Numeric(10, 2))  # Target multiplier set by player
    cashout_at = db.Column(db.Numeric(10, 2))  # Actual multiplier when cashed out
    payout_amount = db.Column(db.Numeric(12, 2))  # bet_amount * cashout_at
    status = db.Column(db.String(20), default="active", index=True)
    is_auto_cashout = db.Column(db.Boolean, default=False)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)
    cashed_out_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to user (assuming your User model exists)
    # user = db.relationship("User", backref="crash_bets")

    def to_dict(self, include_user=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "game_id": self.game_id,
            "bet_amount": float(self.bet_amount),
            "cashout_multiplier": float(self.cashout_multiplier) if self.cashout_multiplier else None,
            "cashout_at": float(self.cashout_at) if self.cashout_at else None,
            "payout_amount": float(self.payout_amount) if self.payout_amount else None,
            "status": self.status,
            "is_auto_cashout": self.is_auto_cashout,
            "placed_at": self.placed_at.isoformat() if self.placed_at else None,
            "cashed_out_at": self.cashed_out_at.isoformat() if self.cashed_out_at else None,
        }
        return data

    def calculate_payout(self, multiplier):
        """Calculate payout if cashing out at given multiplier"""
        return float(self.bet_amount) * float(multiplier)

    def __repr__(self):
        return f"<CrashBet user={self.user_id} game={self.game_id} amount={self.bet_amount}>"


class CrashStats(db.Model):
    __tablename__ = "crash_stats"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_bets = db.Column(db.Integer, default=0)
    total_wagered = db.Column(db.Numeric(15, 2), default=0)
    total_winnings = db.Column(db.Numeric(15, 2), default=0)
    total_losses = db.Column(db.Numeric(15, 2), default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)
    biggest_win = db.Column(db.Numeric(15, 2), default=0)
    current_streak = db.Column(db.Integer, default=0)  # Positive for wins, negative for losses
    best_multiplier = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "total_bets": self.total_bets,
            "total_wagered": float(self.total_wagered),
            "total_winnings": float(self.total_winnings),
            "total_losses": float(self.total_losses),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "biggest_win": float(self.biggest_win),
            "current_streak": self.current_streak,
            "best_multiplier": float(self.best_multiplier),
        }

    def __repr__(self):
        return f"<CrashStats user={self.user_id} bets={self.total_bets}>"
