from functools import wraps
from pathlib import Path

from flask import render_template, redirect, abort, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app.blueprints.admin import bp
from app.extensions import db
from app.models.auth import User, Role
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload
import logging


# ── Helper functions ──

def is_owner(user):
    return user.is_authenticated and user.email == current_app.config.get('OWNER_EMAIL', '')


def is_admin(user):
    return user.is_authenticated and any(r.name == 'admin' for r in user.roles)


def is_admin_or_owner(user):
    return is_admin(user) or is_owner(user)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not is_admin_or_owner(current_user):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Routes ──

@bp.route('/admin')
@admin_required
def admin_users():
    users = User.query.order_by(User.register_date.desc()).all()

    # Count shapes per user
    shape_counts_q = (
        db.session.query(Shape.user_id, func.count(Shape.id))
        .group_by(Shape.user_id)
        .all()
    )
    shape_counts = dict(shape_counts_q)

    # Count stencils per user
    stencil_counts_q = (
        db.session.query(Stencil.user_id, func.count(Stencil.id))
        .group_by(Stencil.user_id)
        .all()
    )
    stencil_counts = dict(stencil_counts_q)

    admin_user_ids = {u.id for u in users if any(r.name == 'admin' for r in u.roles)}
    owner_email = current_app.config.get('OWNER_EMAIL', '')

    return render_template(
        'browser/admin_users.html',
        users=users,
        shape_counts=shape_counts,
        stencil_counts=stencil_counts,
        admin_user_ids=admin_user_ids,
        owner_email=owner_email,
    )


@bp.route('/admin/user/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)

    # Option A: Shapes uploaded by this user (with download count)
    uploaded_shapes = (
        db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
        .outerjoin(ShapeDownload, Shape.id == ShapeDownload.shape_id)
        .filter(Shape.user_id == user_id)
        .group_by(Shape.id)
        .order_by(func.count(ShapeDownload.id).desc())
        .all()
    )

    # Option B: Shapes downloaded by this user
    downloaded_shapes = (
        db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
        .join(ShapeDownload, Shape.id == ShapeDownload.shape_id)
        .filter(ShapeDownload.user_id == user_id)
        .group_by(Shape.id)
        .order_by(func.count(ShapeDownload.id).desc())
        .all()
    )

    # Option A: Stencils uploaded by this user (with download count)
    uploaded_stencils = (
        db.session.query(Stencil, func.count(StencilDownload.id).label('cnt'))
        .outerjoin(StencilDownload, Stencil.id == StencilDownload.stencil_id)
        .filter(Stencil.user_id == user_id)
        .group_by(Stencil.id)
        .order_by(func.count(StencilDownload.id).desc())
        .all()
    )

    # Option B: Stencils downloaded by this user
    downloaded_stencils = (
        db.session.query(Stencil, func.count(StencilDownload.id).label('cnt'))
        .join(StencilDownload, Stencil.id == StencilDownload.stencil_id)
        .filter(StencilDownload.user_id == user_id)
        .group_by(Stencil.id)
        .order_by(func.count(StencilDownload.id).desc())
        .all()
    )

    return render_template(
        'browser/admin_user_detail.html',
        user=user,
        uploaded_shapes=uploaded_shapes,
        downloaded_shapes=downloaded_shapes,
        uploaded_stencils=uploaded_stencils,
        downloaded_stencils=downloaded_stencils,
    )


@bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    owner_email = current_app.config.get('OWNER_EMAIL', '')

    # Owner cannot be deleted
    if user.email == owner_email:
        abort(403)

    # Only owner can delete admins
    if is_admin(user) and not is_owner(current_user):
        abort(403)

    # 1. Delete ShapeDownloads (by user or for user's shapes)
    shape_ids = [s.id for s in user.shapes]
    if shape_ids:
        ShapeDownload.query.filter(
            db.or_(
                ShapeDownload.user_id == user_id,
                ShapeDownload.shape_id.in_(shape_ids)
            )
        ).delete(synchronize_session=False)
    else:
        ShapeDownload.query.filter(ShapeDownload.user_id == user_id).delete(synchronize_session=False)

    # 2. Delete StencilDownloads (by user or for user's stencils)
    stencil_ids = [st.id for st in user.stencils]
    if stencil_ids:
        StencilDownload.query.filter(
            db.or_(
                StencilDownload.user_id == user_id,
                StencilDownload.stencil_id.in_(stencil_ids)
            )
        ).delete(synchronize_session=False)
    else:
        StencilDownload.query.filter(StencilDownload.user_id == user_id).delete(synchronize_session=False)

    # 3. Delete shape PNG files
    for shape in user.shapes:
        img_path = Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{shape.id}.png'
        try:
            if img_path.exists():
                img_path.unlink()
        except Exception:
            logging.warning(f'Could not delete image for shape {shape.id}')

    # 4. Delete stencil files
    for stencil in user.stencils:
        ext = Path(stencil.file_name).suffix
        stencil_path = Path(current_app.root_path) / 'stencils' / f'{stencil.id}{ext}'
        try:
            if stencil_path.exists():
                stencil_path.unlink()
        except Exception:
            logging.warning(f'Could not delete stencil file {stencil.id}')

    # 5. Delete user (cascade deletes shapes + stencils)
    db.session.delete(user)

    # 6. Commit
    db.session.commit()

    return redirect('/admin')


@bp.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    # Only owner can toggle admin role
    if not is_owner(current_user):
        abort(403)

    user = User.query.get_or_404(user_id)
    owner_email = current_app.config.get('OWNER_EMAIL', '')

    # Owner cannot be affected
    if user.email == owner_email:
        abort(403)

    # Get or create admin role
    role = Role.query.filter_by(name='admin').first()
    if role is None:
        role = Role(name='admin', description='Administrator')
        db.session.add(role)

    # Toggle
    if role in user.roles:
        user.roles.remove(role)
    else:
        user.roles.append(role)

    db.session.commit()

    return redirect('/admin')
