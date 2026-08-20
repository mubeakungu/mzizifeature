"""
Models for the self-hosted Blackjack engine (app/routes/cards_blueprint.py).
Lives under app/models/ to match casino.py, wallet.py, sports.py, and
crash_models.py's eventual home — NOT a loose root-level file.

IMPORTANT: db is imported from app.extensions, same instance the rest of
the app uses, so these tables are created by db.create_all() in
app/__init__.py and participate in the same transactions/session as
Wallet/Transaction.
"""

from datetime import datetime
from app.extensions import db


class BlackjackRound(db.Model):
    __tablename__ = "blackjack_rounds"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    bet_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    # active -> player is still hitting/standing
    # settled -> round resolved (win/lose/push/blackjack), wallet updated

    server_seed = db.Column(db.String(64), nullable=False)
    server_seed_hash = db.Column(db.String(64), nullable=False)  # sha256(server_seed), shown to player at bet time
    client_seed = db.Column(db.String(64), nullable=True)

    player_cards = db.Column(db.JSON, nullable=False, default=list)  # [{"rank": "K", "suit": "H"}, ...]
    dealer_cards = db.Column(db.JSON, nullable=False, default=list)
    deck_position = db.Column(db.Integer, nullable=False, default=0)  # next undealt card index in the shuffled deck

    outcome = db.Column(db.String(20), nullable=True)  # "win" | "lose" | "push" | "blackjack"
    payout = db.Column(db.Numeric(12, 2), nullable=True)
    doubled = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "round_id": self.id,
            "bet_amount": float(self.bet_amount),
            "status": self.status,
            "player_cards": self.player_cards,
            "dealer_cards": self.dealer_cards,
            "outcome": self.outcome,
            "payout": float(self.payout) if self.payout is not None else None,
            "doubled": self.doubled,
            "server_seed_hash": self.server_seed_hash,
            "server_seed": self.server_seed if self.status == "settled" else None,  # only reveal after settlement
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
        }


class BlackjackStats(db.Model):
    __tablename__ = "blackjack_stats"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)

    hands_played = db.Column(db.Integer, nullable=False, default=0)
    hands_won = db.Column(db.Integer, nullable=False, default=0)
    hands_lost = db.Column(db.Integer, nullable=False, default=0)
    hands_pushed = db.Column(db.Integer, nullable=False, default=0)
    blackjacks_hit = db.Column(db.Integer, nullable=False, default=0)
    total_wagered = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_winnings = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    def to_dict(self):
        return {
            "hands_played": self.hands_played,
            "hands_won": self.hands_won,
            "hands_lost": self.hands_lost,
            "hands_pushed": self.hands_pushed,
            "blackjacks_hit": self.blackjacks_hit,
            "total_wagered": float(self.total_wagered),
            "total_winnings": float(self.total_winnings),
        }
