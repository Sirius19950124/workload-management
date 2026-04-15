# -*- coding: utf-8 -*-
"""
患者查询 API 蓝图
功能：按治疗项目查询患者
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func
from app import db
from app.models import Patient, WorkloadTherapist, WorkloadRecord, WorkloadTreatmentItem
from datetime import date

patient_bp = Blueprint('patient', __name__, url_prefix='/api')


@patient_bp.route('/patients/by-treatment-item', methods=['GET'])
def get_patients_by_treatment_item():
    """按治疗项目查询患者列表（支持按最小治疗次数过滤）

    参数:
        treatment_item_id: 治疗项目ID（必填）
        min_sessions: 最小治疗次数（可选，默认1）
        search: 患者姓名模糊搜索（可选）

    示例: /api/patients/by-treatment-item?treatment_item_id=3&min_sessions=5
    """
    treatment_item_id = request.args.get('treatment_item_id', type=int)
    min_sessions = request.args.get('min_sessions', type=int, default=1)
    search = request.args.get('search', '').strip()

    if not treatment_item_id:
        return jsonify({'success': False, 'message': '请选择治疗项目'}), 400

    # 按患者聚合查询
    query = db.session.query(
        WorkloadRecord.patient_info,
        WorkloadRecord.patient_id,
        func.sum(WorkloadRecord.session_count).label('total_sessions'),
        func.count(WorkloadRecord.id).label('record_count'),
        func.min(WorkloadRecord.record_date).label('first_treatment_date'),
        func.max(WorkloadRecord.record_date).label('last_treatment_date'),
        func.group_concat(func.distinct(WorkloadTherapist.name)).label('therapists')
    ).join(
        WorkloadTreatmentItem,
        WorkloadRecord.treatment_item_id == WorkloadTreatmentItem.id
    ).outerjoin(
        WorkloadTherapist,
        WorkloadRecord.therapist_id == WorkloadTherapist.id
    ).filter(
        WorkloadRecord.treatment_item_id == treatment_item_id,
        WorkloadRecord.patient_info != None,
        WorkloadRecord.patient_info != ''
    ).group_by(
        WorkloadRecord.patient_info
    ).having(
        func.sum(WorkloadRecord.session_count) >= min_sessions
    ).order_by(
        func.sum(WorkloadRecord.session_count).desc()
    )

    # 患者姓名搜索
    if search:
        query = query.filter(WorkloadRecord.patient_info.contains(search))

    results = query.all()

    # 获取治疗项目名称
    item = WorkloadTreatmentItem.query.get(treatment_item_id)
    item_name = item.name if item else '未知项目'

    patients = []
    for r in results:
        patient = None
        if r.patient_id:
            patient = Patient.query.get(r.patient_id)
        if not patient:
            patient_name = r.patient_info.split('/')[-1] if '/' in r.patient_info else r.patient_info
            patient = Patient.query.filter(Patient.name == patient_name).first()

        days_since_last = None
        if r.last_treatment_date:
            days_since_last = (date.today() - r.last_treatment_date).days

        patients.append({
            'patient_info': r.patient_info,
            'patient_id': r.patient_id,
            'patient_name': patient.name if patient else r.patient_info,
            'status': patient.status if patient else None,
            'status_display': patient.get_status_display() if patient else None,
            'total_sessions': int(r.total_sessions) if r.total_sessions else 0,
            'record_count': r.record_count,
            'first_treatment_date': r.first_treatment_date.isoformat() if r.first_treatment_date else None,
            'last_treatment_date': r.last_treatment_date.isoformat() if r.last_treatment_date else None,
            'days_since_last_treatment': days_since_last,
            'therapists': r.therapists.split(',') if r.therapists else []
        })

    return jsonify({
        'success': True,
        'data': {
            'treatment_item_name': item_name,
            'min_sessions': min_sessions,
            'patients': patients,
            'total': len(patients)
        }
    })


@patient_bp.route('/patients/search', methods=['GET'])
def search_patients():
    """患者模糊搜索（用于录入时自动补全）

    参数:
        q: 搜索关键字（必填，至少1字符）
        limit: 返回条数上限（默认10，最大20）

    示例: /api/patients/search?q=张三&limit=10
    """
    q = request.args.get('q', '').strip()
    limit = min(request.args.get('limit', 10, type=int), 20)

    if not q or len(q) < 1:
        return jsonify({'success': True, 'data': []})

    results = []
    seen_names = set()

    # 1. 从 Patient 表查询
    db_patients = Patient.query.filter(
        db.or_(
            Patient.name.contains(q),
            Patient.patient_no.contains(q)
        )
    ).order_by(
        db.case((Patient.status == 'active', 1), else_=2),
        Patient.name
    ).limit(limit).all()

    for p in db_patients:
        if p.name not in seen_names:
            seen_names.add(p.name)
            results.append({
                'id': p.id,
                'name': p.name,
                'patient_no': p.patient_no,
                'status': p.status,
                'source': 'db'
            })

    # 2. 从 WorkloadRecord.patient_info 补充（覆盖手动输入但未建Patient记录的情况）
    if len(results) < limit:
        record_infos = db.session.query(
            WorkloadRecord.patient_info
        ).filter(
            WorkloadRecord.patient_info != None,
            WorkloadRecord.patient_info != '',
            WorkloadRecord.patient_info.contains(q)
        ).distinct().limit(limit * 2).all()

        for r in record_infos:
            # 提取纯姓名（去掉可能的 ID/ 前缀）
            raw = r.patient_info.strip()
            name = raw.split('/')[-1] if '/' in raw else raw
            if name and name not in seen_names:
                seen_names.add(name)
                results.append({
                    'id': None,
                    'name': name,
                    'patient_no': None,
                    'status': None,
                    'source': 'record'
                })
                if len(results) >= limit:
                    break

    return jsonify({'success': True, 'data': results[:limit]})
