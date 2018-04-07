# coding:utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, TextAreaField, Form
from wtforms.validators import DataRequired, Length
from app.models import User


# DataRequired 验证器只是简单地检查相应域提交的数据是否是空


class LoginForm(FlaskForm):
    openid = StringField('openid', validators=[DataRequired()])
    remember_me = BooleanField('remember_me', default=False)


class EditForm(FlaskForm):
    nickname = StringField('nickname', validators=[DataRequired()])
    about_me = TextAreaField('about_me', validators=[Length(min=0, max=140)])

    def __init__(self, original_nickname, *args, **kwargs):
        super(EditForm, self).__init__(*args, **kwargs)
        self.original_nickname = original_nickname

    def validate(self):
        if not Form.validate(self):
            return False
        if self.nickname.data == self.original_nickname:
            return True
        user = User.query.filter_by(nickname=self.nickname.data).first()
        if user is not None:
            self.nickname.errors.append('This nickname is already in use. Please choose another one.')
            return False
        return True


class PostForm(FlaskForm):
    post = StringField('post', validators=[DataRequired()], render_kw={'style': 'width:98%'})

class SearchForm(FlaskForm):
    search = StringField('search', validators=[DataRequired()], render_kw={'placeholder': 'Search', 'class': 'search-query'})
