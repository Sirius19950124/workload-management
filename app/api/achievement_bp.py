# -*- coding: utf-8 -*-
"""
成就徽章系统 API
"""

from flask import Blueprint, request, jsonify
from datetime import date, timedelta
from app import db
from app.models import (
    Achievement, TherapistAchievement, TherapistStats,
    WorkloadTherapist, WorkloadRecord, DEFAULT_ACHIEVEMENTS
)

achievement_bp = Blueprint('achievement', __name__, url_prefix='/api/achievements')


def init_default_achievements():
    """初始化默认成就"""
    for ach_data in DEFAULT_ACHIEVEMENTS:
        existing = Achievement.query.filter_by(code=ach_data['code']).first()
        if not existing:
            achievement = Achievement(**ach_data)
            db.session.add(achievement)
    db.session.commit()


def get_or_create_therapist_stats(therapist_id):
    """获取或创建治疗师统计数据"""
    stats = TherapistStats.query.filter_by(therapist_id=therapist_id).first()
    if not stats:
        stats = TherapistStats(therapist_id=therapist_id)
        db.session.add(stats)
        db.session.commit()
    return stats


def update_therapist_stats(therapist_id):
    """更新治疗师统计数据"""
    stats = get_or_create_therapist_stats(therapist_id)

    # 计算累计数据
    records = WorkloadRecord.query.filter_by(therapist_id=therapist_id).all()
    stats.total_sessions = sum(r.session_count for r in records)
    stats.total_workload = sum(r.weighted_workload for r in records)

    # 计算累计积分 (工作量 * 0.1 = 积分)
    stats.total_points = int(stats.total_workload * 0.1)

    # 计算连续打卡
    dates = sorted(set(r.record_date for r in records), reverse=True)
    if dates:
        stats.last_record_date = dates[0]

        # 计算连续天数
        streak = 0
        today = date.today()
        for i, d in enumerate(dates):
            expected_date = today - timedelta(days=i)
            if d == expected_date:
                streak += 1
            else:
                break
        stats.current_streak = streak
        stats.longest_streak = max(stats.longest_streak, streak)

    # 计算等级
    level, progress = stats.calculate_level()
    stats.current_level = level
    stats.level_progress = progress

    # 计算成就数量
    stats.achievements_count = TherapistAchievement.query.filter_by(therapist_id=therapist_id).count()

    db.session.commit()
    return stats


def check_and_award_achievements(therapist_id):
    """检查并授予成就"""
    stats = get_or_create_therapist_stats(therapist_id)
    new_achievements = []

    # 获取所有激活的成就
    achievements = Achievement.query.filter_by(is_active=True).all()

    for ach in achievements:
        # 检查是否已获得
        existing = TherapistAchievement.query.filter_by(
            therapist_id=therapist_id,
            achievement_id=ach.id
        ).first()
        if existing:
            continue

        # 检查条件
        unlocked = False
        if ach.condition_type == 'total_sessions':
            unlocked = stats.total_sessions >= ach.condition_value
        elif ach.condition_type == 'total_workload':
            unlocked = stats.total_workload >= ach.condition_value
        elif ach.condition_type == 'streak_days':
            unlocked = stats.current_streak >= ach.condition_value
        elif ach.condition_type == 'daily_workload':
            # 检查今日工作量
            today = date.today()
            today_workload = db.session.query(
                db.func.sum(WorkloadRecord.weighted_workload)
            ).filter(
                WorkloadRecord.therapist_id == therapist_id,
                WorkloadRecord.record_date == today
            ).scalar() or 0
            unlocked = today_workload >= ach.condition_value

        if unlocked:
            # 授予成就
            therapist_ach = TherapistAchievement(
                therapist_id=therapist_id,
                achievement_id=ach.id
            )
            db.session.add(therapist_ach)

            # 增加积分
            stats.total_points += ach.points_reward

            new_achievements.append(ach.to_dict())

    db.session.commit()

    # 更新统计
    if new_achievements:
        update_therapist_stats(therapist_id)

    return new_achievements


# ===================== API 端点 =====================

@achievement_bp.route('/', methods=['GET'])
def get_all_achievements():
    """获取所有成就列表"""
    achievements = Achievement.query.filter_by(is_active=True).order_by(Achievement.sort_order, Achievement.id).all()
    return jsonify({
        'success': True,
        'data': {
            'achievements': [a.to_dict() for a in achievements],
            'total': len(achievements)
        }
    })


@achievement_bp.route('/therapist/<int:therapist_id>', methods=['GET'])
def get_therapist_achievements(therapist_id):
    """获取治疗师已获得的成就"""
    therapist_achievements = TherapistAchievement.query.filter_by(therapist_id=therapist_id).all()

    # 获取所有成就用于显示未获得状态
    all_achievements = Achievement.query.filter_by(is_active=True).all()
    unlocked_ids = {ta.achievement_id for ta in therapist_achievements}

    result = []
    for ach in all_achievements:
        ach_dict = ach.to_dict()
        ach_dict['unlocked'] = ach.id in unlocked_ids
        if ach.id in unlocked_ids:
            ta = next(ta for ta in therapist_achievements if ta.achievement_id == ach.id)
            ach_dict['unlocked_at'] = ta.unlocked_at.isoformat() if ta.unlocked_at else None
        result.append(ach_dict)

    return jsonify({
        'success': True,
        'data': {
            'achievements': result,
            'unlocked_count': len(unlocked_ids),
            'total_count': len(all_achievements)
        }
    })


@achievement_bp.route('/therapist/<int:therapist_id>/stats', methods=['GET'])
def get_therapist_stats_api(therapist_id):
    """获取治疗师游戏化统计"""
    stats = get_or_create_therapist_stats(therapist_id)
    therapist = WorkloadTherapist.query.get(therapist_id)

    return jsonify({
        'success': True,
        'data': {
            'therapist': therapist.to_dict() if therapist else None,
            'stats': stats.to_dict(),
            'level_name': TherapistStats.get_level_name(stats.current_level),
            'level_badge': TherapistStats.get_level_badge(stats.current_level)
        }
    })


@achievement_bp.route('/therapist/<int:therapist_id>/check', methods=['POST'])
def check_achievements(therapist_id):
    """检查是否解锁新成就（登记后调用）"""
    # 先更新统计
    update_therapist_stats(therapist_id)

    # 检查成就
    new_achievements = check_and_award_achievements(therapist_id)

    return jsonify({
        'success': True,
        'message': f'恭喜解锁 {len(new_achievements)} 个新成就！' if new_achievements else '暂无新成就',
        'data': {
            'new_achievements': new_achievements,
            'has_new': len(new_achievements) > 0
        }
    })


@achievement_bp.route('/leaderboard/level', methods=['GET'])
def get_level_leaderboard():
    """等级排行榜"""
    limit = request.args.get('limit', 10, type=int)

    # ✅ 修复：在返回排行榜前，自动更新所有激活治疗师的统计数据
    # 检查是否有 refresh 参数，默认为 true（实时刷新）
    should_refresh = request.args.get('refresh', 'true').lower() == 'true'

    if should_refresh:
        try:
            therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
            for therapist in therapists:
                update_therapist_stats(therapist.id)
                check_and_award_achievements(therapist.id)
            db.session.commit()
        except Exception as e:
            # 即使更新失败也继续返回现有数据
            print(f"[警告] 更新统计数据失败: {e}")

    stats_list = TherapistStats.query.order_by(
        TherapistStats.current_level.desc(),
        TherapistStats.total_points.desc()
    ).limit(limit).all()

    result = []
    for i, stats in enumerate(stats_list, 1):
        therapist = WorkloadTherapist.query.get(stats.therapist_id)
        if therapist and therapist.is_active:
            # 获取该治疗师已获得的成就
            therapist_achievements = TherapistAchievement.query.filter_by(
                therapist_id=stats.therapist_id
            ).all()
            unlocked_achievement_ids = [ta.achievement_id for ta in therapist_achievements]

            # 获取成就详情
            achievements_detail = []
            for ta in therapist_achievements:
                ach = Achievement.query.get(ta.achievement_id)
                if ach:
                    achievements_detail.append({
                        'id': ach.id,
                        'code': ach.code,
                        'name': ach.name,
                        'icon': ach.icon,
                        'unlocked_at': ta.unlocked_at.isoformat() if ta.unlocked_at else None
                    })

            result.append({
                'rank': i,
                'therapist_id': stats.therapist_id,
                'therapist_name': therapist.name,
                'level': stats.current_level,
                'level_name': TherapistStats.get_level_name(stats.current_level),
                'level_badge': TherapistStats.get_level_badge(stats.current_level),
                'total_points': stats.total_points,
                'achievements_count': stats.achievements_count,
                'achievements': achievements_detail  # 添加成就列表
            })

    return jsonify({
        'success': True,
        'data': {
            'leaderboard': result,
            'total': len(result)
        }
    })


@achievement_bp.route('/leaderboard/streak', methods=['GET'])
def get_streak_leaderboard():
    """连续打卡排行榜"""
    limit = request.args.get('limit', 10, type=int)

    # ✅ 修复：在返回排行榜前，自动更新所有激活治疗师的统计数据
    # 检查是否有 refresh 参数，默认为 true（实时刷新）
    should_refresh = request.args.get('refresh', 'true').lower() == 'true'

    if should_refresh:
        try:
            therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
            for therapist in therapists:
                update_therapist_stats(therapist.id)
            db.session.commit()
        except Exception as e:
            # 即使更新失败也继续返回现有数据
            print(f"[警告] 更新统计数据失败: {e}")

    stats_list = TherapistStats.query.order_by(
        TherapistStats.current_streak.desc()
    ).limit(limit).all()

    result = []
    for i, stats in enumerate(stats_list, 1):
        therapist = WorkloadTherapist.query.get(stats.therapist_id)
        if therapist and therapist.is_active and stats.current_streak > 0:
            result.append({
                'rank': i,
                'therapist_id': stats.therapist_id,
                'therapist_name': therapist.name,
                'current_streak': stats.current_streak,
                'longest_streak': stats.longest_streak,
                'last_record_date': stats.last_record_date.isoformat() if stats.last_record_date else None
            })

    return jsonify({
        'success': True,
        'data': {
            'leaderboard': result,
            'total': len(result)
        }
    })


@achievement_bp.route('/init', methods=['POST'])
def init_achievements():
    """初始化默认成就（管理员）"""
    init_default_achievements()
    return jsonify({
        'success': True,
        'message': '成就初始化完成'
    })


@achievement_bp.route('/recalculate/<int:therapist_id>', methods=['POST'])
def recalculate_stats(therapist_id):
    """重新计算治疗师统计"""
    update_therapist_stats(therapist_id)
    new_achievements = check_and_award_achievements(therapist_id)

    return jsonify({
        'success': True,
        'message': '统计已重新计算',
        'data': {
            'new_achievements': new_achievements
        }
    })


@achievement_bp.route('/recalculate-all', methods=['POST'])
def recalculate_all_stats():
    """重新计算所有治疗师统计"""
    therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
    total_new = 0

    for therapist in therapists:
        update_therapist_stats(therapist.id)
        new = check_and_award_achievements(therapist.id)
        total_new += len(new)

    return jsonify({
        'success': True,
        'message': f'所有统计已重新计算，共解锁 {total_new} 个新成就',
        'data': {
            'total_new_achievements': total_new,
            'therapists_count': len(therapists)
        }
    })
