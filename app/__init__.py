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
    """获取应用基础路径（兼容 PyInstaller 打包）
    用于数据库等可写文件
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后运行 - 返回exe所在目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境运行
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    """获取资源文件绝对路径（兼容 PyInstaller 打包）
    用于静态文件、模板等只读资源
    
    PyInstaller打包后，资源会被解压到临时目录 sys._MEIPASS
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后运行
        base_path = sys._MEIPASS
    else:
        # 开发环境运行
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(base_path, relative_path)

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
    """重新计算所有治疗师的积分和等级（修复积分公式变更后的数据）"""
    from sqlalchemy import text

    try:
        # 检查是否有治疗师统计数据
        result = db.session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='therapist_stats'"
        ))
        if result.fetchone() is None:
            return  # 表不存在，跳过

        # ✅ 步骤1：更新所有治疗师的积分：积分 = 工作量 × 0.1
        db.session.execute(text(
            "UPDATE therapist_stats SET total_points = CAST(total_workload * 0.1 AS INTEGER)"
        ))

        # ✅ 步骤2：根据积分重新计算等级
        # 等级规则：
        # Level 1: < 500
        # Level 2: 500-1499
        # Level 3: 1500-2999
        # Level 4: 3000-4999
        # Level 5: 5000-7999
        # Level 6: 8000-11999
        # Level 7: 12000-17999
        # Level 8: 18000-24999
        # Level 9: >= 25000
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
        print("[AutoMigrate] Recalculated all therapist points and levels (formula: workload × 0.1)")

    except Exception as e:
        print(f"[AutoMigrate] Error recalculating points: {e}")
        db.session.rollback()

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

        # 检查患者表是否存在
        result = db.session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='patients'"
        ))
        patients_exists = result.fetchone() is not None

        if not patients_exists:
            print("[AutoMigrate] Creating patients table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(50) NOT NULL,
                    patient_no VARCHAR(30) UNIQUE,
                    gender VARCHAR(10),
                    age INTEGER,
                    phone VARCHAR(20),
                    diagnosis VARCHAR(200),
                    bed_no VARCHAR(20),
                    primary_therapist_id INTEGER,
                    status VARCHAR(20) DEFAULT 'active',
                    admission_date DATE,
                    discharge_date DATE,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (primary_therapist_id) REFERENCES workload_therapists(id)
                )
            """))
            db.session.commit()
            print("[AutoMigrate] Patients table created successfully")
        else:
            print("[AutoMigrate] Patients table already exists")
            # 检查并添加 secondary_therapist_id 字段
            try:
                result = db.session.execute(text(
                    "SELECT * FROM pragma_table_info('patients') WHERE name='secondary_therapist_id'"
                ))
                if result.fetchone() is None:
                    print("[AutoMigrate] Adding secondary_therapist_id column to patients table...")
                    db.session.execute(text(
                        "ALTER TABLE patients ADD COLUMN secondary_therapist_id INTEGER REFERENCES workload_therapists(id)"
                    ))
                    db.session.commit()
                    print("[AutoMigrate] secondary_therapist_id column added")
            except Exception as e:
                print(f"[AutoMigrate] Error adding secondary_therapist_id: {e}")

        # 无论patients表是否存在，都检查并添加 patient_id 字段到 workload_records 表
        try:
            result = db.session.execute(text(
                "SELECT * FROM pragma_table_info('workload_records') WHERE name='patient_id'"
            ))
            if result.fetchone() is None:
                print("[AutoMigrate] Adding patient_id column to workload_records table...")
                db.session.execute(text(
                    "ALTER TABLE workload_records ADD COLUMN patient_id INTEGER REFERENCES patients(id)"
                ))
                db.session.commit()
                print("[AutoMigrate] patient_id column added to workload_records")
            else:
                print("[AutoMigrate] workload_records.patient_id column already exists")
        except Exception as e:
            print(f"[AutoMigrate] Error adding patient_id to workload_records: {e}")

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

        # 检查评价表是否存在
        result = db.session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ratings'"
        ))
        ratings_exists = result.fetchone() is not None

        if not ratings_exists:
            print("[AutoMigrate] Creating ratings table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    record_id INTEGER,
                    therapist_id INTEGER,
                    treatment_item_id INTEGER,
                    star_rating INTEGER NOT NULL,
                    comment TEXT,
                    tags VARCHAR(200),
                    openid VARCHAR(64),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (record_id) REFERENCES workload_records(id),
                    FOREIGN KEY (therapist_id) REFERENCES workload_therapists(id),
                    FOREIGN KEY (treatment_item_id) REFERENCES workload_treatment_items(id)
                )
            """))
            db.session.execute(text("CREATE INDEX idx_ratings_patient ON ratings(patient_id)"))
            db.session.execute(text("CREATE INDEX idx_ratings_therapist ON ratings(therapist_id)"))
            db.session.execute(text("CREATE INDEX idx_ratings_record ON ratings(record_id)"))
            db.session.commit()
            print("[AutoMigrate] Ratings table created successfully")
        else:
            print("[AutoMigrate] Ratings table already exists")

        # 检查评价问卷题目表是否存在
        result = db.session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rating_questions'"
        ))
        questions_exists = result.fetchone() is not None

        if not questions_exists:
            print("[AutoMigrate] Creating rating_questions and rating_answers tables...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS rating_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(100) NOT NULL,
                    question_type VARCHAR(20) NOT NULL DEFAULT 'star',
                    options TEXT,
                    is_required BOOLEAN DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS rating_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rating_id INTEGER NOT NULL REFERENCES ratings(id),
                    question_id INTEGER NOT NULL REFERENCES rating_questions(id),
                    answer_value VARCHAR(500),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("CREATE INDEX idx_rating_answers_rating ON rating_answers(rating_id)"))
            db.session.commit()
            print("[AutoMigrate] Rating question/answer tables created successfully")
        else:
            print("[AutoMigrate] Rating question/answer tables already exist")

        # 初始化默认评价问卷题目
        from app.models import RatingQuestion, DEFAULT_RATING_QUESTIONS
        existing_questions = RatingQuestion.query.count()
        if existing_questions == 0:
            print(f"[AutoMigrate] Initializing {len(DEFAULT_RATING_QUESTIONS)} default rating questions...")
            for q_data in DEFAULT_RATING_QUESTIONS:
                question = RatingQuestion(**q_data)
                db.session.add(question)
            db.session.commit()
            print(f"[AutoMigrate] Created {len(DEFAULT_RATING_QUESTIONS)} default rating questions")
        else:
            print(f"[AutoMigrate] Found {existing_questions} existing rating questions")

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

        # 检查培训考试相关表是否存在
        exam_tables = ['training_materials', 'question_bank', 'exam_papers',
                       'exam_paper_questions', 'exam_assignments', 'exam_answers']
        exam_table_exists = db.session.execute(text(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{exam_tables[0]}'"
        )).fetchone() is not None

        if not exam_table_exists:
            print("[AutoMigrate] Creating exam/training tables...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS training_materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    file_name VARCHAR(200) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    file_type VARCHAR(20),
                    file_size INTEGER,
                    extracted_text TEXT,
                    category VARCHAR(50) DEFAULT '通用',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS question_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER REFERENCES training_materials(id),
                    question_type VARCHAR(20) NOT NULL,
                    question_text TEXT NOT NULL,
                    options TEXT,
                    answer TEXT NOT NULL,
                    analysis TEXT,
                    difficulty VARCHAR(10) DEFAULT 'medium',
                    score INTEGER DEFAULT 2,
                    source VARCHAR(20) DEFAULT 'manual',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS exam_papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    total_score INTEGER DEFAULT 100,
                    pass_score INTEGER DEFAULT 60,
                    duration_minutes INTEGER DEFAULT 60,
                    status VARCHAR(20) DEFAULT 'draft',
                    shuffle_questions BOOLEAN DEFAULT 1,
                    shuffle_options BOOLEAN DEFAULT 1,
                    show_answer_after_submit BOOLEAN DEFAULT 1,
                    start_time DATETIME,
                    end_time DATETIME,
                    created_by VARCHAR(50),
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS exam_paper_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES exam_papers(id),
                    question_id INTEGER NOT NULL REFERENCES question_bank(id),
                    sort_order INTEGER DEFAULT 0,
                    score INTEGER DEFAULT 2,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(paper_id, question_id)
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS exam_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES exam_papers(id),
                    therapist_id INTEGER NOT NULL REFERENCES workload_therapists(id),
                    status VARCHAR(20) DEFAULT 'assigned',
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    started_at DATETIME,
                    submitted_at DATETIME,
                    UNIQUE(paper_id, therapist_id)
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS exam_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL UNIQUE REFERENCES exam_assignments(id),
                    answers_json TEXT,
                    score INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    time_spent_seconds INTEGER DEFAULT 0,
                    grading_detail TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            # 创建索引
            db.session.execute(text("CREATE INDEX idx_qbank_material ON question_bank(material_id)"))
            db.session.execute(text("CREATE INDEX idx_qbank_type ON question_bank(question_type)"))
            db.session.execute(text("CREATE INDEX idx_assignment_paper ON exam_assignments(paper_id)"))
            db.session.execute(text("CREATE INDEX idx_assignment_therapist ON exam_assignments(therapist_id)"))
            db.session.execute(text("CREATE INDEX idx_assignment_status ON exam_assignments(status)"))
            db.session.commit()
            print(f"[AutoMigrate] Created {len(exam_tables)} exam/training tables")
        else:
            print("[AutoMigrate] Exam/Training tables already exist")

        print("[AutoMigrate] Database schema check completed")

        # 重新计算所有治疗师的积分（修复积分公式变更后的数据）
        recalculate_all_points()

        print("=" * 50)

    except Exception as e:
        print(f"[AutoMigrate] Error during migration: {e}")
        db.session.rollback()
        # 不抛出异常，允许系统继续运行

def create_app():
    base_path = get_base_path()

    # 使用get_resource_path获取静态文件和模板路径（兼容PyInstaller打包）
    static_path = get_resource_path('static')
    template_path = get_resource_path('app/templates')

    app = Flask(__name__,
                template_folder=template_path,
                static_folder=static_path)

    # 数据库路径：exe打包时使用exe所在目录（可读写），开发时使用项目目录
    if getattr(sys, 'frozen', False):
        data_dir = os.path.dirname(sys.executable)
    else:
        data_dir = base_path
    db_path = os.path.join(data_dir, 'instance', 'workload.db')
    upload_path = os.path.join(data_dir, 'uploads')
    
    # 调试输出：显示数据库路径
    print(f"[数据库] Base path: {base_path}")
    print(f"[数据库] Database path: {db_path}")
    print(f"[数据库] Database exists: {os.path.exists(db_path)}")

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
    from .api.patient_bp import patient_bp
    from .api.rating_bp import rating_bp
    from .api.changelog_bp import changelog_bp
    from .api.operation_log_bp import operation_log_bp
    from .api.dept_stats_bp import dept_stats_bp, referral_bp
    from .api.exam_bp import exam_bp
    from .db_backup import register_backup_routes, start_auto_backup
    from .cos_backup import register_cos_routes, start_cos_auto_backup

    app.register_blueprint(workload_bp)
    app.register_blueprint(workload_excel_bp)
    app.register_blueprint(achievement_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(rating_bp)
    app.register_blueprint(changelog_bp)
    app.register_blueprint(operation_log_bp)
    app.register_blueprint(dept_stats_bp)
    app.register_blueprint(referral_bp)
    app.register_blueprint(exam_bp)

    # 注册数据库备份路由
    register_backup_routes(app, base_path)
    register_cos_routes(app)

    # 保存base_path供其他模块使用
    app._base_path = base_path

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

        # 启动数据库自动备份（每24小时，保留30个）
        try:
            start_auto_backup(base_path, interval_hours=24, keep_count=30)
            print("[备份] 数据库本地自动备份已启用")
        except Exception as e:
            print(f"[备份] 本地自动备份启动失败: {e}")

        # 启动COS云端备份（需要配置环境变量才生效）
        try:
            import db_backup as db_backup_module
            start_cos_auto_backup(db_backup_module, base_path)
        except Exception as e:
            print(f"[COS] 云端备份启动失败（可忽略，未配置时正常）: {e}")

    return app
