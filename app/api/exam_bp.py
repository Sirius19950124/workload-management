# -*- coding: utf-8 -*-
"""
在线培训考试系统 - API模块
包含: 资料管理 / 题库管理 / 试卷管理 / 考试分配 / 答题流程 / 统计分析
"""

import os
import json
import uuid
import random
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from sqlalchemy import text
from app import db
from app.models import (TrainingMaterial, QuestionBank, ExamPaper, ExamPaperQuestion,
                       ExamAssignment, ExamAnswer, WorkloadTherapist)

log = logging.getLogger(__name__)

def log_action(msg):
    log.info('[ACTION] %s', msg)

exam_bp = Blueprint('exam', __name__, url_prefix='/api')


# ==================== 辅助函数 ====================

def get_upload_folder():
    """获取上传目录"""
    upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'exam_materials')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def auto_grade(answers_list, paper_questions, shuffled_answer_map=None):
    """
    自动评分核心函数

    Args:
        answers_list: [{question_id: int, user_answer: str}, ...]
        paper_questions: [ExamPaperQuestion对象列表]
        shuffled_answer_map: 可选，{question_id: shuffled_correct_answer}。
                            当试卷选项被打乱时，客户端应传入打乱后的正确答案。

    Returns:
        (score, total_score, grading_detail)
    """
    # 构建题目ID->标准答案的映射
    answer_map = {}
    question_info = {}
    for pq in paper_questions:
        q = pq.question
        if q:
            # 优先使用传入的打乱后答案（如果选项被shuffle过）
            if shuffled_answer_map and q.id in shuffled_answer_map:
                answer_map[q.id] = shuffled_answer_map[q.id]
            else:
                answer_map[q.id] = q.answer
            question_info[q.id] = {
                'type': q.question_type,
                'text': q.question_text,
                'score': pq.score,
                'analysis': q.analysis,
                'options': json.loads(q.options) if q.options else []
            }

    # 只处理属于当前试卷的答案（忽略客户端伪造的额外题目ID）
    valid_question_ids = set(question_info.keys())

    score = 0
    total_score = 0
    grading_detail = []

    for ans in answers_list:
        qid = ans.get('question_id')

        # 跳过不属于当前试卷的题目
        if qid not in valid_question_ids:
            continue

        user_ans = str(ans.get('user_answer', '')).strip()

        info = question_info.get(qid, {})
        correct_ans = answer_map.get(qid, '')
        q_score = info.get('score', 2)
        total_score += q_score

        # 判断对错
        is_correct = _check_answer(user_ans, correct_ans, info.get('type'))

        if is_correct:
            score += q_score

        grading_detail.append({
            'question_id': qid,
            'question_text': info.get('text', ''),
            'question_type': info.get('type', ''),
            'user_answer': user_ans,
            'correct_answer': correct_ans,
            'is_correct': is_correct,
            'score': q_score if is_correct else 0,
            'analysis': info.get('analysis', '')
        })

    return score, total_score, grading_detail


def _check_answer(user_answer, correct_answer, question_type):
    """判断用户答案是否正确"""
    if not user_answer:
        return False

    user_clean = user_answer.strip().upper().replace(' ', '')
    correct_clean = correct_answer.strip().upper().replace(' ', '')

    if question_type == 'multiple_choice':
        # 多选：排序后比较
        return sorted(user_clean) == sorted(correct_clean)
    elif question_type == 'fill_blank':
        # 填空：模糊匹配（包含关键词即可）
        return user_clean in correct_clean or correct_clean in user_clean
    else:
        # 单选/判断：精确匹配
        return user_clean == correct_clean


def shuffle_list(items):
    """打乱列表顺序"""
    result = list(items)
    random.shuffle(result)
    return result


def shuffle_options_for_question(question_dict):
    """打乱单道题的选项顺序（同时调整答案）"""
    if question_dict.get('question_type') in ('single_choice', 'multiple_choice'):
        options = list(question_dict.get('options', []))
        if len(options) > 1:
            random.shuffle(options)
            # 重新分配label
            new_labels = {}
            for i, opt in enumerate(options):
                old_label = opt['label']
                new_label = chr(ord('A') + i)
                new_labels[old_label] = new_label
                opt['label'] = new_label
            # 调整答案label
            old_answer = question_dict.get('answer', '')
            new_answer = ''.join(sorted(new_labels.get(l, l) for l in old_answer.upper()))
            question_dict['options'] = options
            question_dict['answer'] = new_answer
    return question_dict


# ==================== 1. 培训资料管理 ====================

@exam_bp.route('/exam/materials', methods=['GET'])
def list_materials():
    """获取培训资料列表"""
    try:
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        query = TrainingMaterial.query.filter_by(is_active=True)

        if search:
            query = query.filter(TrainingMaterial.title.contains(search))
        if category:
            query = query.filter(TrainingMaterial.category == category)

        pagination = query.order_by(TrainingMaterial.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'success': True,
            'data': {
                'materials': [m.to_dict() for m in pagination.items],
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/materials', methods=['POST'])
def upload_material():
    """上传培训资料"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400

        title = request.form.get('title', file.filename).strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '通用').strip()

        # 保存文件
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_ext = {'.pdf', '.doc', '.docx', '.txt'}
        if ext not in allowed_ext:
            return jsonify({'success': False, 'error': f'不支持的文件格式: {ext}，允许的格式: PDF/Word(.docx)/TXT'}), 400

        # .doc 旧版Word格式提示
        if ext == '.doc':
            return jsonify({'success': False, 'error': '不支持旧版Word格式(.doc)，请将文件另存为 .docx 格式后重新上传（在Word中：文件→另存为→选择Word文档*.docx）'}), 400

        filename = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        save_path = os.path.join(get_upload_folder(), filename)
        file.save(save_path)

        # 确定文件类型
        file_type = 'pdf' if ext == '.pdf' else ('word' if ext in ('.doc', '.docx') else 'txt')
        file_size = os.path.getsize(save_path)

        # 提取文本（失败不阻断上传，资料仍可正常使用）
        extracted_text = ''
        try:
            from app.services.ai_generator import extract_text_from_file
            extracted_text, _ = extract_text_from_file(save_path)
        except Exception as tex_err:
            print(f'[培训资料] 文本提取警告(不影响上传): {tex_err}')

        # 同步上传到COS（云环境持久化）
        cos_url = ''
        try:
            from app.cos_backup import is_configured, cos_upload_material
            if is_configured():
                ok, result = cos_upload_material(save_path, filename)
                if ok:
                    cos_url = result
                    print(f'[培训资料] COS备份成功: {filename}')
                else:
                    print(f'[培训资料] COS备份跳过(不影响使用): {result}')
        except Exception as cos_err:
            print(f'[培训资料] COS备份异常(不影响上传): {cos_err}')

        material = TrainingMaterial(
            title=title,
            description=description,
            file_name=file.filename,
            file_path=f'exam_materials/{filename}',
            file_type=file_type,
            file_size=file_size,
            extracted_text=extracted_text,
            category=category
        )
        db.session.add(material)
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('create', f'上传培训资料「{title}」')

        return jsonify({
            'success': True,
            'message': '资料上传成功',
            'data': material.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/materials/<int:material_id>', methods=['GET'])
def get_material(material_id):
    """获取资料详情"""
    try:
        material = TrainingMaterial.query.get(material_id)
        if not material:
            return jsonify({'success': False, 'error': '资料不存在'}), 404

        data = material.to_dict()
        # 包含提取的文本预览（截断）
        if material.extracted_text:
            data['extracted_text_preview'] = material.extracted_text[:2000]
            data['text_length'] = len(material.extracted_text)

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/materials/<int:material_id>/text', methods=['GET'])
def get_material_text(material_id):
    """获取资料的完整提取文本（用于AI出题预览）"""
    try:
        material = TrainingMaterial.query.get(material_id)
        if not material:
            return jsonify({'success': False, 'error': '资料不存在'}), 404

        return jsonify({
            'success': True,
            'data': {
                'id': material.id,
                'title': material.title,
                'file_name': material.file_name,
                'file_type': material.file_type,
                'file_size': material.file_size,
                'extracted_text': material.extracted_text or '',
                'text_length': len(material.extracted_text) if material.extracted_text else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/materials/<int:material_id>/download', methods=['GET'])
def download_material(material_id):
    """下载培训资料原始文件（本地优先，COS兜底）"""
    try:
        material = TrainingMaterial.query.get(material_id)
        if not material:
            return jsonify({'success': False, 'error': '资料不存在'}), 404
        if not material.is_active:
            return jsonify({'success': False, 'error': '资料已被删除'}), 410

        # 策略1：尝试从本地文件系统读取
        file_full_path = os.path.join(get_upload_folder().replace('exam_materials', ''), material.file_path)
        if os.path.exists(file_full_path) and os.path.getsize(file_full_path) > 0:
            return send_file(
                file_full_path,
                as_attachment=True,
                download_name=material.file_name,
                mimetype=_guess_mimetype(material.file_name)
            )

        # 策略2：本地文件丢失，尝试COS（云环境容器重建场景）
        from app.cos_backup import is_configured, cos_download_stream, cos_material_exists
        if is_configured():
            # 从file_path中提取存储的文件名 (exam_materials/xxx_filename → xxx_filename)
            stored_name = os.path.basename(material.file_path)
            if cos_material_exists(stored_name):
                # 返回302重定向到COS预签名URL
                presigned_url = cos_download_stream(stored_name)
                if presigned_url:
                    from flask import redirect
                    print(f'[培训资料] 本地文件缺失，使用COS: {material.file_name}')
                    return redirect(presigned_url)

        return jsonify({'success': False, 'error': '文件已丢失且云端也无备份，请重新上传'}), 410
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _guess_mimetype(filename):
    """根据扩展名猜测MIME类型"""
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.txt': 'text/plain',
    }
    return mime_map.get(ext, 'application/octet-stream')


@exam_bp.route('/exam/materials/<int:material_id>', methods=['DELETE'])
def delete_material(material_id):
    """删除培训资料（软删除+清理COS）"""
    try:
        material = TrainingMaterial.query.get(material_id)
        if not material:
            return jsonify({'success': False, 'error': '资料不存在'}), 404

        material.is_active = False
        db.session.commit()

        # 同步删除COS上的文件（异步不阻塞响应）
        try:
            from app.cos_backup import cos_delete_material
            stored_name = os.path.basename(material.file_path)
            cos_delete_material(stored_name)
        except Exception:
            pass  # COS清理失败不影响删除操作

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'删除培训资料「{material.title}」')

        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/materials/cos-sync', methods=['POST'])
def sync_materials_to_cos():
    """将所有本地培训资料同步上传到COS（用于首次配置或容器重建后）"""
    try:
        from app.cos_backup import is_configured, cos_upload_material, cos_material_exists
        if not is_configured():
            return jsonify({'success': False, 'error': 'COS未配置，无法同步'}), 400

        materials = TrainingMaterial.query.filter_by(is_active=True).all()
        synced = 0
        skipped = 0
        failed = 0

        for m in materials:
            stored_name = os.path.basename(m.file_path)
            local_path = os.path.join(get_upload_folder().replace('exam_materials', ''), m.file_path)

            # 跳过没有本地文件的
            if not os.path.exists(local_path):
                failed += 1
                continue

            # COS上已存在的跳过
            if cos_material_exists(stored_name):
                skipped += 1
                continue

            ok, _ = cos_upload_material(local_path, stored_name)
            if ok:
                synced += 1
            else:
                failed += 1

        return jsonify({
            'success': True,
            'message': f'同步完成: 新增{synced}个, 已存在跳过{skipped}个, 失败{failed}个',
            'data': {'synced': synced, 'skipped': skipped, 'failed': failed, 'total': len(materials)}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/materials/categories', methods=['GET'])
def get_material_categories():
    """获取资料分类列表"""
    try:
        categories = db.session.query(
            TrainingMaterial.category
        ).filter_by(is_active=True).distinct().all()
        cat_list = [c[0] for c in categories if c[0]]
        return jsonify({'success': True, 'data': {'categories': cat_list}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 2. 题库管理 ====================

@exam_bp.route('/exam/questions', methods=['GET'])
def list_questions():
    """获取题库列表"""
    try:
        qtype = request.args.get('type', '')
        difficulty = request.args.get('difficulty', '')
        source = request.args.get('source', '')
        material_id = request.args.get('material_id', type=int)
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        query = QuestionBank.query.filter_by(is_active=True)

        if qtype:
            query = query.filter(QuestionBank.question_type == qtype)
        if difficulty:
            query = query.filter(QuestionBank.difficulty == difficulty)
        if source:
            query = query.filter(QuestionBank.source == source)
        if material_id:
            query = query.filter(QuestionBank.material_id == material_id)
        if search:
            query = query.filter(QuestionBank.question_text.contains(search))

        pagination = query.order_by(QuestionBank.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'success': True,
            'data': {
                'questions': [q.to_dict() for q in pagination.items],
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/questions', methods=['POST'])
def create_question():
    """手动创建题目"""
    try:
        data = request.get_json() or {}

        required_fields = ['question_type', 'question_text', 'answer']
        for f in required_fields:
            if not data.get(f):
                return jsonify({'success': False, 'error': f'缺少必填字段: {f}'}), 400

        qtype = data['question_type']
        options_data = data.get('options', [])

        # 处理选项
        options_str = ''
        if qtype in ('single_choice', 'multiple_choice'):
            if isinstance(options_data, list) and len(options_data) >= 2:
                options_str = json.dumps(options_data, ensure_ascii=False)
        elif qtype == 'true_false':
            options_str = json.dumps([
                {'label': 'T', 'text': '正确'},
                {'label': 'F', 'text': '错误'}
            ], ensure_ascii=False)

        question = QuestionBank(
            material_id=data.get('material_id'),
            question_type=qtype,
            question_text=data['question_text'].strip(),
            options=options_str,
            answer=str(data['answer']).strip(),
            analysis=data.get('analysis', '').strip(),
            difficulty=data.get('difficulty', 'medium'),
            score=data.get('score', 2),
            source='manual'
        )
        db.session.add(question)
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('create', f'创建题目「{question.question_text[:30]}...」')

        return jsonify({
            'success': True,
            'message': '题目创建成功',
            'data': question.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/questions/<int:question_id>', methods=['GET'])
def get_question(question_id):
    """获取题目详情"""
    try:
        question = QuestionBank.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'error': '题目不存在'}), 404
        return jsonify({'success': True, 'data': question.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/questions/<int:question_id>', methods=['PUT'])
def update_question(question_id):
    """更新题目"""
    try:
        question = QuestionBank.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'error': '题目不存在'}), 404
        if not question.is_active:
            return jsonify({'success': False, 'error': '该题目已被删除'}), 400

        data = request.get_json() or {}

        if 'question_type' in data:
            question.question_type = data['question_type']
        if 'question_text' in data:
            question.question_text = data['question_text'].strip()
        if 'options' in data:
            question.options = json.dumps(data['options'], ensure_ascii=False) if data['options'] else ''
        if 'answer' in data:
            question.answer = str(data['answer']).strip()
        if 'analysis' in data:
            question.analysis = data['analysis'].strip()
        if 'difficulty' in data:
            question.difficulty = data['difficulty']
        if 'score' in data:
            question.score = data['score']

        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('update', f'修改题目 ID={question_id}')

        return jsonify({
            'success': True,
            'message': '更新成功',
            'data': question.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/questions/<int:question_id>', methods=['DELETE'])
def delete_question(question_id):
    """删除题目（软删除）"""
    try:
        question = QuestionBank.query.get(question_id)
        if not question:
            return jsonify({'success': False, 'error': '题目不存在'}), 404

        # 检查是否在试卷中使用
        used_in_papers = ExamPaperQuestion.query.filter_by(question_id=question_id).all()
        if used_in_papers:
            paper_ids = list(set(pq.paper_id for pq in used_in_papers))
            paper_names = []
            for pid in paper_ids:
                p = ExamPaper.query.get(pid)
                if p:
                    paper_names.append(p.title)
            return jsonify({'success': False, 'error': f'该题目正在被试卷使用中（{"、".join(paper_names[:3])}），请先从试卷中移除'}), 400

        question.is_active = False
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'删除题目 ID={question_id}')

        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/questions/batch-delete', methods=['POST'])
def batch_delete_questions():
    """批量删除题目（软删除）"""
    try:
        data = request.get_json() or {}
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'success': False, 'error': '请选择要删除的题目'}), 400

        questions = QuestionBank.query.filter(QuestionBank.id.in_(ids)).all()
        if not questions:
            return jsonify({'success': False, 'error': '未找到任何题目'}), 404

        # 检查是否有题目在试卷中使用
        used_ids = []
        for q in questions:
            used = ExamPaperQuestion.query.filter_by(question_id=q.id).first()
            if used:
                paper = ExamPaper.query.get(used.paper_id)
                used_ids.append(q.id if not paper else f'{q.id}({paper.title})')

        if used_ids:
            return jsonify({
                'success': False,
                'error': f'以下 {len(used_ids)} 道题目正在被试卷使用，请先从试卷中移除：{"、".join(used_ids[:5])}',
                'used_count': len(used_ids)
            }), 400

        # 批量软删除
        deleted = 0
        for q in questions:
            q.is_active = False
            deleted += 1
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'批量删除题目 {deleted}条 (IDs: {ids[:10]}...)')

        return jsonify({'success': True, 'deleted': deleted, 'message': f'成功删除 {deleted} 道题目'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/questions/generate', methods=['POST'])
def ai_generate_questions():
    """AI智能生成题目"""
    try:
        data = request.get_json() or {}

        material_id = data.get('material_id')
        if not material_id:
            return jsonify({'success': False, 'error': '请选择培训资料'}), 400

        material = TrainingMaterial.query.get(material_id)
        if not material:
            return jsonify({'success': False, 'error': '资料不存在'}), 404

        if not material.extracted_text or not material.extracted_text.strip():
            return jsonify({'success': False, 'error': '该资料未能提取到有效文本内容，无法AI出题。请尝试重新上传或手动创建题目。'}), 400

        # 解析参数
        question_types = data.get('types', ['single_choice', 'multiple_choice', 'true_false'])
        count = min(data.get('count', 10), 30)  # 最多30题
        difficulty = data.get('difficulty', 'auto')

        from app.services.ai_generator import generate_questions

        questions = generate_questions(
            material.extracted_text,
            question_types,
            count,
            difficulty
        )

        # 保存到题库
        saved = []
        for q in questions:
            qb = QuestionBank(
                material_id=material_id,
                question_type=q['question_type'],
                question_text=q['question_text'],
                options=q.get('options', ''),
                answer=q['answer'],
                analysis=q.get('analysis', ''),
                difficulty=q.get('difficulty', 'medium'),
                score=q.get('score', 2),
                source='ai_generated'
            )
            db.session.add(qb)
            saved.append(qb)

        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('create', f'AI生成 {len(saved)} 道题目（资料：{material.title}）')

        return jsonify({
            'success': True,
            'message': f'成功生成并保存 {len(saved)} 道题目',
            'data': {
                'generated_count': len(saved),
                'questions': [q.to_dict() for q in saved]
            }
        }), 201

    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'AI出题失败: {str(e)}'}), 500


@exam_bp.route('/exam/questions/stats', methods=['GET'])
def question_stats():
    """题库统计"""
    try:
        total = QuestionBank.query.filter_by(is_active=True).count()

        type_stats = db.session.query(
            QuestionBank.question_type,
            db.func.count(QuestionBank.id)
        ).filter_by(is_active=True).group_by(QuestionBank.question_type).all()

        difficulty_stats = db.session.query(
            QuestionBank.difficulty,
            db.func.count(QuestionBank.id)
        ).filter_by(is_active=True).group_by(QuestionBank.difficulty).all()

        source_stats = db.session.query(
            QuestionBank.source,
            db.func.count(QuestionBank.id)
        ).filter_by(is_active=True).group_by(QuestionBank.source).all()

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'by_type': {t[0]: t[1] for t in type_stats},
                'by_difficulty': {d[0]: d[1] for d in difficulty_stats},
                'by_source': {s[0]: s[1] for s in source_stats}
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 3. 试卷管理 ====================

@exam_bp.route('/exam/papers', methods=['GET'])
def list_papers():
    """获取试卷列表"""
    try:
        status = request.args.get('status', '')
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        query = ExamPaper.query.filter_by(is_active=True)

        if status:
            query = query.filter(ExamPaper.status == status)
        if search:
            query = query.filter(ExamPaper.title.contains(search))

        pagination = query.order_by(ExamPaper.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'success': True,
            'data': {
                'papers': [p.to_dict() for p in pagination.items],
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers', methods=['POST'])
def create_paper():
    """创建试卷"""
    try:
        data = request.get_json() or {}

        if not data.get('title'):
            return jsonify({'success': False, 'error': '试卷标题不能为空'}), 400

        duration = data.get('duration_minutes', 60)
        if not isinstance(duration, (int, float)) or duration < 1:
            duration = 60

        paper = ExamPaper(
            title=data['title'].strip(),
            description=data.get('description', '').strip(),
            total_score=data.get('total_score', 100),
            pass_score=data.get('pass_score', 60),
            duration_minutes=int(duration),
            shuffle_questions=data.get('shuffle_questions', True),
            shuffle_options=data.get('shuffle_options', True),
            show_answer_after_submit=data.get('show_answer_after_submit', True),
            start_time=None,  # 后续可扩展
            end_time=None,
            created_by=data.get('created_by', '管理员')
        )
        db.session.add(paper)
        db.session.flush()  # 获取paper.id

        # 添加题目
        question_items = data.get('questions', [])
        total = 0
        for idx, qi in enumerate(question_items):
            # 验证题目存在且有效
            q = QuestionBank.query.get(qi.get('question_id'))
            if not q or not q.is_active:
                db.session.rollback()
                return jsonify({'success': False, 'error': f'题目ID={qi.get("question_id")}不存在或已删除'}), 400
            pq = ExamPaperQuestion(
                paper_id=paper.id,
                question_id=qi['question_id'],
                sort_order=idx,
                score=qi.get('score', 2)
            )
            db.session.add(pq)
            total += qi.get('score', 2)

        paper.total_score = total
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('create', f'创建试卷「{paper.title}」（{len(question_items)}题，总分{total}分）')

        return jsonify({
            'success': True,
            'message': '试卷创建成功',
            'data': paper.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>', methods=['GET'])
def get_paper(paper_id):
    """获取试卷详情（含完整题目）"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        data = paper.to_dict()
        # 包含完整题目列表
        pqs = ExamPaperQuestion.query.filter_by(paper_id=paper_id)\
            .order_by(ExamPaperQuestion.sort_order).all()
        data['questions'] = [pq.to_dict() for pq in pqs]

        # 统计已提交答卷数
        submitted_count = ExamAssignment.query.filter_by(
            paper_id=paper_id, status='submitted'
        ).count()
        data['submitted_count'] = submitted_count

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>', methods=['PUT'])
def update_paper(paper_id):
    """更新试卷"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        data = request.get_json() or {}

        updatable = ['title', 'description', 'pass_score', 'shuffle_questions',
                      'shuffle_options', 'show_answer_after_submit']
        for field in updatable:
            if field in data:
                setattr(paper, field, data[field])
        if 'duration_minutes' in data:
            dur = data['duration_minutes']
            if isinstance(dur, (int, float)) and dur >= 1:
                paper.duration_minutes = int(dur)

        # 更新题目（如果提供）
        if 'questions' in data:
            # 删除旧关联
            ExamPaperQuestion.query.filter_by(paper_id=paper_id).delete()
            total = 0
            for idx, qi in enumerate(data['questions']):
                # 验证题目存在且有效
                q = QuestionBank.query.get(qi.get('question_id'))
                if not q or not q.is_active:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': f'题目ID={qi.get("question_id")}不存在或已删除'}), 400
                pq = ExamPaperQuestion(
                    paper_id=paper_id,
                    question_id=qi['question_id'],
                    sort_order=idx,
                    score=qi.get('score', 2)
                )
                db.session.add(pq)
                total += qi.get('score', 2)
            paper.total_score = total

        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('update', f'修改试卷「{paper.title}」')

        return jsonify({
            'success': True,
            'message': '更新成功',
            'data': paper.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>', methods=['DELETE'])
def delete_paper(paper_id):
    """删除试卷"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        # 检查是否已有答卷
        # 检查是否有进行中或已提交的考试
        active_assignments = ExamAssignment.query.filter(
            ExamAssignment.paper_id == paper_id,
            ExamAssignment.status.in_(['started', 'submitted'])
        ).first()
        if active_assignments:
            return jsonify({'success': False, 'error': '该试卷已有进行中或已提交的考试记录，无法删除'}), 400

        paper.is_active = False
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'删除试卷「{paper.title}」')

        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/delete-confirm', methods=['POST'])
def delete_paper_confirm(paper_id):
    """密码确认后硬删除试卷（含关联数据）"""
    try:
        data = request.get_json() or {}
        password = data.get('password', '')
        if password != '2026':
            return jsonify({'success': False, 'error': '密码错误'}), 403

        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        # 删除关联数据：答卷 → 分配记录 → 试卷题目 → 试卷
        answer_ids = [a.id for a in ExamAnswer.query.join(ExamAssignment).filter(
            ExamAssignment.paper_id == paper_id).all()]
        for aid in answer_ids:
            db.session.delete(ExamAnswer.query.get(aid))

        ExamAssignment.query.filter_by(paper_id=paper_id).delete()
        ExamPaperQuestion.query.filter_by(paper_id=paper_id).delete()
        db.session.delete(paper)
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'硬删除试卷「{paper.title}」及全部关联数据')

        return jsonify({'success': True, 'message': '试卷及关联数据已彻底删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/publish', methods=['POST'])
def publish_paper(paper_id):
    """发布试卷"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        # 允许已关闭的试卷重新发布（status closed -> published）
        # if paper.status == 'closed':
        #     return jsonify({'success': False, 'error': '已关闭的试卷不能重新发布'}), 400

        # 检查是否有题目
        qcount = ExamPaperQuestion.query.filter_by(paper_id=paper_id).count()
        if qcount == 0:
            return jsonify({'success': False, 'error': '试卷没有题目，无法发布'}), 400

        # 检查总分是否有效
        if paper.total_score <= 0:
            return jsonify({'success': False, 'error': '试卷总分为0，请设置题目分值后再发布'}), 400

        paper.status = 'published'
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('update', f'发布试卷「{paper.title}」')

        return jsonify({'success': True, 'message': '试卷已发布'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/close', methods=['POST'])
def close_paper(paper_id):
    """关闭试卷"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        paper.status = 'closed'
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('update', f'关闭试卷「{paper.title}」')

        return jsonify({'success': True, 'message': '试卷已关闭'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/preview', methods=['GET'])
def preview_paper(paper_id):
    """预览试卷（考生视角）"""
    import traceback
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        # 安全获取试卷基本信息（避免count()触发懒加载问题）
        try:
            pdict = {
                'id': paper.id,
                'title': paper.title,
                'description': paper.description or '',
                'total_score': paper.total_score,
                'pass_score': paper.pass_score,
                'duration_minutes': paper.duration_minutes,
                'status': paper.status,
                'shuffle_questions': bool(paper.shuffle_questions),
                'shuffle_options': bool(paper.shuffle_options),
            }
        except Exception as pe:
            traceback.print_exc()
            pdict = {'id': paper.id, 'title': getattr(paper,'title','?'), 'total_score':100, 'pass_score':60, 'status':'draft'}

        pqs = ExamPaperQuestion.query.filter_by(paper_id=paper_id)\
            .order_by(ExamPaperQuestion.sort_order).all()

        questions = []
        for pq in pqs:
            try:
                qdict = pq.to_dict()
                opts = qdict.get('options')
                if isinstance(opts, str):
                    try: opts = json.loads(opts)
                    except: opts = []
                elif not isinstance(opts, list):
                    opts = []
                qdict['options'] = opts
                questions.append(qdict)
            except Exception as qe:
                questions.append({
                    'question_type': 'unknown',
                    'question_text': f'[题目加载失败]',
                    'options': [], 'answer': '', 'analysis': '',
                })

        # 应用打乱设置（安全调用）
        try:
            if pdict.get('shuffle_questions'):
                questions = shuffle_list(questions)
            if pdict.get('shuffle_options'):
                questions = [shuffle_options_for_question(q) for q in questions]
        except Exception:
            pass  # 打乱失败不影响预览

        return jsonify({
            'success': True,
            'data': {'paper': pdict, 'questions': questions}
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/test-ai', methods=['POST'])
def test_ai_connection():
    """测试AI API连接是否可用"""
    try:
        from app.services.ai_generator import get_ai_config
        config = get_ai_config()
        import requests
        # 发一个最小请求测试连通性
        resp = requests.post(
            (config['api_base_url'].rstrip('/') + '/v1/messages'),
            headers={
                'Content-Type': 'application/json',
                'x-api-key': config['api_key'],
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': config['model'],
                'max_tokens': 5,
                'messages': [{'role': 'user', 'content': 'hi'}]
            },
            timeout=15
        )
        if resp.status_code == 200:
            return jsonify({'success': True, 'data': {'model': config['model']}})
        else:
            return jsonify({'success': False, 'error': f'API返回HTTP {resp.status_code}: {resp.text[:200]}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 4. 考试分配 ====================

@exam_bp.route('/exam/papers/<int:paper_id>/assign', methods=['POST'])
def assign_exam(paper_id):
    """分配考试给治疗师"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404
        if paper.status != 'published':
            return jsonify({'success': False, 'error': '只有已发布的试卷才能分配'}), 400

        data = request.get_json() or {}
        therapist_ids = data.get('therapist_ids', [])

        if not therapist_ids:
            return jsonify({'success': False, 'error': '请选择要分配的治疗师'}), 400

        # "all" 表示所有在职治疗师
        if therapist_ids == ['all']:
            therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
            therapist_ids = [t.id for t in therapists]

        assigned_count = 0
        skipped_count = 0
        for tid in therapist_ids:
            # 检查是否已分配
            existing = ExamAssignment.query.filter_by(
                paper_id=paper_id, therapist_id=tid
            ).first()
            if existing:
                skipped_count += 1
                continue

            assignment = ExamAssignment(
                paper_id=paper_id,
                therapist_id=tid,
                status='assigned'
            )
            db.session.add(assignment)
            assigned_count += 1

        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('create', f'分配试卷「{paper.title}」给{assigned_count}名治疗师')

        return jsonify({
            'success': True,
            'message': f'成功分配给{assigned_count}人（跳过已分配{skipped_count}人）',
            'data': {'assigned': assigned_count, 'skipped': skipped_count}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/assignments', methods=['GET'])
def list_assignments(paper_id):
    """获取某试卷的所有分配记录"""
    try:
        assignments = ExamAssignment.query.filter_by(paper_id=paper_id)\
            .order_by(ExamAssignment.assigned_at.desc()).all()

        result = []
        for a in assignments:
            ad = a.to_dict()
            # 附加答案信息
            if a.answer_record:
                ad['answer'] = a.answer_record.to_dict()
            result.append(ad)

        return jsonify({'success': True, 'data': {'assignments': result}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/assignments/my-exams', methods=['GET'])
def my_exams():
    """移动端：获取某治疗师的考试列表"""
    try:
        therapist_id = request.args.get('therapist_id', type=int)
        if not therapist_id:
            return jsonify({'success': False, 'error': '缺少therapist_id参数'}), 400

        assignments = ExamAssignment.query.filter_by(therapist_id=therapist_id)\
            .join(ExamPaper, ExamAssignment.paper_id == ExamPaper.id)\
            .filter(ExamPaper.is_active == True)\
            .order_by(ExamAssignment.assigned_at.desc()).all()

        result = []
        for a in assignments:
            ad = a.to_dict()
            # 补充试卷信息
            ad['paper_duration'] = a.paper_rel.duration_minutes if a.paper_rel else None
            ad['paper_total_score'] = a.paper_rel.total_score if a.paper_rel else None
            ad['paper_pass_score'] = a.paper_rel.pass_score if a.paper_rel else None
            ad['has_answer'] = a.answer_record is not None
            if a.answer_record:
                ad['score'] = a.answer_record.score
                ad['is_passed'] = a.answer_record.score >= a.paper_rel.pass_score if a.paper_rel else False
            result.append(ad)

        return jsonify({'success': True, 'data': {'assignments': result}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/assignments/<int:assignment_id>', methods=['DELETE'])
def cancel_assignment(assignment_id):
    """取消考试分配"""
    try:
        assignment = ExamAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': '分配记录不存在'}), 404

        if assignment.status == 'submitted':
            return jsonify({'success': False, 'error': '已交卷的考试无法取消'}), 400

        db.session.delete(assignment)
        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'取消考试分配 ID={assignment_id}')

        return jsonify({'success': True, 'message': '已取消'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/batch-cancel', methods=['POST'])
def batch_cancel_assignments(paper_id):
    """批量取消考试分配（需密码）"""
    try:
        data = request.get_json() or {}
        password = data.get('password', '')
        if password != '2026':
            return jsonify({'success': False, 'error': '密码错误'}), 403

        assignment_ids = data.get('assignment_ids', [])
        if not assignment_ids:
            return jsonify({'success': False, 'error': '未选择任何分配记录'}), 400

        cancelled = 0
        skipped = 0
        for aid in assignment_ids:
            a = ExamAssignment.query.get(aid)
            if not a or a.paper_id != paper_id:
                skipped += 1
                continue
            if a.status == 'submitted':
                skipped += 1
                continue
            # 同时删除关联的答卷
            answer = ExamAnswer.query.filter_by(assignment_id=aid).first()
            if answer:
                db.session.delete(answer)
            db.session.delete(a)
            cancelled += 1

        db.session.commit()

        from app.api.operation_log_bp import log_operation
        log_operation('delete', f'批量取消试卷ID={paper_id}的{cancelled}条分配记录')

        return jsonify({
            'success': True,
            'message': f'已取消 {cancelled} 条分配' + (f'，跳过 {skipped} 条' if skipped else ''),
            'cancelled_count': cancelled,
            'skipped_count': skipped
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 5. 答题流程 ====================

@exam_bp.route('/exam/assignments/<int:assignment_id>/start', methods=['POST'])
def start_exam(assignment_id):
    """开始考试"""
    try:
        assignment = ExamAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': '分配记录不存在'}), 404

        if assignment.status not in ('assigned', 'started'):
            if assignment.status == 'submitted':
                return jsonify({'success': False, 'error': '您已经完成此考试'}), 400
            return jsonify({'success': False, 'error': '当前状态不允许开始考试'}), 400

        paper = assignment.paper_rel
        if not paper or paper.status != 'published':
            return jsonify({'success': False, 'error': '试卷不可用'}), 400

        # 只在首次开始时设置started_at
        if assignment.status == 'assigned':
            assignment.status = 'started'
            assignment.started_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '考试已开始',
            'data': {
                'assignment_id': assignment.id,
                'duration_minutes': paper.duration_minutes,
                'started_at': assignment.started_at.isoformat()
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/assignments/<int:assignment_id>/paper', methods=['GET'])
def get_exam_paper(assignment_id):
    """获取考试用的试卷内容（含打乱处理）"""
    try:
        assignment = ExamAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': '分配记录不存在'}), 404

        if assignment.status not in ('assigned', 'started'):
            return jsonify({'success': False, 'error': '当前状态不允许查看试卷'}), 400

        paper = assignment.paper_rel
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        pqs = ExamPaperQuestion.query.filter_by(paper_id=paper.id)\
            .order_by(ExamPaperQuestion.sort_order).all()

        questions = [pq.to_dict() for pq in pqs]

        # 打乱题目和选项
        if paper.shuffle_questions:
            questions = shuffle_list(questions)
        if paper.shuffle_options:
            questions = [shuffle_options_for_question(q) for q in questions]

        return jsonify({
            'success': True,
            'data': {
                'assignment_id': assignment_id,
                'paper_title': paper.title,
                'duration_minutes': paper.duration_minutes,
                'total_score': paper.total_score,
                'pass_score': paper.pass_score,
                'show_answer_after_submit': paper.show_answer_after_submit,
                'questions': questions
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/assignments/<int:assignment_id>/submit', methods=['POST'])
def submit_exam(assignment_id):
    """提交答卷（自动评分）"""
    try:
        assignment = ExamAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': '分配记录不存在'}), 404

        if assignment.status == 'submitted':
            return jsonify({'success': False, 'error': '您已经提交过答卷了'}), 400

        data = request.get_json() or {}
        answers_list = data.get('answers', [])
        time_spent = data.get('time_spent_seconds', 0)
        # 客户端传入的打乱后正确答案映射（选项shuffle时必须传入）
        shuffled_answer_map = data.get('correct_answers')  # {question_id: answer_label}

        if not answers_list:
            return jsonify({'success': False, 'error': '答卷不能为空'}), 400

        # 获取试卷题目
        paper = assignment.paper_rel
        pqs = ExamPaperQuestion.query.filter_by(paper_id=paper.id)\
            .order_by(ExamPaperQuestion.sort_order).all()

        # 自动评分
        score, total_score, grading_detail = auto_grade(answers_list, pqs, shuffled_answer_map)

        # 保存答卷
        exam_answer = ExamAnswer(
            assignment_id=assignment_id,
            answers_json=json.dumps(answers_list, ensure_ascii=False),
            score=score,
            total_score=total_score,
            time_spent_seconds=time_spent,
            grading_detail=json.dumps(grading_detail, ensure_ascii=False)
        )
        db.session.add(exam_answer)

        # 更新分配状态
        assignment.status = 'submitted'
        assignment.submitted_at = datetime.utcnow()

        db.session.commit()

        from app.api.operation_log_bp import log_operation
        therapist_name = assignment.therapist.name if assignment.therapist else str(assignment.therapist_id)
        log_operation('create', f'{therapist_name} 提交试卷「{paper.title}」，得分 {score}/{total_score}')

        return jsonify({
            'success': True,
            'message': '答卷提交成功',
            'data': exam_answer.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/assignments/<int:assignment_id>/result', methods=['GET'])
def get_exam_result(assignment_id):
    """查看考试成绩"""
    try:
        assignment = ExamAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': '分配记录不存在'}), 404

        if assignment.status != 'submitted' or not assignment.answer_record:
            return jsonify({'success': False, 'error': '尚未提交答卷'}), 400

        result = assignment.answer_record.to_dict()
        result['paper_title'] = assignment.paper_rel.title if assignment.paper_rel else ''
        result['therapist_name'] = assignment.therapist.name if assignment.therapist else ''

        # 补全旧答卷grading_detail中缺失的字段（question_type, question_text, analysis）
        detail = result.get('grading_detail', [])
        if detail:
            need_patch = any(not d.get('question_text') for d in detail)
            if need_patch:
                from app.models import QuestionBank
                # 构建题目ID->题目信息的映射
                qb_map = {}
                qids = [d.get('question_id') for d in detail if d.get('question_id')]
                if qids:
                    for q in QuestionBank.query.filter(QuestionBank.id.in_(qids)).all():
                        qb_map[q.id] = q
                for d in detail:
                    qid = d.get('question_id')
                    q = qb_map.get(qid)
                    if q:
                        if not d.get('question_text'):
                            d['question_text'] = q.question_text or ''
                        if not d.get('question_type'):
                            d['question_type'] = q.question_type or ''
                        if not d.get('analysis'):
                            d['analysis'] = q.analysis or ''
                result['grading_detail'] = detail

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 6. 统计分析 ====================

@exam_bp.route('/exam/statistics/overview', methods=['GET'])
def stats_overview():
    """总览统计"""
    try:
        total_papers = ExamPaper.query.filter_by(is_active=True).count()
        published_papers = ExamPaper.query.filter_by(is_active=True, status='published').count()

        total_submitted = ExamAssignment.query.filter_by(status='submitted').count()

        # 平均分
        avg_result = db.session.query(
            db.func.avg(ExamAnswer.score)
        ).join(ExamAssignment, ExamAnswer.assignment_id == ExamAssignment.id)\
         .scalar()
        avg_score = round(avg_result, 1) if avg_result else 0

        # 及格率
        pass_query = db.session.query(ExamAnswer).join(
            ExamAssignment, ExamAnswer.assignment_id == ExamAssignment.id
        ).join(ExamPaper, ExamAssignment.paper_id == ExamPaper.id)
        total_answers = pass_query.count()
        passed = pass_query.filter(ExamAnswer.score >= ExamPaper.pass_score).count()
        pass_rate = round(passed / total_answers * 100, 1) if total_answers > 0 else 0

        # 参考人数
        unique_therapists = db.session.query(
            ExamAssignment.therapist_id
        ).filter(ExamAssignment.status == 'submitted').distinct().count()

        return jsonify({
            'success': True,
            'data': {
                'total_papers': total_papers,
                'published_papers': published_papers,
                'total_submissions': total_submitted,
                'avg_score': avg_score,
                'pass_rate': pass_rate,
                'unique_participants': unique_therapists
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/statistics/rankings', methods=['GET'])
def stats_rankings():
    """成绩排行榜"""
    try:
        paper_id = request.args.get('paper_id', type=int)
        limit = request.args.get('limit', 50, type=int)

        query = db.session.query(
            ExamAnswer.id.label('answer_id'),
            WorkloadTherapist.name,
            ExamPaper.title.label('paper_title'),
            ExamPaper.pass_score,
            ExamAnswer.score,
            ExamAnswer.total_score,
            ExamAnswer.time_spent_seconds,
            ExamAnswer.created_at
        ).join(ExamAssignment, ExamAnswer.assignment_id == ExamAssignment.id)\
         .join(WorkloadTherapist, ExamAssignment.therapist_id == WorkloadTherapist.id)\
         .join(ExamPaper, ExamAssignment.paper_id == ExamPaper.id)\
         .filter(ExamPaper.is_active == True)

        if paper_id:
            query = query.filter(ExamAssignment.paper_id == paper_id)

        results = query.order_by(ExamAnswer.score.desc())\
            .limit(limit).all()

        rankings = []
        for r in results:
            rankings.append({
                'answer_id': r.answer_id,
                'name': r.name,
                'paper_title': r.paper_title,
                'score': r.score,
                'total_score': r.total_score,
                'pass_score': r.pass_score,
                'pass_rate': round(r.score / r.total_score * 100, 1) if r.total_score > 0 else 0,
                'is_passed': r.score >= r.pass_score if r.pass_score else False,
                'time_spent': f'{r.time_spent_seconds // 60}分{r.time_spent_seconds % 60}秒',
                'date': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else ''
            })

        return jsonify({'success': True, 'data': {'rankings': rankings}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/results', methods=['GET'])
def paper_results(paper_id):
    """某试卷的所有答卷结果"""
    try:
        assignments = ExamAssignment.query.filter_by(
            paper_id=paper_id, status='submitted'
        ).join(ExamAnswer, ExamAssignment.id == ExamAnswer.assignment_id)\
         .order_by(ExamAnswer.score.desc())\
         .all()

        results = []
        for a in assignments:
            results.append({
                'assignment_id': a.id,
                'therapist_name': a.therapist.name if a.therapist else '',
                'score': a.answer_record.score if a.answer_record else 0,
                'total_score': a.answer_record.total_score if a.answer_record else 0,
                'is_passed': (a.answer_record.score >= a.paper_rel.pass_score) if a.answer_record and a.paper_rel else False,
                'time_spent': f'{a.answer_record.time_spent_seconds // 60}分{a.answer_record.time_spent_seconds % 60}秒' if a.answer_record else '',
                'submitted_at': a.submitted_at.strftime('%Y-%m-%d %H:%M') if a.submitted_at else ''
            })

        return jsonify({'success': True, 'data': {'results': results}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/papers/<int:paper_id>/analysis', methods=['GET'])
def paper_analysis(paper_id):
    """逐题分析（错误率等）"""
    try:
        paper = ExamPaper.query.get(paper_id)
        if not paper:
            return jsonify({'success': False, 'error': '试卷不存在'}), 404

        pqs = ExamPaperQuestion.query.filter_by(paper_id=paper_id)\
            .order_by(ExamPaperQuestion.sort_order).all()

        # 获取所有答卷
        assignments = ExamAssignment.query.filter_by(
            paper_id=paper_id, status='submitted'
        ).all()

        total_submissions = len(assignments)

        analysis = []
        for pq in pqs:
            q = pq.question
            if not q:
                continue

            # 统计这道题的错误次数
            error_count = 0
            for a in assignments:
                if a.answer_record and a.answer_record.grading_detail:
                    detail = json.loads(a.answer_record.grading_detail)
                    for d in detail:
                        if d.get('question_id') == q.id and not d.get('is_correct'):
                            error_count += 1
                            break

            error_rate = round(error_count / total_submissions * 100, 1) if total_submissions > 0 else 0

            analysis.append({
                'sort_order': pq.sort_order,
                'question_id': q.id,
                'question_type': q.question_type,
                'question_text': q.question_text[:100],
                'correct_answer': q.answer,
                'score': pq.score,
                'total_submissions': total_submissions,
                'error_count': error_count,
                'error_rate': error_rate,
                'correct_count': total_submissions - error_count,
                'difficulty': q.difficulty
            })

        return jsonify({
            'success': True,
            'data': {
                'paper_title': paper.title,
                'total_submissions': total_submissions,
                'analysis': analysis
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/statistics/therapist/<int:therapist_id>', methods=['GET'])
def therapist_history(therapist_id):
    """个人考试历史"""
    try:
        assignments = ExamAssignment.query.filter_by(
            therapist_id=therapist_id, status='submitted'
        ).order_by(ExamAssignment.submitted_at.desc()).all()

        history = []
        for a in assignments:
            history.append({
                'paper_title': a.paper_rel.title if a.paper_rel else '',
                'score': a.answer_record.score if a.answer_record else 0,
                'total_score': a.answer_record.total_score if a.answer_record else 0,
                'is_passed': (a.answer_record.score >= a.paper_rel.pass_score) if a.answer_record and a.paper_rel else False,
                'time_spent_seconds': a.answer_record.time_spent_seconds if a.answer_record else 0,
                'submitted_at': a.submitted_at.strftime('%Y-%m-%d %H:%M') if a.submitted_at else ''
            })

        # 个人统计
        scores = [h['score'] for h in history]
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        passed_count = sum(1 for h in history if h['is_passed'])

        return jsonify({
            'success': True,
            'data': {
                'history': history,
                'total_exams': len(history),
                'avg_score': avg,
                'passed_count': passed_count,
                'pass_rate': round(passed_count / len(history) * 100, 1) if history else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/statistics/therapists-all', methods=['GET'])
def therapists_all_stats():
    """全部人员答题统计汇总"""
    try:
        assignments = db.session.query(
            ExamAssignment, ExamAnswer, ExamPaper
        ).join(ExamAnswer, ExamAssignment.id == ExamAnswer.assignment_id)\
         .join(ExamPaper, ExamAssignment.paper_id == ExamPaper.id)\
         .filter(ExamAssignment.status == 'submitted')\
         .all()

        from collections import defaultdict
        stats = defaultdict(lambda: {'total': 0, 'score_sum': 0, 'passed': 0})
        names = {}
        for a, ans, paper in assignments:
            tid = a.therapist_id
            stats[tid]['total'] += 1
            stats[tid]['score_sum'] += ans.score or 0
            if ans.score >= paper.pass_score:
                stats[tid]['passed'] += 1
            if tid not in names:
                names[tid] = a.therapist.name if a.therapist else ''

        therapists = []
        for tid, s in sorted(stats.items(), key=lambda x: -x[1]['score_sum']/max(x[1]['total'],1)):
            therapists.append({
                'therapist_id': tid,
                'name': names.get(tid, ''),
                'total_exams': s['total'],
                'avg_score': round(s['score_sum'] / s['total'], 1) if s['total'] > 0 else 0,
                'passed_count': s['passed'],
                'pass_rate': round(s['passed'] / s['total'] * 100, 1) if s['total'] > 0 else 0
            })

        return jsonify({'success': True, 'data': {'therapists': therapists}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/answers/<int:answer_id>/delete', methods=['POST'])
def delete_answer(answer_id):
    """删除单条答题记录（需密码确认）"""
    try:
        data = request.get_json(force=True) or {}
        pwd = data.get('password', '')
        if pwd != '2026':
            return jsonify({'success': False, 'error': '密码错误'}), 403
        ans = ExamAnswer.query.get(answer_id)
        if not ans:
            return jsonify({'success': False, 'error': '记录不存在'}), 404
        assignment_id = ans.assignment_id
        db.session.delete(ans)
        # 检查分配是否还有其他答题记录，没有则重置为assigned状态
        remaining = ExamAnswer.query.filter_by(assignment_id=assignment_id).count()
        if remaining == 0:
            assign = ExamAssignment.query.get(assignment_id)
            if assign:
                assign.status = 'assigned'
        db.session.commit()
        log_action(f'删除答题记录 ID={answer_id}')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@exam_bp.route('/exam/answers/batch-delete', methods=['POST'])
def batch_delete_answers():
    """批量删除答题记录（需密码确认）"""
    try:
        data = request.get_json(force=True) or {}
        pwd = data.get('password', '')
        if pwd != '2026':
            return jsonify({'success': False, 'error': '密码错误'}), 403
        answer_ids = data.get('answer_ids', [])
        if not answer_ids:
            return jsonify({'success': False, 'error': '请选择要删除的记录'}), 400
        deleted = 0
        for aid in answer_ids:
            ans = ExamAnswer.query.get(aid)
            if ans:
                assignment_id = ans.assignment_id
                db.session.delete(ans)
                remaining = ExamAnswer.query.filter_by(assignment_id=assignment_id).count()
                if remaining == 0:
                    assign = ExamAssignment.query.get(assignment_id)
                    if assign:
                        assign.status = 'assigned'
                deleted += 1
        db.session.commit()
        log_action(f'批量删除答题记录 {deleted}条')
        return jsonify({'success': True, 'data': {'deleted_count': deleted}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

