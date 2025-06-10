import os
import random
import string
from flask import Flask, request, redirect, url_for, render_template_string, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, FileField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64

# 创建 Flask 应用
app = Flask(__name__)

# 配置项
app.config['SECRET_KEY'] = 'your_secret_key'  # 请替换为您的密钥
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # 数据库 URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭追踪修改
app.config['UPLOAD_FOLDER'] = 'uploads'  # 文件上传目录
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 最大上传文件大小为 100MB

# 初始化扩展
db = SQLAlchemy(app)  # 数据库
login_manager = LoginManager(app)  # 登录管理
login_manager.login_view = 'login'  # 未登录时重定向到登录页面
csrf = CSRFProtect(app)  # CSRF 防护

# 设置允许上传的文件扩展名
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv'}

# 加载用户的回调函数
@login_manager.user_loader
def load_user(user_id):
    """根据用户 ID 加载用户对象"""
    return User.query.get(int(user_id))

# 数据库模型
class User(db.Model, UserMixin):
    """用户模型，包含用户名和密码哈希"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)  # 用户名
    password_hash = db.Column(db.String(128), nullable=False)  # 密码哈希
    videos = db.relationship('Video', backref='author', lazy=True)  # 关联用户上传的视频

    def set_password(self, password):
        """设置密码哈希值"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """检查密码是否正确"""
        return check_password_hash(self.password_hash, password)

class Video(db.Model):
    """视频模型，包含视频标题、文件名和所属用户"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)  # 视频标题
    filename = db.Column(db.String(150), nullable=False)  # 文件名
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 所属用户 ID

# 表单
class RegistrationForm(FlaskForm):
    """注册表单"""
    username = StringField('用户名', validators=[DataRequired(), Length(2, 20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(6, 20)])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    captcha = StringField('验证码', validators=[DataRequired(), Length(4, 4)])
    submit = SubmitField('注册')

class LoginForm(FlaskForm):
    """登录表单"""
    username = StringField('用户名', validators=[DataRequired(), Length(2, 20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(6, 20)])
    captcha = StringField('验证码', validators=[DataRequired(), Length(4, 4)])
    submit = SubmitField('登录')

# 辅助函数
def generate_captcha():
    """生成验证码图片及对应的文本"""
    # 随机生成4位验证码
    captcha_text = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    # 创建图片
    image = Image.new('RGB', (100, 30), color=(255, 255, 255))
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(image)
    draw.text((10, 5), captcha_text, font=font, fill=(0, 0, 0))
    # 将图片转换为 Base64 编码
    buffer = BytesIO()
    image.save(buffer, format='png')
    image_data = base64.b64encode(buffer.getvalue()).decode()
    return captcha_text, image_data

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def longest_common_subsequence(s1, s2):
    """计算两个字符串的最长公共子序列长度"""
    m, n = len(s1), len(s2)
    dp = [0] * (n + 1)
    for i in range(m):
        prev = 0
        for j in range(n):
            temp = dp[j + 1]
            if s1[i] == s2[j]:
                dp[j + 1] = prev + 1
            else:
                dp[j + 1] = max(dp[j], dp[j + 1])
            prev = temp
    return dp[n]

# 路由
@app.route('/')
def index():
    """主页，重定向到登录或用户主页"""
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    form = RegistrationForm()
    if request.method == 'GET':
        # 生成新的验证码
        captcha_text, captcha_image = generate_captcha()
        session['captcha'] = captcha_text  # 将验证码文本存储在 session 中
    else:
        captcha_image = None

    if form.validate_on_submit():
        # 验证码校验
        if form.captcha.data.lower() != session.get('captcha', '').lower():
            flash('验证码错误', 'danger')
            return render_template_string(register_template, form=form, captcha_image=captcha_image)
        # 检查用户名是否已存在
        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在', 'danger')
            return render_template_string(register_template, form=form, captcha_image=captcha_image)
        # 创建新用户
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))

    return render_template_string(register_template, form=form, captcha_image=captcha_image)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    form = LoginForm()
    if request.method == 'GET':
        # 生成新的验证码
        captcha_text, captcha_image = generate_captcha()
        session['captcha'] = captcha_text
    else:
        captcha_image = None

    if form.validate_on_submit():
        # 验证码校验
        if form.captcha.data.lower() != session.get('captcha', '').lower():
            flash('验证码错误', 'danger')
            return render_template_string(login_template, form=form, captcha_image=captcha_image)
        # 检查用户
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('登录成功', 'success')
            return redirect(url_for('dashboard'))
        flash('用户名或密码错误', 'danger')

    return render_template_string(login_template, form=form, captcha_image=captcha_image)

@app.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    flash('您已登出', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """用户主页"""
    return render_template_string(dashboard_template)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    """处理视频上传的 AJAX 请求"""
    file = request.files.get('file')
    title = request.form.get('title', '').strip()
    if not file or not title:
        return jsonify({'status': 'error', 'message': '缺少必要的参数'}), 400
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '未选择文件'}), 400
    if not allowed_file(file.filename):
        return jsonify({'status': 'error', 'message': '文件类型不允许'}), 400

    # 保存文件
    filename = secure_filename(file.filename)
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
    os.makedirs(user_folder, exist_ok=True)
    file_path = os.path.join(user_folder, filename)
    file.save(file_path)

    # 保存视频信息到数据库
    new_video = Video(title=title, filename=filename, user_id=current_user.id)
    db.session.add(new_video)
    db.session.commit()

    return jsonify({'status': 'success', 'message': '文件上传成功'})

@app.route('/my_videos')
@login_required
def my_videos():
    """显示用户的所有视频"""
    videos = Video.query.filter_by(user_id=current_user.id).all()
    return render_template_string(my_videos_template, videos=videos)

@app.route('/delete_video', methods=['POST'])
@login_required
def delete_video():
    """处理删除视频的 AJAX 请求"""
    video_id = request.form.get('video_id', type=int)
    video = Video.query.get(video_id)
    if not video or video.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': '未找到视频或没有权限'}), 400

    # 删除文件
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
    file_path = os.path.join(user_folder, video.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # 删除数据库记录
    db.session.delete(video)
    db.session.commit()

    return jsonify({'status': 'success', 'message': '视频已删除'})

@app.route('/play_video/<int:video_id>')
def play_video(video_id):
    """播放视频"""
    video = Video.query.get(video_id)
    if not video:
        flash('视频不存在', 'danger')
        return redirect(url_for('index'))

    user_id = video.user_id
    video_url = url_for('uploaded_file', user_id=user_id, filename=video.filename)
    return render_template_string(play_video_template, video=video, video_url=video_url)

@app.route('/uploads/<int:user_id>/<filename>')
def uploaded_file(user_id, filename):
    """提供上传的文件供播放"""
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(user_id)), filename)

@app.route('/search')
def search():
    """搜索用户"""
    query = request.args.get('q', '').strip()
    users = []
    if query:
        all_users = User.query.all()
        # 使用最长公共子序列算法排序用户
        users = sorted(
            all_users,
            key=lambda u: -longest_common_subsequence(query.lower(), u.username.lower())
        )
        users = [u for u in users if longest_common_subsequence(query.lower(), u.username.lower()) > 0]

    return render_template_string(search_results_template, users=users, query=query)

@app.route('/user_videos/<int:user_id>')
def user_videos(user_id):
    """显示指定用户的视频"""
    user = User.query.get(user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('index'))

    videos = Video.query.filter_by(user_id=user_id).all()
    return render_template_string(user_videos_template, user=user, videos=videos)

# 模板字符串
register_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>注册</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">用户注册</h2>
    <form method="POST">
        {{ form.hidden_tag() }}
        <div class="form-group">
            {{ form.username.label }}
            {{ form.username(class_='form-control') }}
        </div>
        <div class="form-group">
            {{ form.password.label }}
            {{ form.password(class_='form-control') }}
        </div>
        <div class="form-group">
            {{ form.confirm_password.label }}
            {{ form.confirm_password(class_='form-control') }}
        </div>
        <div class="form-group">
            <label>验证码</label><br>
            {% if captcha_image %}
                <img src="data:image/png;base64,{{ captcha_image }}" alt="验证码"><br><br>
            {% endif %}
            {{ form.captcha(class_='form-control') }}
        </div>
        <button type="submit" class="btn btn-primary">注册</button>
    </form>
    <p>已有账号？<a href="{{ url_for('login') }}">登录</a></p>
</div>
</body>
</html>
'''

login_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>登录</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">用户登录</h2>
    <form method="POST">
        {{ form.hidden_tag() }}
        <div class="form-group">
            {{ form.username.label }}
            {{ form.username(class_='form-control') }}
        </div>
        <div class="form-group">
            {{ form.password.label }}
            {{ form.password(class_='form-control') }}
        </div>
        <div class="form-group">
            <label>验证码</label><br>
            {% if captcha_image %}
                <img src="data:image/png;base64,{{ captcha_image }}" alt="验证码"><br><br>
            {% endif %}
            {{ form.captcha(class_='form-control') }}
        </div>
        <button type="submit" class="btn btn-primary">登录</button>
    </form>
    <p>还没有账号？<a href="{{ url_for('register') }}">注册</a></p>
</div>
</body>
</html>
'''

dashboard_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>用户主页</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">欢迎，{{ current_user.username }}</h2>
    <a href="{{ url_for('my_videos') }}" class="btn btn-primary">我的视频</a>
    <a href="{{ url_for('logout') }}" class="btn btn-secondary">登出</a>
    <hr>
    <h3>上传新视频</h3>
    <form id="uploadForm">
        <div class="form-group">
            <label for="title">标题</label>
            <input type="text" name="title" id="title" class="form-control" required>
        </div>
        <div class="form-group">
            <label for="file">选择视频文件</label>
            <input type="file" name="file" id="file" class="form-control-file" accept="video/*" required>
        </div>
        <button type="submit" class="btn btn-success">上传</button>
    </form>
    <div id="uploadStatus"></div>
</div>
<script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
<script>
$(function() {
    $('#uploadForm').submit(function(event) {
        event.preventDefault();
        var formData = new FormData(this);
        $.ajax({
            url: '{{ url_for('upload') }}',
            type: 'POST',
            data: formData,
            headers: {'X-CSRFToken': '{{ csrf_token() }}'},
            contentType: false,
            processData: false,
            success: function(response) {
                $('#uploadStatus').html('<div class="alert alert-success">' + response.message + '</div>');
                $('#uploadForm')[0].reset();
            },
            error: function(xhr) {
                var message = xhr.responseJSON ? xhr.responseJSON.message : '上传失败';
                $('#uploadStatus').html('<div class="alert alert-danger">' + message + '</div>');
            }
        });
    });
});
</script>
</body>
</html>
'''

my_videos_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>我的视频</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">我的视频</h2>
    <a href="{{ url_for('dashboard') }}" class="btn btn-primary">返回主页</a>
    {% if videos %}
    <table class="table mt-3">
        <thead>
            <tr>
                <th>标题</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
        {% for video in videos %}
            <tr>
                <td>{{ video.title }}</td>
                <td>
                    <a href="{{ url_for('play_video', video_id=video.id) }}" class="btn btn-success btn-sm">播放</a>
                    <button class="btn btn-danger btn-sm delete-btn" data-id="{{ video.id }}">删除</button>
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p>您还没有上传视频。</p>
    {% endif %}
</div>
<script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
<script>
$(function() {
    $('.delete-btn').click(function() {
        var videoId = $(this).data('id');
        if(confirm('确定要删除这个视频吗？')) {
            $.ajax({
                url: '{{ url_for('delete_video') }}',
                type: 'POST',
                data: {video_id: videoId},
                headers: {'X-CSRFToken': '{{ csrf_token() }}'},
                success: function(response) {
                    location.reload();
                },
                error: function(xhr) {
                    var message = xhr.responseJSON ? xhr.responseJSON.message : '删除失败';
                    alert(message);
                }
            });
        }
    });
});
</script>
</body>
</html>
'''

play_video_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>{{ video.title }}</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">{{ video.title }}</h2>
    <video width="640" height="480" controls>
        <source src="{{ video_url }}" type="video/mp4">
        您的浏览器不支持HTML5视频
    </video>
    <br>
    <a href="javascript:history.back();" class="btn btn-primary mt-3">返回</a>
</div>
</body>
</html>
'''

search_results_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>搜索结果</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">搜索用户</h2>
    <form method="GET" action="{{ url_for('search') }}">
        <input type="text" name="q" value="{{ query }}" class="form-control mb-2" placeholder="搜索用户名">
        <button type="submit" class="btn btn-primary">搜索</button>
    </form>
    {% if users %}
    <ul class="list-group mt-3">
    {% for user in users %}
        <li class="list-group-item">
            <a href="{{ url_for('user_videos', user_id=user.id) }}">{{ user.username }}</a>
        </li>
    {% endfor %}
    </ul>
    {% else %}
    <p class="mt-4">未找到相关用户。</p>
    {% endif %}
</div>
</body>
</html>
'''

user_videos_template = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>{{ user.username }} 的视频</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <h2 class="mt-4">{{ user.username }} 的视频</h2>
    {% if videos %}
    <table class="table mt-3">
        <thead>
            <tr>
                <th>标题</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
        {% for video in videos %}
            <tr>
                <td>{{ video.title }}</td>
                <td>
                    <a href="{{ url_for('play_video', video_id=video.id) }}" class="btn btn-success btn-sm">播放</a>
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p>该用户还没有上传视频。</p>
    {% endif %}
</div>
</body>
</html>
'''

# 应用程序启动
if __name__ == '__main__':
    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 自动创建数据库
    with app.app_context():
        db.create_all()

    # 运行应用程序
    app.run(debug=True)
