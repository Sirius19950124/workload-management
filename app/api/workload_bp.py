# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统 - API蓝图
V1.0 - 2026-02-24

API端点:
1. 治疗师管理: /api/therapists
2. 治疗项目管理: /api/treatment-items
3. 治疗类别管理: /api/categories
4. 工作量登记: /api/records
5. 统计分析: /api/statistics
"""

from flask import Blueprint, request, jsonify
import re
from sqlalchemy import extract, func
from app import db
from app.models import (
    WorkloadTherapist, WorkloadTreatmentCategory,
    WorkloadTreatmentItem, WorkloadRecord, WorkloadSettings
)
from app.api.achievement_bp import update_therapist_stats, check_and_award_achievements
from app.api.achievement_bp import update_therapist_stats, check_and_award_achievements
from datetime import date, datetime, timedelta

workload_bp = Blueprint('workload', __name__, url_prefix='/api')


# ============================================================================
# 治疗师管理 API
# ============================================================================

@workload_bp.route('/therapists', methods=['GET'])
def get_therapists():
    """获取治疗师列表"""
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    query = WorkloadTherapist.query
    if active_only:
        query = query.filter_by(is_active=True)

    therapists = query.order_by(WorkloadTherapist.sort_order).all()

    return jsonify({
        'success': True,
        'data': {
            'therapists': [t.to_dict() for t in therapists],
            'total': len(therapists)
        }
    })


@workload_bp.route('/therapists', methods=['POST'])
def create_therapist():
    """创建治疗师"""
    try:
        data = request.get_json()

        if not data or not data.get('name'):
            return jsonify({'success': False, 'error': '治疗师姓名不能为空'}), 400

        # 检查姓名是否已存在
        if WorkloadTherapist.query.filter_by(name=data['name']).first():
            return jsonify({'success': False, 'error': '该治疗师姓名已存在'}), 400

        # 处理工号：空字符串转为 None，避免唯一约束冲突
        employee_id = data.get('employee_id')
        if employee_id is not None:
            employee_id = employee_id.strip() if employee_id.strip() else None

        # 检查工号是否已存在（仅当工号不为空时）
        if employee_id and WorkloadTherapist.query.filter_by(employee_id=employee_id).first():
            return jsonify({'success': False, 'error': f'工号 "{employee_id}" 已被使用，请使用其他工号'}), 400

        therapist = WorkloadTherapist(
            name=data['name'],
            employee_id=employee_id,
            department=data.get('department', '康复科'),
            sort_order=data.get('sort_order', 0)
        )

        db.session.add(therapist)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '治疗师创建成功',
            'data': therapist.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'创建失败: {str(e)}'}), 500


@workload_bp.route('/therapists/<int:therapist_id>', methods=['PUT'])
def update_therapist(therapist_id):
    """更新治疗师"""
    try:
        therapist = WorkloadTherapist.query.get(therapist_id)
        if not therapist:
            return jsonify({'success': False, 'error': '治疗师不存在'}), 404

        data = request.get_json()

        # 检查姓名是否与其他治疗师重复
        if data.get('name') and data['name'] != therapist.name:
            existing = WorkloadTherapist.query.filter_by(name=data['name']).first()
            if existing:
                return jsonify({'success': False, 'error': '该治疗师姓名已存在'}), 400
            therapist.name = data['name']

        # 处理工号更新
        if 'employee_id' in data:
            new_employee_id = data['employee_id']
            if new_employee_id is not None:
                new_employee_id = new_employee_id.strip() if new_employee_id.strip() else None

            # 检查工号是否与其他治疗师重复
            if new_employee_id and new_employee_id != therapist.employee_id:
                existing = WorkloadTherapist.query.filter_by(employee_id=new_employee_id).first()
                if existing:
                    return jsonify({'success': False, 'error': f'工号 "{new_employee_id}" 已被使用，请使用其他工号'}), 400
            therapist.employee_id = new_employee_id

        if 'department' in data:
            therapist.department = data['department']
        if 'is_active' in data:
            therapist.is_active = data['is_active']
        if 'sort_order' in data:
            therapist.sort_order = data['sort_order']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '治疗师更新成功',
            'data': therapist.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'更新失败: {str(e)}'}), 500


@workload_bp.route('/therapists/<int:therapist_id>', methods=['DELETE'])
def delete_therapist(therapist_id):
    """删除治疗师（软删除）"""
    therapist = WorkloadTherapist.query.get(therapist_id)
    if not therapist:
        return jsonify({'success': False, 'error': '治疗师不存在'}), 404

    therapist.is_active = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '治疗师已删除'
    })


# ============================================================================
# 治疗项目管理 API
# ============================================================================

@workload_bp.route('/treatment-items', methods=['GET'])
def get_treatment_items():
    """获取治疗项目列表"""
    category_id = request.args.get('category_id', type=int)
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    search = request.args.get('search', '').strip()

    query = WorkloadTreatmentItem.query

    if category_id:
        query = query.filter_by(category_id=category_id)
    if active_only:
        query = query.filter_by(is_active=True)
    if search:
        query = query.filter(WorkloadTreatmentItem.name.contains(search))

    items = query.join(WorkloadTreatmentCategory, isouter=True).order_by(
        WorkloadTreatmentCategory.sort_order, WorkloadTreatmentItem.sort_order
    ).all()

    return jsonify({
        'success': True,
        'data': {
            'items': [item.to_dict() for item in items],
            'total': len(items)
        }
    })


@workload_bp.route('/treatment-items', methods=['POST'])
def create_treatment_item():
    """创建治疗项目"""
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': '治疗项目名称不能为空'}), 400

    if WorkloadTreatmentItem.query.filter_by(name=data['name']).first():
        return jsonify({'success': False, 'error': '该治疗项目已存在'}), 400

    if data.get('code') and WorkloadTreatmentItem.query.filter_by(code=data['code']).first():
        return jsonify({'success': False, 'error': '该编号已被使用'}), 400

    item = WorkloadTreatmentItem(
        code=data.get('code'),
        name=data['name'],
        category_id=data.get('category_id'),
        weight_coefficient=data.get('weight_coefficient', 1.0),
        description=data.get('description'),
        sort_order=data.get('sort_order', 0)
    )

    db.session.add(item)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '治疗项目创建成功',
        'data': item.to_dict()
    }), 201


@workload_bp.route('/treatment-items/<int:item_id>', methods=['PUT'])
def update_treatment_item(item_id):
    """更新治疗项目"""
    item = WorkloadTreatmentItem.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'error': '治疗项目不存在'}), 404

    data = request.get_json()

    if data.get('code'):
        existing = WorkloadTreatmentItem.query.filter_by(code=data['code']).first()
        if existing and existing.id != item_id:
            return jsonify({'success': False, 'error': '该编号已被使用'}), 400
        item.code = data['code']
    if data.get('name'):
        item.name = data['name']
    if 'category_id' in data:
        item.category_id = data['category_id']
    if 'weight_coefficient' in data:
        item.weight_coefficient = data['weight_coefficient']
    if 'description' in data:
        item.description = data['description']
    if 'is_active' in data:
        item.is_active = data['is_active']
    if 'sort_order' in data:
        item.sort_order = data['sort_order']

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '治疗项目更新成功',
        'data': item.to_dict()
    })


@workload_bp.route('/treatment-items/<int:item_id>', methods=['DELETE'])
def delete_treatment_item(item_id):
    """删除治疗项目（软删除）"""
    item = WorkloadTreatmentItem.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'error': '治疗项目不存在'}), 404

    item.is_active = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '治疗项目已删除'
    })


@workload_bp.route('/treatment-items/batch', methods=['POST'])
def batch_create_treatment_items():
    """批量创建治疗项目"""
    data = request.get_json()

    if not data or not data.get('items'):
        return jsonify({'success': False, 'error': '请提供项目数据'}), 400

    items_data = data['items']
    created = 0
    skipped = 0
    categories_created = 0
    errors = []

    for item_data in items_data:
        name = item_data.get('name', '').strip()
        if not name:
            continue

        code = item_data.get('code', '').strip() if item_data.get('code') else None

        # 检查是否已存在（按名称或编号）
        existing = WorkloadTreatmentItem.query.filter(
            (WorkloadTreatmentItem.name == name) |
            (code and WorkloadTreatmentItem.code == code)
        ).first()
        if existing:
            skipped += 1
            continue

        # 处理类别
        category_id = None
        category_name = item_data.get('category', '').strip()
        if category_name:
            category = WorkloadTreatmentCategory.query.filter_by(name=category_name).first()
            if not category:
                category = WorkloadTreatmentCategory(
                    name=category_name,
                    sort_order=0
                )
                db.session.add(category)
                db.session.flush()
                categories_created += 1
            category_id = category.id

        try:
            item = WorkloadTreatmentItem(
                code=code,
                name=name,
                category_id=category_id,
                weight_coefficient=float(item_data.get('weight', 1.0)),
                sort_order=0
            )
            db.session.add(item)
            created += 1
        except Exception as e:
            errors.append(f'{name}: {str(e)}')

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'成功创建 {created} 个项目',
        'data': {
            'created': created,
            'skipped': skipped,
            'categories_created': categories_created,
            'errors': errors
        }
    }), 201


@workload_bp.route('/treatment-items/batch-delete', methods=['POST'])
def batch_delete_treatment_items():
    """批量删除治疗项目"""
    data = request.get_json()

    if not data or not data.get('ids'):
        return jsonify({'success': False, 'error': '请提供要删除的项目ID'}), 400

    ids = data['ids']
    deleted = 0
    failed = 0

    for item_id in ids:
        item = WorkloadTreatmentItem.query.get(item_id)
        if item:
            # 检查是否有关联的工作量记录
            record_count = WorkloadRecord.query.filter_by(treatment_item_id=item_id).count()
            if record_count > 0:
                failed += 1
                continue

            db.session.delete(item)
            deleted += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'成功删除 {deleted} 个项目',
        'data': {
            'deleted': deleted,
            'failed': failed
        }
    })


# ============================================================================
# 治疗类别管理 API
# ============================================================================

@workload_bp.route('/categories', methods=['GET'])
def get_categories():
    """获取治疗类别列表"""
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    query = WorkloadTreatmentCategory.query
    if active_only:
        query = query.filter_by(is_active=True)

    categories = query.order_by(WorkloadTreatmentCategory.sort_order).all()

    return jsonify({
        'success': True,
        'data': {
            'categories': [c.to_dict() for c in categories],
            'total': len(categories)
        }
    })


@workload_bp.route('/categories', methods=['POST'])
def create_category():
    """创建治疗类别"""
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': '类别名称不能为空'}), 400

    if WorkloadTreatmentCategory.query.filter_by(name=data['name']).first():
        return jsonify({'success': False, 'error': '该类别已存在'}), 400

    category = WorkloadTreatmentCategory(
        name=data['name'],
        description=data.get('description'),
        sort_order=data.get('sort_order', 0)
    )

    db.session.add(category)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '类别创建成功',
        'data': category.to_dict()
    }), 201


@workload_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """更新治疗类别"""
    category = WorkloadTreatmentCategory.query.get(category_id)
    if not category:
        return jsonify({'success': False, 'error': '类别不存在'}), 404

    data = request.get_json()

    if data.get('name'):
        category.name = data['name']
    if 'description' in data:
        category.description = data['description']
    if 'is_active' in data:
        category.is_active = data['is_active']
    if 'sort_order' in data:
        category.sort_order = data['sort_order']

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '类别更新成功',
        'data': category.to_dict()
    })


@workload_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """删除治疗类别（软删除）"""
    category = WorkloadTreatmentCategory.query.get(category_id)
    if not category:
        return jsonify({'success': False, 'error': '类别不存在'}), 404

    category.is_active = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '类别已删除'
    })


@workload_bp.route('/categories/batch-delete', methods=['POST'])
def batch_delete_categories():
    """批量删除治疗类别"""
    data = request.get_json()

    if not data or not data.get('ids'):
        return jsonify({'success': False, 'error': '请提供要删除的类别ID'}), 400

    ids = data['ids']
    deleted = 0
    failed = 0
    errors = []

    for category_id in ids:
        try:
            category = WorkloadTreatmentCategory.query.get(category_id)
            if not category:
                failed += 1
                errors.append(f'类别ID {category_id} 不存在')
                continue

            # 检查是否有关联的治疗项目
            item_count = WorkloadTreatmentItem.query.filter_by(category_id=category_id).count()
            if item_count > 0:
                failed += 1
                errors.append(f'类别"{category.name}"下有 {item_count} 个治疗项目，无法删除')
                continue

            # 硬删除
            db.session.delete(category)
            deleted += 1
        except Exception as e:
            failed += 1
            errors.append(f'删除类别ID {category_id} 失败: {str(e)}')

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'成功删除 {deleted} 个类别',
        'data': {
            'deleted': deleted,
            'failed': failed,
            'errors': errors[:10]
        }
    })


# ============================================================================
# 工作量登记 API
# ============================================================================

@workload_bp.route('/records', methods=['GET'])
def get_records():
    """获取工作量记录列表"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    therapist_id = request.args.get('therapist_id', type=int)
    category_id = request.args.get('category_id', type=int)
    patient_info = request.args.get('patient_info', '').strip()  # 患者姓名筛选

    query = WorkloadRecord.query

    if start_date:
        query = query.filter(WorkloadRecord.record_date >= start_date)
    if end_date:
        query = query.filter(WorkloadRecord.record_date <= end_date)
    if therapist_id:
        query = query.filter_by(therapist_id=therapist_id)
    if category_id:
        # 通过治疗项目关联查询
        query = query.join(WorkloadTreatmentItem).filter_by(category_id=category_id)
    if patient_info:
        # 按患者信息模糊搜索
        query = query.filter(WorkloadRecord.patient_info.contains(patient_info))

    records = query.order_by(WorkloadRecord.record_date.desc()).all()

    return jsonify({
        'success': True,
        'data': {
            'records': [r.to_dict() for r in records],
            'total': len(records)
        }
    })


def parse_record_date(date_value):
    """解析记录日期，支持字符串和date对象"""
    if date_value is None:
        return date.today()

    if isinstance(date_value, date):
        return date_value

    if isinstance(date_value, str):
        try:
            # 支持 YYYY-MM-DD 格式
            return datetime.strptime(date_value, '%Y-%m-%d').date()
        except ValueError:
            pass
        try:
            # 支持 YYYY/MM/DD 格式
            return datetime.strptime(date_value, '%Y/%m/%d').date()
        except ValueError:
            pass

    return date.today()


@workload_bp.route('/records', methods=['POST'])
def create_record():
    """创建工作量记录（支持批量）"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': '请求数据不能为空'}), 400

    # 获取设置：是否允许过往日期
    allow_past_date = WorkloadSettings.get_value('allow_past_date', False)
    past_date_max_days = WorkloadSettings.get_value('past_date_max_days', 7)

    # 支持批量创建
    records_data = data if isinstance(data, list) else [data]
    created_records = []
    errors = []

    for idx, record_data in enumerate(records_data):
        if not record_data.get('therapist_id') or not record_data.get('treatment_item_id'):
            errors.append(f'第{idx+1}条: 缺少治疗师或治疗项目')
            continue

        therapist_id = record_data['therapist_id']
        treatment_item_id = record_data['treatment_item_id']

        # 获取治疗项目
        treatment_item = WorkloadTreatmentItem.query.get(treatment_item_id)
        if not treatment_item:
            errors.append(f'第{idx+1}条: 治疗项目不存在')
            continue

        # 解析日期
        record_date = parse_record_date(record_data.get('record_date'))

        # 检查日期限制
        today = date.today()
        if record_date > today:
            errors.append(f'第{idx+1}条: 不能录入未来日期')
            continue

        if record_date < today and not allow_past_date:
            errors.append(f'第{idx+1}条: 系统设置不允许录入过往日期')
            continue

        if record_date < today:
            days_diff = (today - record_date).days
            if days_diff > past_date_max_days:
                errors.append(f'第{idx+1}条: 只能录入过去{past_date_max_days}天内的记录')
                continue

        # 检查重复记录（同一日期、同一治疗师、同一患者、同一治疗项目）
        patient_info = record_data.get('patient_info', '').strip()
        existing_record = WorkloadRecord.query.filter(
            WorkloadRecord.record_date == record_date,
            WorkloadRecord.therapist_id == therapist_id,
            WorkloadRecord.patient_info == patient_info,
            WorkloadRecord.treatment_item_id == treatment_item_id
        ).first()

        if existing_record:
            item_name = treatment_item.name if treatment_item else f'ID:{treatment_item_id}'
            errors.append(f'第{idx+1}条: 重复记录 - 日期{record_date}、患者"{patient_info}"、项目"{item_name}"已存在')
            continue

        # 使用传入的权重或默认权重
        weight = record_data.get('weight_coefficient', treatment_item.weight_coefficient)
        sessions = record_data.get('session_count', 1)

        record = WorkloadRecord(
            record_date=record_date,
            therapist_id=therapist_id,
            patient_info=record_data.get('patient_info'),
            treatment_item_id=treatment_item_id,
            weight_coefficient=weight,
            session_count=sessions,
            weighted_workload=WorkloadRecord.calculate_weighted_workload(weight, sessions),
            remark=record_data.get('remark')
        )

        db.session.add(record)
        created_records.append(record)

    if created_records:
        db.session.commit()

        # 触发成就检查（获取所有涉及的治疗师）
        therapist_ids = set(r.therapist_id for r in created_records)
        new_achievements_by_therapist = {}
        for tid in therapist_ids:
            update_therapist_stats(tid)
            new_achievements = check_and_award_achievements(tid)
            if new_achievements:
                new_achievements_by_therapist[tid] = new_achievements
    else:
        new_achievements_by_therapist = {}

    return jsonify({
        'success': True,
        'message': f'成功创建 {len(created_records)} 条记录',
        'data': {
            'records': [r.to_dict() for r in created_records],
            'total': len(created_records),
            'errors': errors if errors else None,
            'new_achievements': new_achievements_by_therapist
        }
    }), 201


@workload_bp.route('/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    """更新工作量记录"""
    record = WorkloadRecord.query.get(record_id)
    if not record:
        return jsonify({'success': False, 'error': '记录不存在'}), 404

    data = request.get_json()

    if data.get('record_date'):
        record.record_date = data['record_date']
    if 'patient_info' in data:
        record.patient_info = data['patient_info']
    if data.get('treatment_item_id'):
        record.treatment_item_id = data['treatment_item_id']
        # 更新权重
        treatment_item = WorkloadTreatmentItem.query.get(data['treatment_item_id'])
        if treatment_item:
            record.weight_coefficient = data.get('weight_coefficient', treatment_item.weight_coefficient)
    if 'weight_coefficient' in data:
        record.weight_coefficient = data['weight_coefficient']
    if 'session_count' in data:
        record.session_count = data['session_count']
    if 'remark' in data:
        record.remark = data['remark']

    # 重新计算工作量
    record.weighted_workload = WorkloadRecord.calculate_weighted_workload(
        record.weight_coefficient, record.session_count
    )

    db.session.commit()

    # 触发统计和成就更新
    update_therapist_stats(record.therapist_id)
    new_achievements = check_and_award_achievements(record.therapist_id)

    return jsonify({
        'success': True,
        'message': '记录更新成功',
        'data': record.to_dict(),
        'new_achievements': new_achievements if new_achievements else None
    })


@workload_bp.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    """删除工作量记录"""
    record = WorkloadRecord.query.get(record_id)
    if not record:
        return jsonify({'success': False, 'error': '记录不存在'}), 404

    # 保存治疗师ID用于后续更新统计
    therapist_id = record.therapist_id

    db.session.delete(record)
    db.session.commit()

    # 触发统计和成就更新
    update_therapist_stats(therapist_id)

    return jsonify({
        'success': True,
        'message': '记录已删除'
    })


@workload_bp.route('/records/batch-delete', methods=['POST'])
def batch_delete_records():
    """批量删除工作量记录"""
    data = request.get_json()

    if not data or not data.get('ids'):
        return jsonify({'success': False, 'error': '请提供要删除的记录ID'}), 400

    ids = data['ids']
    deleted = 0
    affected_therapists = set()

    for record_id in ids:
        record = WorkloadRecord.query.get(record_id)
        if record:
            affected_therapists.add(record.therapist_id)
            db.session.delete(record)
            deleted += 1

    db.session.commit()

    # 批量更新受影响治疗师的统计
    for tid in affected_therapists:
        update_therapist_stats(tid)

    return jsonify({
        'success': True,
        'message': f'成功删除 {deleted} 条记录',
        'data': {
            'deleted': deleted
        }
    })


@workload_bp.route('/records/batch-import', methods=['POST'])
def batch_import_records():
    """批量导入工作量记录"""
    try:
        data = request.get_json()

        if not data or not data.get('records'):
            return jsonify({'success': False, 'error': '请提供记录数据'}), 400

        records_data = data['records']
        imported = 0
        failed = 0
        errors = []
        affected_therapists = set()  # 收集受影响的治疗师

        def parse_date_flexible(date_value):
            """灵活解析多种日期格式（兼容WPS/Excel）"""
            if isinstance(date_value, date) and not isinstance(date_value, datetime):
                return date_value

            if isinstance(date_value, datetime):
                return date_value.date()

            date_str = str(date_value).strip() if date_value else ''
            if not date_str:
                return None

            # 支持的日期格式列表
            date_formats = [
                '%Y-%m-%d',       # 2024-01-15
                '%Y/%m/%d',       # 2024/01/15
                '%Y年%m月%d日',    # 2024年01月15日
                '%m/%d/%Y',       # 01/15/2024 (美国格式)
                '%d-%m-%Y',       # 15-01-2024
                '%d/%m/%Y',       # 15/01/2024
            ]

            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            # 尝试解析带时间的格式
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except (ValueError, AttributeError):
                pass

            return None

        for idx, record in enumerate(records_data):
            try:
                # 解析日期（支持多种格式）
                record_date = parse_date_flexible(record.get('date', ''))
                if not record_date:
                    errors.append(f'第{idx+1}行: 日期格式错误 "{record.get("date", "")}"')
                    failed += 1
                    continue

                # 查找治疗师（按姓名或工号）
                therapist_input = record.get('therapist', '').strip()
                therapist = WorkloadTherapist.query.filter(
                    (WorkloadTherapist.name == therapist_input) |
                    (WorkloadTherapist.employee_id == therapist_input)
                ).first()

                if not therapist:
                    errors.append(f'第{idx+1}行: 找不到治疗师 "{therapist_input}"')
                    failed += 1
                    continue

                # 查找治疗项目（按编号或名称）
                item_input = record.get('item', '').strip()
                # 去掉可能的编号前缀 [xxx]
                item_name = re.sub(r'^\[.*?\]\s*', '', item_input) if '[' in item_input else item_input

                treatment_item = WorkloadTreatmentItem.query.filter(
                    (WorkloadTreatmentItem.code == item_input) |
                    (WorkloadTreatmentItem.name == item_input) |
                    (WorkloadTreatmentItem.name == item_name)
                ).first()

                if not treatment_item:
                    errors.append(f'第{idx+1}行: 找不到治疗项目 "{item_input}"')
                    failed += 1
                    continue

                # 创建记录
                sessions = int(record.get('sessions', 1))
                # 使用导入的权重，如果未提供则使用治疗项目的默认权重
                weight = record.get('weight')
                if weight is None or weight == '':
                    weight = treatment_item.weight_coefficient
                else:
                    weight = float(weight)

                new_record = WorkloadRecord(
                    record_date=record_date,
                    therapist_id=therapist.id,
                    patient_info=record.get('patient', ''),
                    treatment_item_id=treatment_item.id,
                    weight_coefficient=weight,
                    session_count=sessions,
                    weighted_workload=round(weight * sessions, 2),
                    remark=record.get('remark', '')
                )

                db.session.add(new_record)
                affected_therapists.add(therapist.id)
                imported += 1

            except Exception as e:
                errors.append(f'第{idx+1}行: {str(e)}')
                failed += 1

        db.session.commit()

        # 批量更新受影响治疗师的统计和成就
        new_achievements_by_therapist = {}
        for tid in affected_therapists:
            update_therapist_stats(tid)
            new_achievements = check_and_award_achievements(tid)
            if new_achievements:
                new_achievements_by_therapist[tid] = new_achievements

        return jsonify({
            'success': True,
            'message': f'成功导入 {imported} 条记录',
            'data': {
                'imported': imported,
                'failed': failed,
                'errors': errors[:20],  # 只返回前20个错误
                'new_achievements': new_achievements_by_therapist if new_achievements_by_therapist else None
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'导入失败: {str(e)}',
            'details': str(e)
        }), 500


# ============================================================================
# 统计分析 API
# ============================================================================

@workload_bp.route('/statistics/daily', methods=['GET'])
def get_daily_statistics():
    """获取每日统计数据"""
    target_date = request.args.get('date', date.today().isoformat())

    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    records = WorkloadRecord.query.filter_by(record_date=target_date).all()

    total_sessions = sum(r.session_count for r in records)
    total_workload = sum(r.weighted_workload for r in records)

    # 按治疗师分组统计
    therapist_stats = {}
    for r in records:
        tid = r.therapist_id
        if tid not in therapist_stats:
            therapist_stats[tid] = {
                'therapist_id': tid,
                'therapist_name': r.therapist_rel.name if r.therapist_rel else '未知',
                'sessions': 0,
                'workload': 0
            }
        therapist_stats[tid]['sessions'] += r.session_count
        therapist_stats[tid]['workload'] += r.weighted_workload

    return jsonify({
        'success': True,
        'data': {
            'date': target_date.isoformat(),
            'total_sessions': total_sessions,
            'total_workload': round(total_workload, 2),
            'therapist_statistics': list(therapist_stats.values())
        }
    })


@workload_bp.route('/statistics/monthly', methods=['GET'])
def get_monthly_statistics():
    """获取月度统计数据"""
    year_month = request.args.get('month', date.today().strftime('%Y-%m'))

    try:
        year, month = map(int, year_month.split('-'))
    except ValueError:
        return jsonify({'success': False, 'error': '月份格式错误，应为YYYY-MM'}), 400

    records = WorkloadRecord.query.filter(
        extract('year', WorkloadRecord.record_date) == year,
        extract('month', WorkloadRecord.record_date) == month
    ).all()

    total_sessions = sum(r.session_count for r in records)
    total_workload = sum(r.weighted_workload for r in records)
    working_days = len(set(r.record_date for r in records))

    # 按治疗师分组统计
    therapist_stats = {}
    for r in records:
        tid = r.therapist_id
        if tid not in therapist_stats:
            therapist_stats[tid] = {
                'therapist_id': tid,
                'therapist_name': r.therapist_rel.name if r.therapist_rel else '未知',
                'sessions': 0,
                'workload': 0,
                'days': set()
            }
        therapist_stats[tid]['sessions'] += r.session_count
        therapist_stats[tid]['workload'] += r.weighted_workload
        therapist_stats[tid]['days'].add(r.record_date)

    # 计算日均
    for tid, stats in therapist_stats.items():
        days = len(stats['days'])
        stats['days'] = days
        stats['daily_average'] = round(stats['workload'] / days, 2) if days > 0 else 0

    # 每周工作量统计（用于排班参考）- 使用所有历史记录
    # weekday: 0=周日, 1=周一, ..., 6=周六
    all_records = WorkloadRecord.query.all()
    weekday_stats = {i: {'workload': 0, 'sessions': 0, 'count': 0} for i in range(7)}
    for r in all_records:
        weekday = r.record_date.weekday()
        # Python weekday: 0=周一, 6=周日，需要转换为我们需要的格式（0=周日）
        weekday_index = (weekday + 1) % 7  # 转换：周一=1, 周日=0
        weekday_stats[weekday_index]['workload'] += r.weighted_workload
        weekday_stats[weekday_index]['sessions'] += r.session_count
        weekday_stats[weekday_index]['count'] += 1

    # 格式化每周统计（计算平均值）
    weekday_data = {}
    weekday_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    for day, stats in weekday_stats.items():
        avg_workload = round(stats['workload'] / stats['count'], 2) if stats['count'] > 0 else 0
        avg_sessions = round(stats['sessions'] / stats['count'], 1) if stats['count'] > 0 else 0
        weekday_data[day] = {
            'name': weekday_names[day],
            'workload': round(stats['workload'], 2),
            'sessions': stats['sessions'],
            'count': stats['count'],
            'avg_workload': avg_workload,
            'avg_sessions': avg_sessions
        }

    return jsonify({
        'success': True,
        'data': {
            'month': year_month,
            'total_sessions': total_sessions,
            'total_workload': round(total_workload, 2),
            'working_days': working_days,
            'therapist_statistics': list(therapist_stats.values()),
            'weekday_statistics': weekday_data
        }
    })


@workload_bp.route('/statistics/ranking', methods=['GET'])
def get_ranking():
    """获取治疗师排行榜"""
    ranking_type = request.args.get('type', 'monthly')  # daily or monthly

    if ranking_type == 'daily':
        target_date = request.args.get('date', date.today().isoformat())
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

        records = WorkloadRecord.query.filter_by(record_date=target_date).all()
    else:
        year_month = request.args.get('month', date.today().strftime('%Y-%m'))
        try:
            year, month = map(int, year_month.split('-'))
        except ValueError:
            return jsonify({'success': False, 'error': '月份格式错误'}), 400

        records = WorkloadRecord.query.filter(
            extract('year', WorkloadRecord.record_date) == year,
            extract('month', WorkloadRecord.record_date) == month
        ).all()

    # 按治疗师统计
    therapist_stats = {}
    for r in records:
        tid = r.therapist_id
        if tid not in therapist_stats:
            therapist_stats[tid] = {
                'therapist_id': tid,
                'therapist_name': r.therapist_rel.name if r.therapist_rel else '未知',
                'sessions': 0,
                'workload': 0
            }
            # 月度统计需要记录工作日
            if ranking_type == 'monthly':
                therapist_stats[tid]['days_set'] = set()

        therapist_stats[tid]['sessions'] += r.session_count
        therapist_stats[tid]['workload'] += r.weighted_workload
        if ranking_type == 'monthly':
            therapist_stats[tid]['days_set'].add(r.record_date)

    # 计算日均（仅月度统计）
    if ranking_type == 'monthly':
        for tid, stats in therapist_stats.items():
            days = len(stats.pop('days_set', set()))  # 移除set并获取天数
            stats['days'] = days
            stats['daily_average'] = round(stats['workload'] / days, 2) if days > 0 else 0

    # 排序
    ranking = sorted(therapist_stats.values(), key=lambda x: x['workload'], reverse=True)

    # 添加排名
    for i, item in enumerate(ranking, 1):
        item['rank'] = i

    return jsonify({
        'success': True,
        'data': {
            'type': ranking_type,
            'ranking': ranking
        }
    })


@workload_bp.route('/statistics/dashboard', methods=['GET'])
def get_dashboard():
    """获取仪表盘数据"""
    today = date.today()
    current_month = today.strftime('%Y-%m')

    # 今日统计
    today_records = WorkloadRecord.query.filter_by(record_date=today).all()
    today_sessions = sum(r.session_count for r in today_records)
    today_workload = sum(r.weighted_workload for r in today_records)

    # 本月统计
    try:
        year, month = map(int, current_month.split('-'))
    except:
        year, month = today.year, today.month

    month_records = WorkloadRecord.query.filter(
        extract('year', WorkloadRecord.record_date) == year,
        extract('month', WorkloadRecord.record_date) == month
    ).all()
    month_workload = sum(r.weighted_workload for r in month_records)

    # 活跃治疗师
    active_therapists = WorkloadTherapist.query.filter_by(is_active=True).count()

    # 今日排行
    therapist_today = {}
    for r in today_records:
        tid = r.therapist_id
        if tid not in therapist_today:
            therapist_today[tid] = {
                'therapist_id': tid,
                'therapist_name': r.therapist_rel.name if r.therapist_rel else '未知',
                'workload': 0,
                'sessions': 0
            }
        therapist_today[tid]['workload'] += r.weighted_workload
        therapist_today[tid]['sessions'] += r.session_count

    today_ranking = sorted(therapist_today.values(), key=lambda x: x['workload'], reverse=True)[:5]

    # 本月排行
    therapist_month = {}
    for r in month_records:
        tid = r.therapist_id
        if tid not in therapist_month:
            therapist_month[tid] = {
                'therapist_id': tid,
                'therapist_name': r.therapist_rel.name if r.therapist_rel else '未知',
                'workload': 0,
                'sessions': 0
            }
        therapist_month[tid]['workload'] += r.weighted_workload
        therapist_month[tid]['sessions'] += r.session_count

    month_ranking = sorted(therapist_month.values(), key=lambda x: x['workload'], reverse=True)[:5]

    return jsonify({
        'success': True,
        'data': {
            'today_sessions': today_sessions,
            'today_workload': round(today_workload, 2),
            'month_workload': round(month_workload, 2),
            'active_therapists': active_therapists,
            'today_ranking': today_ranking,
            'month_ranking': month_ranking
        }
    })


# ============================================================================
# 数据备份与恢复 API
# ============================================================================

@workload_bp.route('/backup/restore', methods=['POST'])
def restore_backup():
    """从备份文件恢复数据"""
    data = request.get_json()

    if not data or not data.get('data'):
        return jsonify({'success': False, 'error': '无效的备份数据'}), 400

    backup_data = data['data']

    try:
        # 开始事务
        therapists_created = 0
        items_created = 0
        categories_created = 0
        records_created = 0

        # 恢复类别
        if backup_data.get('categories'):
            for cat_data in backup_data['categories']:
                if not cat_data.get('name'):
                    continue
                existing = WorkloadTreatmentCategory.query.filter_by(name=cat_data['name']).first()
                if not existing:
                    category = WorkloadTreatmentCategory(
                        name=cat_data['name'],
                        description=cat_data.get('description'),
                        sort_order=cat_data.get('sort_order', 0),
                        is_active=cat_data.get('is_active', True)
                    )
                    db.session.add(category)
                    categories_created += 1
            db.session.flush()

        # 恢复治疗师
        if backup_data.get('therapists'):
            for th_data in backup_data['therapists']:
                if not th_data.get('name'):
                    continue
                existing = WorkloadTherapist.query.filter_by(name=th_data['name']).first()
                if not existing:
                    therapist = WorkloadTherapist(
                        name=th_data['name'],
                        employee_id=th_data.get('employee_id'),
                        department=th_data.get('department', '康复科'),
                        sort_order=th_data.get('sort_order', 0),
                        is_active=th_data.get('is_active', True)
                    )
                    db.session.add(therapist)
                    therapists_created += 1
            db.session.flush()

        # 恢复治疗项目
        if backup_data.get('treatment_items'):
            for item_data in backup_data['treatment_items']:
                if not item_data.get('name'):
                    continue
                existing = WorkloadTreatmentItem.query.filter_by(name=item_data['name']).first()
                if not existing:
                    # 查找类别
                    category_id = None
                    if item_data.get('category_name'):
                        cat = WorkloadTreatmentCategory.query.filter_by(name=item_data['category_name']).first()
                        if cat:
                            category_id = cat.id
                    elif item_data.get('category_id'):
                        category_id = item_data['category_id']

                    item = WorkloadTreatmentItem(
                        name=item_data['name'],
                        category_id=category_id,
                        weight_coefficient=item_data.get('weight_coefficient', 1.0),
                        description=item_data.get('description'),
                        sort_order=item_data.get('sort_order', 0),
                        is_active=item_data.get('is_active', True)
                    )
                    db.session.add(item)
                    items_created += 1
            db.session.flush()

        # 恢复工作量记录
        if backup_data.get('records'):
            for rec_data in backup_data['records']:
                if not rec_data.get('therapist_id') or not rec_data.get('treatment_item_id'):
                    continue

                # 查找治疗师和治疗项目
                therapist = None
                if rec_data.get('therapist_name'):
                    therapist = WorkloadTherapist.query.filter_by(name=rec_data['therapist_name']).first()
                if not therapist:
                    therapist = WorkloadTherapist.query.get(rec_data.get('therapist_id'))

                item = WorkloadTreatmentItem.query.filter_by(name=rec_data.get('item_name')).first()
                if not item:
                    item = WorkloadTreatmentItem.query.get(rec_data.get('treatment_item_id'))

                if therapist and item:
                    # 解析日期
                    record_date = date.today()
                    if rec_data.get('record_date'):
                        try:
                            if isinstance(rec_data['record_date'], str):
                                record_date = datetime.strptime(rec_data['record_date'], '%Y-%m-%d').date()
                            else:
                                record_date = rec_data['record_date']
                        except:
                            pass

                    record = WorkloadRecord(
                        record_date=record_date,
                        therapist_id=therapist.id,
                        patient_info=rec_data.get('patient_info'),
                        treatment_item_id=item.id,
                        weight_coefficient=rec_data.get('weight_coefficient', 1.0),
                        session_count=rec_data.get('session_count', 1),
                        weighted_workload=rec_data.get('weighted_workload', 0),
                        remark=rec_data.get('remark')
                    )
                    db.session.add(record)
                    records_created += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '数据恢复成功',
            'data': {
                'therapists_created': therapists_created,
                'items_created': items_created,
                'categories_created': categories_created,
                'records_created': records_created
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'恢复失败: {str(e)}'}), 500


# ============================================================================
# Excel 导入导出 API
# ============================================================================

@workload_bp.route('/records/template', methods=['GET'])
def download_records_template():
    """下载工作量记录Excel模板"""
    from flask import Response
    import io

    # 获取治疗师和治疗项目数据用于模板
    therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
    items = WorkloadTreatmentItem.query.filter_by(is_active=True).all()

    # 创建CSV内容（简单格式，Excel可直接打开）
    output = io.StringIO()

    # 写入说明行
    output.write("工作量记录导入模板\n")
    output.write("说明: 日期格式为YYYY-MM-DD，治疗师可填写工号或姓名，项目可填写编号或名称\n")
    output.write("治疗师参考: " + ", ".join([f"{t.employee_id or t.id}({t.name})" for t in therapists[:10]]) + "...\n")
    output.write("治疗项目参考: " + ", ".join([f"{i.code or i.id}({i.name})" for i in items[:10]]) + "...\n")
    output.write("\n")

    # 写入表头
    output.write("日期,治疗师(工号/姓名),患者信息,治疗项目(编号/名称),权重系数,人次,备注\n")

    # 写入示例数据
    today = date.today().isoformat()
    output.write(f"{today},T001,患者A,PT001,1.5,2,示例记录1\n")
    output.write(f"{today},张三,患者B,推拿按摩,1.0,1,示例记录2\n")

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv;charset=utf-8-sig',
        headers={
            'Content-Disposition': f'attachment; filename=workload_records_template_{date.today().isoformat()}.csv'
        }
    )


@workload_bp.route('/records/export', methods=['GET'])
def export_records():
    """导出工作量记录到CSV/Excel"""
    from flask import Response
    import io

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = WorkloadRecord.query

    if start_date:
        query = query.filter(WorkloadRecord.record_date >= start_date)
    if end_date:
        query = query.filter(WorkloadRecord.record_date <= end_date)

    records = query.order_by(WorkloadRecord.record_date.desc()).all()

    output = io.StringIO()

    # 写入UTF-8 BOM以便Excel正确识别
    output.write('\ufeff')

    # 写入表头
    output.write("日期,治疗师工号,治疗师姓名,患者信息,项目编号,项目名称,类别,权重系数,人次,工作量,备注\n")

    # 写入数据
    for r in records:
        therapist_code = r.therapist_rel.employee_id if r.therapist_rel else ''
        therapist_name = r.therapist_rel.name if r.therapist_rel else ''
        item_code = r.treatment_item_rel.code if r.treatment_item_rel else ''
        item_name = r.treatment_item_rel.name if r.treatment_item_rel else ''
        category = r.treatment_item_rel.category_rel.name if r.treatment_item_rel and r.treatment_item_rel.category_rel else ''

        row = [
            r.record_date.isoformat() if r.record_date else '',
            therapist_code or '',
            therapist_name or '',
            r.patient_info or '',
            item_code or '',
            item_name or '',
            category,
            str(r.weight_coefficient),
            str(r.session_count),
            str(r.weighted_workload),
            r.remark or ''
        ]
        output.write(','.join(row) + '\n')

    output.seek(0)

    filename = f'workload_records_{date.today().isoformat()}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv;charset=utf-8-sig',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )


@workload_bp.route('/records/import', methods=['POST'])
def import_records():
    """从CSV/Excel导入工作量记录"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '请上传文件'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': '未选择文件'}), 400

    try:
        # 读取文件内容
        content = file.read().decode('utf-8-sig')
        lines = content.strip().split('\n')

        # 跳过说明行和表头，找到数据行
        data_lines = []
        for line in lines:
            # 跳过空行和说明行
            if not line.strip() or line.startswith('说明') or line.startswith('治疗师参考') or line.startswith('治疗项目参考'):
                continue
            # 检查是否是表头行
            if '日期' in line and '治疗师' in line:
                continue
            data_lines.append(line)

        created = 0
        skipped = 0
        errors = []

        for line in data_lines:
            parts = line.split(',')
            if len(parts) < 6:
                continue

            try:
                record_date_str = parts[0].strip()
                therapist_ref = parts[1].strip()
                patient_info = parts[2].strip() if len(parts) > 2 else ''
                item_ref = parts[3].strip()
                weight = float(parts[4]) if len(parts) > 4 and parts[4].strip() else 1.0
                sessions = int(parts[5]) if len(parts) > 5 and parts[5].strip() else 1
                remark = parts[6].strip() if len(parts) > 6 else ''

                # 解析日期
                try:
                    record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
                except:
                    errors.append(f'日期格式错误: {record_date_str}')
                    continue

                # 查找治疗师（支持工号或姓名）
                therapist = None
                if therapist_ref:
                    therapist = WorkloadTherapist.query.filter(
                        (WorkloadTherapist.employee_id == therapist_ref) |
                        (WorkloadTherapist.name == therapist_ref)
                    ).first()

                if not therapist:
                    errors.append(f'未找到治疗师: {therapist_ref}')
                    continue

                # 查找治疗项目（支持编号或名称）
                item = None
                if item_ref:
                    item = WorkloadTreatmentItem.query.filter(
                        (WorkloadTreatmentItem.code == item_ref) |
                        (WorkloadTreatmentItem.name == item_ref)
                    ).first()

                if not item:
                    errors.append(f'未找到治疗项目: {item_ref}')
                    continue

                # 创建记录
                record = WorkloadRecord(
                    record_date=record_date,
                    therapist_id=therapist.id,
                    patient_info=patient_info,
                    treatment_item_id=item.id,
                    weight_coefficient=weight,
                    session_count=sessions,
                    weighted_workload=round(weight * sessions, 2),
                    remark=remark
                )
                db.session.add(record)
                created += 1

            except Exception as e:
                errors.append(f'行解析错误: {str(e)}')
                skipped += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'成功导入 {created} 条记录',
            'data': {
                'created': created,
                'skipped': skipped,
                'errors': errors[:20]  # 只返回前20个错误
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'导入失败: {str(e)}'}), 500


@workload_bp.route('/lookup/therapist', methods=['GET'])
def lookup_therapist():
    """根据工号或姓名查找治疗师"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'error': '请提供查询参数'}), 400

    therapist = WorkloadTherapist.query.filter(
        (WorkloadTherapist.employee_id == query) |
        (WorkloadTherapist.name == query),
        WorkloadTherapist.is_active == True
    ).first()

    if therapist:
        return jsonify({
            'success': True,
            'data': therapist.to_dict()
        })
    else:
        return jsonify({
            'success': False,
            'error': '未找到治疗师'
        })


@workload_bp.route('/lookup/item', methods=['GET'])
def lookup_item():
    """根据编号或名称查找治疗项目"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'error': '请提供查询参数'}), 400

    item = WorkloadTreatmentItem.query.filter(
        (WorkloadTreatmentItem.code == query) |
        (WorkloadTreatmentItem.name == query),
        WorkloadTreatmentItem.is_active == True
    ).first()

    if item:
        return jsonify({
            'success': True,
            'data': item.to_dict()
        })
    else:
        return jsonify({
            'success': False,
            'error': '未找到治疗项目'
        })


@workload_bp.route('/patients/names', methods=['GET'])
def get_patient_names():
    """获取所有患者姓名列表（用于自动完成）

    返回数据库中所有不重复的患者姓名，按使用次数排序
    """
    try:
        # 查询所有非空的患者姓名，按出现次数排序
        result = db.session.query(
            WorkloadRecord.patient_info,
            func.count(WorkloadRecord.id).label('count')
        ).filter(
            WorkloadRecord.patient_info != None,
            WorkloadRecord.patient_info != ''
        ).group_by(
            WorkloadRecord.patient_info
        ).order_by(
            func.count(WorkloadRecord.id).desc()
        ).limit(100).all()

        # 返回姓名和真实记录数
        names_with_count = [
            {'name': r.patient_info, 'count': r.count}
            for r in result if r.patient_info and r.patient_info.strip()
        ]

        return jsonify({
            'success': True,
            'data': {
                'names': names_with_count,
                'total': len(names_with_count)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'获取患者姓名失败: {str(e)}'}), 500


# ============================================================================
# 系统设置 API
# ============================================================================

# 默认设置
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
    },
    'allow_delete': {
        'value': False,
        'type': 'bool',
        'description': '启用删除功能（删除操作不可恢复，请谨慎使用）'
    }
}


def init_default_settings():
    """初始化默认设置"""
    for key, config in DEFAULT_SETTINGS.items():
        existing = WorkloadSettings.query.filter_by(setting_key=key).first()
        if not existing:
            setting = WorkloadSettings(
                setting_key=key,
                setting_value=str(config['value']) if config['type'] != 'bool' else ('true' if config['value'] else 'false'),
                setting_type=config['type'],
                description=config['description']
            )
            db.session.add(setting)
    db.session.commit()


@workload_bp.route('/settings', methods=['GET'])
def get_settings():
    """获取所有系统设置"""
    # 确保默认设置已初始化
    init_default_settings()

    settings = WorkloadSettings.query.all()
    return jsonify({
        'success': True,
        'data': {
            'settings': [s.to_dict() for s in settings]
        }
    })


@workload_bp.route('/settings/<key>', methods=['GET'])
def get_setting(key):
    """获取单个设置"""
    setting = WorkloadSettings.query.filter_by(setting_key=key).first()
    if setting:
        return jsonify({
            'success': True,
            'data': setting.to_dict()
        })
    else:
        # 返回默认值
        if key in DEFAULT_SETTINGS:
            return jsonify({
                'success': True,
                'data': {
                    'key': key,
                    'value': DEFAULT_SETTINGS[key]['value'],
                    'type': DEFAULT_SETTINGS[key]['type'],
                    'description': DEFAULT_SETTINGS[key]['description']
                }
            })
        return jsonify({'success': False, 'error': '设置项不存在'}), 404


@workload_bp.route('/settings', methods=['PUT'])
def update_settings():
    """批量更新设置"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据不能为空'}), 400

    updated = []
    for key, value in data.items():
        if key not in DEFAULT_SETTINGS:
            continue

        setting = WorkloadSettings.query.filter_by(setting_key=key).first()
        if not setting:
            # 创建新设置
            setting = WorkloadSettings(
                setting_key=key,
                setting_type=DEFAULT_SETTINGS[key]['type'],
                description=DEFAULT_SETTINGS[key]['description']
            )
            db.session.add(setting)

        # 转换值为字符串
        if DEFAULT_SETTINGS[key]['type'] == 'bool':
            setting.setting_value = 'true' if value else 'false'
        else:
            setting.setting_value = str(value)

        updated.append(key)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'已更新 {len(updated)} 个设置',
        'data': {'updated': updated}
    })


@workload_bp.route('/settings/<key>', methods=['PUT'])
def update_setting(key):
    """更新单个设置"""
    if key not in DEFAULT_SETTINGS:
        return jsonify({'success': False, 'error': '无效的设置项'}), 400

    data = request.get_json()
    if not data or 'value' not in data:
        return jsonify({'success': False, 'error': '请提供设置值'}), 400

    setting = WorkloadSettings.query.filter_by(setting_key=key).first()
    if not setting:
        setting = WorkloadSettings(
            setting_key=key,
            setting_type=DEFAULT_SETTINGS[key]['type'],
            description=DEFAULT_SETTINGS[key]['description']
        )
        db.session.add(setting)

    # 转换值为字符串
    if DEFAULT_SETTINGS[key]['type'] == 'bool':
        setting.setting_value = 'true' if data['value'] else 'false'
    else:
        setting.setting_value = str(data['value'])

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '设置已更新',
        'data': setting.to_dict()
    })
