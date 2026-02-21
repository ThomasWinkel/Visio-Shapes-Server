from flask import render_template, request, jsonify, abort
from app.blueprints.account import bp
from app.extensions import db
from app.models.visio import Shape, Stencil
from flask_login import login_required, current_user
from pathlib import Path
from flask import current_app
import logging


@bp.route('/account')
@login_required
def account():
    shapes = Shape.query.filter_by(user_id=current_user.id).order_by(Shape.upload_date.desc()).all()
    stencils = Stencil.query.filter_by(user_id=current_user.id).order_by(Stencil.upload_date.desc()).all()
    return render_template('browser/account.html', shapes=shapes, stencils=stencils)


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
