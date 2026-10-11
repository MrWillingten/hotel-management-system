"""Backups (managers only). Restoring is done from the command line."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_babel import gettext as _

from hotel.domain.enums import Role
from hotel.web.context import current_actor, services
from hotel.web.security import roles_required

bp = Blueprint("backups", __name__, url_prefix="/backups")


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    backups = services().backups
    return render_template(
        "backups/index.html", backups=backups.list(current_actor()), folder=backups.backup_dir
    )


@bp.post("/")
@roles_required(Role.MANAGER)
def create():
    path = services().backups.create(current_actor())
    flash(_("Backup %(name)s written.", name=path.name), "success")
    return redirect(url_for("backups.index"))
