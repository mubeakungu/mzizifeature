from flask import Blueprint, render_template, abort

from app.models.content import ContentPage

content_bp = Blueprint("content", __name__, url_prefix="/page")


@content_bp.route("/<slug>")
def page(slug):
    page_obj = ContentPage.query.filter_by(slug=slug, is_published=True).first()
    if not page_obj:
        abort(404)
    return render_template("content/page.html", page=page_obj)
