from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---- 模型 ----
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def __repr__(self): return f'<User {self.username}>'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')
    def __repr__(self): return f'<Post {self.content[:20]}>'

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(140), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    def __repr__(self): return f'<Comment {self.content[:20]}>'

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# ---- 表单 ----
class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 20)])
    password = PasswordField('密码', validators=[DataRequired()])
    password2 = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册')
    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError('用户名已存在。')

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class PostForm(FlaskForm):
    content = TextAreaField('说说内容', validators=[DataRequired(), Length(1, 140)])
    submit = SubmitField('发表')

class CommentForm(FlaskForm):
    content = TextAreaField('评论内容', validators=[DataRequired(), Length(1, 140)])
    submit = SubmitField('评论')

class SearchUserForm(FlaskForm):
    username = StringField('搜索用户', validators=[DataRequired(), Length(1, 20)])
    submit = SubmitField('搜索')

# ---- 辅助函数 ----
def lcs_length(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1):
        for j in range(1,n+1):
            if s1[i-1].lower() == s2[j-1].lower(): dp[i][j] = dp[i-1][j-1] + 1
            else: dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]

# ---- 视图 ----

@app.route('/')
@login_required
def index():
    posts = Post.query.order_by(Post.timestamp.asc()).all() # 时间升序
    comment_forms = {}
    for post in posts: comment_forms[post.id] = CommentForm(prefix=f'c{post.id}')
    return render_template('index.html', posts=posts, comment_forms=comment_forms)

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('注册成功，欢迎！')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('登录成功！')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('用户名或密码错误。')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/post', methods=['GET','POST'])
@login_required
def post():
    form = PostForm()
    if form.validate_on_submit():
        p = Post(content=form.content.data, author=current_user)
        db.session.add(p)
        db.session.commit()
        flash('发表成功！')
        return redirect(url_for('index'))
    return render_template('post.html', form=form)

@app.route('/user/<username>')
@login_required
def user_posts(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = user.posts.order_by(Post.timestamp.asc()).all()
    comment_forms = {post.id: CommentForm(prefix=f'c{post.id}') for post in posts}
    return render_template('user_posts.html', posts=posts, user=user, comment_forms=comment_forms)

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
    return redirect(request.referrer or url_for('index'))

@app.route('/search', methods=['GET','POST'])
@login_required
def search():
    form = SearchUserForm()
    if form.validate_on_submit():
        keyword = form.username.data.strip()
        users = User.query.all()
        candidates = []
        for u in users:
            score = lcs_length(keyword, u.username)
            candidates.append((score,u))
        candidates.sort(key=lambda x:x[0], reverse=True)
        if not candidates or candidates[0][0] == 0:
            flash(f'用户 "{keyword}" 不存在。')
            return render_template('search.html', form=form)
        max_score = candidates[0][0]
        best_users = [u for score,u in candidates if score == max_score]
        return redirect(url_for('user_posts', username=best_users[0].username))
    return render_template('search.html', form=form)

# ---- 运行 ----
if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)



<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}我的Flask博客{% endblock %}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { padding-top: 70px; }
    .form-error { color: #dc3545; font-size: 0.875em; }
    .post-content { white-space: pre-wrap; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg fixed-top navbar-dark bg-primary">
  <div class="container">
    <a class="navbar-brand" href="{{ url_for('index') }}">Flask博客</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav"
      aria-controls="navbarNav" aria-expanded="false" aria-label="切换导航">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarNav">
      {% if current_user.is_authenticated %}
      <ul class="navbar-nav me-auto">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('index') }}">首页</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('post') }}">发表说说</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('user_posts', username=current_user.username) }}">我的说说</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('search') }}">搜索用户</a></li>
      </ul>
      <ul class="navbar-nav ms-auto">
        <li class="nav-item"><span class="navbar-text">欢迎，{{ current_user.username }}</span></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('logout') }}">登出</a></li>
      </ul>
      {% else %}
      <ul class="navbar-nav ms-auto">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('login') }}">登录</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('register') }}">注册</a></li>
      </ul>
      {% endif %}
    </div>
  </div>
</nav>

<div class="container">
  {% with messages = get_flashed_messages() %}
    {% if messages %}
    <div class="alert alert-info alert-dismissible fade show" role="alert">
      {% for message in messages %}
      <div>{{ message }}</div>
      {% endfor %}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="关闭"></button>
    </div>
    {% endif %}
  {% endwith %}

  {% block content %}{% endblock %}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
---

### 2. 首页 index.html — 列出所有说说和评论区
{% extends 'base.html' %}

{% block title %}首页 - Flask博客{% endblock %}

{% block content %}
<h1 class="mb-4">最新说说</h1>

{% for post in posts %}
<div class="card mb-4">
  <div class="card-body">
    <h5 class="card-title">{{ post.author.username }}</h5>
    <h6 class="card-subtitle mb-2 text-muted">{{ post.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</h6>
    <p class="card-text post-content">{{ post.content }}</p>

    <hr>
    <h6>评论：</h6>

    {% if post.comments.count() == 0 %}
      <p class="text-muted">还没有评论哦~</p>
    {% else %}
      {% for comment in post.comments.order_by('timestamp asc') %}
      <div class="mb-2">
        <strong>{{ comment.author.username }}</strong>
        <small class="text-muted">{{ comment.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</small>
        <p class="mb-0">{{ comment.content }}</p>
      </div>
      {% endfor %}
    {% endif %}

    <form method="post" action="{{ url_for('add_comment', post_id=post.id) }}" class="mt-3">
      {{ comment_forms[post.id].hidden_tag() }}
      <div class="mb-3">
        {{ comment_forms[post.id].content(class="form-control", rows="2", placeholder="写评论...") }}
        {% if comment_forms[post.id].content.errors %}
          <div class="form-error">{{ comment_forms[post.id].content.errors[0] }}</div>
        {% endif %}
      </div>
      <button type="submit" class="btn btn-sm btn-primary">{{ comment_forms[post.id].submit.label.text }}</button>
    </form>
  </div>
</div>
{% else %}
<p>还没有说说，快去发表吧！</p>
{% endfor %}
{% endblock %}
---

### 3. 用户说说页 user_posts.html — 显示某用户的所有说说和评论
{% extends 'base.html' %}

{% block title %}{{ user.username }} 的说说{% endblock %}

{% block content %}
<h2 class="mb-4">{{ user.username }} 的说说</h2>

{% for post in posts %}
<div class="card mb-4">
  <div class="card-body">
    <h6 class="card-subtitle mb-2 text-muted">{{ post.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</h6>
    <p class="card-text post-content">{{ post.content }}</p>

    <hr>
    <h6>评论：</h6>

    {% if post.comments.count() == 0 %}
      <p class="text-muted">还没有评论哦~</p>
    {% else %}
      {% for comment in post.comments.order_by('timestamp asc') %}
      <div class="mb-2">
        <strong>{{ comment.author.username }}</strong>
        <small class="text-muted">{{ comment.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</small>
        <p class="mb-0">{{ comment.content }}</p>
      </div>
      {% endfor %}
    {% endif %}

    <form method="post" action="{{ url_for('add_comment', post_id=post.id) }}" class="mt-3">
      {{ comment_forms[post.id].hidden_tag() }}
      <div class="mb-3">
        {{ comment_forms[post.id].content(class="form-control", rows="2", placeholder="写评论...") }}
        {% if comment_forms[post.id].content.errors %}
          <div class="form-error">{{ comment_forms[post.id].content.errors[0] }}</div>
        {% endif %}
      </div>
      <button type="submit" class="btn btn-sm btn-primary">{{ comment_forms[post.id].submit.label.text }}</button>
    </form>
  </div>
</div>
{% else %}
<p>该用户还没有发表说说。</p>
{% endfor %}
{% endblock %}

---

### 4. 发表说说 post.html — 发布新说说
{% extends 'base.html' %}

{% block title %}发表说说{% endblock %}

{% block content %}
<h2>发表说说</h2>
<form method="post">
  {{ form.hidden_tag() }}
  <div class="mb-3">
    {{ form.content.label(class="form-label") }}
    {{ form.content(class="form-control", rows=4, placeholder="写点什么吧...") }}
    {% if form.content.errors %}
      <div class="form-error">{{ form.content.errors[0] }}</div>
    {% endif %}
  </div>
  <button type="submit" class="btn btn-primary">{{ form.submit.label.text }}</button>
</form>
{% endblock %}
```

---

### 5. 登录 login.html

{% extends 'base.html' %}

{% block title %}登录{% endblock %}

{% block content %}
<h2>登录</h2>
<form method="post" class="w-50 mx-auto">
  {{ form.hidden_tag() }}
  <div class="mb-3">
    {{ form.username.label(class="form-label") }}
    {{ form.username(class="form-control") }}
    {% if form.username.errors %}
      <div class="form-error">{{ form.username.errors[0] }}</div>
    {% endif %}
  </div>
  <div class="mb-3">
    {{ form.password.label(class="form-label") }}
    {{ form.password(class="form-control") }}
    {% if form.password.errors %}
      <div class="form-error">{{ form.password.errors[0] }}</div>
    {% endif %}
  </div>
  <button type="submit" class="btn btn-primary">{{ form.submit.label.text }}</button>
</form>
<p class="text-center mt-3">还没有账户？<a href="{{ url_for('register') }}">注册一个</a></p>
{% endblock %}

---

### 6. 注册 register.html
{% extends 'base.html' %}

{% block title %}注册{% endblock %}

{% block content %}
<h2>注册</h2>
<form method="post" class="w-50 mx-auto">
  {{ form.hidden_tag() }}

  <div class="mb-3">
    {{ form.username.label(class="form-label") }}
    {{ form.username(class="form-control") }}
    {% if form.username.errors %}
      <div class="form-error">{{ form.username.errors[0] }}</div>
    {% endif %}
  </div>

  <div class="mb-3">
    {{ form.password.label(class="form-label") }}
    {{ form.password(class="form-control") }}
    {% if form.password.errors %}
      <div class="form-error">{{ form.password.errors[0] }}</div>
    {% endif %}
  </div>

  <div class="mb-3">
    {{ form.password2.label(class="form-label") }}
    {{ form.password2(class="form-control") }}
    {% if form.password2.errors %}
      <div class="form-error">{{ form.password2.errors[0] }}</div>
    {% endif %}
  </div>

  <button type="submit" class="btn btn-primary">{{ form.submit.label.text }}</button>
</form>
<p class="text-center mt-3">已有账户？<a href="{{ url_for('login') }}">登录</a></p>
{% endblock %}
---

### 7. 搜索 search.html
{% extends 'base.html' %}

{% block title %}搜索用户{% endblock %}

{% block content %}
<h2>搜索用户</h2>
<form method="post" class="w-50 mx-auto">
  {{ form.hidden_tag() }}
  <div class="mb-3">
    {{ form.username.label(class="form-label") }}
    {{ form.username(class="form-control", placeholder="输入用户名") }}
    {% if form.username.errors %}
      <div class="form-error">{{ form.username.errors[0] }}</div>
    {% endif %}
  </div>
  <button type="submit" class="btn btn-primary">{{ form.submit.label.text }}</button>
</form>
{% endblock %}
