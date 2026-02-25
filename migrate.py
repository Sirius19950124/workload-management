# -*- coding: utf-8 -*-
"""
工作量管理系统数据库迁移脚本
运行方式: python migrate.py
"""

import sys
import os

# 设置控制台编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    WorkloadTherapist, WorkloadTreatmentCategory,
    WorkloadTreatmentItem, WorkloadRecord
)

def migrate():
    """执行数据库迁移"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("工作量管理系统数据库迁移")
        print("=" * 60)

        # 创建所有表
        print("\n[1/3] 创建数据库表...")
        try:
            db.create_all()
            print("[OK] 数据库表创建成功")
        except Exception as e:
            print(f"[ERROR] 创建表失败: {e}")
            return False

        # 检查是否已有数据
        print("\n[2/3] 检查初始数据...")
        if WorkloadTherapist.query.count() == 0:
            print("正在创建初始治疗师数据...")
            default_therapists = [
                ('李德裕', None, 1),
                ('陈宇凡', None, 2),
                ('白芮', None, 3),
                ('张婷', None, 4),
                ('刘惠彬', None, 5),
                ('黄子珊', None, 6),
                ('詹秋怡', None, 7),
                ('黄伟红', None, 8),
                ('胡玉芬', None, 9),
            ]
            for name, emp_id, sort_order in default_therapists:
                therapist = WorkloadTherapist(name=name, employee_id=emp_id, sort_order=sort_order)
                db.session.add(therapist)
            db.session.commit()
            print(f"[OK] 创建了 {len(default_therapists)} 个默认治疗师")
        else:
            print(f"[INFO] 已存在 {WorkloadTherapist.query.count()} 个治疗师")

        if WorkloadTreatmentCategory.query.count() == 0:
            print("正在创建初始治疗类别...")
            default_categories = [
                ('仪器治疗', '使用仪器设备进行的治疗项目', 1),
                ('手法治疗', '治疗师手工操作的治疗项目', 2),
                ('运动疗法', '运动康复训练项目', 3),
                ('物理因子治疗', '电疗、光疗、磁疗等', 4),
                ('中医传统治疗', '针灸、推拿、拔罐等', 5),
            ]
            for name, desc, sort_order in default_categories:
                category = WorkloadTreatmentCategory(name=name, description=desc, sort_order=sort_order)
                db.session.add(category)
            db.session.commit()
            print(f"[OK] 创建了 {len(default_categories)} 个默认治疗类别")
        else:
            print(f"[INFO] 已存在 {WorkloadTreatmentCategory.query.count()} 个治疗类别")

        if WorkloadTreatmentItem.query.count() == 0:
            print("正在创建初始治疗项目...")
            # 获取类别
            categories = {c.name: c.id for c in WorkloadTreatmentCategory.query.all()}

            default_items = [
                # 仪器治疗
                ('盆底电', '仪器治疗', 1.83),
                ('盆底磁', '仪器治疗', 0.83),
                ('盆底筛查', '仪器治疗', 1.83),
                ('悬空灸', '仪器治疗', 0.83),
                ('低频脉冲电治疗', '仪器治疗', 0.83),
                ('中频脉冲电治疗', '仪器治疗', 0.83),
                ('冲击波', '仪器治疗', 1.50),
                ('DMS', '仪器治疗', 1.41),
                ('超声波治疗', '仪器治疗', 1.51),
                # 手法治疗
                ('腰腿病治疗（套餐手法）', '手法治疗', 10.08),
                ('颈椎病治疗（套餐手法）', '手法治疗', 10.08),
                ('颈椎病筋膜松解', '手法治疗', 5.92),
                ('腰腿病筋膜松解', '手法治疗', 5.92),
                ('骨盆调整（套餐手法）', '手法治疗', 10.08),
                ('骨盆调整（体）（套餐手法）', '手法治疗', 15.67),
                ('盆底康复体外筋膜松解（套餐手法）', '手法治疗', 4.92),
                ('腹部修复（套餐手法）', '手法治疗', 4.92),
                ('产伤性腹直肌分离治疗（套餐手法）', '手法治疗', 5.00),
                ('产后/妊娠合并耻骨联合分离治疗（套餐手法）', '手法治疗', 7.00),
                ('关节疾病治疗（单关节）（套餐手法）', '手法治疗', 6.25),
                ('正骨', '手法治疗', 2.83),
                ('家庭康复训练指导', '手法治疗', 1.33),
            ]

            for name, cat_name, weight in default_items:
                cat_id = categories.get(cat_name)
                item = WorkloadTreatmentItem(name=name, category_id=cat_id, weight_coefficient=weight)
                db.session.add(item)
            db.session.commit()
            print(f"[OK] 创建了 {len(default_items)} 个默认治疗项目")
        else:
            print(f"[INFO] 已存在 {WorkloadTreatmentItem.query.count()} 个治疗项目")

        # 显示统计
        print("\n[3/3] 数据库迁移完成")
        print("=" * 60)
        print(f"治疗师数量: {WorkloadTherapist.query.count()}")
        print(f"治疗类别数量: {WorkloadTreatmentCategory.query.count()}")
        print(f"治疗项目数量: {WorkloadTreatmentItem.query.count()}")
        print(f"工作量记录数量: {WorkloadRecord.query.count()}")
        print("=" * 60)
        print("\n[OK] 迁移成功!")
        print("\n访问地址: http://localhost:5001")

        return True


if __name__ == '__main__':
    migrate()
