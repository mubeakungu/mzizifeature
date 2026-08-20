from app import db
from datetime import datetime


class SportsEvent(db.Model):
    __tablename__ = "sports_events"
    
    # Your EXISTING fields (keep all of these):
    id = db.Column(db.Integer, primary_key=True)
    sport = db.Column(db.String(50), nullable=False, index=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    event_time = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(50), default='upcoming')  # upcoming, live, finished, postponed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- ADD THESE NEW FIELDS FOR LIVE SUPPORT ---
    home_score = db.Column(db.Integer)           # Live score: e.g., 2
    away_score = db.Column(db.Integer)           # Live score: e.g., 1
    is_live = db.Column(db.Boolean, default=False, index=True)  # Quick flag for live games
    external_id = db.Column(db.String(100), unique=True)  # The Odds API ID for syncing
    odds_provider = db.Column(db.String(50), default='the_odds_api')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    markets = db.relationship('SportsMarket', backref='event', lazy=True, cascade='all, delete-orphan')
    selections = db.relationship('SportsSelection', backref='event', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<SportsEvent {self.home_team} vs {self.away_team}>"
    
    # --- HELPER PROPERTIES ---
    @property
    def is_live_now(self):
        """Check if game is currently live"""
        return self.is_live and self.status == 'live'
    
    @property
    def display_score(self):
        """Return formatted score string"""
        if self.home_score is not None and self.away_score is not None:
            return f"{self.home_score}-{self.away_score}"
        return "—"
    
    @property
    def time_until_kickoff(self):
        """Return minutes until event starts"""
        delta = self.event_time - datetime.utcnow()
        return int(delta.total_seconds() / 60)
    
    @property
    def event_time_formatted(self):
        """Return formatted event time"""
        return self.event_time.strftime("%H:%M")


class SportsMarket(db.Model):
    __tablename__ = "sports_markets"
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('sports_events.id'), nullable=False)
    market_type = db.Column(db.String(100), nullable=False)  # e.g., "winner", "over_under", "handicap"
    market_name = db.Column(db.String(200), nullable=False)  # e.g., "Match Winner", "Over 2.5 Goals"
    external_market_id = db.Column(db.String(100))  # The Odds API market ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    selections = db.relationship('SportsSelection', backref='market', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<SportsMarket {self.market_name}>"


class SportsSelection(db.Model):
    __tablename__ = "sports_selections"
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('sports_events.id'), nullable=False)
    market_id = db.Column(db.Integer, db.ForeignKey('sports_markets.id'), nullable=False)
    selection_name = db.Column(db.String(200), nullable=False)  # e.g., "Home Win", "Over 2.5"
    odds = db.Column(db.Float, nullable=False)  # Decimal odds
    external_selection_id = db.Column(db.String(100))  # The Odds API selection ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    bet_slip_legs = db.relationship('BetSlipLeg', backref='selection', lazy=True)
    bets = db.relationship('Bet', backref='selection', lazy=True)
    
    def __repr__(self):
        return f"<SportsSelection {self.selection_name} @ {self.odds}>"


class BetSlip(db.Model):
    __tablename__ = "bet_slips"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(50), default='open')  # open, submitted, confirmed, cancelled
    total_stake = db.Column(db.Float)  # Total amount being wagered
    potential_return = db.Column(db.Float)  # Potential winnings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)  # When bet was placed
    
    # Relationships
    legs = db.relationship('BetSlipLeg', backref='slip', lazy=True, cascade='all, delete-orphan')
    bet = db.relationship('Bet', backref='slip', uselist=False, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<BetSlip {self.id} - {self.status}>"
    
    @property
    def leg_count(self):
        """Return number of legs in this slip"""
        return len(self.legs)
    
    @property
    def odds_multiplier(self):
        """Calculate combined odds for all legs"""
        if not self.legs:
            return 1.0
        result = 1.0
        for leg in self.legs:
            result *= leg.selection.odds
        return result


class BetSlipLeg(db.Model):
    __tablename__ = "bet_slip_legs"
    
    id = db.Column(db.Integer, primary_key=True)
    slip_id = db.Column(db.Integer, db.ForeignKey('bet_slips.id'), nullable=False)
    selection_id = db.Column(db.Integer, db.ForeignKey('sports_selections.id'), nullable=False)
    odds_at_placement = db.Column(db.Float, nullable=False)  # Odds when bet was added
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<BetSlipLeg {self.selection.selection_name}>"


class Bet(db.Model):
    __tablename__ = "bets"
    
    id = db.Column(db.Integer, primary_key=True)
    slip_id = db.Column(db.Integer, db.ForeignKey('bet_slips.id'), nullable=False)
    selection_id = db.Column(db.Integer, db.ForeignKey('sports_selections.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stake = db.Column(db.Float, nullable=False)  # Amount wagered
    odds = db.Column(db.Float, nullable=False)  # Odds at time of bet
    potential_return = db.Column(db.Float)  # stake × odds
    status = db.Column(db.String(50), default='pending')  # pending, won, lost, void, cancelled
    result = db.Column(db.String(50))  # won, lost, void (filled when event finishes)
    actual_return = db.Column(db.Float)  # Actual amount returned (only if won/lost)
    bet_type = db.Column(db.String(50), default='single')  # single, accumulator, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime)  # When result was determined
    
    def __repr__(self):
        return f"<Bet {self.id} - {self.status}>"
    
    @property
    def is_settled(self):
        """Check if bet has been resolved"""
        return self.status in ['won', 'lost', 'void']
