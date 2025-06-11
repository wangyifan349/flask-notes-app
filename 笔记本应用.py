import random
import io
import re
import sqlite3
from flask import (
    Flask, render_template, redirect, url_for, request, flash, session, send_file, g
)
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageDraw, ImageFont
from markdown2 import markdown

app = Flask(__name__)
app.config['SECRET_KEY'] = '请使用强随机密钥替换我'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session_dir'
app.config['SESSION_PERMANENT'] = False
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
Session(app)

DATABASE = './notes.db'
USERNAME_RE = re.compile(r'^[a-zA-Z0-9]+$')

# -----------------------------
# 数据库相关函数
# -----------------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        g._database = db
    return db

@app.teardown_appcontext
def close_connection(exc):
    db = getattr(g, '_database', None)
    if db:
        db.close()

def init_db():
    db = get_db()
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    ''')
    db.commit()

# -----------------------------
# 验证码相关函数
# -----------------------------
def generate_captcha_text(length=4):
    return ''.join(random.choices('0123456789', k=length))

def generate_captcha_image(text):
    img = Image.new('RGB', (100, 40), color=(0,0,0))
    draw = ImageDraw.Draw(img)
    font_path = os.path.join(os.path.dirname(__file__), 'captcha_font', 'Arial.ttf')
    try:
        font = ImageFont.truetype(font_path, 30)
    except:
        font = ImageFont.load_default()
    draw.text((10, 3), text, font=font, fill=(255,0,0))  # 纯红色字体
    for _ in range(5):
        x1,y1=random.randint(0,100), random.randint(0,40)
        x2,y2=random.randint(0,100), random.randint(0,40)
        draw.line((x1,y1,x2,y2), fill=(180,20,30), width=1)
    return img

@app.route('/captcha')
def captcha():
    text = generate_captcha_text()
    session['captcha'] = text
    img = generate_captcha_image(text)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# -----------------------------
# 用户相关函数
# -----------------------------
def get_user_by_username(username):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()

def get_user_by_id(user_id):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()

def login_user(user):
    session['user_id'] = user['id']

def logout_user():
    session.pop('user_id', None)

def current_user():
    uid = session.get('user_id')
    if uid:
        return get_user_by_id(uid)
    return None

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            flash('请先登录', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_user_and_extensions():
    return dict(current_user=current_user(),
                extensions_enabled=session.get('enable_extensions', True))

# -----------------------------
# 辅助函数
# -----------------------------
def get_note(note_id, user_id):
    db = get_db()
    return db.execute('SELECT * FROM notes WHERE id=? AND user_id=?',(note_id,user_id)).fetchone()

# -----------------------------
# 路由定义
# -----------------------------

@app.route('/')
@login_required
def index():
    user = current_user()
    db = get_db()
    notes = db.execute('SELECT * FROM notes WHERE user_id=? ORDER BY id DESC', (user['id'],)).fetchall()
    return render_template('index.html', notes=notes)

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user():
        return redirect(url_for('index'))
    if request.method=='POST':
        username=request.form.get('username','').strip()
        password=request.form.get('password','').strip()
        password2=request.form.get('password2','').strip()
        captcha=request.form.get('captcha','').strip()
        error=None
        if not username or not password or not password2 or not captcha:
            error='所有字段必须填写'
        elif not USERNAME_RE.match(username):
            error='用户名只能由字母和数字组成'
        elif password!=password2:
            error='两次密码输入不一致'
        elif len(password)<6:
            error='密码长度至少6位'
        elif 'captcha' not in session or captcha.lower()!=session['captcha'].lower():
            error='验证码错误'
        elif get_user_by_username(username):
            error='用户名已存在'
        if error:
            flash(error,'danger')
            return render_template('register.html')
        pw_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password) VALUES (?,?)',(username, pw_hash))
            db.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名已存在','danger')
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user():
        return redirect(url_for('index'))
    if request.method=='POST':
        username=request.form.get('username','').strip()
        password=request.form.get('password','').strip()
        captcha=request.form.get('captcha','').strip()
        error=None
        if not username or not password or not captcha:
            error='所有字段必须填写'
        elif not USERNAME_RE.match(username):
            error='用户名只能由字母和数字组成'
        elif 'captcha' not in session or captcha.lower()!=session['captcha'].lower():
            error='验证码错误'
        else:
            user = get_user_by_username(username)
            if user and check_password_hash(user['password'], password):
                login_user(user)
                flash('登录成功', 'success')
                next_url = request.args.get('next')
                return redirect(next_url if next_url else url_for('index'))
            else:
                error='用户名或密码错误'
        if error:
            flash(error,'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已登出','info')
    return redirect(url_for('login'))

@app.route('/note/new', methods=['GET','POST'])
@login_required
def note_new():
    if request.method=='POST':
        title = request.form.get('title','').strip()
        content = request.form.get('content','').strip()
        if not title:
            flash('标题不能为空','warning')
            return render_template('note_edit.html', mode='新建', title=title, content=content)
        db = get_db()
        db.execute('INSERT INTO notes (user_id,title,content) VALUES (?,?,?)', (current_user()['id'], title, content))
        db.commit()
        flash('笔记创建成功','success')
        return redirect(url_for('index'))
    return render_template('note_edit.html', mode='新建')

@app.route('/note/<int:note_id>/edit', methods=['GET','POST'])
@login_required
def note_edit(note_id):
    note = get_note(note_id, current_user()['id'])
    if not note:
        flash('笔记未找到','danger')
        return redirect(url_for('index'))
    if request.method=='POST':
        title=request.form.get('title','').strip()
        content=request.form.get('content','').strip()
        if not title:
            flash('标题不能为空','warning')
            return render_template('note_edit.html', mode='编辑', note=note)
        db = get_db()
        db.execute('UPDATE notes SET title=?, content=? WHERE id=? AND user_id=?', (title, content, note_id, current_user()['id']))
        db.commit()
        flash('笔记更新成功','success')
        return redirect(url_for('index'))
    return render_template('note_edit.html', mode='编辑', note=note)

@app.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def note_delete(note_id):
    note = get_note(note_id, current_user()['id'])
    if not note:
        flash('笔记未找到','danger')
    else:
        db = get_db()
        db.execute('DELETE FROM notes WHERE id=? AND user_id=?', (note_id, current_user()['id']))
        db.commit()
        flash('笔记已删除','info')
    return redirect(url_for('index'))

@app.route('/note/<int:note_id>/rename', methods=['POST'])
@login_required
def note_rename(note_id):
    note = get_note(note_id, current_user()['id'])
    if not note:
        flash('笔记未找到','danger')
        return redirect(url_for('index'))
    new_title = request.form.get('new_title','').strip()
    if not new_title:
        flash('标题不能为空','warning')
    else:
        db = get_db()
        db.execute('UPDATE notes SET title=? WHERE id=? AND user_id=?', (new_title, note_id, current_user()['id']))
        db.commit()
        flash('重命名成功','success')
    return redirect(url_for('index'))

@app.route('/note/<int:note_id>')
@login_required
def note_view(note_id):
    note = get_note(note_id, current_user()['id'])
    if not note:
        flash('笔记未找到','danger')
        return redirect(url_for('index'))
    font = request.args.get('font', 'serif')
    enable_ext = session.get('enable_extensions', True)
    if enable_ext:
        extras=['fenced-code-blocks', 'tables', 'strike', 'math', 'footnotes']
    else:
        extras=[]
    html_content = markdown(note['content'] or '', extras=extras)
    return render_template('note_view.html', note=note, content=html_content, font_family=font, extensions_enabled=enable_ext)

@app.route('/toggle_extensions')
@login_required
def toggle_extensions():
    current = session.get('enable_extensions', True)
    session['enable_extensions'] = not current
    flash(f"扩展功能已{'启用' if session['enable_extensions'] else '关闭'}", 'info')
    return redirect(request.referrer or url_for('index'))

# -----------------------------
# 启动应用程序
# -----------------------------
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
```

---
`templates/base.html`
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <title>{% block title %}笔记系统{% endblock %}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />

    <!-- 引入 Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

    <style>
        /* 护眼模式样式 */
        body {
            background-color: #000000; /* 黑色背景 */
            color: #FF0000; /* 纯红色字体 */
            min-height: 100vh;
            padding: 20px 0;
            font-family: 'Arial', 'Helvetica Neue', Helvetica, 'WenQuanYi Micro Hei', 'DejaVu Sans', 'SimHei', 'Microsoft YaHei', sans-serif;
        }
        a, a:hover, a:visited {
            color: #FF4040;
        }
        .btn-danger {
            background-color: #FF0000;
            border-color: #FF0000;
        }
        .btn-danger:hover {
            background-color: #FF3333;
            border-color: #FF3333;
        }
        .form-control, .form-control:focus {
            background-color: #111;
            color: #FF0000;
            border: 1px solid #FF0000;
        }
        table {
            background-color: #1a1a1a;
            color: #FF0000;
        }
        th, td {
            border-color: #FF0000 !important;
            vertical-align: middle;
        }
        input::placeholder, textarea::placeholder {
            color: #FF6666;
        }
        .flash {
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
            font-weight: 600;
        }
        .flash-success {background: #330000; color: #ff8080;}
        .flash-danger {background: #440000; color: #ff4c4c;}
        .flash-info {background: #222222; color: #ff9a9a;}
        .flash-warning {background: #331111; color: #ff6666;}
        nav a {
            margin-right: 15px;
            font-weight: 600;
        }
        .btn.toggle-ext {
            vertical-align: middle;
            padding: 0 10px;
            border: 1px solid #FF0000;
            border-radius: 4px;
            font-size: 0.9rem;
            margin-left: 15px;
            color:#FF0000;
            background:none;
        }
        .btn.toggle-ext:hover {
            background-color: #440000;
        }
        img.captcha-img {
            cursor: pointer;
            border: 1px solid #FF0000;
            border-radius: 4px;
            margin-left: 8px;
        }
        .note-content pre {
            background-color: #330000;
            color: #ff7575;
            padding: 12px;
            border-radius: 5px;
            overflow-x: auto;
        }
        .form-inline {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
            align-items: center;
        }
        .font-select select {
            background-color: #222;
            color: #FF0000;
            border: 1px solid #FF0000;
            padding: 2px 6px;
            border-radius: 4px;
        }
    </style>
    {% block head %}{% endblock %}
</head>
<body>
<div class="container">
<nav class="mb-4">
{% if current_user %}
    <span>欢迎，{{ current_user['username'] }}</span> |
    <a href="{{ url_for('index') }}">笔记列表</a> |
    <a href="{{ url_for('note_new') }}">新建笔记</a> |
    <a href="{{ url_for('toggle_extensions') }}" class="btn toggle-ext" title="开关扩展功能">
        {% if extensions_enabled %}
            关闭扩展功能
        {% else %}
            启用扩展功能
        {% endif %}
    </a> |
    <a href="{{ url_for('logout') }}">登出</a>
{% else %}
    <a href="{{ url_for('login') }}">登录</a> |
    <a href="{{ url_for('register') }}">注册</a>
{% endif %}
</nav>

{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, msg in messages %}
          <div class="flash flash-{{ category }}">{{ msg }}</div>
        {% endfor %}
    {% endif %}
{% endwith %}

{% block content %}{% endblock %}
</div>
</body>
</html>
```
`templates/register.html`
```html
{% extends 'base.html' %}
{% block title %}注册{% endblock %}
{% block content %}
<h2 class="mb-4">用户注册</h2>
<form method="post" novalidate>
  <div class="mb-3">
    <label for="username" class="form-label">用户名（仅字母数字）</label>
    <input id="username" name="username" type="text" class="form-control" minlength="3" maxlength="30" required autofocus pattern="[A-Za-z0-9]+">
  </div>
  <div class="mb-3">
    <label for="password" class="form-label">密码（至少6位）</label>
    <input id="password" name="password" type="password" minlength="6" class="form-control" required>
  </div>
  <div class="mb-3">
    <label for="password2" class="form-label">确认密码</label>
    <input id="password2" name="password2" type="password" minlength="6" class="form-control" required>
  </div>
  <div class="mb-3 d-flex align-items-center">
    <div>
      <label for="captcha" class="form-label">验证码</label>
      <input id="captcha" name="captcha" type="text" minlength="4" maxlength="4" class="form-control" style="width: 100px;" required>
    </div>
    <img src="{{ url_for('captcha') }}" alt="验证码" class="captcha-img ms-3" title="点击刷新" onclick="this.src='{{ url_for('captcha') }}?'+Math.random()" />
  </div>
  <button type="submit" class="btn btn-danger">注册</button>
</form>
{% endblock %}
```

#### `templates/login.html`

```html
{% extends 'base.html' %}
{% block title %}登录{% endblock %}
{% block content %}
<h2 class="mb-4">用户登录</h2>
<form method="post" novalidate>
  <div class="mb-3">
    <label for="username" class="form-label">用户名</label>
    <input id="username" name="username" type="text" class="form-control" minlength="3" maxlength="30" required autofocus pattern="[A-Za-z0-9]+">
  </div>
  <div class="mb-3">
    <label for="password" class="form-label">密码</label>
    <input id="password" name="password" type="password" minlength="6" class="form-control" required>
  </div>
  <div class="mb-3 d-flex align-items-center">
    <div>
      <label for="captcha" class="form-label">验证码</label>
      <input id="captcha" name="captcha" type="text" minlength="4" maxlength="4" class="form-control" style="width: 100px;" required>
    </div>
    <img src="{{ url_for('captcha') }}" alt="验证码" class="captcha-img ms-3" title="点击刷新" onclick="this.src='{{ url_for('captcha') }}?'+Math.random()" />
  </div>
  <button type="submit" class="btn btn-danger">登录</button>
</form>
{% endblock %}
```

#### `templates/index.html`

```html
{% extends 'base.html' %}
{% block title %}笔记列表{% endblock %}
{% block content %}
<h2 class="mb-4">笔记列表</h2>

{% if notes|length == 0 %}
  <p>还没有笔记，<a href="{{ url_for('note_new') }}">新建一个</a></p>
{% else %}
<table class="table table-striped table-dark align-middle">
  <thead>
    <tr>
      <th>标题</th>
      <th style="width:360px;">操作</th>
    </tr>
  </thead>
  <tbody>
    {% for note in notes %}
    <tr>
      <td>{{ note['title'] }}</td>
      <td>
        <a href="{{ url_for('note_view', note_id=note['id']) }}" class="btn btn-sm btn-outline-danger me-1">阅览</a>
        <a href="{{ url_for('note_edit', note_id=note['id']) }}" class="btn btn-sm btn-outline-danger me-1">编辑</a>
        <form method="post" action="{{ url_for('note_rename', note_id=note['id']) }}" class="d-inline-flex me-1" style="vertical-align:middle;">
          <input type="text" name="new_title" placeholder="重命名" required minlength="1" maxlength="150"
                 class="form-control form-control-sm" style="width: 150px;" />
          <button type="submit" class="btn btn-sm btn-outline-danger ms-1">重命名</button>
        </form>
        <form method="post" action="{{ url_for('note_delete', note_id=note['id']) }}" class="d-inline" onsubmit="return confirm('确认删除《{{ note.title }}》吗?');">
          <button type="submit" class="btn btn-sm btn-danger">删除</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}
{% endblock %}
```

#### `templates/note_edit.html`

```html
{% extends 'base.html' %}
{% block title %}{{ mode }} 笔记{% endblock %}
{% block content %}
<h2 class="mb-4">{{ mode }} 笔记</h2>
<form method="post" novalidate>
  <div class="mb-3">
    <label for="title" class="form-label">标题</label>
    <input id="title" name="title" type="text" class="form-control" maxlength="150" required
           value="{% if note %}{{ note['title'] }}{% elif title is defined %}{{ title }}{% endif %}">
  </div>
  <div class="mb-3">
    <label for="content" class="form-label">内容 (支持 Markdown，可以插入视频音频 &lt;video&gt; &lt;audio&gt; HTML)</label>
    <textarea id="content" name="content" class="form-control" rows="15">{% if note %}{{ note['content'] }}{% elif content is defined %}{{ content }}{% endif %}</textarea>
  </div>
  <button type="submit" class="btn btn-danger">保存</button>
  <a href="{{ url_for('index') }}" class="btn btn-outline-danger ms-2">取消</a>
</form>
{% endblock %}
```

#### `templates/note_view.html`

```html
{% extends 'base.html' %}
{% block head %}
<style>
.note-content {
    font-family: {{ font_family|e }};
    background-color: #1a1a1a;
    padding: 15px;
    border-radius: 6px;
    box-shadow: 0 0 12px #660000;
    color: #FF0000;
    white-space: pre-wrap;
}
.note-content pre {
    background-color: #330000;
    color: #ff7878;
    padding: 12px;
    border-radius: 5px;
    overflow-x: auto;
}
</style>
{% if extensions_enabled %}
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" defer></script>
{% endif %}
{% endblock %}
{% block content %}
<h2 class="mb-3">{{ note['title'] }}</h2>
<div class="font-select mb-3">
    <label for="font-family" class="form-label me-2">字体：</label>
    <select id="font-family" onchange="changeFont()">
        <option value="serif" {% if font_family == 'serif' %}selected{% endif %}>Serif（衬线体）</option>
        <option value="sans-serif" {% if font_family == 'sans-serif' %}selected{% endif %}>Sans-serif（无衬线）</option>
        <option value="monospace" {% if font_family == 'monospace' %}selected{% endif %}>Monospace（等宽字体）</option>
        <option value="Arial, Helvetica, sans-serif" {% if font_family == 'Arial, Helvetica, sans-serif' %}selected{% endif %}>Arial</option>
        <option value="Courier New, monospace" {% if font_family == 'Courier New, monospace' %}selected{% endif %}>Courier New</option>
    </select>
</div>
<div class="note-content">{{ content|safe }}</div>
<a href="{{ url_for('index') }}" class="btn btn-outline-danger mt-4">返回列表</a>
<script>
function changeFont() {
    var font = document.getElementById('font-family').value;
    var params = new URLSearchParams(window.location.search);
    params.set('font', font);
    window.location.search = params.toString();
}
</script>
{% endblock %}
```
