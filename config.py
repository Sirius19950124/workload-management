# -*- coding: utf-8 -*-
"""
云托管配置文件
支持微信云托管、腾讯云、阿里云等
"""

import os
from datetime import timedelta


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'workload-management-secret-key-2026'
    
    # 数据库配置 - 优先使用环境变量（云托管会自动注入）
    # 微信云托管 MySQL: MYSQL_ADDON_HOST, MYSQL_ADDON_PORT, MYSQL_ADDON_USER, MYSQL_ADDON_PASSWORD, MYSQL_ADDON_DB
    # 也可以直接使用 MYSQL_ADDON_URI (完整连接字符串)
    MYSQL_HOST = os.environ.get('MYSQL_ADDON_HOST') or os.environ.get('DB_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_ADDON_PORT') or os.environ.get('DB_PORT', '3306')
    MYSQL_USER = os.environ.get('MYSQL_ADDON_USER') or os.environ.get('DB_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_ADDON_PASSWORD') or os.environ.get('DB_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_ADDON_DB') or os.environ.get('DB_NAME', 'workload')
    
    # 完整的数据库 URI
    SQLALCHEMY_DATABASE_URI = os.environ.get('MYSQL_ADDON_URI') or \
        os.environ.get('DATABASE_URL') or \
        f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/tmp/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Session 配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # 云存储配置（可选，用于存储图片等文件）
    # 如果配置了，会上传到云存储，否则存本地
    COS_SECRET_ID = os.environ.get('COS_SECRET_ID')
    COS_SECRET_KEY = os.environ.get('COS_SECRET_KEY')
    COS_BUCKET = os.environ.get('COS_BUCKET')
    COS_REGION = os.environ.get('COS_REGION')
    
    @staticmethod
    def init_app(app):
        """初始化应用时创建必要的目录"""
        import os
        upload_folder = app.config.get('UPLOAD_FOLDER')
        if upload_folder and not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)


class DevelopmentConfig(Config):
    """开发环境配置 - 使用 SQLite"""
    SQLALCHEMY_DATABASE_URI = 'sqlite:///instance/workload.db'
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置 - 使用 MySQL"""
    DEBUG = False


class TestingConfig(Config):
    """测试配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}


def get_config():
    """获取当前配置"""
    env = os.environ.get('FLASK_ENV', 'production')
    return config.get(env, config['default'])
