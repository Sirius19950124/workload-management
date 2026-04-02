# -*- coding: utf-8 -*-
"""
患者管理 API 蓝图
功能：治疗师管理患者、患者-治疗师关联展示

API端点:
1. 患者管理: /api/patients
2. 治疗师-患者关系: /api/therapist-patients
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func
from app import db
from app.models import Patient, WorkloadTherapist, WorkloadRecord, WorkloadTreatmentItem
from datetime import date, datetime

patient_bp = Blueprint('patient', __name__, url_prefix='/api')


# ============================================================================
# 患者管理 API
# ============================================================================

@patient_bp.route('/patients', methods=['GET'])
def get_patients():
    """获取患者列表"""
    # 过滤参数
    status = request.args.get('status', 'active')
    therapist_id = request.args.get('therapist_id')
    search = request.args.get('search', '').strip()

    query = Patient.query

    # 状态过滤
    if status != 'all':
        query = query.filter_by(status=status)

    # 治疗师过滤
    if therapist_id:
        query = query.filter_by(primary_therapist_id=int(therapist_id))

    # 搜索
    if search:
        query = query.filter(
            db.or_(
                Patient.name.contains(search),
                Patient.patient_no.contains(search),
                Patient.phone.contains(search)
            )
        )

    patients = query.order_by(Patient.updated_at.desc()).all()

    return jsonify({
        'success': True,
        'data': {
            'patients': [p.to_dict() for p in patients],
            'total': len(patients)
        }
    })


@patient_bp.route('/patients/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    """获取单个患者详情"""
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'message': '患者不存在'}), 404

    # 获取患者的治疗记录统计
    records = WorkloadRecord.query.filter_by(patient_id=patient_id).all()
    total_sessions = sum(r.session_count for r in records)
    total_workload = sum(r.weighted_workload for r in records)

    patient_dict = patient.to_dict()
    patient_dict['total_sessions'] = total_sessions
    patient_dict['total_workload'] = round(total_workload, 2)

    return jsonify({
        'success': True,
        'data': patient_dict
    })


@patient_bp.route('/patients', methods=['POST'])
def create_patient():
    """创建患者"""
    try:
        data = request.get_json()

        # 必填字段检查
        if not data.get('name'):
            return jsonify({'success': False, 'message': '患者姓名不能为空'}), 400

        # 检查患者编号是否重复
        if data.get('patient_no'):
            existing = Patient.query.filter_by(patient_no=data['patient_no']).first()
            if existing:
                return jsonify({'success': False, 'message': '患者编号已存在'}), 400

        # 验证主管治疗师
        therapist_id = data.get('primary_therapist_id')
        if therapist_id:
            therapist = WorkloadTherapist.query.get(therapist_id)
            if not therapist:
                return jsonify({'success': False, 'message': '指定的治疗师不存在'}), 400

        # 处理日期
        admission_date = None
        if data.get('admission_date'):
            try:
                admission_date = datetime.strptime(data['admission_date'], '%Y-%m-%d').date()
            except:
                pass

        # 验证副管治疗师
        secondary_therapist_id = data.get('secondary_therapist_id')
        if secondary_therapist_id:
            secondary_therapist = WorkloadTherapist.query.get(secondary_therapist_id)
            if not secondary_therapist:
                return jsonify({'success': False, 'message': '指定的副管治疗师不存在'}), 400

        # 验证第三治疗师
        tertiary_therapist_id = data.get('tertiary_therapist_id')
        if tertiary_therapist_id:
            tertiary_therapist = WorkloadTherapist.query.get(tertiary_therapist_id)
            if not tertiary_therapist:
                return jsonify({'success': False, 'message': '指定的第三治疗师不存在'}), 400

        patient = Patient(
            name=data['name'],
            patient_no=data.get('patient_no'),
            gender=data.get('gender'),
            age=data.get('age'),
            phone=data.get('phone'),
            diagnosis=data.get('diagnosis'),
            bed_no=data.get('bed_no'),
            primary_therapist_id=therapist_id,
            secondary_therapist_id=secondary_therapist_id,
            tertiary_therapist_id=tertiary_therapist_id,
            status=data.get('status', 'active'),
            admission_date=admission_date,
            notes=data.get('notes')
        )

        db.session.add(patient)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '患者创建成功',
            'data': patient.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'}), 500


@patient_bp.route('/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    """更新患者信息"""
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'message': '患者不存在'}), 404

        data = request.get_json()

        # 检查患者编号是否重复
        if data.get('patient_no') and data['patient_no'] != patient.patient_no:
            existing = Patient.query.filter_by(patient_no=data['patient_no']).first()
            if existing:
                return jsonify({'success': False, 'message': '患者编号已存在'}), 400

        # 更新字段
        if 'name' in data:
            patient.name = data['name']
        if 'patient_no' in data:
            patient.patient_no = data['patient_no']
        if 'gender' in data:
            patient.gender = data['gender']
        if 'age' in data:
            patient.age = data['age']
        if 'phone' in data:
            patient.phone = data['phone']
        if 'diagnosis' in data:
            patient.diagnosis = data['diagnosis']
        if 'bed_no' in data:
            patient.bed_no = data['bed_no']
        if 'primary_therapist_id' in data:
            # 验证治疗师存在
            if data['primary_therapist_id']:
                therapist = WorkloadTherapist.query.get(data['primary_therapist_id'])
                if not therapist:
                    return jsonify({'success': False, 'message': '指定的治疗师不存在'}), 400
            patient.primary_therapist_id = data['primary_therapist_id']
        if 'secondary_therapist_id' in data:
            # 验证副管治疗师存在
            if data['secondary_therapist_id']:
                secondary_therapist = WorkloadTherapist.query.get(data['secondary_therapist_id'])
                if not secondary_therapist:
                    return jsonify({'success': False, 'message': '指定的副管治疗师不存在'}), 400
            patient.secondary_therapist_id = data['secondary_therapist_id']
        if 'tertiary_therapist_id' in data:
            # 验证第三治疗师存在
            if data['tertiary_therapist_id']:
                tertiary_therapist = WorkloadTherapist.query.get(data['tertiary_therapist_id'])
                if not tertiary_therapist:
                    return jsonify({'success': False, 'message': '指定的第三治疗师不存在'}), 400
            patient.tertiary_therapist_id = data['tertiary_therapist_id']
        if 'status' in data:
            patient.status = data['status']
        if 'admission_date' in data:
            try:
                patient.admission_date = datetime.strptime(data['admission_date'], '%Y-%m-%d').date()
            except:
                patient.admission_date = None
        if 'discharge_date' in data:
            try:
                patient.discharge_date = datetime.strptime(data['discharge_date'], '%Y-%m-%d').date()
            except:
                patient.discharge_date = None
        if 'notes' in data:
            patient.notes = data['notes']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '患者信息更新成功',
            'data': patient.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@patient_bp.route('/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    """删除患者"""
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'message': '患者不存在'}), 404

        # 检查是否有关联的工作量记录
        record_count = WorkloadRecord.query.filter_by(patient_id=patient_id).count()
        if record_count > 0:
            return jsonify({
                'success': False,
                'message': f'该患者有 {record_count} 条工作量记录，无法删除。建议将状态改为"已结束"。'
            }), 400

        db.session.delete(patient)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '患者删除成功'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


# ============================================================================
# 治疗师-患者关系 API
# ============================================================================

@patient_bp.route('/therapist-patients', methods=['GET'])
def get_therapist_patients():
    """获取治疗师-患者关系面板数据"""
    # 获取所有在职治疗师
    therapists = WorkloadTherapist.query.filter_by(is_active=True).order_by(WorkloadTherapist.sort_order).all()

    result = []
    for therapist in therapists:
        # 获取该治疗师主管的患者（包括作为主管、副管、第三治疗师）
        patients = Patient.query.filter(
            db.or_(
                Patient.primary_therapist_id == therapist.id,
                Patient.secondary_therapist_id == therapist.id,
                Patient.tertiary_therapist_id == therapist.id
            ),
            Patient.status == 'active'
        ).all()

        # 统计数据
        total_patients = len(patients)
        patient_list = [p.to_dict() for p in patients]

        # 计算该治疗师主管患者的总治疗次数和工作量
        patient_ids = [p.id for p in patients]
        if patient_ids:
            records = WorkloadRecord.query.filter(
                WorkloadRecord.patient_id.in_(patient_ids)
            ).all()
            total_sessions = sum(r.session_count for r in records)
            total_workload = sum(r.weighted_workload for r in records)
        else:
            total_sessions = 0
            total_workload = 0

        result.append({
            'therapist': therapist.to_dict(),
            'patient_count': total_patients,
            'patients': patient_list,
            'total_sessions': total_sessions,
            'total_workload': round(total_workload, 2)
        })

    # 获取未分配主管治疗师的患者（没有任何治疗师）
    unassigned_patients = Patient.query.filter(
        Patient.primary_therapist_id == None,
        Patient.secondary_therapist_id == None,
        Patient.tertiary_therapist_id == None,
        Patient.status == 'active'
    ).all()

    return jsonify({
        'success': True,
        'data': {
            'therapist_patients': result,
            'unassigned_patients': [p.to_dict() for p in unassigned_patients],
            'unassigned_count': len(unassigned_patients),
            'total_therapists': len(therapists)
        }
    })


@patient_bp.route('/therapist-patients/summary', methods=['GET'])
def get_therapist_patients_summary():
    """获取治疗师-患者关系统计摘要"""
    # 各治疗师主管患者数统计
    therapist_stats = db.session.query(
        WorkloadTherapist.id,
        WorkloadTherapist.name,
        func.count(Patient.id).label('patient_count')
    ).outerjoin(
        Patient,
        db.and_(
            WorkloadTherapist.id == Patient.primary_therapist_id,
            Patient.status == 'active'
        )
    ).filter(
        WorkloadTherapist.is_active == True
    ).group_by(
        WorkloadTherapist.id
    ).order_by(
        func.count(Patient.id).desc()
    ).all()

    # 总患者数
    total_active_patients = Patient.query.filter_by(status='active').count()
    total_patients = Patient.query.count()

    # 未分配治疗师的患者数
    unassigned_count = Patient.query.filter(
        Patient.primary_therapist_id == None,
        Patient.status == 'active'
    ).count()

    return jsonify({
        'success': True,
        'data': {
            'therapist_stats': [{
                'therapist_id': t.id,
                'therapist_name': t.name,
                'patient_count': t.patient_count
            } for t in therapist_stats],
            'total_active_patients': total_active_patients,
            'total_patients': total_patients,
            'unassigned_count': unassigned_count,
            'assigned_count': total_active_patients - unassigned_count
        }
    })


@patient_bp.route('/patients/batch-assign', methods=['POST'])
def batch_assign_therapist():
    """批量分配主管治疗师"""
    try:
        data = request.get_json()
        patient_ids = data.get('patient_ids', [])
        therapist_id = data.get('therapist_id')

        if not patient_ids:
            return jsonify({'success': False, 'message': '请选择要分配的患者'}), 400

        # 验证治疗师
        if therapist_id:
            therapist = WorkloadTherapist.query.get(therapist_id)
            if not therapist:
                return jsonify({'success': False, 'message': '指定的治疗师不存在'}), 400

        # 批量更新
        updated_count = Patient.query.filter(
            Patient.id.in_(patient_ids)
        ).update(
            {'primary_therapist_id': therapist_id},
            synchronize_session='fetch'
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'成功为 {updated_count} 名患者分配主管治疗师',
            'data': {'updated_count': updated_count}
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'分配失败: {str(e)}'}), 500


@patient_bp.route('/patients/<int:patient_id>/dismiss-alert', methods=['POST'])
def dismiss_patient_alert(patient_id):
    """消除患者复诊提醒"""
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'message': '患者不存在'}), 404

        data = request.get_json()
        reason = data.get('reason', '')

        if not reason:
            return jsonify({'success': False, 'message': '请提供消除理由'}), 400

        # 更新消除提醒状态
        patient.alert_dismissed = True
        patient.alert_dismiss_reason = reason
        patient.alert_dismissed_at = datetime.now()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '提醒已消除',
            'data': patient.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500


@patient_bp.route('/assign-therapist-to-patient', methods=['POST'])
def assign_therapist_to_patient():
    """为患者分配治疗师（从工作量记录中识别的患者）"""
    try:
        data = request.get_json()
        patient_info = data.get('patient_info')
        patient_id = data.get('patient_id')
        primary_therapist_id = data.get('primary_therapist_id')
        secondary_therapist_id = data.get('secondary_therapist_id')
        tertiary_therapist_id = data.get('tertiary_therapist_id')

        if not patient_info:
            return jsonify({'success': False, 'message': '患者信息不能为空'}), 400

        # 验证治疗师存在
        if primary_therapist_id:
            therapist = WorkloadTherapist.query.get(primary_therapist_id)
            if not therapist:
                return jsonify({'success': False, 'message': '主管治疗师不存在'}), 400

        # 查找或创建患者记录
        patient = None
        if patient_id:
            patient = Patient.query.get(patient_id)

        if not patient:
            # 尝试从patient_info中提取姓名
            patient_name = patient_info.split('/')[-1] if '/' in patient_info else patient_info
            # 尝试查找同名患者
            patient = Patient.query.filter(Patient.name == patient_name).first()

        if not patient:
            # 创建新患者记录
            patient = Patient(
                name=patient_name,
                primary_therapist_id=primary_therapist_id,
                secondary_therapist_id=secondary_therapist_id,
                tertiary_therapist_id=tertiary_therapist_id,
                status='active'
            )
            db.session.add(patient)
            db.session.flush()  # 获取ID
        else:
            # 更新现有患者的治疗师
            if primary_therapist_id:
                patient.primary_therapist_id = primary_therapist_id
            if secondary_therapist_id is not None:
                patient.secondary_therapist_id = secondary_therapist_id if secondary_therapist_id else None
            if tertiary_therapist_id is not None:
                patient.tertiary_therapist_id = tertiary_therapist_id if tertiary_therapist_id else None

        # 更新工作量记录中的patient_id
        if patient.id:
            WorkloadRecord.query.filter(
                WorkloadRecord.patient_info == patient_info
            ).update({'patient_id': patient.id}, synchronize_session='fetch')

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '治疗师分配成功',
            'data': patient.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'分配失败: {str(e)}'}), 500


@patient_bp.route('/patients-from-records', methods=['GET'])
def get_patients_from_records():
    """从工作量记录中获取患者列表（按患者聚合）"""
    from app.models import WorkloadRecord, WorkloadTreatmentItem

    # 获取搜索和筛选参数
    search = request.args.get('search', '').strip()
    therapist_id = request.args.get('therapist_id')

    # 从工作量记录中聚合患者数据
    query = db.session.query(
        WorkloadRecord.patient_info,
        WorkloadRecord.patient_id,
        func.group_concat(func.distinct(WorkloadTreatmentItem.name)).label('treatment_items'),
        func.min(WorkloadRecord.therapist_id).label('first_therapist_id'),
        func.max(WorkloadRecord.record_date).label('last_treatment_date'),
        func.sum(WorkloadRecord.session_count).label('total_sessions'),
        func.count(WorkloadRecord.id).label('record_count')
    ).join(
        WorkloadTreatmentItem,
        WorkloadRecord.treatment_item_id == WorkloadTreatmentItem.id
    ).filter(
        WorkloadRecord.patient_info != None,
        WorkloadRecord.patient_info != ''
    ).group_by(
        WorkloadRecord.patient_info
    ).order_by(
        func.max(WorkloadRecord.record_date).desc()
    )

    # 搜索过滤
    if search:
        query = query.filter(WorkloadRecord.patient_info.contains(search))

    # 治疗师过滤（筛选该治疗师治疗过的患者）
    if therapist_id:
        # 获取该治疗师治疗过的患者列表
        therapist_patient_infos = db.session.query(
            WorkloadRecord.patient_info
        ).filter(
            WorkloadRecord.therapist_id == int(therapist_id)
        ).distinct().all()
        therapist_patient_list = [p[0] for p in therapist_patient_infos if p[0]]
        query = query.filter(WorkloadRecord.patient_info.in_(therapist_patient_list))

    results = query.all()

    patients = []
    for r in results:
        # 获取或创建患者记录
        patient = None
        if r.patient_id:
            patient = Patient.query.get(r.patient_id)

        # 如果患者不存在，尝试按姓名匹配
        if not patient:
            patient_name = r.patient_info.split('/')[-1] if '/' in r.patient_info else r.patient_info
            patient = Patient.query.filter(Patient.name == patient_name).first()

        # 获取主管治疗师信息
        primary_therapist = None
        secondary_therapist = None
        tertiary_therapist = None

        if patient:
            if patient.primary_therapist_id:
                primary_therapist = WorkloadTherapist.query.get(patient.primary_therapist_id)
            if patient.secondary_therapist_id:
                secondary_therapist = WorkloadTherapist.query.get(patient.secondary_therapist_id)
            if patient.tertiary_therapist_id:
                tertiary_therapist = WorkloadTherapist.query.get(patient.tertiary_therapist_id)

        # 如果没有主管治疗师，使用第一次登记的治疗师
        if not primary_therapist and r.first_therapist_id:
            primary_therapist = WorkloadTherapist.query.get(r.first_therapist_id)

        # 计算距上次治疗天数
        days_since_last = None
        if r.last_treatment_date:
            days_since_last = (date.today() - r.last_treatment_date).days

        # 构建治疗师显示
        therapists = []
        if primary_therapist:
            therapists.append(primary_therapist.name)
        if secondary_therapist:
            therapists.append(secondary_therapist.name)
        if tertiary_therapist:
            therapists.append(tertiary_therapist.name)

        patients.append({
            'patient_info': r.patient_info,
            'patient_id': patient.id if patient else None,
            'treatment_items': r.treatment_items or '',
            'primary_therapist_id': primary_therapist.id if primary_therapist else None,
            'primary_therapist_name': primary_therapist.name if primary_therapist else None,
            'secondary_therapist_id': secondary_therapist.id if secondary_therapist else None,
            'secondary_therapist_name': secondary_therapist.name if secondary_therapist else None,
            'tertiary_therapist_id': tertiary_therapist.id if tertiary_therapist else None,
            'tertiary_therapist_name': tertiary_therapist.name if tertiary_therapist else None,
            'therapist_display': '、'.join(therapists) if therapists else '未分配',
            'last_treatment_date': r.last_treatment_date.isoformat() if r.last_treatment_date else None,
            'days_since_last_treatment': days_since_last,
            'total_sessions': r.total_sessions,
            'record_count': r.record_count,
            'alert_dismissed': patient.alert_dismissed if patient else False,
            'alert_dismiss_reason': patient.alert_dismiss_reason if patient else None
        })

    return jsonify({
        'success': True,
        'data': {
            'patients': patients,
            'total': len(patients)
        }
    })


@patient_bp.route('/patients/by-treatment-item', methods=['GET'])
def get_patients_by_treatment_item():
    """按治疗项目查询患者列表（支持按最小治疗次数过滤）
    
    参数:
        treatment_item_id: 治疗项目ID（必填）
        min_sessions: 最小治疗次数（可选，默认1）
        search: 患者姓名模糊搜索（可选）
    
    示例: /api/patients/by-treatment-item?treatment_item_id=3&min_sessions=5
    """
    from app.models import WorkloadRecord, WorkloadTreatmentItem
    
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
