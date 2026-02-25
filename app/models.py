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
