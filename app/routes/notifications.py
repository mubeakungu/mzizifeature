from flask import Blueprint, jsonify, redirect, url_for, render_template
from flask_login import login_required, current_user

from app.extensions import db
from app.models.notification import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def list_all():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("notifications/list.html", items=items)


@notifications_bp.route("/recent")
@login_required
def recent():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )
    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "url": n.url,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in items
    ])


@notifications_bp.route("/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    n = Notification.query.get_or_404(notification_id)
    if n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    return redirect(n.url or url_for("casino.lobby"))


@notifications_bp.route("/read-all")
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})


def notify(user_id, title, body=None, url=None):
    """Helper other modules can import to push an in-app notification,
    e.g. from app.routes.notifications import notify"""
    db.session.add(Notification(user_id=user_id, title=title, body=body, url=url))
    db.session.commit()
