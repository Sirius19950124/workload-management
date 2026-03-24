# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统
云托管版本
"""

from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import sys
import re

db = SQLAlchemy()


def get_base_path():
    """获取应用基础路径"""
    # 云托管环境下，使用 /tmp 作为可写目录
    if os.environ.get('KUBERNETES_SERVICE_HOST') or os.environ.get('MYSQL_ADDON_HOST'):
        return '/tmp'
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path):
    """获取资源文件绝对路径"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)


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


def recalculate_all_points():
    """重新计算所有治疗师的积分和等级"""
    from sqlalchemy import text

    try:
        # 检查是否有治疗师统计数据
        result = db.session.execute(text(
            "SELECT 1 FROM therapist_stats LIMIT 1"
        ))
        result.fetchone()
        
        # MySQL 语法更新积分
        db.session.execute(text(
            "UPDATE therapist_stats SET total_points = CAST(total_workload * 0.1 AS SIGNED)"
        ))

        # MySQL 语法更新等级
        db.session.execute(text("""
            UPDATE therapist_stats SET
                current_level = CASE
                    WHEN total_points < 500 THEN 1
                    WHEN total_points < 1500 THEN 2
                    WHEN total_points < 3000 THEN 3
                    WHEN total_points < 5000 THEN 4
                    WHEN total_points < 8000 THEN 5
                    WHEN total_points < 12000 THEN 6
                    WHEN total_points < 18000 THEN 7
                    WHEN total_points < 25000 THEN 8
                    ELSE 9
                END,
                level_progress = CASE
                    WHEN total_points < 500 THEN (total_points * 1.0 / 500) * 100
                    WHEN total_points < 1500 THEN ((total_points - 500) * 1.0 / 1000) * 100
                    WHEN total_points < 3000 THEN ((total_points - 1500) * 1.0 / 1500) * 100
                    WHEN total_points < 5000 THEN ((total_points - 3000) * 1.0 / 2000) * 100
                    WHEN total_points < 8000 THEN ((total_points - 5000) * 1.0 / 3000) * 100
                    WHEN total_points < 12000 THEN ((total_points - 8000) * 1.0 / 4000) * 100
                    WHEN total_points < 18000 THEN ((total_points - 12000) * 1.0 / 6000) * 100
                    WHEN total_points < 25000 THEN ((total_points - 18000) * 1.0 / 7000) * 100
                    ELSE 100
                END
        """))

        db.session.commit()
        print("[AutoMigrate] Recalculated all therapist points and levels")

    except Exception as e:
        print(f"[AutoMigrate] Note: {e}")
        db.session.rollback()


def auto_migrate():
    """自动迁移：检查并创建缺失的表和数据"""
    from sqlalchemy import text

    print("=" * 50)
    print("[AutoMigrate] Checking database schema...")

    try:
        # 创建所有表（如果不存在）
        db.create_all()
        print("[AutoMigrate] Tables created/verified")
        
        # 初始化默认成就
        from app.models import Achievement, DEFAULT_ACHIEVEMENTS
        existing_count = Achievement.query.count()
        if existing_count == 0:
            print("[AutoMigrate] Initializing default achievements...")
            for ach_data in DEFAULT_ACHIEVEMENTS:
                achievement = Achievement(**ach_data)
                db.session.add(achievement)
            db.session.commit()
            print(f"[AutoMigrate] Created {len(DEFAULT_ACHIEVEMENTS)} default achievements")

        # 重新计算积分
        recalculate_all_points()

        print("[AutoMigrate] Database schema check completed")
        print("=" * 50)

    except Exception as e:
        print(f"[AutoMigrate] Error during migration: {e}")
        db.session.rollback()


def create_app():
    """创建 Flask 应用"""
    # 静态文件和模板路径
    static_path = get_resource_path('static')
    template_path = get_resource_path('app/templates')

    app = Flask(__name__,
                template_folder=template_path,
                static_folder=static_path)

    # 加载配置
    # 优先从 cloud/config.py 加载，如果不存在则使用环境变量
    try:
        from cloud.config import get_config
        app.config.from_object(get_config())
    except ImportError:
        # 回退配置
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'workload-secret-key')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///workload.db')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 上传目录
    upload_path = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
    os.makedirs(upload_path, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_path

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图
    from app.api.workload_bp import workload_bp
    from app.api.workload_excel_bp import workload_excel_bp
    from app.api.achievement_bp import achievement_bp
    from app.api.patient_bp import patient_bp

    app.register_blueprint(workload_bp)
    app.register_blueprint(workload_excel_bp)
    app.register_blueprint(achievement_bp)
    app.register_blueprint(patient_bp)

    # PC端首页路由
    @app.route('/')
    def index():
        return render_template('workload_management.html')

    # 移动端路由
    @app.route('/mobile')
    def mobile():
        return render_template('mobile.html')

    # 自动检测设备并跳转
    @app.route('/auto')
    def auto_redirect():
        user_agent = request.headers.get('User-Agent', '')
        if is_mobile_device(user_agent):
            return redirect('/mobile')
        else:
            return redirect('/')

    # 健康检查（云托管需要）
    @app.route('/health')
    def health():
        return {'status': 'ok'}

    # 创建数据库表和初始化数据
    with app.app_context():
        db.create_all()
        auto_migrate()

    return app
