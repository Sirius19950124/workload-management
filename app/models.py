# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统 - 数据模型
V1.0 - 2026-02-24

数据模型设计:
1. WorkloadTherapist - 治疗师信息
2. WorkloadTreatmentCategory - 治疗类别
3. WorkloadTreatmentItem - 治疗项目（含权重系数）
4. WorkloadRecord - 工作量登记记录
"""

from datetime import datetime, date
from app import db


class WorkloadTherapist(db.Model):
    """治疗师信息表"""
    __tablename__ = 'workload_therapists'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, comment='治疗师姓名')
    employee_id = db.Column(db.String(20), unique=True, nullable=True, comment='工号')
    department = db.Column(db.String(50), default='康复科', comment='所属科室')
    is_active = db.Column(db.Boolean, default=True, comment='是否在职')
    sort_order = db.Column(db.Integer, default=0, comment='排序顺序')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    workload_records = db.relationship('WorkloadRecord', backref='therapist_rel', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'employee_id': self.employee_id,
            'department': self.department,
            'is_active': self.is_active,
            'sort_order': self.sort_order
        }

    def __repr__(self):
        return f'<WorkloadTherapist {self.name}>'


class WorkloadTreatmentCategory(db.Model):
    """治疗类别表（仪器治疗、手法治疗等）"""
    __tablename__ = 'workload_treatment_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, comment='类别名称')
    description = db.Column(db.String(200), comment='类别描述')
    sort_order = db.Column(db.Integer, default=0, comment='排序顺序')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    treatment_items = db.relationship('WorkloadTreatmentItem', backref='category_rel', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'sort_order': self.sort_order,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f'<WorkloadTreatmentCategory {self.name}>'


class WorkloadTreatmentItem(db.Model):
    """治疗项目表（含权重系数）"""
    __tablename__ = 'workload_treatment_items'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=True, comment='项目编号')
    name = db.Column(db.String(100), unique=True, nullable=False, comment='治疗项目名称')
    category_id = db.Column(db.Integer, db.ForeignKey('workload_treatment_categories.id'), comment='所属类别')
    weight_coefficient = db.Column(db.Float, nullable=False, default=1.0, comment='综合权重系数')
    description = db.Column(db.String(200), comment='项目描述')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    sort_order = db.Column(db.Integer, default=0, comment='排序顺序')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    workload_records = db.relationship('WorkloadRecord', backref='treatment_item_rel', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'category_id': self.category_id,
            'category_name': self.category_rel.name if self.category_rel else None,
            'weight_coefficient': self.weight_coefficient,
            'description': self.description,
            'is_active': self.is_active,
            'sort_order': self.sort_order
        }

    def __repr__(self):
        return f'<WorkloadTreatmentItem {self.code or self.name} (权重:{self.weight_coefficient})>'


class WorkloadRecord(db.Model):
    """工作量登记记录表"""
    __tablename__ = 'workload_records'

    id = db.Column(db.Integer, primary_key=True)
    record_date = db.Column(db.Date, nullable=False, index=True, comment='登记日期')
    therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), nullable=False, comment='治疗师ID')
    patient_info = db.Column(db.String(100), comment='患者ID/姓名')
    treatment_item_id = db.Column(db.Integer, db.ForeignKey('workload_treatment_items.id'), nullable=False, comment='治疗项目ID')
    weight_coefficient = db.Column(db.Float, nullable=False, comment='权重系数（登记时的快照）')
    session_count = db.Column(db.Integer, default=1, comment='人次')
    weighted_workload = db.Column(db.Float, nullable=False, comment='加权工作量 = 权重系数 × 人次')
    remark = db.Column(db.String(200), comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(50), comment='登记人')

    # 索引
    __table_args__ = (
        db.Index('idx_workload_date_therapist', 'record_date', 'therapist_id'),
        db.Index('idx_workload_date_item', 'record_date', 'treatment_item_id'),
    )

    # 属性访问器，便于模板使用
    @property
    def therapist(self):
        return self.therapist_rel

    @property
    def treatment_item(self):
        return self.treatment_item_rel

    def to_dict(self):
        return {
            'id': self.id,
            'record_date': self.record_date.isoformat() if self.record_date else None,
            'therapist_id': self.therapist_id,
            'therapist_name': self.therapist_rel.name if self.therapist_rel else None,
            'patient_info': self.patient_info,
            'treatment_item_id': self.treatment_item_id,
            'treatment_item_name': self.treatment_item_rel.name if self.treatment_item_rel else None,
            'weight_coefficient': self.weight_coefficient,
            'session_count': self.session_count,
            'weighted_workload': self.weighted_workload,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }

    @staticmethod
    def calculate_weighted_workload(weight_coefficient, session_count):
        """计算加权工作量"""
        return round(weight_coefficient * session_count, 2)

    def __repr__(self):
        return f'<WorkloadRecord {self.record_date} {self.therapist_rel.name if self.therapist_rel else "?"} - {self.weighted_workload}>'


class WorkloadSettings(db.Model):
    """系统设置表"""
    __tablename__ = 'workload_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(50), unique=True, nullable=False, comment='设置键')
    setting_value = db.Column(db.Text, comment='设置值')
    setting_type = db.Column(db.String(20), default='string', comment='值类型: string, int, float, bool, json')
    description = db.Column(db.String(200), comment='设置说明')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.setting_key,
            'value': self.get_typed_value(),
            'type': self.setting_type,
            'description': self.description
        }

    def get_typed_value(self):
        """根据类型返回转换后的值"""
        if self.setting_value is None:
            return None

        if self.setting_type == 'int':
            return int(self.setting_value)
        elif self.setting_type == 'float':
            return float(self.setting_value)
        elif self.setting_type == 'bool':
            return self.setting_value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'json':
            import json
            try:
                return json.loads(self.setting_value)
            except:
                return self.setting_value
        else:
            return self.setting_value

    @staticmethod
    def get_value(key, default=None):
        """获取设置值"""
        setting = WorkloadSettings.query.filter_by(setting_key=key).first()
        if setting:
            return setting.get_typed_value()
        return default

    @staticmethod
    def set_value(key, value, setting_type='string', description=None):
        """设置值"""
        setting = WorkloadSettings.query.filter_by(setting_key=key).first()

        # 转换值为字符串存储
        if setting_type == 'bool':
            str_value = 'true' if value else 'false'
        elif setting_type == 'json':
            import json
            str_value = json.dumps(value, ensure_ascii=False)
        else:
            str_value = str(value)

        if setting:
            setting.setting_value = str_value
            setting.setting_type = setting_type
            if description:
                setting.description = description
        else:
            setting = WorkloadSettings(
                setting_key=key,
                setting_value=str_value,
                setting_type=setting_type,
                description=description
            )
            db.session.add(setting)

        db.session.commit()
        return setting

    def __repr__(self):
        return f'<WorkloadSettings {self.setting_key}={self.setting_value}>'


# ===================== 成就徽章系统 =====================

class Achievement(db.Model):
    """成就定义表"""
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, comment='成就代码')
    name = db.Column(db.String(100), nullable=False, comment='成就名称')
    description = db.Column(db.String(200), comment='成就描述')
    icon = db.Column(db.String(50), default='🏆', comment='图标/emoji')
    category = db.Column(db.String(50), default='general', comment='类别: count/skill/streak/special')
    condition_type = db.Column(db.String(50), nullable=False, comment='条件类型: total_sessions/total_workload/streak_days/category_sessions')
    condition_value = db.Column(db.Integer, default=0, comment='条件阈值')
    condition_extra = db.Column(db.String(100), comment='额外条件(如类别ID)')
    points_reward = db.Column(db.Integer, default=0, comment='奖励积分')
    rarity = db.Column(db.String(20), default='common', comment='稀有度: common/rare/epic/legendary')
    sort_order = db.Column(db.Integer, default=0, comment='排序顺序')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    therapist_achievements = db.relationship('TherapistAchievement', backref='achievement_rel', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'category': self.category,
            'condition_type': self.condition_type,
            'condition_value': self.condition_value,
            'points_reward': self.points_reward,
            'rarity': self.rarity,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f'<Achievement {self.code}: {self.name}>'


class TherapistAchievement(db.Model):
    """治疗师已获得的成就"""
    __tablename__ = 'therapist_achievements'

    id = db.Column(db.Integer, primary_key=True)
    therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievements.id'), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow, comment='解锁时间')
    progress = db.Column(db.Integer, default=0, comment='进度(用于部分成就)')

    # 关联
    therapist = db.relationship('WorkloadTherapist', backref='achievements_rel')
    achievement = db.relationship('Achievement')

    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('therapist_id', 'achievement_id', name='uq_therapist_achievement'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'therapist_id': self.therapist_id,
            'achievement_id': self.achievement_id,
            'achievement': self.achievement.to_dict() if self.achievement else None,
            'unlocked_at': self.unlocked_at.isoformat() if self.unlocked_at else None,
            'progress': self.progress
        }

    def __repr__(self):
        return f'<TherapistAchievement therapist={self.therapist_id} achievement={self.achievement_id}>'


class TherapistStats(db.Model):
    """治疗师统计数据（游戏化）"""
    __tablename__ = 'therapist_stats'

    id = db.Column(db.Integer, primary_key=True)
    therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), unique=True, nullable=False)

    # 累计统计
    total_sessions = db.Column(db.Integer, default=0, comment='累计治疗人次')
    total_workload = db.Column(db.Float, default=0, comment='累计加权工作量')
    total_points = db.Column(db.Integer, default=0, comment='累计积分')

    # 等级系统
    current_level = db.Column(db.Integer, default=1, comment='当前等级')
    level_progress = db.Column(db.Float, default=0, comment='当前等级进度(0-100)')

    # 连续打卡
    current_streak = db.Column(db.Integer, default=0, comment='当前连续天数')
    longest_streak = db.Column(db.Integer, default=0, comment='最长连续天数')
    last_record_date = db.Column(db.Date, comment='最后登记日期')

    # 成就统计
    achievements_count = db.Column(db.Integer, default=0, comment='已获得成就数')

    # 时间戳
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    therapist = db.relationship('WorkloadTherapist', backref='stats_rel')

    def to_dict(self):
        return {
            'id': self.id,
            'therapist_id': self.therapist_id,
            'total_sessions': self.total_sessions,
            'total_workload': self.total_workload,
            'total_points': self.total_points,
            'current_level': self.current_level,
            'level_progress': self.level_progress,
            'current_streak': self.current_streak,
            'longest_streak': self.longest_streak,
            'achievements_count': self.achievements_count,
            'last_record_date': self.last_record_date.isoformat() if self.last_record_date else None
        }

    def calculate_level(self):
        """根据总积分计算等级"""
        points = self.total_points
        if points < 500:
            return 1, (points / 500) * 100
        elif points < 1500:
            return 2, ((points - 500) / 1000) * 100
        elif points < 3000:
            return 3, ((points - 1500) / 1500) * 100
        elif points < 5000:
            return 4, ((points - 3000) / 2000) * 100
        elif points < 8000:
            return 5, ((points - 5000) / 3000) * 100
        elif points < 12000:
            return 6, ((points - 8000) / 4000) * 100
        elif points < 18000:
            return 7, ((points - 12000) / 6000) * 100
        elif points < 25000:
            return 8, ((points - 18000) / 7000) * 100
        else:
            return 9, 100

    @staticmethod
    def get_level_name(level):
        """获取等级名称"""
        level_names = {
            1: '初级治疗师',
            2: '中级治疗师',
            3: '高级治疗师',
            4: '资深治疗师',
            5: '专家治疗师',
            6: '副主任技师',
            7: '主任技师',
            8: '康复大师',
            9: '传奇治疗师'
        }
        return level_names.get(level, '未知等级')

    @staticmethod
    def get_level_badge(level):
        """获取等级徽章"""
        badges = {
            1: '🥉',
            2: '🥈',
            3: '🥇',
            4: '💎',
            5: '👑',
            6: '🌟',
            7: '💫',
            8: '🏆',
            9: '🏅'
        }
        return badges.get(level, '⭐')

    def __repr__(self):
        return f'<TherapistStats therapist={self.therapist_id} level={self.current_level} points={self.total_points}>'


# 默认成就定义
DEFAULT_ACHIEVEMENTS = [
    # 数量成就 - 治疗人次
    {'code': 'first_10', 'name': '初露锋芒', 'description': '累计完成10次治疗', 'icon': '🌱', 'category': 'count', 'condition_type': 'total_sessions', 'condition_value': 10, 'points_reward': 10, 'rarity': 'common'},
    {'code': 'first_50', 'name': '渐入佳境', 'description': '累计完成50次治疗', 'icon': '🌿', 'category': 'count', 'condition_type': 'total_sessions', 'condition_value': 50, 'points_reward': 30, 'rarity': 'common'},
    {'code': 'first_100', 'name': '技艺精进', 'description': '累计完成100次治疗', 'icon': '⭐', 'category': 'count', 'condition_type': 'total_sessions', 'condition_value': 100, 'points_reward': 50, 'rarity': 'common'},
    {'code': 'first_500', 'name': '炉火纯青', 'description': '累计完成500次治疗', 'icon': '🌟', 'category': 'count', 'condition_type': 'total_sessions', 'condition_value': 500, 'points_reward': 100, 'rarity': 'rare'},
    {'code': 'first_1000', 'name': '康复大师', 'description': '累计完成1000次治疗', 'icon': '💫', 'category': 'count', 'condition_type': 'total_sessions', 'condition_value': 1000, 'points_reward': 200, 'rarity': 'epic'},
    {'code': 'first_5000', 'name': '传奇治疗师', 'description': '累计完成5000次治疗', 'icon': '🏆', 'category': 'count', 'condition_type': 'total_sessions', 'condition_value': 5000, 'points_reward': 500, 'rarity': 'legendary'},

    # 数量成就 - 工作量
    {'code': 'workload_100', 'name': '勤奋之星', 'description': '累计工作量达到100', 'icon': '💪', 'category': 'count', 'condition_type': 'total_workload', 'condition_value': 100, 'points_reward': 20, 'rarity': 'common'},
    {'code': 'workload_500', 'name': '努力标兵', 'description': '累计工作量达到500', 'icon': '🔥', 'category': 'count', 'condition_type': 'total_workload', 'condition_value': 500, 'points_reward': 50, 'rarity': 'common'},
    {'code': 'workload_1000', 'name': '劳动模范', 'description': '累计工作量达到1000', 'icon': '👑', 'category': 'count', 'condition_type': 'total_workload', 'condition_value': 1000, 'points_reward': 100, 'rarity': 'rare'},
    {'code': 'workload_5000', 'name': '工作狂人', 'description': '累计工作量达到5000', 'icon': '💎', 'category': 'count', 'condition_type': 'total_workload', 'condition_value': 5000, 'points_reward': 300, 'rarity': 'epic'},

    # 连续打卡成就
    {'code': 'streak_3', 'name': '三天成习', 'description': '连续3天有治疗记录', 'icon': '🎯', 'category': 'streak', 'condition_type': 'streak_days', 'condition_value': 3, 'points_reward': 10, 'rarity': 'common'},
    {'code': 'streak_7', 'name': '周周坚持', 'description': '连续7天有治疗记录', 'icon': '🔥', 'category': 'streak', 'condition_type': 'streak_days', 'condition_value': 7, 'points_reward': 30, 'rarity': 'common'},
    {'code': 'streak_14', 'name': '坚持达人', 'description': '连续14天有治疗记录', 'icon': '💪', 'category': 'streak', 'condition_type': 'streak_days', 'condition_value': 14, 'points_reward': 60, 'rarity': 'rare'},
    {'code': 'streak_30', 'name': '敬业之星', 'description': '连续30天有治疗记录', 'icon': '⭐', 'category': 'streak', 'condition_type': 'streak_days', 'condition_value': 30, 'points_reward': 100, 'rarity': 'epic'},
    {'code': 'streak_60', 'name': '劳模称号', 'description': '连续60天有治疗记录', 'icon': '🏅', 'category': 'streak', 'condition_type': 'streak_days', 'condition_value': 60, 'points_reward': 200, 'rarity': 'legendary'},

    # 单日成就
    {'code': 'daily_50', 'name': '高效能者', 'description': '单日工作量达到50', 'icon': '⚡', 'category': 'special', 'condition_type': 'daily_workload', 'condition_value': 50, 'points_reward': 30, 'rarity': 'rare'},
    {'code': 'daily_100', 'name': '爆发之星', 'description': '单日工作量达到100', 'icon': '💥', 'category': 'special', 'condition_type': 'daily_workload', 'condition_value': 100, 'points_reward': 80, 'rarity': 'epic'},
]


# 默认设置常量
DEFAULT_SETTINGS = {
    'allow_past_date': {
        'value': False,
        'type': 'bool',
        'description': '允许录入过往日期的记录'
    },
    'past_date_max_days': {
        'value': 7,
        'type': 'int',
        'description': '允许录入的最大过往天数（从今天起）'
    }
}
