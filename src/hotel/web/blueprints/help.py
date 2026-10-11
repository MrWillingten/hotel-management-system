"""The Help page (story 6.10): what each page is for, per role."""

from __future__ import annotations

from flask import Blueprint, g, render_template

from hotel.web.help import topics_for
from hotel.web.security import login_required

bp = Blueprint("help", __name__, url_prefix="/help")


@bp.get("/")
@login_required
def index():
    return render_template("help/index.html", topics=topics_for(g.user.is_manager))
