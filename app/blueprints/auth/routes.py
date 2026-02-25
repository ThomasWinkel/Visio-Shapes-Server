from flask import render_template, request, url_for, redirect, flash
from flask_babel import gettext as _
from app.blueprints.auth import bp
from app.models.auth import User, Team, Role
from app.extensions import db, bcrypt, mail
from flask_login import login_user, login_required, logout_user, current_user
from app.utilities import generate_password, delete_user_if_not_loggedIn_after_time
from flask_mail import Message
from sqlalchemy import func


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user: User = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            user.last_active = func.now()
            db.session.commit()
            login_user(user, remember=True)
            next_url = request.args.get('next') or url_for('browse')
            return redirect(next_url)

        flash(_('Login failed. Please try again.'), category='error')

    return render_template('browser/login.html')


@bp.route('/token_login', methods=['POST'])
def token_login():
    if current_user.is_authenticated:
        logout_user()

    token = request.form['token']
    user: User = User.query.filter_by(token=token).first()

    if user:
        user.last_active = func.now()
        db.session.commit()
        login_user(user, remember=True)

    return redirect(url_for('visio.panel'))


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']

        if User.query.filter_by(email=email).first():
            flash(_('Email address already registered.'), category='error')
            return render_template('browser/register.html')

        if User.query.filter_by(name=name).first():
            flash(_('Username already taken.'), category='error')
            return render_template('browser/register.html')

        if len(name) < 2:
            flash(_('Username must be at least 2 characters long.'), category='error')
            return render_template('browser/register.html')

        password = generate_password(10)
        token = password

        new_user = User(
            email=email,
            name=name,
            password_hash=bcrypt.generate_password_hash(password),
            token=token
        )
        db.session.add(new_user)
        db.session.commit()

        msg = Message(
            _('Welcome to visio-shapes.com'),
            recipients=[email],
            body='\n'.join([
                _('You have registered at https://www.visio-shapes.com.'),
                _('Please log in within the next 5 minutes.'),
                '',
                _('  Your password is: %(password)s', password=password),
                '',
                _('If you missed the time window, simply register again:'),
                'https://www.visio-shapes.com/register',
                '',
                _("You didn't expect this email?"),
                _('Someone probably made a typo \u2013 ignore this email.'),
            ])
        )
        mail.send(msg)

        flash(_('An email has been sent to %(email)s. Please log in within 5 minutes.', email=email), category='success')
        delete_user_if_not_loggedIn_after_time(new_user.id)
        return redirect(url_for('auth.login'))

    return render_template('browser/register.html')
