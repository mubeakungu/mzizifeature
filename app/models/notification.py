from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    """In-app bell notifications for a single user."""

    __tablename__ = "site_notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.String(500), nullable=True)
    url = db.Column(db.String(255), nullable=True)  # where clicking it should go
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")


class MessageTemplate(db.Model):
    """Admin-editable templates for transactional email/SMS, so copy can be
    changed without a redeploy. `code` is the lookup key used in application
    code, e.g. 'kyc_approved', 'withdrawal_processed', 'referral_bonus'."""

    __tablename__ = "message_templates"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False, index=True)
    channel = db.Column(db.String(10), nullable=False, default="sms")  # sms, email
    subject = db.Column(db.String(150), nullable=True)  # email only
    body = db.Column(db.Text, nullable=False)
    # body supports {placeholders} like {full_name}, {amount}, {code}
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def render(self, **kwargs) -> str:
        try:
            return self.body.format(**kwargs)
        except (KeyError, IndexError):
            return self.body


def seed_default_templates():
    defaults = [
        dict(code="kyc_approved", channel="sms",
             body="Hi {full_name}, your ID has been verified. Withdrawals are now unlocked on Mzizibet."),
        dict(code="kyc_rejected", channel="sms",
             body="Hi {full_name}, we couldn't verify your ID: {reason}. Please resubmit clearer documents."),
        dict(code="withdrawal_processed", channel="sms",
             body="KES {amount} has been sent to your M-Pesa. Ref: {reference}."),
        dict(code="referral_bonus", channel="sms",
             body="You earned a KES {amount} referral bonus! Thanks for growing Mzizibet."),
        dict(code="ticket_reply", channel="sms",
             body="Support replied to your ticket #{ticket_id}. Log in to view the response."),
    ]
    from app.extensions import db as _db
    for tpl in defaults:
        if not MessageTemplate.query.filter_by(code=tpl["code"]).first():
            _db.session.add(MessageTemplate(**tpl))
    _db.session.commit()
