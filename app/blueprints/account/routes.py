from flask import render_template, request, jsonify, abort, redirect, flash, current_app
from flask_babel import gettext as _
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import re
from app.blueprints.account import bp
from app.extensions import db, mail
from app.models.auth import User, Team, TeamMembership
from app.utilities import expire_pending_email_after_time
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload
from flask_login import login_required, current_user
from pathlib import Path
from sqlalchemy import func
from datetime import datetime, timedelta
import logging


# ── Helper: team access ──

def _get_team_role(user_id, team_id):
    """Returns the role string for a user in a team, or None if not a member."""
    m = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    return m.role if m else None


def _can_manage_shape(shape):
    """True if current_user may edit/delete this shape."""
    if shape.user_id == current_user.id:
        return True
    if shape.team_id:
        role = _get_team_role(current_user.id, shape.team_id)
        if role in ('admin', 'owner'):
            return True
    return False


def _can_manage_stencil(stencil):
    """True if current_user may edit/delete this stencil."""
    if stencil.user_id == current_user.id:
        return True
    if stencil.team_id:
        role = _get_team_role(current_user.id, stencil.team_id)
        if role in ('admin', 'owner'):
            return True
    return False


# ── Account overview ──

@bp.route('/account')
@login_required
def account():
    shapes = Shape.query.filter_by(user_id=current_user.id).order_by(Shape.upload_date.desc()).all()
    stencils = Stencil.query.filter_by(user_id=current_user.id).order_by(Stencil.upload_date.desc()).all()

    my_shape_ids = [s.id for s in shapes]
    my_stencil_ids = [s.id for s in stencils]

    if my_shape_ids:
        my_shapes_used_by_others = (
            ShapeDownload.query
            .filter(ShapeDownload.shape_id.in_(my_shape_ids), ShapeDownload.user_id != current_user.id)
            .count()
        )
        users_used_my_shapes = (
            db.session.query(func.count(func.distinct(ShapeDownload.user_id)))
            .filter(ShapeDownload.shape_id.in_(my_shape_ids), ShapeDownload.user_id != current_user.id)
            .scalar() or 0
        )
        top_own_shapes = (
            db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
            .join(ShapeDownload, ShapeDownload.shape_id == Shape.id)
            .filter(Shape.user_id == current_user.id, ShapeDownload.user_id != current_user.id)
            .group_by(Shape.id)
            .order_by(func.count(ShapeDownload.id).desc())
            .limit(5)
            .all()
        )
    else:
        my_shapes_used_by_others = 0
        users_used_my_shapes = 0
        top_own_shapes = []

    if my_stencil_ids:
        my_stencils_downloaded_by_others = (
            StencilDownload.query
            .filter(StencilDownload.stencil_id.in_(my_stencil_ids), StencilDownload.user_id != current_user.id)
            .count()
        )
        users_downloaded_my_stencils = (
            db.session.query(func.count(func.distinct(StencilDownload.user_id)))
            .filter(StencilDownload.stencil_id.in_(my_stencil_ids), StencilDownload.user_id != current_user.id)
            .scalar() or 0
        )
        top_own_stencils = (
            db.session.query(Stencil, func.count(StencilDownload.id).label('cnt'))
            .join(StencilDownload, StencilDownload.stencil_id == Stencil.id)
            .filter(Stencil.user_id == current_user.id, StencilDownload.user_id != current_user.id)
            .group_by(Stencil.id)
            .order_by(func.count(StencilDownload.id).desc())
            .limit(5)
            .all()
        )
    else:
        my_stencils_downloaded_by_others = 0
        users_downloaded_my_stencils = 0
        top_own_stencils = []

    top_foreign_shapes = (
        db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
        .join(ShapeDownload, ShapeDownload.shape_id == Shape.id)
        .filter(ShapeDownload.user_id == current_user.id, Shape.user_id != current_user.id)
        .group_by(Shape.id)
        .order_by(func.count(ShapeDownload.id).desc())
        .limit(5)
        .all()
    )
    foreign_shapes_used_total = (
        ShapeDownload.query
        .join(Shape, Shape.id == ShapeDownload.shape_id)
        .filter(ShapeDownload.user_id == current_user.id, Shape.user_id != current_user.id)
        .count()
    )
    top_foreign_stencils = (
        db.session.query(Stencil, func.count(StencilDownload.id).label('cnt'))
        .join(StencilDownload, StencilDownload.stencil_id == Stencil.id)
        .filter(StencilDownload.user_id == current_user.id, Stencil.user_id != current_user.id)
        .group_by(Stencil.id)
        .order_by(func.count(StencilDownload.id).desc())
        .limit(5)
        .all()
    )
    foreign_stencils_downloaded_total = (
        StencilDownload.query
        .join(Stencil, Stencil.id == StencilDownload.stencil_id)
        .filter(StencilDownload.user_id == current_user.id, Stencil.user_id != current_user.id)
        .count()
    )

    top_used_shapes = (
        db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
        .join(ShapeDownload, ShapeDownload.shape_id == Shape.id)
        .filter(ShapeDownload.user_id == current_user.id)
        .group_by(Shape.id)
        .order_by(func.count(ShapeDownload.id).desc())
        .limit(5)
        .all()
    )
    shapes_used_total = (
        ShapeDownload.query
        .filter(ShapeDownload.user_id == current_user.id)
        .count()
    )

    top_downloaded_stencils = (
        db.session.query(Stencil, func.count(StencilDownload.id).label('cnt'))
        .join(StencilDownload, StencilDownload.stencil_id == Stencil.id)
        .filter(StencilDownload.user_id == current_user.id)
        .group_by(Stencil.id)
        .order_by(func.count(StencilDownload.id).desc())
        .limit(5)
        .all()
    )
    stencils_downloaded_total = (
        StencilDownload.query
        .filter(StencilDownload.user_id == current_user.id)
        .count()
    )

    since = datetime.utcnow() - timedelta(days=30)

    my_shapes_used_by_others_30d = (
        ShapeDownload.query
        .filter(ShapeDownload.shape_id.in_(my_shape_ids), ShapeDownload.user_id != current_user.id, ShapeDownload.date >= since)
        .count()
    ) if my_shape_ids else 0

    my_stencils_downloaded_by_others_30d = (
        StencilDownload.query
        .filter(StencilDownload.stencil_id.in_(my_stencil_ids), StencilDownload.user_id != current_user.id, StencilDownload.date >= since)
        .count()
    ) if my_stencil_ids else 0

    shapes_used_by_me_30d = (
        ShapeDownload.query
        .filter(ShapeDownload.user_id == current_user.id, ShapeDownload.date >= since)
        .count()
    )

    stencils_downloaded_by_me_30d = (
        StencilDownload.query
        .filter(StencilDownload.user_id == current_user.id, StencilDownload.date >= since)
        .count()
    )

    stats = {
        'my_shapes_used_by_others': my_shapes_used_by_others,
        'users_used_my_shapes': users_used_my_shapes,
        'my_stencils_downloaded_by_others': my_stencils_downloaded_by_others,
        'users_downloaded_my_stencils': users_downloaded_my_stencils,
        'top_own_shapes': top_own_shapes,
        'top_own_stencils': top_own_stencils,
        'shapes_used_total': shapes_used_total,
        'stencils_downloaded_total': stencils_downloaded_total,
        'top_used_shapes': top_used_shapes,
        'top_downloaded_stencils': top_downloaded_stencils,
        'foreign_shapes_used_total': foreign_shapes_used_total,
        'foreign_stencils_downloaded_total': foreign_stencils_downloaded_total,
        'top_foreign_shapes': top_foreign_shapes,
        'top_foreign_stencils': top_foreign_stencils,
        'my_shapes_used_by_others_30d': my_shapes_used_by_others_30d,
        'my_stencils_downloaded_by_others_30d': my_stencils_downloaded_by_others_30d,
        'shapes_used_by_me_30d': shapes_used_by_me_30d,
        'stencils_downloaded_by_me_30d': stencils_downloaded_by_me_30d,
    }

    memberships = current_user.memberships

    return render_template(
        'browser/account.html',
        shapes=shapes,
        stencils=stencils,
        stats=stats,
        memberships=memberships,
    )


# ── Profile edits ──

@bp.route('/account/change_name', methods=['POST'])
@login_required
def change_name():
    new_name = request.form.get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'empty'}), 400
    if new_name == current_user.name:
        return jsonify({'name': current_user.name}), 200
    if User.query.filter(User.name == new_name, User.id != current_user.id).first():
        return jsonify({'error': 'taken'}), 409
    current_user.name = new_name
    db.session.commit()
    return jsonify({'name': current_user.name}), 200


def _build_email_change_email(confirm_url):
    t_title      = _('Confirm your new email address')
    t_intro      = _('You requested a change of your email address on Visio-Shapes. Click the button below to confirm.')
    t_cta        = _('Confirm email address')
    t_expiry     = _('The link is valid for 24 hours.')
    t_disclaimer = _("You didn't expect this email? Just ignore it – your old email address remains active.")
    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#FAFAF8;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">
  <tr><td style="padding-bottom:20px;">
    <span style="font-size:20px;font-weight:700;color:#E07B39;letter-spacing:-0.01em;">Visio-Shapes</span>
  </td></tr>
  <tr><td style="background:#FFFFFF;border:1px solid #E8E0D8;border-radius:8px;padding:32px;">
    <h1 style="font-size:22px;font-weight:700;color:#1C1C1A;margin:0 0 16px 0;">{t_title}</h1>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">{t_intro}</p>
    <a href="{confirm_url}" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{t_cta} &rarr;</a>
    <p style="font-size:13px;color:#6B6B67;margin:24px 0 0 0;padding-top:20px;border-top:1px solid #E8E0D8;">
      {t_expiry}
    </p>
  </td></tr>
  <tr><td style="padding-top:20px;">
    <p style="font-size:12px;color:#6B6B67;margin:0;line-height:1.6;">{t_disclaimer}</p>
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


@bp.route('/account/change_email', methods=['POST'])
@login_required
def change_email():
    new_email = request.form.get('email', '').strip().lower()
    if not new_email:
        return jsonify({'error': 'empty'}), 400
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', new_email):
        return jsonify({'error': 'invalid'}), 422
    if new_email == current_user.email:
        return jsonify({'error': 'same'}), 400
    if User.query.filter(User.email == new_email, User.id != current_user.id).first():
        return jsonify({'error': 'taken'}), 409

    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    token = s.dumps({'user_id': current_user.id, 'new_email': new_email})

    current_user.pending_email = new_email
    db.session.commit()
    expire_pending_email_after_time(current_user.id)

    confirm_url = f"{current_app.config['BASE_URL']}/account/confirm_email/{token}"
    msg = Message(
        _('Confirm your new email address'),
        recipients=[new_email],
        html=_build_email_change_email(confirm_url)
    )
    mail.send(msg)

    return jsonify({'pending_email': new_email}), 200


@bp.route('/account/confirm_email/<token>')
@login_required
def confirm_email(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        data = s.loads(token, max_age=86400)
    except SignatureExpired:
        current_user.pending_email = None
        db.session.commit()
        flash(_('The confirmation link has expired.'), 'error')
        return redirect('/account')
    except BadSignature:
        flash(_('The confirmation link is invalid.'), 'error')
        return redirect('/account')

    if data['user_id'] != current_user.id:
        abort(403)

    new_email = data['new_email']
    if current_user.pending_email != new_email:
        flash(_('This confirmation link is no longer valid.'), 'error')
        return redirect('/account')

    if User.query.filter(User.email == new_email, User.id != current_user.id).first():
        flash(_('This email address is already taken.'), 'error')
        current_user.pending_email = None
        db.session.commit()
        return redirect('/account')

    current_user.email = new_email
    current_user.pending_email = None
    db.session.commit()

    flash(_('Your email address has been updated.'), 'success')
    return redirect('/account')


@bp.route('/account/cancel_email_change', methods=['POST'])
@login_required
def cancel_email_change():
    current_user.pending_email = None
    db.session.commit()
    return jsonify({'ok': True}), 200


# ── Shape / Stencil management ──

@bp.route('/account/shape/<int:shape_id>/delete', methods=['POST'])
@login_required
def delete_shape(shape_id):
    shape = Shape.query.get_or_404(shape_id)
    if not _can_manage_shape(shape):
        abort(403)

    img_path = Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{shape_id}.png'
    try:
        if img_path.exists():
            img_path.unlink()
    except Exception:
        logging.warning(f'Could not delete image for shape {shape_id}')

    db.session.delete(shape)
    db.session.commit()
    return jsonify({'message': 'deleted'}), 200


@bp.route('/account/stencil/<int:stencil_id>/delete', methods=['POST'])
@login_required
def delete_stencil(stencil_id):
    stencil = Stencil.query.get_or_404(stencil_id)
    if not _can_manage_stencil(stencil):
        abort(403)

    ext = Path(stencil.file_name).suffix
    stencil_path = Path(current_app.root_path) / 'stencils' / f'{stencil_id}{ext}'
    try:
        if stencil_path.exists():
            stencil_path.unlink()
    except Exception:
        logging.warning(f'Could not delete stencil file {stencil_id}')

    for shape in stencil.shapes:
        img_path = Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{shape.id}.png'
        try:
            if img_path.exists():
                img_path.unlink()
        except Exception:
            logging.warning(f'Could not delete image for shape {shape.id}')

    db.session.delete(stencil)
    db.session.commit()
    return jsonify({'message': 'deleted'}), 200


@bp.route('/account/shape/<int:shape_id>/edit', methods=['POST'])
@login_required
def edit_shape(shape_id):
    shape = Shape.query.get_or_404(shape_id)
    if not _can_manage_shape(shape):
        abort(403)

    shape.name = request.form.get('name', shape.name).strip()
    shape.keywords = request.form.get('keywords', shape.keywords).strip()
    shape.prompt = request.form.get('prompt', shape.prompt).strip()
    db.session.commit()
    return jsonify({'name': shape.name, 'keywords': shape.keywords, 'prompt': shape.prompt}), 200


@bp.route('/account/stencil/<int:stencil_id>/edit', methods=['POST'])
@login_required
def edit_stencil(stencil_id):
    stencil = Stencil.query.get_or_404(stencil_id)
    if not _can_manage_stencil(stencil):
        abort(403)

    stencil.title = request.form.get('title', stencil.title).strip()
    stencil.categories = request.form.get('categories', stencil.categories).strip()
    stencil.tags = request.form.get('tags', stencil.tags).strip()
    stencil.comments = request.form.get('comments', stencil.comments).strip()
    db.session.commit()
    return jsonify({
        'title': stencil.title,
        'categories': stencil.categories,
        'tags': stencil.tags,
    }), 200


# ── Team member management (Team Owner only) ──

def _build_team_notification_email(subject_text, body_html):
    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#FAFAF8;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">
  <tr><td style="padding-bottom:20px;">
    <span style="font-size:20px;font-weight:700;color:#E07B39;letter-spacing:-0.01em;">Visio-Shapes</span>
  </td></tr>
  <tr><td style="background:#FFFFFF;border:1px solid #E8E0D8;border-radius:8px;padding:32px;">
    {body_html}
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def _send_team_added_email(user, team, role):
    role_labels = {
        'owner': _('Owner'),
        'admin': _('Admin'),
        'contributor': _('Contributor'),
    }
    role_label = role_labels.get(role, _('Member'))
    body = f'''
    <h1 style="font-size:20px;font-weight:700;color:#1C1C1A;margin:0 0 16px 0;">{_('You have been added to a team')}</h1>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 12px 0;">
      {_('You have been added to the team "%(team)s" on Visio-Shapes.', team=team.name)}
    </p>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">
      {_('Your role')}: <strong>{role_label}</strong>
    </p>
    <a href="{current_app.config['BASE_URL']}/account" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{_('Go to My Account')} &rarr;</a>
    '''
    msg = Message(
        _('You have been added to team "%(team)s"', team=team.name),
        recipients=[user.email],
        html=_build_team_notification_email(team.name, body)
    )
    try:
        mail.send(msg)
    except Exception:
        logging.warning(f'Could not send team-added email to {user.email}')


def _send_team_removed_email(user, team):
    body = f'''
    <h1 style="font-size:20px;font-weight:700;color:#1C1C1A;margin:0 0 16px 0;">{_('You have been removed from a team')}</h1>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">
      {_('You have been removed from the team "%(team)s" on Visio-Shapes.', team=team.name)}
    </p>
    '''
    msg = Message(
        _('You have been removed from team "%(team)s"', team=team.name),
        recipients=[user.email],
        html=_build_team_notification_email(team.name, body)
    )
    try:
        mail.send(msg)
    except Exception:
        logging.warning(f'Could not send team-removed email to {user.email}')


@bp.route('/account/team/<int:team_id>/add_member', methods=['POST'])
@login_required
def team_add_member(team_id):
    team = Team.query.get_or_404(team_id)

    my_m = TeamMembership.query.filter_by(user_id=current_user.id, team_id=team_id).first()
    if not my_m or my_m.role != 'owner':
        abort(403)

    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role') or None
    if role not in ('contributor', 'admin', None):
        role = None

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    if TeamMembership.query.filter_by(user_id=user.id, team_id=team_id).first():
        return jsonify({'error': 'already_member'}), 409

    membership = TeamMembership(user_id=user.id, team_id=team_id, role=role)
    db.session.add(membership)
    db.session.commit()

    _send_team_added_email(user, team, role)

    return jsonify({
        'ok': True,
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': role}
    }), 200


@bp.route('/account/team/<int:team_id>/remove_member', methods=['POST'])
@login_required
def team_remove_member(team_id):
    team = Team.query.get_or_404(team_id)

    my_m = TeamMembership.query.filter_by(user_id=current_user.id, team_id=team_id).first()
    if not my_m or my_m.role != 'owner':
        abort(403)

    user_id = request.form.get('user_id', type=int)
    membership = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    if not membership:
        abort(404)

    if membership.role == 'owner':
        return jsonify({'error': 'cannot_remove_owner'}), 400

    user = User.query.get(user_id)
    db.session.delete(membership)
    db.session.commit()

    if user:
        _send_team_removed_email(user, team)

    return jsonify({'ok': True}), 200


@bp.route('/account/team/<int:team_id>/set_visibility', methods=['POST'])
@login_required
def team_set_visibility(team_id):
    team = Team.query.get_or_404(team_id)

    my_m = TeamMembership.query.filter_by(user_id=current_user.id, team_id=team_id).first()
    if not my_m or my_m.role != 'owner':
        abort(403)

    visibility = request.form.get('visibility')
    if visibility not in ('public', 'visible', 'private'):
        return jsonify({'error': 'invalid_visibility'}), 400

    team.visibility = visibility
    db.session.commit()
    return jsonify({'ok': True, 'visibility': visibility}), 200


@bp.route('/account/team/<int:team_id>/set_member_role', methods=['POST'])
@login_required
def team_set_member_role(team_id):
    team = Team.query.get_or_404(team_id)  # noqa: F841

    my_m = TeamMembership.query.filter_by(user_id=current_user.id, team_id=team_id).first()
    if not my_m or my_m.role != 'owner':
        abort(403)

    user_id = request.form.get('user_id', type=int)
    role = request.form.get('role') or None
    if role not in ('contributor', 'admin', None):
        return jsonify({'error': 'invalid_role'}), 400

    membership = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    if not membership or membership.role == 'owner':
        abort(403)

    membership.role = role
    db.session.commit()
    return jsonify({'ok': True, 'role': role}), 200
