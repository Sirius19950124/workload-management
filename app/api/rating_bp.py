# -*- coding: utf-8 -*-
"""
评价系统 API 蓝图（小程序 + 管理端）
功能：患者绑定验证、治疗记录查询、评价提交与历史、问卷配置、评价统计

API端点:
小程序用:
1. 患者绑定:   POST /api/patient/bind
2. 绑定检查:   GET  /api/patient/check
3. 最近记录:   GET  /api/records/recent
4. 提交评价:   POST /api/ratings
5. 评价历史:   GET  /api/ratings/history
6. 评价详情:   GET  /api/ratings/<id>
7. 问卷配置:   GET  /api/rating/config

管理端用:
8. 评价统计:   GET  /api/ratings/stats
9. 题目列表:   GET  /api/rating/questions
10. 添加题目:  POST /api/rating/questions
11. 编辑题目:  PUT  /api/rating/questions/<id>
12. 删除题目:  DELETE /api/rating/questions/<id>
13. 题目排序:  PUT  /api/rating/questions/reorder
"""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Patient, Rating, WorkloadRecord, WorkloadTherapist, WorkloadTreatmentItem, RatingQuestion, RatingAnswer
from app.api.log_decorator import log_op
from datetime import datetime, date, timedelta
from sqlalchemy import func, text, case
import json

rating_bp = Blueprint('rating', __name__, url_prefix='/api')


# ============================================================================
# 患者绑定（小程序用）
# ============================================================================

@rating_bp.route('/patient/bind', methods=['POST'])
@log_op('create', '绑定患者')
def bind_patient():
    """
    患者通过姓名+手机号绑定
    小程序端调用，验证身份后返回患者信息
    """
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()

        if not name or not phone:
            return jsonify({'success': False, 'message': '姓名和手机号不能为空'}), 400

        # 查找患者：优先精确匹配姓名+手机号
        patient = Patient.query.filter_by(name=name, phone=phone, status='active').first()

        if not patient:
            # 尝试只匹配手机号（方便输入不全姓名的情况）
            patient = Patient.query.filter_by(phone=phone, status='active').first()
            if not patient:
                return jsonify({'success': False, 'message': '未找到匹配的患者信息，请确认姓名和手机号'}), 404

        return jsonify({
            'success': True,
            'data': {
                'patient_id': patient.id,
                'name': patient.name,
                'phone': patient.phone,
                'patient_no': patient.patient_no,
                'diagnosis': patient.diagnosis,
                'primary_therapist_name': patient.primary_therapist.name if patient.primary_therapist else None
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'绑定失败: {str(e)}'}), 500


@rating_bp.route('/patient/check', methods=['GET'])
def check_patient_bind():
    """
    检查患者绑定状态
    通过 patient_id 验证患者是否存在且有效
    """
    try:
        patient_id = request.args.get('patient_id', type=int)
        if not patient_id:
            return jsonify({'success': False, 'message': '缺少 patient_id 参数'}), 400

        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'message': '患者不存在'}), 404

        if patient.status != 'active':
            return jsonify({'success': False, 'message': '该患者已结束治疗'}), 403

        return jsonify({
            'success': True,
            'data': {
                'patient_id': patient.id,
                'name': patient.name,
                'is_bound': True
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'检查失败: {str(e)}'}), 500


# ============================================================================
# 治疗记录查询（小程序用）
# ============================================================================

@rating_bp.route('/records/recent', methods=['GET'])
def get_recent_records():
    """
    获取患者最近的治疗记录（供评价使用）
    返回最近 30 天内的治疗记录
    """
    try:
        patient_id = request.args.get('patient_id', type=int)
        if not patient_id:
            return jsonify({'success': False, 'message': '缺少 patient_id 参数'}), 400

        # 只查最近30天
        thirty_days_ago = date.today() - timedelta(days=30)

        records = WorkloadRecord.query.filter(
            WorkloadRecord.patient_id == patient_id,
            WorkloadRecord.record_date >= thirty_days_ago
        ).order_by(WorkloadRecord.record_date.desc()).all()

        result = []
        seen = set()  # 去重（同一天同一项目可能有多条记录）

        for r in records:
            # 用 日期+治疗项目+治疗师 作为去重key
            key = (r.record_date, r.treatment_item_id, r.therapist_id)
            if key in seen:
                continue
            seen.add(key)

            result.append({
                'id': r.id,
                'record_date': r.record_date.isoformat() if r.record_date else None,
                'therapist_id': r.therapist_id,
                'therapist_name': r.therapist_rel.name if r.therapist_rel else None,
                'treatment_item_id': r.treatment_item_id,
                'treatment_item_name': r.treatment_item_rel.name if r.treatment_item_rel else None,
                'session_count': r.session_count,
                'remark': r.remark,
                # 检查是否已评价
                'is_rated': Rating.query.filter_by(
                    record_id=r.id, patient_id=patient_id
                ).first() is not None
            })

        return jsonify({
            'success': True,
            'data': {
                'records': result,
                'total': len(result)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'}), 500


@rating_bp.route('/records/<int:record_id>', methods=['GET'])
def get_record_detail(record_id):
    """
    获取单条治疗记录详情
    """
    try:
        record = WorkloadRecord.query.get(record_id)
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404

        return jsonify({
            'success': True,
            'data': record.to_dict()
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'}), 500


# ============================================================================
# 评价系统
# ============================================================================

@rating_bp.route('/ratings', methods=['POST'])
@log_op('create', '提交评价')
def submit_rating():
    """
    提交评价
    支持关联治疗记录或独立评价
    """
    try:
        data = request.get_json()

        # 必填检查
        patient_id = data.get('patient_id')
        star_rating = data.get('star_rating')
        answers = data.get('answers', [])

        if not patient_id:
            return jsonify({'success': False, 'message': '缺少 patient_id'}), 400

        # 如果没有传 star_rating，尝试从 answers 中计算
        if not star_rating and answers:
            star_values = []
            for ans in answers:
                q_data = ans.get('question_type')
                if q_data == 'star' and ans.get('answer_value'):
                    try:
                        star_values.append(int(ans['answer_value']))
                    except (ValueError, TypeError):
                        pass
            if star_values:
                star_rating = round(sum(star_values) / len(star_values))

        if not star_rating or not (1 <= int(star_rating) <= 5):
            return jsonify({'success': False, 'message': '评分必须在1-5之间'}), 400

        # 验证患者存在
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'message': '患者不存在'}), 404

        # 如果关联了治疗记录，验证记录存在且属于该患者
        record_id = data.get('record_id')
        if record_id:
            record = WorkloadRecord.query.get(record_id)
            if not record:
                return jsonify({'success': False, 'message': '治疗记录不存在'}), 404
            if record.patient_id != patient_id:
                return jsonify({'success': False, 'message': '该治疗记录不属于该患者'}), 403

            # 检查是否已评价过
            existing = Rating.query.filter_by(
                record_id=record_id, patient_id=patient_id
            ).first()
            if existing:
                return jsonify({'success': False, 'message': '该治疗记录已评价，请勿重复提交'}), 400

        # 处理标签
        tags = data.get('tags', [])
        if isinstance(tags, list):
            tags = ','.join(tags)

        # 计算总体评分（取星级题目的平均值）
        answers = data.get('answers', [])
        star_values = []
        for ans in answers:
            q = RatingQuestion.query.get(ans.get('question_id'))
            if q and q.question_type == 'star' and ans.get('answer_value'):
                try:
                    star_values.append(int(ans['answer_value']))
                except (ValueError, TypeError):
                    pass
        computed_star = round(sum(star_values) / len(star_values)) if star_values else int(star_rating)

        # 创建评价
        rating = Rating(
            patient_id=patient_id,
            record_id=record_id,
            therapist_id=data.get('therapist_id'),
            treatment_item_id=data.get('treatment_item_id'),
            star_rating=computed_star,
            comment=data.get('comment', ''),
            tags=tags,
            openid=data.get('openid')
        )

        db.session.add(rating)
        db.session.flush()  # 获取 rating.id

        # 保存多维度答案
        for ans in answers:
            question_id = ans.get('question_id')
            answer_value = ans.get('answer_value', '')
            if question_id and answer_value is not None:
                answer = RatingAnswer(
                    rating_id=rating.id,
                    question_id=question_id,
                    answer_value=str(answer_value)
                )
                db.session.add(answer)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '评价提交成功',
            'data': rating.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'提交失败: {str(e)}'}), 500


@rating_bp.route('/ratings/history', methods=['GET'])
def get_rating_history():
    """
    获取患者的评价历史
    """
    try:
        patient_id = request.args.get('patient_id', type=int)
        if not patient_id:
            return jsonify({'success': False, 'message': '缺少 patient_id 参数'}), 400

        # 分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(per_page, 50)  # 最多50条

        query = Rating.query.filter_by(patient_id=patient_id).order_by(Rating.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': {
                'ratings': [r.to_dict() for r in pagination.items],
                'total': pagination.total,
                'page': page,
                'per_page': per_page,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'}), 500


@rating_bp.route('/ratings/<int:rating_id>', methods=['GET'])
def get_rating_detail(rating_id):
    """
    获取评价详情
    """
    try:
        rating = Rating.query.get(rating_id)
        if not rating:
            return jsonify({'success': False, 'message': '评价不存在'}), 404

        return jsonify({
            'success': True,
            'data': rating.to_dict()
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'}), 500


@rating_bp.route('/ratings/<int:rating_id>', methods=['PUT'])
def update_rating(rating_id):
    """
    修改评价（小程序端"修改评价"功能）
    """
    try:
        rating = Rating.query.get(rating_id)
        if not rating:
            return jsonify({'success': False, 'message': '评价不存在'}), 404

        data = request.get_json()

        # 验证 patient_id 匹配（防止改别人的评价）
        if data.get('patient_id') and data['patient_id'] != rating.patient_id:
            return jsonify({'success': False, 'message': '无权修改该评价'}), 403

        if 'star_rating' in data:
            new_rating = data['star_rating']
            if not (1 <= int(new_rating) <= 5):
                return jsonify({'success': False, 'message': '评分必须在1-5之间'}), 400
            rating.star_rating = int(new_rating)

        if 'comment' in data:
            rating.comment = data['comment']

        if 'tags' in data:
            tags = data['tags']
            if isinstance(tags, list):
                tags = ','.join(tags)
            rating.tags = tags

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '评价已更新',
            'data': rating.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@rating_bp.route('/ratings/list', methods=['GET'])
def list_all_ratings():
    """
    管理端：获取所有评价（支持筛选）
    供桌面端评价管理面板使用
    """
    try:
        query = Rating.query

        # 筛选
        therapist_id = request.args.get('therapist_id', type=int)
        star_rating = request.args.get('star_rating', type=int)
        patient_name = request.args.get('patient_name', '').strip()

        if therapist_id:
            query = query.filter_by(therapist_id=therapist_id)
        if star_rating:
            query = query.filter_by(star_rating=star_rating)
        if patient_name:
            query = query.join(Patient, Rating.patient_id == Patient.id).filter(
                Patient.name.contains(patient_name)
            )

        query = query.order_by(Rating.created_at.desc())

        # 分页（前端大数据量时使用）
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 200, type=int)
        per_page = min(per_page, 500)

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'data': {
                'ratings': [r.to_dict() for r in pagination.items],
                'total': pagination.total,
                'page': page,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'}), 500


# ============================================================================
# 评价问卷配置（小程序 + 管理端）
# ============================================================================

@rating_bp.route('/rating/config', methods=['GET'])
def get_rating_config():
    """
    获取评价问卷配置（小程序启动时调用）
    只返回已启用的题目，按 sort_order 排序
    """
    try:
        questions = RatingQuestion.query.filter_by(is_active=True).order_by(
            RatingQuestion.sort_order.asc()
        ).all()

        return jsonify({
            'success': True,
            'data': {
                'questions': [q.to_dict() for q in questions]
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'获取配置失败: {str(e)}'}), 500


@rating_bp.route('/rating/questions', methods=['GET'])
def list_rating_questions():
    """
    管理端：获取所有评价题目（含已禁用的）
    """
    try:
        questions = RatingQuestion.query.order_by(
            RatingQuestion.sort_order.asc()
        ).all()

        return jsonify({
            'success': True,
            'data': {
                'questions': [q.to_dict() for q in questions]
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'}), 500


@rating_bp.route('/rating/questions', methods=['POST'])
@log_op('create', '新增评价题目')
def add_rating_question():
    """
    管理端：添加评价题目
    """
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        question_type = data.get('question_type', 'star')
        options = data.get('options', [])
        is_required = data.get('is_required', True)

        if not title:
            return jsonify({'success': False, 'message': '题目标题不能为空'}), 400

        if question_type not in ('star', 'radio', 'text'):
            return jsonify({'success': False, 'message': '题目类型必须是 star/radio/text'}), 400

        # 获取最大排序号
        max_order = db.session.query(func.max(RatingQuestion.sort_order)).scalar() or 0

        question = RatingQuestion(
            title=title,
            question_type=question_type,
            options=json.dumps(options, ensure_ascii=False) if isinstance(options, list) else options,
            is_required=is_required,
            sort_order=max_order + 1,
            is_active=True
        )

        db.session.add(question)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '题目添加成功',
            'data': question.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'}), 500


@rating_bp.route('/rating/questions/<int:question_id>', methods=['PUT'])
@log_op('update', '修改评价题目')
def update_rating_question(question_id):
    """
    管理端：编辑评价题目
    """
    try:
        question = RatingQuestion.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'message': '题目不存在'}), 404

        data = request.get_json()

        if 'title' in data:
            question.title = data['title'].strip()
        if 'question_type' in data:
            if data['question_type'] not in ('star', 'radio', 'text'):
                return jsonify({'success': False, 'message': '题目类型必须是 star/radio/text'}), 400
            question.question_type = data['question_type']
        if 'options' in data:
            options = data['options']
            if isinstance(options, list):
                options = json.dumps(options, ensure_ascii=False)
            question.options = options
        if 'is_required' in data:
            question.is_required = data['is_required']
        if 'is_active' in data:
            question.is_active = data['is_active']
        if 'sort_order' in data:
            question.sort_order = data['sort_order']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '题目更新成功',
            'data': question.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@rating_bp.route('/rating/questions/<int:question_id>', methods=['DELETE'])
@log_op('delete', '删除评价题目')
def delete_rating_question(question_id):
    """
    管理端：删除评价题目
    """
    try:
        question = RatingQuestion.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'message': '题目不存在'}), 404

        # 检查是否有评价答案引用此题目
        answer_count = RatingAnswer.query.filter_by(question_id=question_id).count()
        if answer_count > 0:
            # 软删除：禁用而不是真正删除
            question.is_active = False
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'该题目已有 {answer_count} 条评价答案，已改为禁用',
                'data': question.to_dict()
            })

        db.session.delete(question)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '题目已删除'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


@rating_bp.route('/rating/questions/reorder', methods=['PUT'])
def reorder_rating_questions():
    """
    管理端：重新排序题目
    body: {"orders": [{"id": 1, "sort_order": 1}, ...]}
    """
    try:
        data = request.get_json()
        orders = data.get('orders', [])

        for item in orders:
            question = RatingQuestion.query.get(item['id'])
            if question:
                question.sort_order = item['sort_order']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '排序已更新'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'排序失败: {str(e)}'}), 500


# ============================================================================
# 评价统计（管理端图表用）
# ============================================================================

@rating_bp.route('/ratings/stats', methods=['GET'])
def get_rating_stats():
    """
    管理端：获取评价统计数据（供图表展示）
    返回：总体统计、评分分布、各治疗师统计、月度趋势
    """
    try:
        # 时间范围筛选
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        therapist_id = request.args.get('therapist_id', type=int)

        base_query = Rating.query

        if start_date:
            base_query = base_query.filter(Rating.created_at >= start_date)
        if end_date:
            base_query = base_query.filter(Rating.created_at <= end_date + ' 23:59:59')
        if therapist_id:
            base_query = base_query.filter_by(therapist_id=therapist_id)

        all_ratings = base_query.all()

        if not all_ratings:
            return jsonify({
                'success': True,
                'data': {
                    'total_count': 0,
                    'avg_score': 0,
                    'five_star_count': 0,
                    'low_star_count': 0,
                    'distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                    'therapist_stats': [],
                    'monthly_trend': [],
                    'recent_comments': []
                }
            })

        # 总体统计
        total_count = len(all_ratings)
        scores = [r.star_rating for r in all_ratings]
        avg_score = round(sum(scores) / total_count, 1)
        five_star_count = scores.count(5)
        low_star_count = len([s for s in scores if s <= 2])

        # 评分分布
        distribution = {i: scores.count(i) for i in range(1, 6)}

        # 各治疗师统计（含好评率、各维度评分、加权评分）
        star_questions = RatingQuestion.query.filter_by(
            question_type='star', is_active=True
        ).order_by(RatingQuestion.sort_order).all()

        therapist_stats_list = []
        therapist_stats_query = db.session.query(
            WorkloadTherapist.id,
            WorkloadTherapist.name,
            func.count(Rating.id).label('count'),
            func.avg(Rating.star_rating).label('avg_score'),
            func.sum(case((Rating.star_rating >= 4, 1), else_=0)).label('good_count')
        ).join(Rating, WorkloadTherapist.id == Rating.therapist_id)

        if start_date:
            therapist_stats_query = therapist_stats_query.filter(Rating.created_at >= start_date)
        if end_date:
            therapist_stats_query = therapist_stats_query.filter(Rating.created_at <= end_date + ' 23:59:59')
        if therapist_id:
            therapist_stats_query = therapist_stats_query.filter(Rating.therapist_id == therapist_id)

        therapist_stats = therapist_stats_query.group_by(
            WorkloadTherapist.id, WorkloadTherapist.name
        ).order_by(func.avg(Rating.star_rating).desc()).all()

        for ts in therapist_stats:
            avg_score = round(float(ts.avg_score), 1) if ts.avg_score else 0
            good_count = int(ts.good_count) if ts.good_count else 0
            good_rate = round(good_count / ts.count * 100, 1) if ts.count > 0 else 0

            # 加权评分：基础分*60% + 好评率*0.04*20% + 评价数量奖励*20%
            count_bonus = min(ts.count / 20.0, 1.0)  # 20条以上满分
            weighted_score = round(avg_score * 0.6 + good_rate * 0.04 * 0.2 + count_bonus * 5 * 0.2, 1)

            # 各维度平均分
            dimension_scores = {}
            try:
                for q in star_questions:
                    dim_answers = db.session.query(RatingAnswer.answer_value).join(
                        Rating, RatingAnswer.rating_id == Rating.id
                    ).filter(
                        RatingAnswer.question_id == q.id,
                        Rating.therapist_id == ts.id
                    ).all()
                    if dim_answers:
                        vals = []
                        for da in dim_answers:
                            try:
                                vals.append(int(da.answer_value))
                            except (ValueError, TypeError):
                                pass
                        if vals:
                            dimension_scores[q.title] = round(sum(vals) / len(vals), 1)
            except Exception:
                pass

            therapist_stats_list.append({
                'therapist_id': ts.id,
                'therapist_name': ts.name,
                'count': ts.count,
                'avg_score': avg_score,
                'good_rate': good_rate,
                'good_count': good_count,
                'weighted_score': weighted_score,
                'dimension_scores': dimension_scores
            })

        # 按加权评分排序
        therapist_stats_list.sort(key=lambda x: x['weighted_score'], reverse=True)

        # 月度趋势（最近6个月）
        monthly_trend = []
        from dateutil.relativedelta import relativedelta
        for i in range(5, -1, -1):
            month_start = (date.today() - relativedelta(months=i)).replace(day=1)
            month_end = (month_start + relativedelta(months=1)) if i > 0 else date.today()

            month_ratings = [r for r in all_ratings
                           if r.created_at and month_start <= r.created_at.date() <= month_end]

            month_scores = [r.star_rating for r in month_ratings]
            month_avg = round(sum(month_scores) / len(month_scores), 1) if month_scores else 0

            monthly_trend.append({
                'month': month_start.strftime('%Y-%m'),
                'count': len(month_ratings),
                'avg_score': month_avg
            })

        # 最近评价（含文字反馈的）
        recent_with_comment = [r for r in all_ratings if r.comment and r.comment.strip()]
        recent_comments = [
            {
                'patient_name': r.patient.name if r.patient else '未知',
                'therapist_name': r.therapist.name if r.therapist else '未知',
                'star_rating': r.star_rating,
                'comment': r.comment,
                'created_at': r.created_at.strftime('%m-%d %H:%M') if r.created_at else ''
            }
            for r in recent_with_comment[:10]
        ]

        # 各维度评分统计（如果有 RatingAnswer）
        question_stats = []
        try:
            for q in star_questions:
                answers = RatingAnswer.query.filter_by(question_id=q.id).all()
                if answers:
                    values = []
                    for a in answers:
                        try:
                            values.append(int(a.answer_value))
                        except (ValueError, TypeError):
                            pass
                    if values:
                        q_dist = {i: values.count(i) for i in range(1, 6)}
                        question_stats.append({
                            'question_id': q.id,
                            'title': q.title,
                            'avg_score': round(sum(values) / len(values), 1),
                            'count': len(values),
                            'distribution': q_dist
                        })
        except Exception:
            pass  # 如果 rating_answers 表不存在，跳过

        return jsonify({
            'success': True,
            'data': {
                'total_count': total_count,
                'avg_score': avg_score,
                'five_star_count': five_star_count,
                'low_star_count': low_star_count,
                'distribution': distribution,
                'therapist_stats': therapist_stats_list,
                'monthly_trend': monthly_trend,
                'recent_comments': recent_comments,
                'question_stats': question_stats
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'统计失败: {str(e)}'}), 500
