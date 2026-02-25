# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统
独立应用
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='../static')

    # 配置
    app.config['SECRET_KEY'] = 'workload-management-secret-key-2026'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workload.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图
    from .api.workload_bp import workload_bp
    from .api.workload_excel_bp import workload_excel_bp

    app.register_blueprint(workload_bp)
    app.register_blueprint(workload_excel_bp)

    # 首页路由
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('workload_management.html')

    # 创建数据库表
    with app.app_context():
        db.create_all()

    return app
