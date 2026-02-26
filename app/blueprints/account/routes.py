from flask import render_template, request, jsonify, abort
from app.blueprints.account import bp
from app.extensions import db
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload
from flask_login import login_required, current_user
from pathlib import Path
from flask import current_app
from sqlalchemy import func
from datetime import datetime, timedelta
import logging


@bp.route('/account')
@login_required
def account():
    shapes = Shape.query.filter_by(user_id=current_user.id).order_by(Shape.upload_date.desc()).all()
    stencils = Stencil.query.filter_by(user_id=current_user.id).order_by(Stencil.upload_date.desc()).all()

    my_shape_ids = [s.id for s in shapes]
    my_stencil_ids = [s.id for s in stencils]

    # How often my shapes were used by others, and by how many distinct users
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

    # How often my stencils were downloaded by others, and by how many distinct users
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

    # Only foreign shapes / stencils I have used
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

    # All shapes / stencils I have used (including my own)
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

    # Last 30 days
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

    return render_template('browser/account.html', shapes=shapes, stencils=stencils, stats=stats)


@bp.route('/account/shape/<int:shape_id>/delete', methods=['POST'])
@login_required
def delete_shape(shape_id):
    shape = Shape.query.get_or_404(shape_id)
    if shape.user_id != current_user.id:
        abort(403)

    # Delete preview image
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
    if stencil.user_id != current_user.id:
        abort(403)

    # Delete stencil file
    ext = Path(stencil.file_name).suffix
    stencil_path = Path(current_app.root_path) / 'stencils' / f'{stencil_id}{ext}'
    try:
        if stencil_path.exists():
            stencil_path.unlink()
    except Exception:
        logging.warning(f'Could not delete stencil file {stencil_id}')

    # Delete shape preview images (cascade deletes shapes from DB)
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
    if shape.user_id != current_user.id:
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
    if stencil.user_id != current_user.id:
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
