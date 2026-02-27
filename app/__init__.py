# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统
独立应用
"""

from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import sys
import re

db = SQLAlchemy()

def get_base_path():
    """获取应用基础路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后运行
        return os.path.dirname(sys.executable)
    else:
        # 开发环境运行
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def is_mobile_device(user_agent):
    """检测是否为移动设备"""
    if not user_agent:
        return False
    mobile_patterns = [
        r'Android',
        r'iPhone',
        r'iPad',
        r'iPod',
        r'Windows Phone',
        r'Mobile',
        r'BlackBerry',
        r'webOS'
    ]
    return any(re.search(pattern, user_agent, re.IGNORECASE) for pattern in mobile_patterns)

def create_app():
    base_path = get_base_path()

    app = Flask(__name__,
                template_folder='templates',
                static_folder='../static')

    # 配置 - 使用绝对路径
    db_path = os.path.join(base_path, 'instance', 'workload.db')
    upload_path = os.path.join(base_path, 'uploads')

    # 确保目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(upload_path, exist_ok=True)

    app.config['SECRET_KEY'] = 'workload-management-secret-key-2026'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = upload_path

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图
    from .api.workload_bp import workload_bp
    from .api.workload_excel_bp import workload_excel_bp
    from .api.achievement_bp import achievement_bp

    app.register_blueprint(workload_bp)
    app.register_blueprint(workload_excel_bp)
    app.register_blueprint(achievement_bp)

    # PC端首页路由
    @app.route('/')
    def index():
        return render_template('workload_management.html')

    # 移动端路由
    @app.route('/mobile')
    def mobile():
        return render_template('mobile.html')

    # 自动检测设备并跳转（可选入口）
    @app.route('/auto')
    def auto_redirect():
        user_agent = request.headers.get('User-Agent', '')
        if is_mobile_device(user_agent):
            return redirect('/mobile')
        else:
            return redirect('/')

    # 创建数据库表（首次运行时自动创建空数据库）
    with app.app_context():
        db.create_all()

    return app
