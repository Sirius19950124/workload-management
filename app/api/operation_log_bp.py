# -*- coding: utf-8 -*-
"""操作日志 API"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from app import db
from app.models import WorkloadOperationLog

operation_log_bp = Blueprint('operation_log', __name__)


@operation_log_bp.route('/api/operation-logs', methods=['GET'])
def get_operation_logs():
    """获取操作日志列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    keyword = request.args.get('keyword', '', type=str).strip()
    log_type = request.args.get('type', '', type=str).strip()
    date_from = request.args.get('date_from', '', type=str).strip()
    date_to = request.args.get('date_to', '', type=str).strip()

    query = WorkloadOperationLog.query

    # 关键字搜索（操作内容）
    if keyword:
        query = query.filter(WorkloadOperationLog.detail.contains(keyword))

    # 按类型筛选
    if log_type:
        query = query.filter(WorkloadOperationLog.log_type == log_type)

    # 按日期筛选
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(WorkloadOperationLog.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(WorkloadOperationLog.created_at < dt)
        except ValueError:
            pass

    # 分页
    pagination = query.order_by(WorkloadOperationLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    logs = [log.to_dict() for log in pagination.items]

    return jsonify({
        'success': True,
        'data': {
            'logs': logs,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@operation_log_bp.route('/api/operation-logs/stats', methods=['GET'])
def get_operation_log_stats():
    """获取操作日志统计"""
    from sqlalchemy import func

    # 总数
    total = WorkloadOperationLog.query.count()

    # 最近24小时
    since_24h = datetime.utcnow() - timedelta(hours=24)
    recent_count = WorkloadOperationLog.query.filter(
        WorkloadOperationLog.created_at >= since_24h
    ).count()

    # 按类型统计
    type_stats = db.session.query(
        WorkloadOperationLog.log_type,
        func.count(WorkloadOperationLog.id)
    ).group_by(WorkloadOperationLog.log_type).all()

    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'recent_24h': recent_count,
            'by_type': {t: c for t, c in type_stats}
        }
    })


@operation_log_bp.route('/api/operation-logs/cleanup', methods=['POST'])
def cleanup_operation_logs():
    """清理旧的操作日志"""
    data = request.get_json() or {}
    days = data.get('days', 90)
    password = data.get('password', '')

    # 验证密码
    from app.models import WorkloadSettings
    setting = WorkloadSettings.query.filter_by(setting_key='settings_password').first()
    if setting and setting.setting_value:
        if password != setting.setting_value:
            return jsonify({'success': False, 'error': '密码错误'}), 403

    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = WorkloadOperationLog.query.filter(
        WorkloadOperationLog.created_at < cutoff
    ).delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'已清理 {deleted} 条 {days} 天前的操作日志'
    })


def log_operation(log_type, detail, operator=None):
    """记录操作日志的辅助函数
    
    Args:
        log_type: 操作类型 (create/update/delete/import/export/backup/restore/setting/other)
        detail: 操作详情描述
        operator: 操作人（可选）
    """
    try:
        log = WorkloadOperationLog(
            log_type=log_type,
            detail=detail,
            operator=operator or '系统'
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
