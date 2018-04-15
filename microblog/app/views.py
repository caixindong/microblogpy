# coding:utf-8
from datetime import datetime
from flask import render_template, flash, redirect, session, url_for, request, g, jsonify, abort
from flask_login import login_user, logout_user, current_user, login_required
from app import app, lm, oid, db
from .forms import LoginForm, EditForm, PostForm, SearchForm
from .models import User, Post, Blog
from config import POSTS_PER_PAGE, MAX_SEARCH_RESULTS
from .emails import follower_notification
from config import DATABASE_QUERY_TIMEOUT
from flask_sqlalchemy import get_debug_queries


# 两个 route 装饰器创建了从网址 / 以及 /index 到这个函数的映射
# render_template 调用了 Jinja2 模板引擎，Jinja2 模板引擎是 Flask 框架的一部分。Jinja2 会把模板参数提供的相应的值替换了 {{…}} 块。
# login_required 装饰器,这确保了这页只被已经登录的用户看到
@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@app.route('/index/<int:page>', methods=['GET', 'POST'])
@login_required
def index(page=1):
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, timestamp=datetime.utcnow(), author=g.user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    # paginate用于分页，从第1页开始，每页展示3篇，错误标志。
    # 如果是 True，当请求的范围页超出范围的话，一个 404 错误将会自动地返回到客户端的网页浏览器。
    # 如果是 False，返回一个空列表而不是错误。
    posts = g.user.followed_posts().paginate(page, POSTS_PER_PAGE, False)
    return render_template('index.html',
                           title='Home',
                           form=form,
                           posts=posts)


# oid.loginhandle 告诉 Flask-OpenID 这是我们的登录视图函数
@app.route('/login', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    # flask.g 全局变量是一个在请求生命周期中用来存储和共享数据
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    # validate_on_submit 在表单提交请求中被调用，它将会收集所有的数据,对字段进行验证，
    # 如果所有的事情都通过的话，它将会返回 True，
    # 至少一个字段验证失败的话，它将会返回 False，接着表单会重新呈现给用户
    if form.validate_on_submit():
        # flask.session 提供了一个更加复杂的服务对于存储和共享数据,数据保持在会话中直到会话被明确地删除
        session['remember_me'] = form.remember_me.data
        # oid.try_login 被调用是为了触发用户使用 Flask-OpenID 认证
        return oid.try_login(form.openid.data, ask_for=['nickname', 'email'])
    return render_template('login.html',
                           title='Sign In',
                           form=form,
                           providers=app.config['OPENID_PROVIDERS'])


@lm.user_loader
def load_user(id):
    return User.query.get(int(id))


# resp 参数传入给 after_login 函数，它包含了从 OpenID 提供商返回来的信息。
@oid.after_login
def after_login(resp):
    if resp.email is None or resp.email == "":
        flash('Invalid login. Please try again.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=resp.email).first()
    if user is None:
        nickname = resp.nickname
        if nickname is None or nickname == "":
            nickname = resp.email.split('@')[0]
        nickname = User.make_unique_nickname(nickname)
        user = User(nickname=nickname, email=resp.email)
        db.session.add(user)
        db.session.commit()
        # follow self
        db.session.add(user.follow(user))
        db.session.commit()
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        # 删除session的键值
        session.pop('remember_me', None)
    login_user(user, remember=remember_me)
    return redirect(request.args.get('next') or url_for('index'))


# before_request 装饰器的函数在接收请求之前都会运行
@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated:
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/user/<nickname>')
@app.route('/user/<nickname>/<int:page>')
@login_required
def user(nickname, page=1):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('index'))
    posts = user.posts.paginate(page, POSTS_PER_PAGE, False)
    return render_template('user.html',
                           user=user,
                           posts=posts)


@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    form = EditForm(g.user.nickname)
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.about_me = form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    else:
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me
    return render_template('edit.html',
                           form=form)


@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    # 如果异常是被一个数据库错误触发，数据库的会话会处于一个不正常的状态，
    # 因此我们必须把会话回滚到正常工作状态在渲染 500 错误页模板之前。
    db.session.rollback()
    return render_template('500.html'), 500


@app.route('/follow/<nickname>')
@login_required
def follow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t follow yourself!')
        return redirect(url_for('user', nickname=nickname))
    u = g.user.follow(user)
    if u is None:
        flash('Cannot follow ' + nickname + '.')
        return redirect(url_for('user', nickname=nickname))
    db.session.add(u)
    db.session.commit()
    flash('You are now following ' + nickname + '!')
    follower_notification(user, g.user)
    return redirect(url_for('user', nickname=nickname))


@app.route('/unfollow/<nickname>')
@login_required
def unfollow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t unfollow yourself!')
        return redirect(url_for('user', nickname=nickname))
    u = g.user.unfollow(user)
    if u is None:
        flash('Cannot unfollow ' + nickname + '.')
        return redirect(url_for('user', nickname=nickname))
    db.session.add(u)
    db.session.commit()
    flash('You have stopped following ' + nickname + '.')
    return redirect(url_for('user', nickname=nickname))


@app.route('/search', methods=['POST'])
@login_required
def search():
    if not g.search_form.validate_on_submit():
        return redirect(url_for('index'))
    return redirect(url_for('search_results', query=g.search_form.search.data))


@app.route('/search_results/<query>')
@login_required
def search_results(query):
    results = Post.query.whoosh_search(query, MAX_SEARCH_RESULTS).all()
    return render_template('search_results.html',
                           query=query,
                           results=results)


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    post = Post.query.get(id)
    if post is None:
        flash('Post not found')
        return redirect(url_for('index'))
    if post.author.id != g.user.id:
        flash('You cannot delete this post')
        return redirect(url_for('index'))
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted.')
    return redirect(url_for('index'))


@app.after_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= DATABASE_QUERY_TIMEOUT:
            app.logger.warning("SLOW QUERY: %s\nParameters: %s\nDuration: %fs\nContext: %s\n" % (
                query.statement, query.parameters, query.duration, query.context))
    return response


@app.route('/api/tasks', methods=['GET'])
def getTasks():
    tasks = [
        {
            'id': 1,
            'msg': 'help'
        },
        {
            'id': 2,
            'msg': 'no'
        }
    ]
    return jsonify({'tasks': tasks})


@app.route('/api/tasks/p', methods=['POST'])
def posttasks():
    if not request.json or not 'title' in request.json:
        abort(400)
    task = {
        'title': request.json['title'],
        'des': request.json.get('des', ''),
        'done': False
    }
    return jsonify({'tasks': [task]}), 201


@app.route('/api/blog/', methods=['POST'])
@login_required
def createblog():
    # import pdb;pdb.set_trace()
    if not request.json:
        abort(404)
    if not 'title' in request.json:
        abort(404)
    if not 'content' in request.json:
        abort(404)
    blog = Blog(title=request.json['title'], content=request.json['content'], timestamp=datetime.utcnow(), author=g.user)
    db.session.add(blog)
    db.session.commit()
    return jsonify({'code': 0}), 200


@app.route('/api/bloglist/<int:page>', methods=['GET'])
@login_required
def getblogs(page):
    # import pdb;pdb.set_trace()
    blogs = g.user.blogs.paginate(page, POSTS_PER_PAGE, False).items
    bloglist = []
    for blog in blogs:
        blogjson = blog.toJSON()
        bloglist.append(blogjson)
    return jsonify({'code': 0,
                    'result': {
                        'blogs': bloglist
                    }})



@app.route('/newblog', methods=['GET'])
@login_required
def newblog():
    return render_template('create_blog.html',
                           title='New blog')


@app.route('/bloglist', methods=['GET'])
@app.route('/bloglist/<int:page>', methods=['GET'])
@login_required
def bloglist(page=1):
    return render_template('blog_list.html',
                           title='blog list',
                           page=page)

@app.route('/test', methods=['GET'])
@login_required
def test():
    return render_template('test2.html')
