"""
game_models.py - Database Models for Mzizibet Casino Platform
Supports all 5 games: mzizicrash, Aviator, Hi-Lo Card, Plinko, Jet X
Single unified model architecture - no game-specific tables needed!
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from decimal import Decimal
from enum import Enum
import json

db = SQLAlchemy()


# ============================================================
# ENUMS
# ============================================================

class GameType(Enum):
    """All supported game types."""
    CRASH = "crash"
    AVIATOR = "aviator"
    HILO_CARD = "hilo_card"
    PLINKO = "plinko"
    JETX = "jetx"


class GameStatus(Enum):
    """Game round status."""
    PENDING = "pending"      # Waiting for bets
    LIVE = "live"            # Game in progress
    ENDED = "ended"          # Game finished
    CRASHED = "crashed"      # Game crashed (for crash-type games)
    COMPLETED = "completed"  # Round completed


class BetStatus(Enum):
    """Individual bet status."""
    PENDING = "pending"          # Waiting for game result
    ACTIVE = "active"            # Bet placed, game running
    CASHED_OUT = "cashed_out"    # Player cashed out (crash/aviator)
    WON = "won"                  # Bet won
    LOST = "lost"                # Bet lost
    CANCELLED = "cancelled"      # Bet cancelled


# ============================================================
# MAIN GAME MODEL - Unified for all games
# ============================================================

class Game(db.Model):
    """
    Unified game round model for ALL 5 games.
    
    game_type determines which game this is:
    - 'crash': mzizicrash
    - 'aviator': Aviator Mzizi
    - 'hilo_card': Hi-Lo Card
    - 'plinko': Plinko Mzizi
    - 'jetx': Jet X Mzizi
    """
    
    __tablename__ = 'games'
    
    # ========== Primary Fields ==========
    id = db.Column(db.Integer, primary_key=True)
    game_type = db.Column(db.String(50), nullable=False, index=True)  # crash, aviator, hilo_card, plinko, jetx
    round_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    
    # ========== Multiplier/Outcome ==========
    crash_point = db.Column(db.Numeric(10, 2), nullable=False)        # Final multiplier for crash-type games
    current_card = db.Column(db.Integer)                              # Hi-Lo: current card value (2-14)
    next_card = db.Column(db.Integer)                                 # Hi-Lo: next card value (2-14)
    landed_slot = db.Column(db.Integer)                               # Plinko: which slot (0-8)
    jetx_coins = db.Column(db.Integer, default=0)                     # Jet X: coins collected
    
    # ========== Fairness/Seeds ==========
    server_seed = db.Column(db.String(64), nullable=False)
    client_seed = db.Column(db.String(32), nullable=False)
    nonce = db.Column(db.Integer, default=0)
    
    # ========== Timing ==========
    game_start_time = db.Column(db.DateTime)
    game_end_time = db.Column(db.DateTime)
    crash_time = db.Column(db.DateTime)                               # When crash occurred (crash games)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== Relationships ==========
    bets = db.relationship('GameBet', backref='game', lazy='dynamic', cascade='all, delete-orphan')
    
    # ========== Constraints ==========
    __table_args__ = (
        db.UniqueConstraint('game_type', 'round_number', name='_game_type_round_uc'),
        db.Index('ix_game_type_status', 'game_type', 'status'),
        db.Index('ix_game_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f'<Game {self.game_type} #{self.round_number} - {self.status}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        data = {
            'id': self.id,
            'game_type': self.game_type,
            'round_number': self.round_number,
            'status': self.status,
            'crash_point': float(self.crash_point) if self.crash_point else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'game_start_time': self.game_start_time.isoformat() if self.game_start_time else None,
        }
        
        # Game-specific fields
        if self.game_type == 'hilo_card':
            data['current_card'] = self.current_card
            data['next_card'] = self.next_card
        elif self.game_type == 'plinko':
            data['landed_slot'] = self.landed_slot
        elif self.game_type == 'jetx':
            data['jetx_coins'] = self.jetx_coins
        
        return data
    
    def get_total_players(self):
        """Get number of players in this round."""
        return self.bets.filter(GameBet.status.in_([
            BetStatus.ACTIVE.value,
            BetStatus.WON.value,
            BetStatus.LOST.value,
            BetStatus.CASHED_OUT.value
        ])).count()
    
    def get_total_wagered(self):
        """Get total amount wagered in this round."""
        from sqlalchemy import func
        total = db.session.query(func.sum(GameBet.bet_amount)).filter(
            GameBet.game_id == self.id
        ).scalar()
        return Decimal(total or 0)
    
    def is_active(self):
        """Check if game is currently active."""
        return self.status in ['pending', 'live']


# ============================================================
# GAME BET MODEL - Unified for all games
# ============================================================

class GameBet(db.Model):
    """
    Individual bet in a game.
    Works for all 5 game types.
    """
    
    __tablename__ = 'game_bets'
    
    # ========== Primary Fields ==========
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, index=True)
    
    # ========== Bet Amount ==========
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # ========== Game-Specific Bet Data ==========
    auto_cashout_multiplier = db.Column(db.Numeric(10, 2))  # crash/aviator: auto cashout point
    prediction = db.Column(db.String(20))                   # hilo_card: 'higher' or 'lower'
    coins_collected = db.Column(db.Integer, default=0)      # jetx: final coins before crash
    
    # ========== Outcome ==========
    actual_cashout_multiplier = db.Column(db.Numeric(10, 2))  # crash/aviator: actual cashout point
    actual_multiplier = db.Column(db.Numeric(10, 2))          # Final multiplier for this bet
    payout_amount = db.Column(db.Numeric(10, 2), default=0)   # Total winnings (includes bet)
    profit_loss = db.Column(db.Numeric(10, 2), default=0)     # payout - bet (can be negative)
    
    # ========== Status ==========
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    
    # ========== Timing ==========
    placed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    cashed_out_at = db.Column(db.DateTime)
    settled_at = db.Column(db.DateTime)
    
    # ========== Relationships ==========
    user = db.relationship('User', backref='game_bets')
    
    # ========== Constraints ==========
    __table_args__ = (
        db.Index('ix_gamebet_user_created', 'user_id', 'placed_at'),
        db.Index('ix_gamebet_game_status', 'game_id', 'status'),
    )
    
    def __repr__(self):
        return f'<GameBet User#{self.user_id} Game#{self.game_id} {self.status}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'game_id': self.game_id,
            'bet_amount': float(self.bet_amount),
            'actual_multiplier': float(self.actual_multiplier) if self.actual_multiplier else None,
            'actual_cashout_multiplier': float(self.actual_cashout_multiplier) if self.actual_cashout_multiplier else None,
            'payout_amount': float(self.payout_amount),
            'profit_loss': float(self.profit_loss),
            'status': self.status,
            'placed_at': self.placed_at.isoformat() if self.placed_at else None,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
        }
    
    def calculate_profit_loss(self):
        """Calculate profit or loss."""
        if self.payout_amount:
            self.profit_loss = self.payout_amount - self.bet_amount
        else:
            self.profit_loss = Decimal('-') + self.bet_amount
    
    def is_win(self):
        """Check if bet won."""
        return self.status == BetStatus.WON.value
    
    def is_loss(self):
        """Check if bet lost."""
        return self.status == BetStatus.LOST.value
    
    def is_settled(self):
        """Check if bet is settled."""
        return self.status in [
            BetStatus.WON.value,
            BetStatus.LOST.value,
            BetStatus.CASHED_OUT.value
        ]


# ============================================================
# GAME STATISTICS MODEL - Per User Per Game
# ============================================================

class GameStats(db.Model):
    """
    Aggregate statistics for a user in a specific game type.
    One row per user per game type.
    """
    
    __tablename__ = 'game_stats'
    
    # ========== Primary Key ==========
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    game_type = db.Column(db.String(50), nullable=False)  # crash, aviator, hilo_card, plinko, jetx
    
    # ========== Totals ==========
    total_bets_placed = db.Column(db.Integer, default=0)
    total_amount_wagered = db.Column(db.Numeric(12, 2), default=0)
    total_amount_won = db.Column(db.Numeric(12, 2), default=0)
    total_amount_lost = db.Column(db.Numeric(12, 2), default=0)
    
    # ========== Win/Loss Counts ==========
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)
    cashed_out_count = db.Column(db.Integer, default=0)
    
    # ========== Records ==========
    best_multiplier = db.Column(db.Numeric(10, 2), default=0)
    biggest_win = db.Column(db.Numeric(12, 2), default=0)
    biggest_loss = db.Column(db.Numeric(12, 2), default=0)
    
    # ========== Streaks ==========
    current_win_streak = db.Column(db.Integer, default=0)
    best_win_streak = db.Column(db.Integer, default=0)
    current_loss_streak = db.Column(db.Integer, default=0)
    
    # ========== Timing ==========
    first_played = db.Column(db.DateTime)
    last_played = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== Relationships ==========
    user = db.relationship('User', backref='game_stats')
    
    # ========== Constraints ==========
    __table_args__ = (
        db.UniqueConstraint('user_id', 'game_type', name='_user_gametype_uc'),
    )
    
    def __repr__(self):
        return f'<GameStats User#{self.user_id} {self.game_type}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        win_rate = 0
        if self.total_bets_placed > 0:
            win_rate = (self.win_count / self.total_bets_placed) * 100
        
        roi = 0
        if self.total_amount_wagered > 0:
            roi = ((self.total_amount_won - self.total_amount_wagered) / self.total_amount_wagered) * 100
        
        return {
            'user_id': self.user_id,
            'game_type': self.game_type,
            'total_bets_placed': self.total_bets_placed,
            'total_amount_wagered': float(self.total_amount_wagered),
            'total_amount_won': float(self.total_amount_won),
            'total_amount_lost': float(self.total_amount_lost),
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate_percent': round(win_rate, 2),
            'roi_percent': round(roi, 2),
            'best_multiplier': float(self.best_multiplier),
            'biggest_win': float(self.biggest_win),
            'current_win_streak': self.current_win_streak,
            'best_win_streak': self.best_win_streak,
            'last_played': self.last_played.isoformat() if self.last_played else None,
        }
    
    def get_win_rate(self):
        """Get win rate as percentage."""
        if self.total_bets_placed == 0:
            return 0
        return (self.win_count / self.total_bets_placed) * 100
    
    def get_roi(self):
        """Get return on investment as percentage."""
        if self.total_amount_wagered == 0:
            return 0
        return ((self.total_amount_won - self.total_amount_wagered) / self.total_amount_wagered) * 100
    
    def update_from_bet(self, bet):
        """Update stats from a settled bet."""
        self.total_bets_placed += 1
        self.total_amount_wagered += bet.bet_amount
        self.last_played = datetime.utcnow()
        
        if not self.first_played:
            self.first_played = datetime.utcnow()
        
        # Win/Loss logic
        if bet.is_win():
            self.win_count += 1
            self.total_amount_won += bet.payout_amount
            self.current_loss_streak = 0
            self.current_win_streak += 1
            
            if self.current_win_streak > self.best_win_streak:
                self.best_win_streak = self.current_win_streak
            
            if bet.profit_loss > self.biggest_win:
                self.biggest_win = bet.profit_loss
        
        elif bet.is_loss():
            self.loss_count += 1
            self.total_amount_lost += abs(bet.profit_loss)
            self.current_win_streak = 0
            self.current_loss_streak += 1
        
        elif bet.status == BetStatus.CASHED_OUT.value:
            self.cashed_out_count += 1
            self.total_amount_won += bet.payout_amount
        
        # Update best multiplier if applicable
        if bet.actual_multiplier and bet.actual_multiplier > self.best_multiplier:
            self.best_multiplier = bet.actual_multiplier


# ============================================================
# GLOBAL STATISTICS MODEL - Per User Across ALL Games
# ============================================================

class UserGameStats(db.Model):
    """
    Aggregate statistics for a user across ALL games.
    Useful for leaderboards, dashboards, etc.
    """
    
    __tablename__ = 'user_game_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # ========== Totals Across All Games ==========
    total_bets_placed = db.Column(db.Integer, default=0)
    total_amount_wagered = db.Column(db.Numeric(12, 2), default=0)
    total_amount_won = db.Column(db.Numeric(12, 2), default=0)
    total_amount_lost = db.Column(db.Numeric(12, 2), default=0)
    
    # ========== Overall Records ==========
    total_win_count = db.Column(db.Integer, default=0)
    total_loss_count = db.Column(db.Integer, default=0)
    best_multiplier_ever = db.Column(db.Numeric(10, 2), default=0)
    biggest_win_ever = db.Column(db.Numeric(12, 2), default=0)
    biggest_loss_ever = db.Column(db.Numeric(12, 2), default=0)
    
    # ========== Favorite Game ==========
    favorite_game_type = db.Column(db.String(50))  # Most played game
    favorite_game_bets = db.Column(db.Integer, default=0)
    
    # ========== Timing ==========
    first_bet_at = db.Column(db.DateTime)
    last_bet_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== Relationships ==========
    user = db.relationship('User', backref='global_game_stats')
    
    def __repr__(self):
        return f'<UserGameStats User#{self.user_id}>'
    
    def to_dict(self):
        """Convert to dictionary for leaderboards/dashboards."""
        overall_roi = 0
        if self.total_amount_wagered > 0:
            overall_roi = ((self.total_amount_won - self.total_amount_wagered) / self.total_amount_wagered) * 100
        
        overall_win_rate = 0
        if self.total_bets_placed > 0:
            overall_win_rate = (self.total_win_count / self.total_bets_placed) * 100
        
        return {
            'user_id': self.user_id,
            'total_bets_placed': self.total_bets_placed,
            'total_amount_wagered': float(self.total_amount_wagered),
            'total_amount_won': float(self.total_amount_won),
            'total_win_count': self.total_win_count,
            'total_loss_count': self.total_loss_count,
            'win_rate_percent': round(overall_win_rate, 2),
            'roi_percent': round(overall_roi, 2),
            'best_multiplier_ever': float(self.best_multiplier_ever),
            'biggest_win_ever': float(self.biggest_win_ever),
            'favorite_game_type': self.favorite_game_type,
        }


# ============================================================
# ROUND LOG MODEL - For Audit/Compliance
# ============================================================

class RoundLog(db.Model):
    """
    Comprehensive log of every round for audit/compliance.
    Used for dispute resolution and fairness verification.
    """
    
    __tablename__ = 'round_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    bet_id = db.Column(db.Integer, db.ForeignKey('game_bets.id'), index=True)
    
    # ========== Game Info ==========
    game_type = db.Column(db.String(50), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    
    # ========== Bet Info ==========
    bet_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payout_amount = db.Column(db.Numeric(10, 2), default=0)
    profit_loss = db.Column(db.Numeric(10, 2), default=0)
    
    # ========== Fairness Proof ==========
    server_seed = db.Column(db.String(64), nullable=False)
    client_seed = db.Column(db.String(32), nullable=False)
    nonce = db.Column(db.Integer, default=0)
    seed_hash = db.Column(db.String(64))
    
    # ========== Outcome ==========
    outcome = db.Column(db.Text)  # JSON string with game-specific outcome
    
    # ========== Timing ==========
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # ========== Constraints ==========
    __table_args__ = (
        db.Index('ix_roundlog_user_created', 'user_id', 'created_at'),
        db.Index('ix_roundlog_game', 'game_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<RoundLog Game#{self.game_id} User#{self.user_id}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        outcome_data = {}
        if self.outcome:
            try:
                outcome_data = json.loads(self.outcome)
            except:
                outcome_data = {}
        
        return {
            'id': self.id,
            'game_type': self.game_type,
            'round_number': self.round_number,
            'bet_amount': float(self.bet_amount),
            'payout_amount': float(self.payout_amount),
            'profit_loss': float(self.profit_loss),
            'outcome': outcome_data,
            'seed_hash': self.seed_hash,
            'created_at': self.created_at.isoformat(),
        }


# ============================================================
# ADD TO USER MODEL
# ============================================================

# If you have an existing User model, add these relationships:
"""
In your User model (app/models/user.py), add:

    game_bets = db.relationship('GameBet', backref='user')
    game_stats = db.relationship('GameStats', backref='user')
    global_game_stats = db.relationship('UserGameStats', backref='user')
    round_logs = db.relationship('RoundLog', backref='user')
"""
