from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
from io import BytesIO
import random
import string
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure database
DATABASE = 'users.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------------------------
# User Model
# -------------------------------------------
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    @staticmethod
    def get(userId):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (userId,))
        user = cursor.fetchone()
        if user:
            return User(user['id'], user['username'], user['password'])
        return None

    @staticmethod
    def findByUsername(username):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user:
            return User(user['id'], user['username'], user['password'])
        return None

    @staticmethod
    def searchUsers(query):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users')
        usersData = cursor.fetchall()
        usersWithScores = []
        for userRow in usersData:
            username = userRow['username']
            score = lcsLength(query, username)
            if score > 0:
                user = User(userRow['id'], username, userRow['password'])
                usersWithScores.append((score, user))
        usersWithScores.sort(reverse=True, key=lambda x: x[0])
        resultUsers = []
        for score, user in usersWithScores:
            resultUsers.append(user)
        return resultUsers

# -------------------------------------------
# Note Model
# -------------------------------------------
class Note:
    def __init__(self, id, userId, title, content):
        self.id = id
        self.userId = userId
        self.title = title
        self.content = content

    @staticmethod
    def get(noteId, userId):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes WHERE id = ? AND userId = ?', (noteId, userId))
        note = cursor.fetchone()
        if note:
            return Note(note['id'], note['userId'], note['title'], note['content'])
        return None

    @staticmethod
    def getAll(userId):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes WHERE userId = ?', (userId,))
        notesData = cursor.fetchall()
        notes = []
        for noteRow in notesData:
            note = Note(noteRow['id'], noteRow['userId'], noteRow['title'], noteRow['content'])
            notes.append(note)
        return notes

    @staticmethod
    def getAllByUser(userId):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes WHERE userId = ?', (userId,))
        notesData = cursor.fetchall()
        notes = []
        for noteRow in notesData:
            note = Note(noteRow['id'], noteRow['userId'], noteRow['title'], noteRow['content'])
            notes.append(note)
        return notes

# -------------------------------------------
# Load User Function for Login Manager
# -------------------------------------------
@login_manager.user_loader
def loadUser(userId):
    return User.get(userId)

# -------------------------------------------
# Initialize Database
# -------------------------------------------
@app.before_first_request
def initializeDatabase():
    conn = get_db()
    # Create users table
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL
                    )''')
    # Create notes table
    conn.execute('''CREATE TABLE IF NOT EXISTS notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        userId INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        FOREIGN KEY(userId) REFERENCES users(id)
                    )''')
    conn.commit()

# -------------------------------------------
# Forms
# -------------------------------------------
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(3, 20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(6, 50)])
    captcha = StringField('验证码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(3, 20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(6, 50)])
    confirmPassword = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    captcha = StringField('验证码', validators=[DataRequired()])
    submit = SubmitField('注册')

class ChangePasswordForm(FlaskForm):
    oldPassword = PasswordField('旧密码', validators=[DataRequired()])
    newPassword = PasswordField('新密码', validators=[DataRequired(), Length(6, 50)])
    confirmNewPassword = PasswordField('确认新密码', validators=[DataRequired(), EqualTo('newPassword')])
    submit = SubmitField('修改密码')

class NoteForm(FlaskForm):
    title = StringField('标题', validators=[DataRequired(), Length(max=100)])
    content = TextAreaField('内容', validators=[DataRequired()])
    submit = SubmitField('保存')

class SearchForm(FlaskForm):
    query = StringField('搜索内容', validators=[DataRequired()])
    submit = SubmitField('搜索')

class UserSearchForm(FlaskForm):
    query = StringField('搜索用户', validators=[DataRequired()])
    submit = SubmitField('搜索')

# -------------------------------------------
# Captcha Generation
# -------------------------------------------
def generateCaptcha():
    characters = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    session['captcha'] = characters
    img = Image.new('RGB', (100, 30), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Load a font
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()

    d.text((10, 0), characters, fill=(0, 0, 0), font=font)
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

@app.route('/captcha')
def captcha():
    image = generateCaptcha()
    return send_file(image, mimetype='image/png')

# -------------------------------------------
# LCS Algorithm
# -------------------------------------------
def lcsLength(a, b):
    a = a.lower()
    b = b.lower()
    m = len(a)
    n = len(b)
    dp = []
    for i in range(m+1):
        dp.append([0]*(n+1))
    for i in range(m):
        for j in range(n):
            if a[i] == b[j]:
                dp[i+1][j+1] = dp[i][j]+1
            else:
                dp[i+1][j+1] = max(dp[i][j+1], dp[i+1][j])
    return dp[m][n]

# -------------------------------------------
# Home Page Route
# -------------------------------------------
@app.route('/')
def home():
    if current_user.is_authenticated:
        return render_template('home.html', username=current_user.username)
    else:
        return redirect(url_for('login'))

# -------------------------------------------
# User Registration Route
# -------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegisterForm()
    if form.validate_on_submit():
        if form.captcha.data.upper() != session.get('captcha', '').upper():
            flash('验证码错误，请重试。', 'danger')
            return redirect(url_for('register'))
        if User.findByUsername(form.username.data):
            flash('用户名已存在。', 'danger')
        else:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (form.username.data, form.password.data))
            conn.commit()
            flash('注册成功。现在您可以登录了。', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

# -------------------------------------------
# User Login Route
# -------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        if form.captcha.data.upper() != session.get('captcha', '').upper():
            flash('验证码错误，请重试。', 'danger')
            return redirect(url_for('login'))
        user = User.findByUsername(form.username.data)
        if user and user.password == form.password.data:
            login_user(user)
            flash('登录成功。', 'success')
            return redirect(url_for('home'))
        else:
            flash('用户名或密码错误', 'danger')
    return render_template('login.html', form=form)

# -------------------------------------------
# User Logout Route
# -------------------------------------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------------------------------
# Change Password Route
# -------------------------------------------
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def changePassword():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.password == form.oldPassword.data:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password = ? WHERE id = ?', (form.newPassword.data, current_user.id))
            conn.commit()
            flash('密码修改成功。', 'success')
            return redirect(url_for('home'))
        else:
            flash('旧密码错误。', 'danger')
    return render_template('change_password.html', form=form)

# -------------------------------------------
# List Notes Route
# -------------------------------------------
@app.route('/notes')
@login_required
def notes():
    notes = Note.getAll(current_user.id)
    return render_template('notes.html', notes=notes)

# -------------------------------------------
# Create New Note Route
# -------------------------------------------
@app.route('/notes/new', methods=['GET', 'POST'])
@login_required
def newNote():
    form = NoteForm()
    if form.validate_on_submit():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO notes (userId, title, content) VALUES (?, ?, ?)', (current_user.id, form.title.data, form.content.data))
        conn.commit()
        flash('笔记创建成功！', 'success')
        return redirect(url_for('notes'))
    return render_template('new_note.html', form=form)

# -------------------------------------------
# Edit Note Route
# -------------------------------------------
@app.route('/notes/<int:noteId>/edit', methods=['GET', 'POST'])
@login_required
def editNote(noteId):
    note = Note.get(noteId, current_user.id)
    if not note:
        flash('未找到笔记。', 'danger')
        return redirect(url_for('notes'))
    form = NoteForm(title=note.title, content=note.content)
    if form.validate_on_submit():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE notes SET title = ?, content = ? WHERE id = ? AND userId = ?', (form.title.data, form.content.data, noteId, current_user.id))
        conn.commit()
        flash('笔记更新成功！', 'success')
        return redirect(url_for('notes'))
    return render_template('edit_note.html', form=form)

# -------------------------------------------
# Delete Note Route
# -------------------------------------------
@app.route('/notes/<int:noteId>/delete', methods=['POST'])
@login_required
def deleteNote(noteId):
    note = Note.get(noteId, current_user.id)
    if not note:
        flash('未找到笔记。', 'danger')
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notes WHERE id = ? AND userId = ?', (noteId, current_user.id))
        conn.commit()
        flash('笔记已删除。', 'success')
    return redirect(url_for('notes'))

# -------------------------------------------
# Search Notes Route
# -------------------------------------------
@app.route('/notes/search', methods=['GET', 'POST'])
@login_required
def searchNotes():
    form = SearchForm()
    notes = []
    if form.validate_on_submit():
        query = form.query.data
        allNotes = Note.getAll(current_user.id)
        notesWithScores = []
        for note in allNotes:
            combinedText = note.title + note.content
            score = lcsLength(query, combinedText)
            if score > 0:
                notesWithScores.append((score, note))
        notesWithScores.sort(reverse=True, key=lambda x: x[0])
        notes = []
        for score, note in notesWithScores:
            notes.append(note)
        if not notes:
            flash('未找到匹配的笔记。', 'info')
        return render_template('search_results.html', notes=notes)
    return render_template('search.html', form=form)

# -------------------------------------------
# Search Users Route
# -------------------------------------------
@app.route('/user_search', methods=['GET', 'POST'])
def userSearch():
    form = UserSearchForm()
    users = []
    if form.validate_on_submit():
        query = form.query.data
        users = User.searchUsers(query)
        if not users:
            flash('未找到匹配的用户。', 'info')
    return render_template('user_search.html', form=form, users=users)

# -------------------------------------------
# View User's Public Notes Route
# -------------------------------------------
@app.route('/user/<int:userId>/notes')
def userNotes(userId):
    user = User.get(userId)
    if not user:
        flash('用户不存在。', 'danger')
        return redirect(url_for('userSearch'))
    notes = Note.getAllByUser(userId)
    return render_template('public_notes.html', user=user, notes=notes)

# -------------------------------------------
# Run the Application
# -------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
