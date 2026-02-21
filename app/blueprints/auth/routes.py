from flask import render_template, request, url_for, redirect, flash
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

        flash('Login fehlgeschlagen. Bitte versuche es erneut.', category='error')

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
            flash('E-Mail-Adresse bereits registriert.', category='error')
            return render_template('browser/register.html')

        if User.query.filter_by(name=name).first():
            flash('Benutzername bereits vergeben.', category='error')
            return render_template('browser/register.html')

        if len(name) < 2:
            flash('Benutzername muss mindestens 2 Zeichen lang sein.', category='error')
            return render_template('browser/register.html')

        password = generate_password(10)
        token = '#' + password

        from flask import current_app
        current_app.logger.warning(
            f'\n--- REGISTRATION ---\n  User:     {name}\n  Password: {password}\n  Token:    {token}\n---'
        )

        new_user = User(
            email=email,
            name=name,
            password_hash=bcrypt.generate_password_hash(password),
            token=token
        )
        db.session.add(new_user)
        db.session.commit()

        msg = Message(
            'Willkommen bei visio-shapes.com',
            recipients=[email],
            body=(
                f'Du hast dich bei https://www.visio-shapes.com registriert.\n'
                f'Bitte logge dich innerhalb der nächsten 5 Minuten ein.\n'
                f'\n'
                f'  Dein Passwort lautet: {password}\n'
                f'\n'
                f'Falls du die Zeit verpasst hast, registriere dich einfach erneut:\n'
                f'https://www.visio-shapes.com/register\n'
                f'\n'
                f'Du hast diese E-Mail nicht erwartet?\n'
                f'Jemand hat wahrscheinlich einen Tippfehler gemacht – ignoriere diese E-Mail.'
            )
        )
        mail.send(msg)

        flash(f'Eine E-Mail wurde an {email} gesendet. Bitte logge dich innerhalb von 5 Minuten ein.', category='success')
        delete_user_if_not_loggedIn_after_time(new_user.id)
        return redirect(url_for('auth.login'))

    return render_template('browser/register.html')
