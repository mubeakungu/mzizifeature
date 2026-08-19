import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.kyc import KycDocument

kyc_bp = Blueprint("kyc", __name__, url_prefix="/kyc")

ALLOWED_EXT = {"jpg", "jpeg", "png", "pdf"}
UPLOAD_SUBDIR = "kyc"


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _save(file_storage, user_id):
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    fname = secure_filename(f"{user_id}_{uuid.uuid4().hex}.{ext}")
    upload_root = os.path.join(current_app.root_path, "static", "uploads", UPLOAD_SUBDIR)
    os.makedirs(upload_root, exist_ok=True)
    file_storage.save(os.path.join(upload_root, fname))
    return f"uploads/{UPLOAD_SUBDIR}/{fname}"


@kyc_bp.route("/", methods=["GET", "POST"])
@login_required
def upload():
    latest = (
        KycDocument.query.filter_by(user_id=current_user.id)
        .order_by(KycDocument.created_at.desc())
        .first()
    )

    if current_user.kyc_verified:
        return render_template("kyc/upload.html", latest=latest, verified=True)

    if request.method == "POST":
        doc_type = request.form.get("document_type", "").strip()
        doc_number = request.form.get("document_number", "").strip()
        id_front = request.files.get("id_front")
        id_back = request.files.get("id_back")
        selfie = request.files.get("selfie")

        if not doc_type or not doc_number or not id_front or not selfie:
            flash("Document type, number, ID front photo, and selfie are all required.", "error")
            return render_template("kyc/upload.html", latest=latest, verified=False)

        if not _allowed(id_front.filename) or not _allowed(selfie.filename):
            flash("Only JPG, PNG, or PDF files are accepted.", "error")
            return render_template("kyc/upload.html", latest=latest, verified=False)

        id_front_path = _save(id_front, current_user.id)
        id_back_path = _save(id_back, current_user.id) if id_back and id_back.filename else None
        selfie_path = _save(selfie, current_user.id)

        doc = KycDocument(
            user_id=current_user.id,
            document_type=doc_type,
            document_number=doc_number,
            id_front_path=id_front_path,
            id_back_path=id_back_path,
            selfie_path=selfie_path,
            status="pending",
        )
        db.session.add(doc)
        db.session.commit()

        flash("Documents submitted. We'll review them shortly.", "success")
        return redirect(url_for("kyc.upload"))

    return render_template("kyc/upload.html", latest=latest, verified=False)
