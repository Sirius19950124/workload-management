# -*- coding: utf-8 -*-
"""更新日志 API"""

from flask import Blueprint, jsonify
from datetime import datetime

changelog_bp = Blueprint('changelog', __name__)

CHANGELOG = [
    {
        "version": "1.3",
        "date": "2026-04-06",
        "title": "治疗项目统计优化",
        "changes": [
            "治疗项目排名列表完整展示，不再需要滚动",
            "修复若干界面显示问题"
        ]
    },
    {
        "version": "1.2",
        "date": "2026-03-23",
        "title": "评价系统 + 成就徽章",
        "changes": [
            "新增治疗项目统计：日期范围查询、柱状图、饼图、导出Excel",
            "新增按治疗项目查询患者：支持最少治疗次数过滤",
            "新增成就徽章系统：Win7兼容、排行榜、多维度评价"
        ]
    },
    {
        "version": "1.1",
        "date": "2026-03-15",
        "title": "每日多次治疗 + 评价系统",
        "changes": [
            "支持每日多次治疗的确认机制",
            "新增治疗师多维度评价功能",
            "修复设置功能开关不生效的问题"
        ]
    },
    {
        "version": "1.0",
        "date": "2026-02-20",
        "title": "系统上线",
        "changes": [
            "基础工作量登记与查询",
            "月度汇总统计",
            "Excel导入导出",
            "重复录入检测"
        ]
    }
]


@changelog_bp.route('/api/changelog')
def get_changelog():
    """获取更新日志"""
    return jsonify({"success": True, "data": CHANGELOG})
