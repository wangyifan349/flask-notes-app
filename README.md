# 📝 Flask 在线笔记管理系统

一个基于 Flask 的在线笔记管理 Web 应用，支持用户注册登录、笔记创建编辑删除、用户之间公开笔记浏览，带有图形验证码和基于最长公共子序列（LCS）算法的模糊搜索功能。界面采用 Bootstrap 美化，风格简洁美观。

---

## 🚀 功能特色

- ✅ **用户管理**：注册、登录、退出及修改密码
- ✅ **验证码**：图形验证码防刷，保障账户安全
- ✅ **笔记管理**：
  - 创建、编辑、删除个人笔记
  - 查看其它用户公开笔记，纯文本阅读
- ✅ **搜索功能**：
  - 支持全站基于最长公共子序列(LCS)算法的模糊搜索
  - 搜索笔记内容
  - 搜索用户名并查看其笔记
- ✅ **权限分明**：
  - 未登录用户可浏览公开笔记及搜索用户
  - 登录用户享有笔记的创建管理权限
- ✅ **响应式界面**：采用 Bootstrap，手机电脑均可良好浏览
- ✅ **轻量易用**：SQLite 数据库存储，简单快速部署

---

## 💻 技术栈

- Python 3.8+
- Flask
- Flask-Login
- Flask-WTF
- Pillow
- SQLite
- Bootstrap 4.5 CSS 框架

---

## 📦 目录结构

```
flask-notes-app/
│
├── app.py               # 主程序入口，Flask Web 服务
├── requirements.txt     # Python 依赖列表
├── README.md            # 项目说明文档
├── users.db             # 数据库文件（首次运行自动生成）
├── static/              # 静态资源（空）
└── templates/           # Jinja2 HTML 模板
    ├── base.html
    ├── home.html
    ├── login.html
    ├── register.html
    ├── change_password.html
    ├── notes.html
    ├── new_note.html
    ├── edit_note.html
    ├── search.html
    ├── search_results.html
    ├── user_search.html
    └── public_notes.html
```

---

## ⚙️ 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/flask-notes-app.git
cd flask-notes-app
```

### 2. 创建虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate      # Windows 下运行：venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行程序

```bash
python app.py
```

### 5. 访问应用

打开浏览器访问：

```
http://127.0.0.1:5000
```

---

## 📚 使用指南

- 前往【注册】页面创建账号→ 登录
- 登录后可创建、编辑、删除自己的笔记
- 使用导航中的【搜索】框，可模糊搜索自己笔记内容
- 通过【搜索用户】可以查找平台上的其他用户，点击进入可浏览其公开笔记
- 通过【修改密码】安全管理账户
- 未登录用户也可以搜索用户及查看其公开笔记，但无法编辑及删除笔记

---

## 🔐 安全提示

- 当前存储密码为明文（演示用）建议部署时使用哈希加密方法（如 werkzeug.security）
- 验证码防止机器注册和登录暴力破解
- SQLite适合小型轻量应用，生产请评估需求选择更合适数据库

---


## 🤝 贡献者

欢迎 fork 和 PR，如遇问题请提交 Issue。

---

## 📄 许可证

MIT License

---

🙏 感谢阅读，祝你使用愉快，享受编码乐趣！  
欢迎给项目点个⭐！

---

**作者：王一帆**  
**邮箱：wangyifan349@gmail.com**  

**GitHub：https://github.com/wangyifan349**
