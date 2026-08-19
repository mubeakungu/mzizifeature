from datetime import datetime
from app.extensions import db


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    subject = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), default="general")  # general, payments, kyc, technical, account
    status = db.Column(db.String(20), default="open", index=True)  # open, pending, resolved, closed
    priority = db.Column(db.String(10), default="normal")  # low, normal, high

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], backref="tickets")
    messages = db.relationship(
        "TicketMessage", backref="ticket", lazy=True, cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )

    def __repr__(self):
        return f"<Ticket #{self.id} {self.subject!r} ({self.status})>"


class TicketMessage(db.Model):
    __tablename__ = "ticket_messages"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_staff = db.Column(db.Boolean, default=False)

    body = db.Column(db.Text, nullable=False)
    attachment_path = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", foreign_keys=[author_id])
