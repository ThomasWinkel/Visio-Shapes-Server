from functools import wraps
from pathlib import Path

import logging

from flask import render_template, redirect, abort, flash, current_app, request, jsonify
from flask_babel import gettext as _
from flask_login import login_required, current_user
from flask_mail import Message
from sqlalchemy import func

from app.blueprints.admin import bp
from app.extensions import db, mail
from app.models.auth import User, Role, Team, TeamMembership
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload


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


# ── User routes ──

@bp.route('/admin')
@admin_required
def admin_users():
    users = User.query.order_by(User.register_date.desc()).all()

    shape_counts_q = (
        db.session.query(Shape.user_id, func.count(Shape.id))
        .group_by(Shape.user_id)
        .all()
    )
    shape_counts = dict(shape_counts_q)

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

    uploaded_shapes = (
        db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
        .outerjoin(ShapeDownload, Shape.id == ShapeDownload.shape_id)
        .filter(Shape.user_id == user_id)
        .group_by(Shape.id)
        .order_by(func.count(ShapeDownload.id).desc())
        .all()
    )

    downloaded_shapes = (
        db.session.query(Shape, func.count(ShapeDownload.id).label('cnt'))
        .join(ShapeDownload, Shape.id == ShapeDownload.shape_id)
        .filter(ShapeDownload.user_id == user_id)
        .group_by(Shape.id)
        .order_by(func.count(ShapeDownload.id).desc())
        .all()
    )

    uploaded_stencils = (
        db.session.query(Stencil, func.count(StencilDownload.id).label('cnt'))
        .outerjoin(StencilDownload, Stencil.id == StencilDownload.stencil_id)
        .filter(Stencil.user_id == user_id)
        .group_by(Stencil.id)
        .order_by(func.count(StencilDownload.id).desc())
        .all()
    )

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

    if user.email == owner_email:
        abort(403)

    if is_admin(user) and not is_owner(current_user):
        abort(403)

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

    for shape in user.shapes:
        img_path = Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{shape.id}.png'
        try:
            if img_path.exists():
                img_path.unlink()
        except Exception:
            logging.warning(f'Could not delete image for shape {shape.id}')

    for stencil in user.stencils:
        ext = Path(stencil.file_name).suffix
        stencil_path = Path(current_app.root_path) / 'stencils' / f'{stencil.id}{ext}'
        try:
            if stencil_path.exists():
                stencil_path.unlink()
        except Exception:
            logging.warning(f'Could not delete stencil file {stencil.id}')

    db.session.delete(user)
    db.session.commit()

    return redirect('/admin')


@bp.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    if not is_owner(current_user):
        abort(403)

    user = User.query.get_or_404(user_id)
    owner_email = current_app.config.get('OWNER_EMAIL', '')

    if user.email == owner_email:
        abort(403)

    role = Role.query.filter_by(name='admin').first()
    if role is None:
        role = Role(name='admin', description='Administrator')
        db.session.add(role)

    if role in user.roles:
        user.roles.remove(role)
    else:
        user.roles.append(role)

    db.session.commit()

    return redirect('/admin')


# ── Team mail helpers ──

def _build_team_notification_email(body_html):
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


def _send_team_owner_email(user, team):
    body = f'''
    <h1 style="font-size:20px;font-weight:700;color:#1C1C1A;margin:0 0 16px 0;">{_('You have been appointed team owner')}</h1>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 12px 0;">
      {_('You are now the owner of team "%(team)s" on Visio-Shapes.', team=team.name)}
    </p>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">
      {_('Your role')}: <strong>{_('Owner')}</strong>
    </p>
    <a href="{current_app.config['BASE_URL']}/account" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{_('Go to My Account')} &rarr;</a>
    '''
    msg = Message(
        _('You are now the owner of team "%(team)s"', team=team.name),
        recipients=[user.email],
        html=_build_team_notification_email(body)
    )
    try:
        mail.send(msg)
    except Exception:
        logging.warning(f'Could not send team-owner email to {user.email}')


def _send_team_owner_revoked_email(user, team):
    body = f'''
    <h1 style="font-size:20px;font-weight:700;color:#1C1C1A;margin:0 0 16px 0;">{_('Your team owner role has been revoked')}</h1>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">
      {_('You are no longer the owner of team "%(team)s" on Visio-Shapes.', team=team.name)}
    </p>
    <a href="{current_app.config['BASE_URL']}/account" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{_('Go to My Account')} &rarr;</a>
    '''
    msg = Message(
        _('You are no longer the owner of team "%(team)s"', team=team.name),
        recipients=[user.email],
        html=_build_team_notification_email(body)
    )
    try:
        mail.send(msg)
    except Exception:
        logging.warning(f'Could not send team-owner-revoked email to {user.email}')


def _send_team_member_added_email(user, team, role):
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
        html=_build_team_notification_email(body)
    )
    try:
        mail.send(msg)
    except Exception:
        logging.warning(f'Could not send team-member-added email to {user.email}')


def _send_team_member_removed_email(user, team):
    body = f'''
    <h1 style="font-size:20px;font-weight:700;color:#1C1C1A;margin:0 0 16px 0;">{_('You have been removed from a team')}</h1>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">
      {_('You have been removed from the team "%(team)s" on Visio-Shapes.', team=team.name)}
    </p>
    <a href="{current_app.config['BASE_URL']}/account" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{_('Go to My Account')} &rarr;</a>
    '''
    msg = Message(
        _('You have been removed from team "%(team)s"', team=team.name),
        recipients=[user.email],
        html=_build_team_notification_email(body)
    )
    try:
        mail.send(msg)
    except Exception:
        logging.warning(f'Could not send team-member-removed email to {user.email}')


# ── Team routes (Owner only) ──

def owner_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not is_owner(current_user):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@bp.route('/admin/teams')
@owner_required
def admin_teams():
    teams = Team.query.order_by(Team.name).all()
    all_users = User.query.order_by(User.name).all()
    return render_template(
        'browser/admin_teams.html',
        teams=teams,
        all_users=all_users,
    )


@bp.route('/admin/team/create', methods=['POST'])
@owner_required
def admin_team_create():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip() or None
    visibility = request.form.get('visibility', 'public')

    if not name:
        flash(_('Team name is required.'), 'error')
        return redirect('/admin/teams')

    if visibility not in ('public', 'visible', 'private'):
        visibility = 'public'

    if Team.query.filter_by(name=name).first():
        flash(_('A team with this name already exists.'), 'error')
        return redirect('/admin/teams')

    team = Team(name=name, description=description, visibility=visibility)
    db.session.add(team)
    db.session.commit()
    return redirect('/admin/teams')


@bp.route('/admin/team/<int:team_id>/rename', methods=['POST'])
@owner_required
def admin_team_rename(team_id):
    team = Team.query.get_or_404(team_id)
    new_name = request.form.get('name', '').strip()

    if not new_name:
        return jsonify({'error': _('Team name is required.')}), 400

    if Team.query.filter(Team.name == new_name, Team.id != team_id).first():
        return jsonify({'error': _('A team with this name already exists.')}), 409

    team.name = new_name
    db.session.commit()
    return jsonify({'ok': True, 'name': new_name})


@bp.route('/admin/team/<int:team_id>/update_description', methods=['POST'])
@owner_required
def admin_team_update_description(team_id):
    team = Team.query.get_or_404(team_id)
    description = request.form.get('description', '').strip()
    team.description = description or None
    db.session.commit()
    return jsonify({'ok': True, 'description': team.description})


@bp.route('/admin/team/<int:team_id>/delete', methods=['POST'])
@owner_required
def admin_team_delete(team_id):
    team = Team.query.get_or_404(team_id)

    if team.shapes or team.stencils:
        flash(_('Cannot delete team: it still has shapes or stencils.'), 'error')
        return redirect('/admin/teams')

    db.session.delete(team)
    db.session.commit()
    return redirect('/admin/teams')


@bp.route('/admin/team/<int:team_id>/set_visibility', methods=['POST'])
@owner_required
def admin_team_set_visibility(team_id):
    team = Team.query.get_or_404(team_id)
    visibility = request.form.get('visibility', 'public')

    if visibility not in ('public', 'visible', 'private'):
        visibility = 'public'

    team.visibility = visibility
    db.session.commit()
    return redirect('/admin/teams')


@bp.route('/admin/team/<int:team_id>/set_owner', methods=['POST'])
@owner_required
def admin_team_set_owner(team_id):
    team = Team.query.get_or_404(team_id)
    user_id = request.form.get('user_id', type=int)

    if not user_id:
        return jsonify({'error': _('Please select a user.')}), 400

    membership = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first()
    if not membership:
        return jsonify({'error': 'not_a_member'}), 400

    # Revoke existing owner
    former_owner = None
    for m in team.memberships:
        if m.role == 'owner' and m.user_id != user_id:
            former_owner = m.user
            m.role = None

    membership.role = 'owner'
    db.session.commit()

    new_owner = db.session.get(User, user_id)
    _send_team_owner_email(new_owner, team)
    if former_owner:
        _send_team_owner_revoked_email(former_owner, team)

    return jsonify({'ok': True})


@bp.route('/admin/team/<int:team_id>/remove_owner', methods=['POST'])
@owner_required
def admin_team_remove_owner(team_id):
    team = Team.query.get_or_404(team_id)

    former_owner = None
    for m in team.memberships:
        if m.role == 'owner':
            former_owner = m.user
            m.role = None

    db.session.commit()
    if former_owner:
        _send_team_owner_revoked_email(former_owner, team)
    return redirect('/admin/teams')


@bp.route('/admin/team/<int:team_id>')
@owner_required
def admin_team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    all_users = User.query.order_by(User.name).all()
    return render_template('browser/admin_team_detail.html', team=team, all_users=all_users)


@bp.route('/admin/team/<int:team_id>/member/<int:user_id>/set_role', methods=['POST'])
@owner_required
def admin_team_member_set_role(team_id, user_id):
    team = Team.query.get_or_404(team_id)
    target_m = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first_or_404()
    role = request.form.get('role') or None

    if role not in ('owner', 'admin', 'contributor', None):
        return jsonify({'error': 'invalid_role'}), 400

    if role == 'owner':
        former_owner = None
        for m in team.memberships:
            if m.role == 'owner' and m.user_id != user_id:
                former_owner = m.user
                m.role = None
        target_m.role = 'owner'
        db.session.commit()
        new_owner = db.session.get(User, user_id)
        _send_team_owner_email(new_owner, team)
        if former_owner:
            _send_team_owner_revoked_email(former_owner, team)
    else:
        target_m.role = role
        db.session.commit()

    return jsonify({'ok': True, 'role': role})


@bp.route('/admin/team/<int:team_id>/member/<int:user_id>/remove', methods=['POST'])
@owner_required
def admin_team_member_remove(team_id, user_id):
    team = Team.query.get_or_404(team_id)
    membership = TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first_or_404()
    was_owner = membership.role == 'owner'
    user = db.session.get(User, user_id)

    db.session.delete(membership)
    db.session.commit()

    if user:
        if was_owner:
            _send_team_owner_revoked_email(user, team)
        else:
            _send_team_member_removed_email(user, team)

    return jsonify({'ok': True})


@bp.route('/admin/team/<int:team_id>/add_member', methods=['POST'])
@owner_required
def admin_team_add_member(team_id):
    team = Team.query.get_or_404(team_id)
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role') or None
    if role not in ('owner', 'admin', 'contributor'):
        role = None

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    if TeamMembership.query.filter_by(user_id=user.id, team_id=team_id).first():
        return jsonify({'error': 'already_member'}), 409

    membership = TeamMembership(user_id=user.id, team_id=team_id, role=role)
    db.session.add(membership)
    db.session.commit()

    _send_team_member_added_email(user, team, role)

    return jsonify({
        'ok': True,
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': role}
    })
