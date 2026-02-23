from flask import render_template, request, send_file, jsonify, current_app, redirect, url_for
from app.blueprints.visio import bp
from app.extensions import db, http_auth
from flask_login import current_user
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload
from app.utilities import register_shape
from sqlalchemy import func
import json, logging
from pathlib import Path


@bp.route('/panel')
def panel():
    return render_template('panel/panel.html')


@bp.route('/get_shapes')
def get_shapes():
    sort = request.args.get('sort', 'date_desc')

    download_counts = (
        db.session.query(ShapeDownload.shape_id, func.count(ShapeDownload.id).label('cnt'))
        .group_by(ShapeDownload.shape_id)
        .subquery()
    )

    base_query = (
        db.session.query(Shape, func.coalesce(download_counts.c.cnt, 0).label('cnt'))
        .outerjoin(download_counts, Shape.id == download_counts.c.shape_id)
    )

    if sort == 'popular':
        rows = base_query.order_by(func.coalesce(download_counts.c.cnt, 0).desc()).all()
    elif sort == 'date_asc':
        rows = base_query.order_by(Shape.upload_date.asc()).all()
    else:  # date_desc (default)
        rows = base_query.order_by(Shape.upload_date.desc()).all()

    result = []
    for shape, cnt in rows:
        s = shape.serialize()
        s['download_count'] = cnt
        result.append(s)
    return jsonify(result)


@bp.route('/search', methods=['GET', 'POST'])
def search():
    return redirect(url_for('index'))


@bp.route('/download_stencil/<int:stencil_id>')
def download_stencil(stencil_id):
    if  current_user.is_authenticated:
        stencil = Stencil.query.get(stencil_id)
        
        file_path = Path(current_app.root_path) / 'stencils' / f'{stencil_id}{Path(stencil.file_name).suffix}'

        download = StencilDownload(
            stencil_id = stencil_id,
            user_id = current_user.id
        )
        
        db.session.add(download)
        db.session.commit()

        return send_file(file_path, download_name = stencil.file_name, as_attachment=True)
    else:
        return redirect(url_for('auth.login'))


@bp.route('/get_shape/<int:shape_id>')
def get_shape(shape_id):
    if current_user.is_authenticated:
        shape = Shape.query.get(shape_id)

        download = ShapeDownload(
            shape_id = shape_id,
            user_id = current_user.id
        )
        
        db.session.add(download)
        db.session.commit()

        return shape.data_object
    else:
        return register_shape


@bp.route('/add_shape', methods=['POST'])
@http_auth.login_required
def add_shape():
    try:
        add_shape_request = json.loads(request.form['json'])
        file = request.files['image']

        new_shape = Shape(
            name = add_shape_request['Name'],
            prompt = add_shape_request['Prompt'],
            keywords = add_shape_request['Keywords'],
            data_object = add_shape_request['DataObject'],
            user_id = http_auth.current_user().id
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

        i = 0
        shape_id = (db.session.query(func.max(Shape.id)).scalar() or 0) + 1
        shapes_list = []

        for shape in add_stencil_request['Shapes']:
            image = images[i]
            
            shapes_list.append(Shape(
                id = shape_id,
                name = shape['Name'],
                prompt = shape['Prompt'],
                keywords = shape['Keywords'],
                data_object = shape['DataObject'],
                user_id = http_auth.current_user().id
            ))
            
            image.save(Path(current_app.root_path) / 'static' / 'images' / 'shapes' / f'{shape_id}.png')

            i += 1
            shape_id += 1
        
        new_stencil = Stencil(
            file_name = add_stencil_request['FileName'],
            title = add_stencil_request['Title'],
            subject = add_stencil_request['Subject'],
            author = add_stencil_request['Author'],
            manager = add_stencil_request['Manager'],
            company = add_stencil_request['Company'],
            language = add_stencil_request['Language'],
            categories = add_stencil_request['Categories'],
            tags = add_stencil_request['Tags'],
            comments = add_stencil_request['Comments'],
            shapes = shapes_list,
            user_id = http_auth.current_user().id
        )
        
        db.session.add(new_stencil)
        db.session.commit()

        stencil.save(Path(current_app.root_path) / 'stencils' / f'{new_stencil.id}{Path(stencil.filename).suffix}')

    except Exception:
        logging.exception('Error adding stencil.')
        return jsonify({'message': 'Failed'}), 500
    
    return jsonify({'message': 'Success'}), 201