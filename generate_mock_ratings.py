# -*- coding: utf-8 -*-
"""
生成模拟评价数据（用于测试评价统计和图表）
运行后可通过 workload_management.exe 的「评价管理」Tab 查看效果
"""

import sys
import os
import random
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    WorkloadTherapist, WorkloadTreatmentItem, Patient,
    Rating, RatingAnswer, RatingQuestion
)

def generate_mock_ratings():
    app = create_app()

    with app.app_context():
        # 获取现有数据
        therapists = WorkloadTherapist.query.filter_by(is_active=True).all()
        items = WorkloadTreatmentItem.query.filter_by(is_active=True).all()
        patients = Patient.query.filter_by(status='active').all()
        questions = RatingQuestion.query.filter_by(is_active=True).order_by(RatingQuestion.sort_order).all()

        if not therapists:
            print("[错误] 没有治疗师数据，请先在系统中添加治疗师")
            return
        if not patients:
            print("[错误] 没有患者数据，请先在系统中添加患者")
            return

        # 如果没有患者，创建一些模拟患者
        if len(patients) < 5:
            mock_names = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十',
                          '郑十一', '冯十二', '陈十三', '褚十四', '卫十五', '蒋十六']
            for name in mock_names:
                existing = Patient.query.filter_by(name=name).first()
                if not existing:
                    p = Patient(
                        name=name,
                        phone=f'138{random.randint(10000000, 99999999)}',
                        diagnosis='颈椎病',
                        primary_therapist_id=random.choice(therapists).id,
                        status='active'
                    )
                    db.session.add(p)
            db.session.commit()
            patients = Patient.query.filter_by(status='active').all()

        print(f"[数据] 治疗师: {len(therapists)} 人")
        print(f"[数据] 治疗项目: {len(items)} 个")
        print(f"[数据] 患者: {len(patients)} 人")
        print(f"[数据] 问卷题目: {len(questions)} 道")

        # 清除旧的评价数据
        old_count = Rating.query.count()
        if old_count > 0:
            print(f"\n[清理] 清除旧评价数据: {old_count} 条")
            RatingAnswer.query.delete()
            Rating.query.delete()
            db.session.commit()

        # 生成评价数据
        total = 0
        now = datetime.utcnow()

        # 生成最近 90 天的数据
        for days_ago in range(90):
            date = now - timedelta(days=days_ago)
            # 每天随机 1-5 条评价
            daily_count = random.randint(1, 5)
            for _ in range(daily_count):
                patient = random.choice(patients)
                therapist = random.choice(therapists)
                item = random.choice(items) if items else None

                # 生成星级评分（偏向高分，模拟真实场景）
                star_weights = [0.05, 0.08, 0.15, 0.32, 0.40]  # 1-5星概率
                star = random.choices([1, 2, 3, 4, 5], weights=star_weights, k=1)[0]

                # 评价内容（有 40% 概率有文字反馈）
                comments = [
                    '服务很好，治疗师很专业！', '态度非常好，效果也不错',
                    '环境整洁，服务态度好', '治疗过程很舒适',
                    '效果明显，推荐！', '非常满意，下次还来',
                    '技术娴熟，体验不错', '整体感觉很棒',
                    '态度一般般', '等待时间有点长',
                    '治疗效果还需要观察', '服务态度很好但效果一般',
                    '很专业的治疗师', '手法到位，点赞',
                    '', '', '', '', '',  # 很多时候不写
                ]
                comment = random.choice(comments)

                # 标签
                all_tags = ['服务好', '效果好', '态度好', '专业', '推荐', '耐心', '环境好']
                tags = random.sample(all_tags, k=random.randint(0, 3))

                # 创建评价
                rating = Rating(
                    patient_id=patient.id,
                    therapist_id=therapist.id,
                    treatment_item_id=item.id if item else None,
                    star_rating=star,
                    comment=comment,
                    tags=','.join(tags) if tags else '',
                    created_at=date + timedelta(
                        hours=random.randint(8, 17),
                        minutes=random.randint(0, 59)
                    )
                )
                db.session.add(rating)
                db.session.flush()  # 获取 rating.id

                # 为每道题目生成答案
                for q in questions:
                    if q.question_type == 'star':
                        # 每道星题独立评分，略有差异
                        q_star = max(1, min(5, star + random.choice([-1, 0, 0, 0, 1])))
                        answer = RatingAnswer(
                            rating_id=rating.id,
                            question_id=q.id,
                            answer_value=str(q_star)
                        )
                    elif q.question_type == 'radio':
                        # 80% 愿意，20% 暂不考虑
                        options = ['愿意', '暂不考虑']
                        answer_val = random.choices(options, weights=[80, 20], k=1)[0]
                        answer = RatingAnswer(
                            rating_id=rating.id,
                            question_id=q.id,
                            answer_value=answer_val
                        )
                    elif q.question_type == 'text':
                        # 50% 概率有文字
                        text_answers = [
                            '希望环境能更好一些', '总体很满意',
                            '治疗师很耐心', '', '', ''
                        ]
                        answer = RatingAnswer(
                            rating_id=rating.id,
                            question_id=q.id,
                            answer_value=random.choice(text_answers)
                        )
                    else:
                        continue

                    if answer:
                        db.session.add(answer)

                total += 1

        db.session.commit()

        print(f"\n[完成] 成功生成 {total} 条模拟评价数据")
        print(f"[提示] 打开系统 → 评价管理 → 评价统计，查看图表效果")


if __name__ == '__main__':
    generate_mock_ratings()
