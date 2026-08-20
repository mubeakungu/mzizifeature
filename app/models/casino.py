from datetime import datetime
from app.extensions import db


class GameCategory(db.Model):
    __tablename__ = "game_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)  # Crash, Slots, Table, Live, Jackpots
    slug = db.Column(db.String(40), unique=True, nullable=False)
    display_order = db.Column(db.Integer, default=0)

    games = db.relationship("Game", backref="category", lazy="dynamic")


class Game(db.Model):
    """
    Catalog entry only. Round outcomes, RTP, and payout math are NOT computed
    here — they come from the certified game provider referenced by
    `provider_game_code`. This table just drives the lobby UI.
    """

    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("game_categories.id"), nullable=False)

    provider_name = db.Column(db.String(80), nullable=True)       # e.g. licensed aggregator
    provider_game_code = db.Column(db.String(120), nullable=True)  # ID the provider expects
    rtp_percent = db.Column(db.Numeric(5, 2), nullable=True)       # published by provider, not us

    thumbnail_url = db.Column(db.String(255), nullable=True)
    badge = db.Column(db.String(20), nullable=True)  # HOT, NEW, LIVE, POPULAR
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Game {self.name}>"


class CasinoRound(db.Model):
    """
    Local record of a round a user played, for ledger/audit purposes.
    The authoritative outcome (win/loss, multiplier, RNG seed/hash) is
    whatever the provider's callback reports — stored verbatim in
    `provider_result` for dispute resolution, never recalculated locally.
    """

    __tablename__ = "casino_rounds"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)

    stake = db.Column(db.Numeric(12, 2), nullable=False)
    payout = db.Column(db.Numeric(12, 2), default=0.00)
    provider_round_id = db.Column(db.String(120), nullable=True)
    provider_result = db.Column(db.JSON, nullable=True)

    status = db.Column(db.String(20), default="pending")  # pending, settled, void
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True)
