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

def auto_migrate():
    """自动迁移：检查并创建缺失的表和数据"""
    from sqlalchemy import text

    print("=" * 50)
    print("[AutoMigrate] Checking database schema...")

    try:
        # 检查成就表是否存在
        result = db.session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='achievements'"
        ))
        achievements_exists = result.fetchone() is not None

        if not achievements_exists:
            print("[AutoMigrate] Creating achievement tables...")
            # 创建成就相关表
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    icon VARCHAR(50),
                    category VARCHAR(50),
                    condition_type VARCHAR(50),
                    condition_value INTEGER,
                    points_reward INTEGER DEFAULT 0,
                    rarity VARCHAR(20) DEFAULT 'common',
                    is_active BOOLEAN DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS therapist_achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    therapist_id INTEGER NOT NULL,
                    achievement_id INTEGER NOT NULL,
                    unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (therapist_id) REFERENCES therapists(id),
                    FOREIGN KEY (achievement_id) REFERENCES achievements(id),
                    UNIQUE(therapist_id, achievement_id)
                )
            """))

            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS therapist_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    therapist_id INTEGER UNIQUE NOT NULL,
                    total_sessions INTEGER DEFAULT 0,
                    total_workload FLOAT DEFAULT 0,
                    total_points INTEGER DEFAULT 0,
                    current_level INTEGER DEFAULT 1,
                    level_progress FLOAT DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    longest_streak INTEGER DEFAULT 0,
                    last_record_date DATE,
                    achievements_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (therapist_id) REFERENCES therapists(id)
                )
            """))

            db.session.commit()
            print("[AutoMigrate] Achievement tables created successfully")
        else:
            print("[AutoMigrate] Achievement tables already exist")

        # 检查并初始化默认成就
        from app.models import Achievement, DEFAULT_ACHIEVEMENTS
        existing_count = Achievement.query.count()
        if existing_count == 0:
            print("[AutoMigrate] Initializing default achievements...")
            for ach_data in DEFAULT_ACHIEVEMENTS:
                achievement = Achievement(**ach_data)
                db.session.add(achievement)
            db.session.commit()
            print(f"[AutoMigrate] Created {len(DEFAULT_ACHIEVEMENTS)} default achievements")
        else:
            print(f"[AutoMigrate] Found {existing_count} existing achievements")

        # 检查并添加 allow_delete 设置
        from app.models import WorkloadSettings
        allow_delete_exists = WorkloadSettings.query.filter_by(setting_key='allow_delete').first()
        if not allow_delete_exists:
            print("[AutoMigrate] Adding allow_delete setting...")
            setting = WorkloadSettings(
                setting_key='allow_delete',
                setting_value='false',
                setting_type='bool',
                description='启用删除功能（删除操作不可恢复，请谨慎使用）'
            )
            db.session.add(setting)
            db.session.commit()
            print("[AutoMigrate] allow_delete setting added")
        else:
            print("[AutoMigrate] allow_delete setting already exists")

        print("[AutoMigrate] Database schema check completed")
        print("=" * 50)

    except Exception as e:
        print(f"[AutoMigrate] Error during migration: {e}")
        db.session.rollback()
        # 不抛出异常，允许系统继续运行

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
        # 自动迁移检查
        auto_migrate()

    return app
