import os
from decouple import config

basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = config('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = config('DATABASE_URI') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = config('MAIL_SERVER')
    MAIL_PORT = config('MAIL_PORT')
    MAIL_USE_TLS = config('MAIL_USE_TLS')
    #MAIL_USE_SSL = config('MAIL_USE_SSL')
    MAIL_USERNAME = config('MAIL_USERNAME')
    MAIL_PASSWORD = config('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = config('MAIL_DEFAULT_SENDER')
    MAX_FORM_MEMORY_SIZE = config('MAX_FORM_MEMORY_SIZE', default=16 * 1024 * 1024, cast=int)  # 16 MB
    MAX_CONTENT_LENGTH = config('MAX_CONTENT_LENGTH', default=100 * 1024 * 1024, cast=int)    # 100 MB