from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.support import Ticket, TicketMessage

support_bp = Blueprint("support", __name__, url_prefix="/support")


@support_bp.route("/")
@login_required
def list_tickets():
    tickets = (
        Ticket.query.filter_by(user_id=current_user.id)
        .order_by(Ticket.updated_at.desc())
        .all()
    )
    return render_template("support/list.html", tickets=tickets)


@support_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        category = request.form.get("category", "general")
        body = request.form.get("body", "").strip()

        if not subject or not body:
            flash("Subject and message are required.", "error")
            return render_template("support/new.html")

        ticket = Ticket(user_id=current_user.id, subject=subject, category=category)
        db.session.add(ticket)
        db.session.flush()
        db.session.add(TicketMessage(ticket_id=ticket.id, author_id=current_user.id, body=body))
        db.session.commit()

        flash("Ticket submitted. Our support team will respond soon.", "success")
        return redirect(url_for("support.view_ticket", ticket_id=ticket.id))

    return render_template("support/new.html")


@support_bp.route("/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(TicketMessage(ticket_id=ticket.id, author_id=current_user.id, body=body))
            if ticket.status in ("resolved", "closed"):
                ticket.status = "open"
            db.session.commit()
        return redirect(url_for("support.view_ticket", ticket_id=ticket.id))

    return render_template("support/detail.html", ticket=ticket)
