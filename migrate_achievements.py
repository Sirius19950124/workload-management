# -*- coding: utf-8 -*-
"""
成就系统数据库迁移脚本
添加 Achievement, TherapistAchievement, TherapistStats 表
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Achievement, DEFAULT_ACHIEVEMENTS

def migrate():
    """执行数据库迁移"""
    app = create_app()

    with app.app_context():
        print("开始成就系统数据库迁移...")

        # 创建新表
        print("1. 创建成就相关表...")
        try:
            # 导入模型以确保表定义被加载
            from app.models import Achievement, TherapistAchievement, TherapistStats

            # 创建表
            db.create_all()
            print("   ✓ 表创建成功")
        except Exception as e:
            print(f"   ✗ 表创建失败: {e}")
            return False

        # 初始化默认成就
        print("2. 初始化默认成就...")
        try:
            existing_count = Achievement.query.count()
            if existing_count > 0:
                print(f"   ✓ 已存在 {existing_count} 个成就，跳过初始化")
            else:
                for ach_data in DEFAULT_ACHIEVEMENTS:
                    achievement = Achievement(**ach_data)
                    db.session.add(achievement)
                db.session.commit()
                print(f"   ✓ 成功创建 {len(DEFAULT_ACHIEVEMENTS)} 个默认成就")
        except Exception as e:
            db.session.rollback()
            print(f"   ✗ 成就初始化失败: {e}")
            return False

        # 为现有治疗师创建统计数据
        print("3. 初始化治疗师统计数据...")
        try:
            from app.models import WorkloadTherapist, TherapistStats, WorkloadRecord
            from datetime import date, timedelta

            therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
            created = 0

            for therapist in therapists:
                # 检查是否已有统计记录
                existing = TherapistStats.query.filter_by(therapist_id=therapist.id).first()
                if existing:
                    continue

                # 创建统计记录
                stats = TherapistStats(therapist_id=therapist.id)

                # 计算累计数据
                records = WorkloadRecord.query.filter_by(therapist_id=therapist.id).all()
                stats.total_sessions = sum(r.session_count for r in records)
                stats.total_workload = sum(r.weighted_workload for r in records)

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

                db.session.add(stats)
                created += 1

            db.session.commit()
            print(f"   ✓ 成功创建 {created} 个治疗师统计记录")
        except Exception as e:
            db.session.rollback()
            print(f"   ✗ 统计数据初始化失败: {e}")
            return False

        print("\n迁移完成！")
        print("=" * 50)
        print("新增表:")
        print("  - achievements (成就定义表)")
        print("  - therapist_achievements (治疗师成就记录)")
        print("  - therapist_stats (治疗师统计数据)")
        print("=" * 50)
        print(f"默认成就: {len(DEFAULT_ACHIEVEMENTS)} 个")
        print("=" * 50)

        return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
