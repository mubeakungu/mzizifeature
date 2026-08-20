"""
Crash Game Models
Add this to app/models/crash.py
"""
from app.extensions import db
from datetime import datetime
from decimal import Decimal

class CrashGame(db.Model):
    """Represents a single crash game round"""
    __tablename__ = 'crash_games'
    
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.BigInteger, unique=True, nullable=False)
    crash_point = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, live, crashed, completed
    betting_window_start = db.Column(db.DateTime, default=datetime.utcnow)
    betting_window_end = db.Column(db.DateTime)
    game_start_time = db.Column(db.DateTime)
    crash_time = db.Column(db.DateTime)
    seed = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bets = db.relationship('CrashBet', backref='game', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CrashGame {self.round_number} - {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'round_number': self.round_number,
            'crash_point': float(self.crash_point),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CrashBet(db.Model):
    """Represents a bet placed on a crash game"""
    __tablename__ = 'crash_bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('crash_games.id'), nullable=False)
    bet_amount = db.Column(db.Numeric(12, 2), nullable=False)
    cashout_multiplier = db.Column(db.Numeric(10, 2))  # Target if auto-cashout
    cashout_at = db.Column(db.Numeric(10, 2))  # Actual multiplier when cashed out
    payout_amount = db.Column(db.Numeric(12, 2))
    status = db.Column(db.String(20), default='active')  # active, cashed_out, lost, won
    is_auto_cashout = db.Column(db.Boolean, default=False)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)
    cashed_out_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='crash_bets')
    
    def __repr__(self):
        return f'<CrashBet {self.id} - {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'game_id': self.game_id,
            'bet_amount': float(self.bet_amount),
            'cashout_at': float(self.cashout_at) if self.cashout_at else None,
            'payout_amount': float(self.payout_amount) if self.payout_amount else None,
            'status': self.status
        }


class CrashStats(db.Model):
    """User crash game statistics"""
    __tablename__ = 'crash_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    total_bets = db.Column(db.Integer, default=0)
    total_wagered = db.Column(db.Numeric(15, 2), default=0)
    total_winnings = db.Column(db.Numeric(15, 2), default=0)
    total_losses = db.Column(db.Numeric(15, 2), default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)
    biggest_win = db.Column(db.Numeric(15, 2), default=0)
    best_multiplier = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='crash_stats')
    
    def __repr__(self):
        return f'<CrashStats {self.user_id}>'
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'total_bets': self.total_bets,
            'total_wagered': float(self.total_wagered),
            'total_winnings': float(self.total_winnings),
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'best_multiplier': float(self.best_multiplier)
        }
