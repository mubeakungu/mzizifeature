from datetime import datetime
from app.extensions import db


class KycDocument(db.Model):
    """A single ID/selfie submission from a user, queued for admin review.

    A user can have multiple submissions over time (e.g. a rejected one
    followed by a corrected resubmission) — we keep the full history and
    only the most recent 'approved' one counts toward User.kyc_verified.
    """

    __tablename__ = "kyc_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    document_type = db.Column(db.String(30), nullable=False)  # national_id, passport, drivers_license
    document_number = db.Column(db.String(50), nullable=False)

    id_front_path = db.Column(db.String(255), nullable=False)
    id_back_path = db.Column(db.String(255), nullable=True)
    selfie_path = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), default="pending", index=True)  # pending, approved, rejected
    rejection_reason = db.Column(db.String(255), nullable=True)

    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], backref="kyc_submissions")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self):
        return f"<KycDocument user={self.user_id} status={self.status}>"
