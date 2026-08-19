"""Additional admin routes, attached to the existing admin_bp blueprint.

IMPORTANT: this module must be imported in app/__init__.py *before*
app.register_blueprint(admin_bp, url_prefix="/admin") runs, since Flask
only picks up routes added to a blueprint before it's registered.
"""
from functools import wraps
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.routes.admin import admin_bp, roles_required
from app.models.user import User
from app.models.kyc import KycDocument
from app.models.support import Ticket, TicketMessage
from app.models.rbac import Role, ALL_PERMISSIONS
from app.models.referral import Referral, ReferralSettings
from app.models.content import ContentPage
from app.models.notification import MessageTemplate
from app.models.gateway import PaymentGateway
from app.models.wallet import Wallet, Transaction
from app.routes.notifications import notify
from app.services.messaging import send_templated


def permission_required(perm):
    """Finer-grained than roles_required — checks the Role row's
    permission list. Falls back to allowing 'ceo'/'admin' string roles even
    if no Role row exists yet, so this never locks anyone out before the
    roles table is seeded."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_user.role.lower() == "ceo":
                return f(*args, **kwargs)
            role = Role.query.filter_by(name=current_user.role.lower()).first()
            if role and role.has(perm):
                return f(*args, **kwargs)
            if not role and current_user.role.lower() in ("admin", "ceo"):
                return f(*args, **kwargs)
            abort(403)
        return wrapped
    return decorator


# ---------------------------------------------------------------- KYC ----
@admin_bp.route("/kyc")
@login_required
@permission_required("kyc.review")
def kyc_queue():
    status = request.args.get("status", "pending")
    query = KycDocument.query
    if status != "all":
        query = query.filter_by(status=status)
    docs = query.order_by(KycDocument.created_at.desc()).all()
    return render_template("admin/kyc_queue.html", docs=docs, status=status)


@admin_bp.route("/kyc/<int:doc_id>", methods=["GET", "POST"])
@login_required
@permission_required("kyc.review")
def kyc_review(doc_id):
    doc = KycDocument.query.get_or_404(doc_id)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "approve":
            doc.status = "approved"
            doc.user.kyc_verified = True
        elif action == "reject":
            doc.status = "rejected"
            doc.rejection_reason = request.form.get("reason", "").strip() or "Documents unclear"
        doc.reviewed_by = current_user.id
        doc.reviewed_at = datetime.utcnow()
        db.session.commit()

        if doc.status == "approved":
            notify(doc.user_id, "ID verified", "Your identity has been verified. Withdrawals are unlocked.",
                   url="/kyc/")
            send_templated("kyc_approved", doc.user.phone_number, full_name=doc.user.full_name)
        elif doc.status == "rejected":
            notify(doc.user_id, "ID verification needs another try", doc.rejection_reason, url="/kyc/")
            send_templated("kyc_rejected", doc.user.phone_number,
                            full_name=doc.user.full_name, reason=doc.rejection_reason)

        flash(f"KYC submission #{doc.id} marked {doc.status}.", "success")
        return redirect(url_for("admin.kyc_queue"))

    return render_template("admin/kyc_review.html", doc=doc)


# ------------------------------------------------------------ Tickets ----
@admin_bp.route("/support")
@login_required
@permission_required("support.manage")
def support_list():
    status = request.args.get("status", "open")
    query = Ticket.query
    if status != "all":
        query = query.filter_by(status=status)
    tickets = query.order_by(Ticket.updated_at.desc()).all()
    return render_template("admin/support_list.html", tickets=tickets, status=status)


@admin_bp.route("/support/<int:ticket_id>", methods=["GET", "POST"])
@login_required
@permission_required("support.manage")
def support_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if request.method == "POST":
        if "reply" in request.form:
            body = request.form.get("body", "").strip()
            if body:
                db.session.add(TicketMessage(
                    ticket_id=ticket.id, author_id=current_user.id, body=body, is_staff=True,
                ))
                ticket.status = "pending"
                db.session.commit()
                notify(ticket.user_id, f"Support replied to ticket #{ticket.id}", body[:120],
                       url=f"/support/{ticket.id}")
                send_templated("ticket_reply", ticket.user.phone_number, ticket_id=ticket.id)
        elif "set_status" in request.form:
            ticket.status = request.form.get("set_status")
            db.session.commit()
        return redirect(url_for("admin.support_detail", ticket_id=ticket.id))

    return render_template("admin/support_detail.html", ticket=ticket)


# --------------------------------------------------------------- RBAC ----
@admin_bp.route("/roles", methods=["GET", "POST"])
@login_required
@permission_required("roles.manage")
def roles():
    if request.method == "POST":
        role_id = request.form.get("role_id")
        role = Role.query.get_or_404(role_id)
        selected = request.form.getlist("permissions")
        role.permissions = [p for p in selected if p in ALL_PERMISSIONS]
        db.session.commit()
        flash(f"Updated permissions for '{role.name}'.", "success")
        return redirect(url_for("admin.roles"))

    all_roles = Role.query.order_by(Role.name).all()
    return render_template("admin/roles.html", roles=all_roles, all_permissions=ALL_PERMISSIONS)


# ---------------------------------------------------------- Referrals ----
@admin_bp.route("/referrals", methods=["GET", "POST"])
@login_required
@permission_required("referrals.manage")
def referrals():
    settings = ReferralSettings.get()

    if request.method == "POST":
        settings.signup_bonus = request.form.get("signup_bonus", 0) or 0
        settings.deposit_bonus_pct = request.form.get("deposit_bonus_pct", 0) or 0
        settings.is_active = "is_active" in request.form
        db.session.commit()
        flash("Referral settings updated.", "success")
        return redirect(url_for("admin.referrals"))

    all_referrals = Referral.query.order_by(Referral.created_at.desc()).limit(100).all()
    return render_template("admin/referrals.html", settings=settings, referrals=all_referrals)


# -------------------------------------------------------------- CMS ------
@admin_bp.route("/content")
@login_required
@permission_required("content.manage")
def content_list():
    pages = ContentPage.query.order_by(ContentPage.slug).all()
    return render_template("admin/content_list.html", pages=pages)


@admin_bp.route("/content/new", methods=["GET", "POST"])
@admin_bp.route("/content/<int:page_id>", methods=["GET", "POST"])
@login_required
@permission_required("content.manage")
def content_edit(page_id=None):
    page_obj = ContentPage.query.get(page_id) if page_id else None

    if request.method == "POST":
        slug = request.form.get("slug", "").strip().lower()
        title = request.form.get("title", "").strip()
        body_html = request.form.get("body_html", "")
        is_published = "is_published" in request.form

        if not slug or not title:
            flash("Slug and title are required.", "error")
            return render_template("admin/content_edit.html", page=page_obj)

        if page_obj is None:
            page_obj = ContentPage(slug=slug)
            db.session.add(page_obj)

        page_obj.title = title
        page_obj.body_html = body_html
        page_obj.is_published = is_published
        page_obj.updated_by = current_user.id
        db.session.commit()
        flash("Page saved.", "success")
        return redirect(url_for("admin.content_list"))

    return render_template("admin/content_edit.html", page=page_obj)


# ------------------------------------------------------ Msg Templates ----
@admin_bp.route("/templates")
@login_required
@permission_required("templates.manage")
def templates_list():
    tpls = MessageTemplate.query.order_by(MessageTemplate.code).all()
    return render_template("admin/templates_list.html", templates=tpls)


@admin_bp.route("/templates/<int:template_id>", methods=["GET", "POST"])
@login_required
@permission_required("templates.manage")
def template_edit(template_id):
    tpl = MessageTemplate.query.get_or_404(template_id)

    if request.method == "POST":
        tpl.subject = request.form.get("subject", "")
        tpl.body = request.form.get("body", tpl.body)
        db.session.commit()
        flash("Template updated.", "success")
        return redirect(url_for("admin.templates_list"))

    return render_template("admin/template_edit.html", template=tpl)


# ---------------------------------------------------------- Gateways -----
@admin_bp.route("/gateways", methods=["GET", "POST"])
@login_required
@permission_required("gateways.manage")
def gateways():
    if request.method == "POST":
        gw = PaymentGateway.query.get_or_404(request.form.get("gateway_id"))
        gw.is_active = "is_active" in request.form
        gw.min_amount = request.form.get("min_amount", gw.min_amount)
        gw.max_amount = request.form.get("max_amount", gw.max_amount)
        gw.fee_flat = request.form.get("fee_flat", gw.fee_flat)
        gw.fee_pct = request.form.get("fee_pct", gw.fee_pct)
        db.session.commit()
        flash(f"Updated {gw.display_name}.", "success")
        return redirect(url_for("admin.gateways"))

    all_gateways = PaymentGateway.query.order_by(PaymentGateway.direction).all()
    return render_template("admin/gateways.html", gateways=all_gateways)
