import os
from datetime import datetime, date

from flask import (
    Flask, redirect, url_for, flash, request, abort
)
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError

from jinja2 import Template

# ----- 初始化 -----

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-please-change'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shuoshuo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # 未登录重定向到 login


# ----- 模板列表（name: content）-----

_templates = {
    'base.html': '''
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>{% block title %}说说应用{% endblock %}</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; }
    nav a { margin-right: 10px; }
    .flash { background: #ffd; padding: 8px; margin-bottom: 15px; border: 1px solid #dda; }
    textarea { font-family: inherit; }
    button { cursor: pointer; }
    form.inline { display: inline; }
  </style>
</head>
<body>
  <nav>
    {% if current_user.is_authenticated %}
      <span>登录用户：<strong>{{ current_user.username }}</strong></span> |
      <a href="{{ url_for('index') }}">首页</a> |
      <a href="{{ url_for('new_post') }}">发说说</a> |
      <a href="{{ url_for('search') }}">搜索用户</a> |
      <a href="{{ url_for('logout') }}">退出</a>
    {% else %}
      <a href="{{ url_for('login') }}">登录</a> |
      <a href="{{ url_for('register') }}">注册</a>
    {% endif %}
  </nav>

  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="flash">
        {% for msg in messages %}
          <p>{{ msg }}</p>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}

  {% block content %}{% endblock %}
</body>
</html>
''',

    'index.html': '''
{% extends 'base.html' %}
{% block title %}首页 - 说说{% endblock %}
{% block content %}
  <h1>最新说说</h1>
  {% for post in posts %}
    <div style="border:1px solid #aaa; margin-bottom:20px; padding:10px;">
      <p>
        <a href="{{ url_for('user_posts', username=post.author.username) }}"><strong>{{ post.author.username }}</strong></a>
        发表于 {{ post.timestamp.strftime('%Y-%m-%d %H:%M') }}
      </p>
      <p>{{ post.content | e }}</p>
      {% if post.author == current_user %}
        <p>
          {% if post.timestamp.date() == current_time.date() %}
            <a href="{{ url_for('edit_post', post_id=post.id) }}">编辑</a> |
          {% endif %}
          <form method="post" action="{{ url_for('delete_post', post_id=post.id) }}" class="inline" onsubmit="return confirm('确认删除这条说说？');">
            <button type="submit">删除</button>
          </form>
        </p>
      {% endif %}

      <h4>评论</h4>
      {% for comment in post.comments.order_by(Comment.timestamp.asc()) %}
        <p><strong>{{ comment.author.username }}</strong> {{ comment.timestamp.strftime('%Y-%m-%d %H:%M') }} : {{ comment.content | e }}</p>
      {% endfor %}
      <form action="{{ url_for('add_comment', post_id=post.id) }}" method="post">
        {{ comment_forms[post.id].hidden_tag() }}
        {{ comment_forms[post.id].content(rows=2, cols=60) }}
        {{ comment_forms[post.id].submit() }}
      </form>
    </div>
  {% else %}
    <p>暂时没有说说，快去发一条吧！</p>
  {% endfor %}
{% endblock %}
''',

    'register.html': '''
{% extends "base.html" %}
{% block title %}注册{% endblock %}
{% block content %}
  <h1>注册新用户</h1>
  <form method="post" novalidate>
    {{ form.hidden_tag() }}
    <p>
      {{ form.username.label }}<br>
      {{ form.username(size=32) }}<br>
      {% for err in form.username.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>
      {{ form.password.label }}<br>
      {{ form.password(size=32) }}<br>
      {% for err in form.password.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>
      {{ form.password2.label }}<br>
      {{ form.password2(size=32) }}<br>
      {% for err in form.password2.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>{{ form.submit() }}</p>
  </form>
  <p>已有账号？<a href="{{ url_for('login') }}">登录</a></p>
{% endblock %}
''',

    'login.html': '''
{% extends "base.html" %}
{% block title %}登录{% endblock %}
{% block content %}
  <h1>登录</h1>
  <form method="post" novalidate>
    {{ form.hidden_tag() }}
    <p>
      {{ form.username.label }}<br>
      {{ form.username(size=32) }}<br>
      {% for err in form.username.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>
      {{ form.password.label }}<br>
      {{ form.password(size=32) }}<br>
      {% for err in form.password.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>{{ form.submit() }}</p>
  </form>
  <p>没有账号？<a href="{{ url_for('register') }}">注册</a></p>
{% endblock %}
''',

    'new_post.html': '''
{% extends "base.html" %}
{% block title %}发说说{% endblock %}
{% block content %}
  <h1>发布新说说</h1>
  <form method="post" novalidate>
    {{ form.hidden_tag() }}
    <p>
      {{ form.content.label }}<br>
      {{ form.content(rows=5, cols=60) }}<br>
      {% for err in form.content.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>{{ form.submit() }}</p>
  </form>
{% endblock %}
''',

    'edit_post.html': '''
{% extends "base.html" %}
{% block title %}编辑说说{% endblock %}
{% block content %}
  <h1>编辑说说（限当天）</h1>
  <form method="post" novalidate>
    {{ form.hidden_tag() }}
    <p>
      {{ form.content.label }}<br>
      {{ form.content(rows=5, cols=60) }}<br>
      {% for err in form.content.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>{{ form.submit() }}</p>
  </form>
{% endblock %}
''',

    'user_posts.html': '''
{% extends "base.html" %}
{% block title %}{{ user.username }} 的说说{% endblock %}
{% block content %}
  <h1>{{ user.username }} 的说说</h1>

  {% if posts %}
    {% for post in posts %}
      <div style="border:1px solid #aaa; margin-bottom:20px; padding:10px;">
        <p>
          {{ post.timestamp.strftime('%Y-%m-%d %H:%M') }}
          {% if post.author == current_user %}
            （你发的）
          {% endif %}
        </p>
        <p>{{ post.content | e }}</p>
        {% if post.author == current_user %}
          <p>
            {% if post.timestamp.date() == current_time.date() %}
              <a href="{{ url_for('edit_post', post_id=post.id) }}">编辑</a> |
            {% endif %}
            <form method="post" action="{{ url_for('delete_post', post_id=post.id) }}" class="inline" onsubmit="return confirm('确认删除这条说说？');">
              <button type="submit">删除</button>
            </form>
          </p>
        {% endif %}

        <h4>评论</h4>
        {% for comment in post.comments.order_by(Comment.timestamp.asc()) %}
          <p><strong>{{ comment.author.username }}</strong> {{ comment.timestamp.strftime('%Y-%m-%d %H:%M') }} : {{ comment.content | e }}</p>
        {% endfor %}
        <form action="{{ url_for('add_comment', post_id=post.id) }}" method="post">
          {{ comment_forms[post.id].hidden_tag() }}
          {{ comment_forms[post.id].content(rows=2, cols=60) }}
          {{ comment_forms[post.id].submit() }}
        </form>
      </div>
    {% endfor %}
  {% else %}
    <p>该用户尚未发表说说。</p>
  {% endif %}

{% endblock %}
''',

    'search.html': '''
{% extends "base.html" %}
{% block title %}搜索用户{% endblock %}
{% block content %}
  <h1>搜索用户</h1>
  <form method="post" novalidate>
    {{ form.hidden_tag() }}
    <p>
      {{ form.username.label }}<br>
      {{ form.username(size=32) }}<br>
      {% for err in form.username.errors %}
        <span style="color:red;">{{ err }}</span><br>
      {% endfor %}
    </p>
    <p>{{ form.submit() }}</p>
  </form>
{% endblock %}
''',

    '403.html': '''
{% extends "base.html" %}
{% block title %}无权限{% endblock %}
{% block content %}
  <h1>403 - 无权限访问</h1>
  <p>您没有权限访问此页面。</p>
  <p><a href="{{ url_for('index') }}">返回首页</a></p>
{% endblock %}
''',

    '404.html': '''
{% extends "base.html" %}
{% block title %}页面未找到{% endblock %}
{% block content %}
  <h1>404 - 页面未找到</h1>
  <p>抱歉，您访问的页面不存在。</p>
  <p><a href="{{ url_for('index') }}">返回首页</a></p>
{% endblock %}
''',
}


# ----- 自定义render_template，利用模板字典 -----

def render_template(name, **context):
    # 递归渲染支持inherit（简易版）
    # 先载入模板对象
    tpl_source = _templates.get(name)
    if not tpl_source:
        abort(500, '未找到模板: ' + name)
    # 这里我们用 jinja2.Template简单render，继承需要渲染全部层级，稍作处理：
    # python-jinja2 支持在 Template 实例里通过 environment 找到加载器，但这里自定义字典，故重载父模板加载

    # 简单实现模板继承：
    from jinja2 import Environment, DictLoader, select_autoescape

    env = Environment(
        loader=DictLoader(_templates),
        autoescape=select_autoescape(['html', 'xml'])
    )
    template = env.get_template(name)
    return template.render(context)


# ----- 数据模型 -----

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    posts = db.relationship('Post', backref='author', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    comments = db.relationship('Comment', backref='post', cascade="all,delete", lazy='dynamic')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----- 表单 -----

class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(3, 50)])
    password = PasswordField('密码', validators=[DataRequired(), Length(6, 128)])
    password2 = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('用户名已被使用，请更换。')


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')


class PostForm(FlaskForm):
    content = TextAreaField('说说内容', validators=[DataRequired(), Length(1, 500)])
    submit = SubmitField('提交')


class CommentForm(FlaskForm):
    content = TextAreaField('评论内容', validators=[DataRequired(), Length(1, 300)])
    submit = SubmitField('发表评论')


class SearchUserForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 50)])
    submit = SubmitField('搜索')


# ----- 路由 -----

@app.route('/')
@login_required
def index():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    comment_forms = {post.id: CommentForm(prefix=f'c{post.id}') for post in posts}
    current_time = datetime.utcnow()
    return render_template(
        'index.html',
        posts=posts,
        comment_forms=comment_forms,
        current_time=current_time
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('您已登录')
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录。')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('您已登录')
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('登录成功')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录')
    return redirect(url_for('login'))


@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('说说发布成功！')
        return redirect(url_for('index'))
    return render_template('new_post.html', form=form)


@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    # 只能在当天编辑
    if post.timestamp.date() != date.today():
        flash('只能在说说发布当天修改内容。')
        return redirect(url_for('index'))
    form = PostForm()
    if form.validate_on_submit():
        post.content = form.content.data
        db.session.commit()
        flash('说说修改成功！')
        return redirect(url_for('index'))
    elif request.method == 'GET':
        form.content.data = post.content
    return render_template('edit_post.html', form=form)


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('说说已删除！')
    return redirect(url_for('index'))


@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm(prefix=f'c{post_id}')
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash('评论成功！')
    else:
        flash('评论内容不能为空。')
    return redirect(url_for('index'))


@app.route('/user/<username>')
@login_required
def user_posts(username):
    """查看指定用户名的所有说说"""
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.timestamp.desc()).all()
    comment_forms = {post.id: CommentForm(prefix=f'c{post.id}') for post in posts}
    current_time = datetime.utcnow()
    return render_template(
        'user_posts.html',
        posts=posts,
        user=user,
        comment_forms=comment_forms,
        current_time=current_time
    )


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    form = SearchUserForm()
    if form.validate_on_submit():
        username = form.username.data
        user = User.query.filter_by(username=username).first()
        if user:
            return redirect(url_for('user_posts', username=user.username))
        else:
            flash(f'用户 "{username}" 不存在。')
    return render_template('search.html', form=form)


# ----- 错误处理 -----

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# ----- 入口 -----

if __name__ == '__main__':
    if not os.path.exists('shuoshuo.db'):
        db.create_all()
        print('数据库已创建')
    app.run(debug=True)
