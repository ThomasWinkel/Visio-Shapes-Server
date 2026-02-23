from flask import Flask, render_template, session, request, redirect, url_for
from flask_babel import lazy_gettext as _l
from config import Config
from app.extensions import db, migrate, bcrypt, login_manager, http_auth, mail, cors, babel

LANGUAGES = ['de', 'en']


def get_locale():
    lang = session.get('lang')
    if lang in LANGUAGES:
        return lang
    return request.accept_languages.best_match(LANGUAGES, default='de')


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['BABEL_DEFAULT_LOCALE'] = 'de'
    app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    cors.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    # User loader / token verifier
    from app.models.auth import User

    @login_manager.user_loader
    def user_loader(id):
        return User.query.get(int(id))

    @http_auth.verify_token
    def verify_token(token):
        return User.query.filter_by(token=token).first()

    # Redirect unauthenticated users to login page
    login_manager.login_view = 'auth.login'
    login_manager.login_message = _l('Please log in to access this page.')
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.blueprints.visio import bp as visio_bp
    app.register_blueprint(visio_bp)

    from app.blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.blueprints.account import bp as account_bp
    app.register_blueprint(account_bp)

    # Inject current locale and JS translations into every template
    @app.context_processor
    def inject_i18n():
        from flask_babel import get_locale, gettext as _
        locale = str(get_locale())
        js_translations = {
            'loading':           _('Loading shapes\u2026'),
            'no_shapes':         _('No shapes yet.'),
            'load_error':        _('Could not load shapes.'),
            'load_stencil':      _('Load stencil'),
            'download':          _('Download'),
            'login_to_download': _('Log in to download'),
            'no_shapes_found':   _('No shapes found.'),
            'save_error':        _('Error saving. Please try again.'),
            'network_error':     _('Network error. Please try again.'),
            'delete_error':      _('Error deleting. Please try again.'),
            'delete_confirm':    _('Do you really want to permanently delete "{name}"?'),
            'keywords_label':    _('Keywords:'),
        }
        return {'current_locale': locale, 'js_translations': js_translations}

    # Language switching
    @app.route('/set_lang/<lang>')
    def set_lang(lang):
        if lang in LANGUAGES:
            session['lang'] = lang
        return redirect(request.referrer or url_for('index'))

    # Browser-site routes
    @app.route('/')
    def index():
        return render_template('browser/landing.html')

    @app.route('/browse')
    def browse():
        return render_template('browser/browse.html')

    @app.route('/impressum')
    def impressum():
        return render_template('browser/impressum.html')

    @app.route('/datenschutz')
    def datenschutz():
        return render_template('browser/datenschutz.html')

    return app
