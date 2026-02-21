from flask import Flask, render_template
from config import Config
from app.extensions import db, migrate, bcrypt, login_manager, http_auth, mail, cors

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    cors.init_app(app)

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

    # Register blueprints
    from app.blueprints.visio import bp as visio_bp
    app.register_blueprint(visio_bp)

    from app.blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.blueprints.account import bp as account_bp
    app.register_blueprint(account_bp)

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
