# -*- coding: utf-8 -*-
"""
惠阳妇幼保健院康复科业务管理系统 - 数据模型
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
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=True, comment='患者ID（关联患者表）')
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
            'patient_id': self.patient_id,
            'patient_name': self.patient_rel.name if self.patient_rel else self.patient_info,
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
        points = self.total_points or 0
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
            1: '康复新星',      # 新入门
            2: '治疗能手',      # 有能力
            3: '优秀治疗师',    # 优秀
            4: '资深治疗师',    # 资深
            5: '康复专家',      # 专家
            6: '治疗达人',      # 达人级
            7: '康复大师',      # 大师级
            8: '传奇治疗师',    # 传奇
            9: '荣耀至尊'       # 最高荣誉
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


# ===================== 患者管理系统 =====================

class Patient(db.Model):
    """患者信息表"""
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, comment='患者姓名')
    patient_no = db.Column(db.String(30), unique=True, nullable=True, comment='患者编号/住院号')
    gender = db.Column(db.String(10), comment='性别')
    age = db.Column(db.Integer, comment='年龄')
    phone = db.Column(db.String(20), comment='联系电话')
    diagnosis = db.Column(db.String(200), comment='诊断')
    bed_no = db.Column(db.String(20), comment='床号')

    # 主管治疗师关联（支持最多3个治疗师）
    primary_therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), comment='主管治疗师1 ID')
    secondary_therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), comment='主管治疗师2 ID')
    tertiary_therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), comment='主管治疗师3 ID')

    # 状态
    status = db.Column(db.String(20), default='active', comment='状态: active-在治, completed-已结束, paused-暂停')

    # 复诊提醒相关
    alert_dismissed = db.Column(db.Boolean, default=False, comment='是否已消除提醒')
    alert_dismiss_reason = db.Column(db.String(200), comment='消除提醒的理由')
    alert_dismissed_at = db.Column(db.DateTime, comment='消除提醒时间')
    admission_date = db.Column(db.Date, comment='入院日期')
    discharge_date = db.Column(db.Date, comment='出院日期')

    # 备注
    notes = db.Column(db.Text, comment='备注信息')

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    primary_therapist = db.relationship('WorkloadTherapist', foreign_keys=[primary_therapist_id],
                                          backref=db.backref('managed_patients', lazy='dynamic'))
    secondary_therapist = db.relationship('WorkloadTherapist', foreign_keys=[secondary_therapist_id],
                                            backref=db.backref('secondary_patients', lazy='dynamic'))
    tertiary_therapist = db.relationship('WorkloadTherapist', foreign_keys=[tertiary_therapist_id],
                                          backref=db.backref('tertiary_patients', lazy='dynamic'))
    workload_records = db.relationship('WorkloadRecord', backref='patient_rel',
                                       foreign_keys='WorkloadRecord.patient_id',
                                       lazy='dynamic')

    def to_dict(self):
        # 计算最后治疗日期
        last_record = self.workload_records.order_by(db.desc('record_date')).first()
        last_treatment_date = last_record.record_date.isoformat() if last_record and last_record.record_date else None

        # 计算距今天数
        days_since_last = None
        if last_treatment_date:
            from datetime import date
            last_date = date.fromisoformat(last_treatment_date)
            days_since_last = (date.today() - last_date).days

        return {
            'id': self.id,
            'name': self.name,
            'patient_no': self.patient_no,
            'gender': self.gender,
            'age': self.age,
            'phone': self.phone,
            'diagnosis': self.diagnosis,
            'bed_no': self.bed_no,
            'primary_therapist_id': self.primary_therapist_id,
            'primary_therapist_name': self.primary_therapist.name if self.primary_therapist else None,
            'secondary_therapist_id': self.secondary_therapist_id,
            'secondary_therapist_name': self.secondary_therapist.name if self.secondary_therapist else None,
            'tertiary_therapist_id': self.tertiary_therapist_id,
            'tertiary_therapist_name': self.tertiary_therapist.name if self.tertiary_therapist else None,
            'status': self.status,
            'status_display': self.get_status_display(),
            'admission_date': self.admission_date.isoformat() if self.admission_date else None,
            'discharge_date': self.discharge_date.isoformat() if self.discharge_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'treatment_count': self.workload_records.count(),
            'last_treatment_date': last_treatment_date,
            'days_since_last_treatment': days_since_last,
            'alert_dismissed': self.alert_dismissed,
            'alert_dismiss_reason': self.alert_dismiss_reason
        }

    def get_status_display(self):
        """获取状态显示文本"""
        status_map = {
            'active': '在治',
            'completed': '已结束',
            'paused': '暂停'
        }
        return status_map.get(self.status, self.status)

    def __repr__(self):
        return f'<Patient {self.name} (主管: {self.primary_therapist.name if self.primary_therapist else "无"})>'


# ===================== 评价系统（小程序用） =====================

class Rating(db.Model):
    """治疗评价表"""
    __tablename__ = 'ratings'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, comment='患者ID')
    record_id = db.Column(db.Integer, db.ForeignKey('workload_records.id'), nullable=True, comment='治疗记录ID（可选）')
    therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), nullable=True, comment='治疗师ID')
    treatment_item_id = db.Column(db.Integer, db.ForeignKey('workload_treatment_items.id'), nullable=True, comment='治疗项目ID')

    star_rating = db.Column(db.Integer, nullable=False, comment='星级评分(1-5)')
    comment = db.Column(db.Text, comment='评价内容')
    tags = db.Column(db.String(200), comment='评价标签(逗号分隔)')

    # 微信相关
    openid = db.Column(db.String(64), comment='微信openid')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    patient = db.relationship('Patient', backref='ratings')
    record = db.relationship('WorkloadRecord', backref='ratings')
    therapist = db.relationship('WorkloadTherapist', backref='ratings')

    __table_args__ = (
        db.Index('idx_ratings_patient', 'patient_id'),
        db.Index('idx_ratings_therapist', 'therapist_id'),
        db.Index('idx_ratings_record', 'record_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.name if self.patient else None,
            'record_id': self.record_id,
            'therapist_id': self.therapist_id,
            'therapist_name': self.therapist.name if self.therapist else None,
            'treatment_item_id': self.treatment_item_id,
            'treatment_item_name': self.record.treatment_item_rel.name if self.record and self.record.treatment_item_rel else None,
            'star_rating': self.star_rating,
            'comment': self.comment,
            'tags': self.tags.split(',') if self.tags else [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Rating id={self.id} patient={self.patient_id} stars={self.star_rating}>'


# ===================== 评价问卷配置 =====================

class RatingQuestion(db.Model):
    """评价问卷题目配置表"""
    __tablename__ = 'rating_questions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, comment='问题标题')
    question_type = db.Column(db.String(20), nullable=False, default='star', comment='类型: star/radio/text')
    options = db.Column(db.Text, comment='选项(JSON数组, 用于radio类型)')
    is_required = db.Column(db.Boolean, default=True, comment='是否必填')
    sort_order = db.Column(db.Integer, default=0, comment='排序顺序')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        options_list = []
        if self.options:
            import json
            try:
                options_list = json.loads(self.options)
            except:
                options_list = []
        return {
            'id': self.id,
            'title': self.title,
            'question_type': self.question_type,
            'options': options_list,
            'is_required': self.is_required,
            'sort_order': self.sort_order,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f'<RatingQuestion id={self.id} title={self.title} type={self.question_type}>'


class RatingAnswer(db.Model):
    """评价答案表（支持多维度问卷）"""
    __tablename__ = 'rating_answers'

    id = db.Column(db.Integer, primary_key=True)
    rating_id = db.Column(db.Integer, db.ForeignKey('ratings.id'), nullable=False, comment='评价ID')
    question_id = db.Column(db.Integer, db.ForeignKey('rating_questions.id'), nullable=False, comment='问题ID')
    answer_value = db.Column(db.String(500), comment='答案值(星级存数字, 单选存选项文本, 文本存内容)')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    rating = db.relationship('Rating', backref='answers')
    question = db.relationship('RatingQuestion')

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'question_title': self.question.title if self.question else None,
            'question_type': self.question.question_type if self.question else None,
            'answer_value': self.answer_value
        }

    def __repr__(self):
        return f'<RatingAnswer rating={self.rating_id} question={self.question_id}>'


class WorkloadOperationLog(db.Model):
    """操作日志表"""
    __tablename__ = 'workload_operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    log_type = db.Column(db.String(20), nullable=False, index=True, comment='操作类型: create/update/delete/import/export/backup/restore/setting/other')
    detail = db.Column(db.Text, nullable=False, comment='操作详情')
    operator = db.Column(db.String(50), default='系统', comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True, comment='操作时间')

    def to_dict(self):
        return {
            'id': self.id,
            'log_type': self.log_type,
            'detail': self.detail,
            'operator': self.operator,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f'<WorkloadOperationLog [{self.log_type}] {self.detail[:30]}>'


# 默认评价问卷题目
import json as _json
DEFAULT_RATING_QUESTIONS = [
    {'title': '服务态度', 'question_type': 'star', 'is_required': True, 'sort_order': 1},
    {'title': '治疗效果', 'question_type': 'star', 'is_required': True, 'sort_order': 2},
    {'title': '整体满意度', 'question_type': 'star', 'is_required': True, 'sort_order': 3},
    {'title': '是否愿意该治疗师继续为您治疗？', 'question_type': 'radio',
     'options': _json.dumps(['愿意', '暂不考虑'], ensure_ascii=False), 'is_required': True, 'sort_order': 4},
    {'title': '其他建议', 'question_type': 'text', 'is_required': False, 'sort_order': 5},
]


# ===================== 在线培训考试系统 =====================

class TrainingMaterial(db.Model):
    """培训资料表 - 上传的PDF/Word/文本文件"""
    __tablename__ = 'training_materials'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, comment='资料标题')
    description = db.Column(db.Text, comment='资料描述')
    file_name = db.Column(db.String(200), nullable=False, comment='原始文件名')
    file_path = db.Column(db.String(500), nullable=False, comment='存储路径(相对uploads)')
    file_type = db.Column(db.String(20), comment='文件类型: pdf/word/txt')
    file_size = db.Column(db.Integer, comment='文件大小(bytes)')
    extracted_text = db.Column(db.Text, comment='从文件提取的纯文本内容')
    category = db.Column(db.String(50), default='通用', comment='资料分类')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship('QuestionBank', backref='material_rel', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'category': self.category,
            'question_count': self.questions.count(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<TrainingMaterial {self.title}>'


class QuestionBank(db.Model):
    """题库表 - AI生成或手动创建的题目"""
    __tablename__ = 'question_bank'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('training_materials.id'), nullable=True, comment='关联的培训资料ID')
    question_type = db.Column(db.String(20), nullable=False, comment='题型: single_choice/multiple_choice/true_false/fill_blank')
    question_text = db.Column(db.Text, nullable=False, comment='题干内容')
    options = db.Column(db.Text, comment='选项(JSON数组)')
    answer = db.Column(db.Text, nullable=False, comment='正确答案')
    analysis = db.Column(db.Text, comment='解析/说明')
    difficulty = db.Column(db.String(10), default='medium', comment='难度: easy/medium/hard')
    score = db.Column(db.Integer, default=2, comment='分值(默认2分)')
    source = db.Column(db.String(20), default='manual', comment='来源: ai_generated/manual/imported')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json as _json
        options_list = []
        if self.options:
            try:
                options_list = _json.loads(self.options)
            except:
                options_list = []
        return {
            'id': self.id,
            'material_id': self.material_id,
            'material_title': self.material_rel.title if self.material_rel else None,
            'question_type': self.question_type,
            'question_text': self.question_text,
            'options': options_list,
            'answer': self.answer,
            'analysis': self.analysis,
            'difficulty': self.difficulty,
            'score': self.score,
            'source': self.source,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<QuestionBank [{self.question_type}] {self.question_text[:30]}...>'


class ExamPaper(db.Model):
    """试卷表 - 由题目组成的考试"""
    __tablename__ = 'exam_papers'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, comment='试卷标题')
    description = db.Column(db.Text, comment='试卷说明')
    total_score = db.Column(db.Integer, default=100, comment='总分')
    pass_score = db.Column(db.Integer, default=60, comment='及格分数')
    duration_minutes = db.Column(db.Integer, default=60, comment='考试时长(分钟)')
    status = db.Column(db.String(20), default='draft', comment='状态: draft/published/closed')
    shuffle_questions = db.Column(db.Boolean, default=True, comment='是否打乱题目顺序')
    shuffle_options = db.Column(db.Boolean, default=True, comment='是否打乱选项顺序')
    show_answer_after_submit = db.Column(db.Boolean, default=True, comment='提交后显示答案')
    start_time = db.Column(db.DateTime, comment='考试开始时间')
    end_time = db.Column(db.DateTime, comment='考试截止时间')
    created_by = db.Column(db.String(50), comment='创建人')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship('ExamPaperQuestion', backref='paper_rel', lazy='dynamic', cascade='all, delete-orphan')
    assignments = db.relationship('ExamAssignment', backref='paper_rel', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'total_score': self.total_score,
            'pass_score': self.pass_score,
            'duration_minutes': self.duration_minutes,
            'status': self.status,
            'shuffle_questions': self.shuffle_questions,
            'shuffle_options': self.shuffle_options,
            'show_answer_after_submit': self.show_answer_after_submit,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'question_count': self.questions.count(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<ExamPaper {self.title} [{self.status}]>'


class ExamPaperQuestion(db.Model):
    """试卷题目关联表"""
    __tablename__ = 'exam_paper_questions'

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('exam_papers.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question_bank.id'), nullable=False)
    sort_order = db.Column(db.Integer, default=0, comment='在试卷中的排序')
    score = db.Column(db.Integer, default=2, comment='该题在试卷中的分值')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('QuestionBank')

    __table_args__ = (
        db.UniqueConstraint('paper_id', 'question_id', name='uq_paper_question'),
    )

    def to_dict(self):
        qdict = self.question.to_dict() if self.question else {}
        qdict['sort_order'] = self.sort_order
        qdict['score'] = self.score
        return qdict

    def __repr__(self):
        return f'<ExamPaperQuestion paper={self.paper_id} q={self.question_id}>'


class ExamAssignment(db.Model):
    """考试分配表 - 哪些治疗师需要参加哪个考试"""
    __tablename__ = 'exam_assignments'

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('exam_papers.id'), nullable=False)
    therapist_id = db.Column(db.Integer, db.ForeignKey('workload_therapists.id'), nullable=False)
    status = db.Column(db.String(20), default='assigned', comment='状态: assigned/started/submitted')
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, comment='分配时间')
    started_at = db.Column(db.DateTime, comment='开始答题时间')
    submitted_at = db.Column(db.DateTime, comment='提交时间')

    therapist = db.relationship('WorkloadTherapist')
    answer_record = db.relationship('ExamAnswer', backref='assignment_rel', uselist=False)

    __table_args__ = (
        db.UniqueConstraint('paper_id', 'therapist_id', name='uq_paper_therapist'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'paper_id': self.paper_id,
            'paper_title': self.paper_rel.title if self.paper_rel else None,
            'therapist_id': self.therapist_id,
            'therapist_name': self.therapist.name if self.therapist else None,
            'status': self.status,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'has_answer': self.answer_record is not None
        }

    def __repr__(self):
        return f'<ExamAssignment paper={self.paper_id} therapist={self.therapist_id} [{self.status}]>'


class ExamAnswer(db.Model):
    """答卷记录表 - 治疗师的答案和评分"""
    __tablename__ = 'exam_answers'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('exam_assignments.id'), nullable=False, unique=True)
    answers_json = db.Column(db.Text, comment='所有答案(JSON数组)')
    score = db.Column(db.Integer, default=0, comment='得分')
    total_score = db.Column(db.Integer, default=0, comment='试卷总分')
    time_spent_seconds = db.Column(db.Integer, default=0, comment='答题耗时(秒)')
    grading_detail = db.Column(db.Text, comment='评卷详情(JSON)')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json as _json
        answers = []
        if self.answers_json:
            try:
                answers = _json.loads(self.answers_json)
            except:
                answers = []
        detail = []
        if self.grading_detail:
            try:
                detail = _json.loads(self.grading_detail)
            except:
                detail = []
        # 获取试卷及格分（通过assignment关联）
        pass_score = None
        if self.assignment_rel and self.assignment_rel.paper_rel:
            pass_score = self.assignment_rel.paper_rel.pass_score
        is_passed = self.score >= pass_score if (pass_score is not None and self.total_score > 0) else (self.score >= self.total_score * 0.6 if self.total_score > 0 else False)
        return {
            'id': self.id,
            'assignment_id': self.assignment_id,
            'answers': answers,
            'score': self.score,
            'total_score': self.total_score,
            'time_spent_seconds': self.time_spent_seconds,
            'time_spent_display': f'{self.time_spent_seconds // 60}分{self.time_spent_seconds % 60}秒',
            'is_passed': is_passed,
            'pass_rate': round(self.score / self.total_score * 100, 1) if self.total_score > 0 else 0,
            'grading_detail': detail,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<ExamAnswer assignment={self.assignment_id} score={self.score}/{self.total_score}>'


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
