# coding:utf-8
# 模块初始化脚本
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_openid import OpenID
from config import basedir, ADMINS, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
from flask_mail import Mail
from .momentjs import momentjs
from flask_babel import Babel
from flask_cors import CORS
from flask_restful import Api

app = Flask(__name__)

app.config.from_object('config')

db = SQLAlchemy(app)

lm = LoginManager()
lm.init_app(app)
# Flask-Login 需要知道哪个视图允许用户登录
lm.login_view = 'login'

oid = OpenID(app, os.path.join(basedir, 'tmp'))

if not app.debug:
    import logging
    from logging.handlers import SMTPHandler

    credential = None
    if MAIL_USERNAME or MAIL_PASSWORD:
        credential = (MAIL_USERNAME, MAIL_PASSWORD)
    mail_handler = SMTPHandler((MAIL_SERVER, MAIL_PORT), 'no-reply@' + MAIL_SERVER, ADMINS, 'microblog failure',
                               credential)
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler

    # 日志文件的大小限制在 1 兆，我们将保留最后 10 个日志文件作为备份
    file_handler = RotatingFileHandler('tmp/microblog.log', 'a', 1 * 1024 * 1024, 10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('microblog startup')

mail = Mail(app)

app.jinja_env.globals['momentjs'] = momentjs

babel = Babel(app)

CORS(app)

api = Api(app)

# 这句话放最后
from app import views, models
