from datetime import datetime
from app.extensions import db


class ContentPage(db.Model):
    """Admin-editable static pages — Terms, Privacy, About, FAQ, Responsible
    Gambling, etc. Rendered at /page/<slug>."""

    __tablename__ = "content_pages"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    is_published = db.Column(db.Boolean, default=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ContentPage {self.slug}>"
