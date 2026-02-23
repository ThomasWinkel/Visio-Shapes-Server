from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_httpauth import HTTPTokenAuth
from flask_mail import Mail
from flask_cors import CORS
from flask_babel import Babel

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
bcrypt = Bcrypt()
login_manager = LoginManager()
http_auth = HTTPTokenAuth()
mail = Mail()
cors = CORS()
babel = Babel()