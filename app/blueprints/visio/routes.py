from flask import render_template, request, send_file, jsonify, current_app, redirect, url_for
from app.blueprints.visio import bp
from app.extensions import db, http_auth
from flask_login import current_user
from app.models.auth import Team, TeamMembership
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload
from app.utilities import register_shape
from sqlalchemy import func
from sqlalchemy.orm import selectinload
import json, logging
from pathlib import Path


@bp.route('/panel')
def panel():
    contributor_teams = []
    if current_user.is_authenticated:
        contributor_teams = [
            m for m in current_user.memberships
            if m.role in ('contributor', 'admin', 'owner')
        ]
    return render_template('panel/panel.html', contributor_teams=contributor_teams)


@bp.route('/get_shapes')
def get_shapes():
    sort  = request.args.get('sort', 'date_desc')
    limit = request.args.get('limit', type=int)

    download_counts = (
        db.session.query(ShapeDownload.shape_id, func.count(ShapeDownload.id).label('cnt'))
        .group_by(ShapeDownload.shape_id)
        .subquery()
    )

    # Visibility filter: Private team shapes are only shown to members.
    # Shapes without a team, or in Public/Visible teams, are shown to everyone.
    if current_user.is_authenticated:
        member_team_ids = (
            db.session.query(TeamMembership.team_id)
            .filter(TeamMembership.user_id == current_user.id)
            .subquery()
        )
        visibility_filter = db.or_(
            Shape.team_id.is_(None),
            Team.visibility.in_(['public', 'visible']),
            Shape.team_id.in_(member_team_ids),
        )
    else:
        visibility_filter = db.or_(
            Shape.team_id.is_(None),
            Team.visibility.in_(['public', 'visible']),
        )

    base_query = (
        db.session.query(Shape, func.coalesce(download_counts.c.cnt, 0).label('cnt'))
        .outerjoin(download_counts, Shape.id == download_counts.c.shape_id)
        .outerjoin(Team, Shape.team_id == Team.id)
        .filter(visibility_filter)
        .options(selectinload(Shape.user), selectinload(Shape.stencil), selectinload(Shape.team))
    )

    if sort == 'popular':
        base_query = base_query.order_by(func.coalesce(download_counts.c.cnt, 0).desc())
    elif sort == 'date_asc':
        base_query = base_query.order_by(Shape.upload_date.asc())
    else:  # date_desc (default)
        base_query = base_query.order_by(Shape.upload_date.desc())

    if limit:
        base_query = base_query.limit(limit)

    result = []
    for shape, cnt in base_query.all():
        s = shape.serialize()
        s['download_count'] = cnt
        result.append(s)
    return jsonify(result)


def _user_is_team_member(user_id, team_id):
    return TeamMembership.query.filter_by(user_id=user_id, team_id=team_id).first() is not None


@bp.route('/download_stencil/<int:stencil_id>')
def download_stencil(stencil_id):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    stencil = Stencil.query.get(stencil_id)
    if not stencil:
        return redirect(url_for('auth.login'))

    # Access check for Visible and Private teams
    if stencil.team_id:
        team = stencil.team
        if team.visibility in ('visible', 'private'):
            if not _user_is_team_member(current_user.id, stencil.team_id):
                return redirect(url_for('auth.login'))

    file_path = Path(current_app.root_path) / 'stencils' / f'{stencil_id}{Path(stencil.file_name).suffix}'

    download = StencilDownload(stencil_id=stencil_id, user_id=current_user.id)
    db.session.add(download)
    db.session.commit()

    return send_file(file_path, download_name=stencil.file_name, as_attachment=True)


@bp.route('/get_shape/<int:shape_id>')
def get_shape(shape_id):
    if not current_user.is_authenticated:
        return register_shape

    shape = Shape.query.get(shape_id)
    if not shape:
        return register_shape

    # Access check for Visible and Private teams
    if shape.team_id:
        team = shape.team
        if team.visibility in ('visible', 'private'):
            if not _user_is_team_member(current_user.id, shape.team_id):
                return register_shape

    download = ShapeDownload(shape_id=shape_id, user_id=current_user.id)
    db.session.add(download)
    db.session.commit()

    return shape.data_object


@bp.route('/get_user_teams')
@http_auth.login_required
def get_user_teams():
    user = http_auth.current_user()
    teams = [
        {'id': m.team_id, 'name': m.team.name}
        for m in user.memberships
        if m.role in ('contributor', 'admin', 'owner')
    ]
    return jsonify(teams)


@bp.route('/add_shape', methods=['POST'])
@http_auth.login_required
def add_shape():
    try:
        add_shape_request = json.loads(request.form['json'])
        file = request.files['image']

        team_id = add_shape_request.get('TeamId') or None
        if team_id:
            team_id = int(team_id)
            membership = TeamMembership.query.filter_by(
                user_id=http_auth.current_user().id,
                team_id=team_id
            ).first()
            if not membership or membership.role not in ('contributor', 'admin', 'owner'):
                return jsonify({'message': 'Forbidden: not a contributor of this team'}), 403

        new_shape = Shape(
            name=add_shape_request['Name'],
            prompt=add_shape_request['Prompt'],
            keywords=add_shape_request['Keywords'],
            data_object=add_shape_request['DataObject'],
            user_id=http_auth.current_user().id,
            team_id=team_id,
        )

        db.session.add(new_shape)
        db.session.commit()

        file.save(Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{new_shape.id}.png')

    except Exception as e:
        logging.exception('Error adding shape.')
        return jsonify({'message': 'Failed'}), 500

    return jsonify({'message': 'Success'}), 201


@bp.route('/add_stencil', methods=['POST'])
@http_auth.login_required
def add_stencil():
    try:
        add_stencil_request = json.loads(request.form['json'])
        stencil = request.files['stencil']
        images = request.files.getlist('images')

        team_id = add_stencil_request.get('TeamId') or None
        if team_id:
            team_id = int(team_id)
            membership = TeamMembership.query.filter_by(
                user_id=http_auth.current_user().id,
                team_id=team_id
            ).first()
            if not membership or membership.role not in ('contributor', 'admin', 'owner'):
                return jsonify({'message': 'Forbidden: not a contributor of this team'}), 403

        shapes_list = [
            Shape(
                name=shape['Name'],
                prompt=shape['Prompt'],
                keywords=shape['Keywords'],
                data_object=shape['DataObject'],
                user_id=http_auth.current_user().id,
                team_id=team_id,
            )
            for shape in add_stencil_request['Shapes']
        ]

        new_stencil = Stencil(
            file_name=add_stencil_request['FileName'],
            title=add_stencil_request['Title'],
            subject=add_stencil_request['Subject'],
            author=add_stencil_request['Author'],
            manager=add_stencil_request['Manager'],
            company=add_stencil_request['Company'],
            language=add_stencil_request['Language'],
            categories=add_stencil_request['Categories'],
            tags=add_stencil_request['Tags'],
            comments=add_stencil_request['Comments'],
            shapes=shapes_list,
            user_id=http_auth.current_user().id,
            team_id=team_id,
        )

        db.session.add(new_stencil)
        db.session.flush()  # IDs werden vergeben, Transaktion noch offen

        for shape, image in zip(shapes_list, images):
            image.save(Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{shape.id}.png')

        stencil.save(Path(current_app.root_path) / 'stencils' / f'{new_stencil.id}{Path(stencil.filename).suffix}')

        db.session.commit()

    except Exception:
        db.session.rollback()
        logging.exception('Error adding stencil.')
        return jsonify({'message': 'Failed'}), 500

    return jsonify({'message': 'Success'}), 201
