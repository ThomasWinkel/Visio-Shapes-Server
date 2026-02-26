from flask import render_template, request, url_for, redirect, flash, current_app
from flask_babel import gettext as _
from app.blueprints.auth import bp
from app.models.auth import User, Team, Role
from app.extensions import db, bcrypt, mail
from flask_login import login_user, login_required, logout_user, current_user
from app.utilities import generate_password, delete_user_if_not_loggedIn_after_time, expire_pending_password_after_time
from flask_mail import Message
from sqlalchemy import func


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user: User = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            user.pending_password_hash = None
            user.last_active = func.now()
            db.session.commit()
            login_user(user, remember=True)
            next_url = request.args.get('next') or url_for('browse')
            return redirect(next_url)

        if user and user.pending_password_hash and bcrypt.check_password_hash(user.pending_password_hash, password):
            user.password_hash = bcrypt.generate_password_hash(password)
            user.token = password
            user.pending_password_hash = None
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


def _build_registration_email(password, base_url):
    t_title      = _('Welcome to Visio-Shapes!')
    t_intro      = _('Your registration was successful. Here is your automatically generated password:')
    t_pw_label   = _('Your password')
    t_time       = _('Please log in within the next 5 minutes to activate your account.')
    t_cta        = _('Log in now')
    t_missed     = _('If you missed the time window, you can register again at any time:')
    t_disclaimer = _("You didn't expect this email? Someone probably made a typo – just ignore it.")
    login_url    = f'{base_url}/login'
    register_url = f'{base_url}/register'
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
    <div style="background:#F5F0EB;border-radius:6px;padding:20px;text-align:center;margin:0 0 24px 0;">
      <p style="font-size:11px;color:#6B6B67;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.08em;">{t_pw_label}</p>
      <p style="font-size:22px;font-weight:700;font-family:monospace;letter-spacing:0.12em;color:#1C1C1A;margin:0;">{password}</p>
    </div>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">{t_time}</p>
    <a href="{login_url}" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{t_cta} &rarr;</a>
    <p style="font-size:13px;color:#6B6B67;margin:24px 0 0 0;padding-top:20px;border-top:1px solid #E8E0D8;">
      {t_missed}<br>
      <a href="{register_url}" style="color:#E07B39;">{register_url}</a>
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


def _build_reset_email(password, base_url):
    t_title      = _('Reset your password')
    t_intro      = _('A new password has been generated for your Visio-Shapes account. Log in below to activate it.')
    t_pw_label   = _('Your new password')
    t_time       = _('Log in within the next 5 minutes to activate the new password.')
    t_cta        = _('Log in now')
    t_unchanged  = _('If you do not log in within 5 minutes, your current password remains unchanged.')
    t_disclaimer = _("You didn't expect this email? Someone probably made a typo – just ignore it.")
    login_url    = f'{base_url}/login'
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
    <div style="background:#F5F0EB;border-radius:6px;padding:20px;text-align:center;margin:0 0 24px 0;">
      <p style="font-size:11px;color:#6B6B67;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.08em;">{t_pw_label}</p>
      <p style="font-size:22px;font-weight:700;font-family:monospace;letter-spacing:0.12em;color:#1C1C1A;margin:0;">{password}</p>
    </div>
    <p style="font-size:14px;line-height:1.7;color:#1C1C1A;margin:0 0 24px 0;">{t_time}</p>
    <a href="{login_url}" style="display:inline-block;background:#E07B39;color:#FFFFFF;text-decoration:none;padding:12px 28px;border-radius:4px;font-size:14px;font-weight:700;">{t_cta} &rarr;</a>
    <p style="font-size:13px;color:#6B6B67;margin:24px 0 0 0;padding-top:20px;border-top:1px solid #E8E0D8;">
      {t_unchanged}
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
            _('Your Visio-Shapes password'),
            recipients=[email],
            html=_build_registration_email(password, current_app.config['BASE_URL'])
        )
        mail.send(msg)

        flash(_('An email has been sent to %(email)s. Please log in within 5 minutes.', email=email), category='success')
        delete_user_if_not_loggedIn_after_time(new_user.id)
        return redirect(url_for('auth.login'))

    return render_template('browser/register.html')


@bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('browse'))

    if request.method == 'POST':
        email = request.form['email']
        user: User = User.query.filter_by(email=email).first()

        if user:
            password = generate_password(10)
            user.pending_password_hash = bcrypt.generate_password_hash(password)
            db.session.commit()

            msg = Message(
                _('Your new Visio-Shapes password'),
                recipients=[email],
                html=_build_reset_email(password, current_app.config['BASE_URL'])
            )
            mail.send(msg)
            expire_pending_password_after_time(user.id)

        flash(_('If a matching account was found, an email has been sent.'), category='success')
        return redirect(url_for('auth.login'))

    return render_template('browser/reset_password.html')
