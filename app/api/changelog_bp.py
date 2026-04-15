# -*- coding: utf-8 -*-
"""更新日志 API — 支持手动条目 + Git自动生成"""

import os
import subprocess
from collections import OrderedDict
from flask import Blueprint, request, jsonify, current_app

changelog_bp = Blueprint('changelog', __name__)

# 手动维护的版本记录（重要版本的手动描述）
CHANGELOG_MANUAL = [
    {
        "version": "1.5",
        "date": "2026-04-13",
        "title": "系统更名 + 题库批量删除 + 体验优化",
        "changes": [
            "系统更名为：惠阳妇幼保健院康复科业务管理系统",
            "UI主题升级为玻璃拟态风格（粉紫渐变+毛玻璃效果）",
            "题库管理新增批量删除功能（checkbox勾选 + 全选/批量删除按钮）",
            "保存记录时去掉confirm弹框，改为右侧toast横幅提示",
            "修复服务崩溃：cos_backup.py参数不匹配、数据库权限、DateTime残留数据",
            "更新日志支持git log自动生成（手动条目+自动合并）",
            "统一操作日志装饰器，覆盖dept_stats/rating/achievement/excel等模块"
        ]
    },
    {
        "version": "1.4",
        "date": "2026-04-12",
        "title": "多项Bug修复 + 考试模块增强",
        "changes": [
            "修复4个录入模态框打开时自动填充历史数据的问题（门诊/病房/儿童医生/儿童月度）",
            "修复儿童医生导入Excel人次数为0时跳过多月份的bug",
            "转介统计：支持多月份导入、按科室分组显示、可在线编辑保存/删除",
            "答题记录删除：新增密码确认机制，支持单条/批量删除",
            "考试模块：试卷密码删除、批量取消分配、题目勾选框修复、已关闭试卷可恢复发布",
            "后端数据校验优化：支持0值导入（is not None替代真值检查）",
            "通用组件：escAttr防XSS、showModal/hideModal弹窗框架"
        ]
    },
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


def _get_git_root():
    """查找git仓库根目录"""
    # 尝试从 app root_path 向上找
    start = current_app.root_path if current_app else os.getcwd()
    path = start
    while path != os.path.dirname(path):
        if os.path.isdir(os.path.join(path, '.git')):
            return path
        path = os.path.dirname(path)
    return None


def get_git_changelog(max_commits=50):
    """从git log解析commit历史，转为changelog格式

    Returns:
        list[dict]: 按日期分组的changelog条目，每项包含 version/date/title/changes
    """
    git_root = _get_git_root()
    if not git_root:
        return []

    try:
        result = subprocess.run(
            ['git', 'log', f'-{max_commits}', '--pretty=format:%H|%s|%ai|%b'],
            capture_output=True, cwd=git_root,
            timeout=10, encoding='utf-8', errors='replace'
        )
        stdout = result.stdout or ''
        if result.returncode != 0 or not stdout.strip():
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    # 按日期分组
    date_groups = OrderedDict()
    for line in result.stdout.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split('|', 3)
        if len(parts) < 3:
            continue
        _hash, msg, date_str = parts[0], parts[1], parts[2]
        # 取日期部分 YYYY-MM-DD
        day = date_str.split()[0] if date_str else 'unknown'

        # 解析 commit message 前缀作为类型提示
        prefix = ''
        if ':' in msg:
            prefix = msg.split(':', 1)[0].strip()

        if day not in date_groups:
            date_groups[day] = {'commits': [], 'prefixes': set()}
        date_groups[day]['commits'].append({
            'hash': _hash[:8],
            'msg': msg.strip(),
            'prefix': prefix
        })
        if prefix:
            date_groups[day]['prefixes'].add(prefix)

    # 转为changelog格式
    entries = []
    for day, group in date_groups.items():
        commits = group['commits']
        prefixes = group['prefixes']

        # 生成标题关键词
        type_labels = {'feat': '新功能', 'fix': '修复', 'refactor': '重构'}
        title_parts = [type_labels.get(p, p) for p in sorted(prefixes) if p in type_labels]
        title = ' + '.join(title_parts) if title_parts else '更新'

        entry = {
            'version': f'git-{day}',
            'date': day,
            'title': f'{title} ({len(commits)}个提交)',
            'changes': [c['msg'] for c in commits]
        }
        entries.append(entry)

    return entries


@changelog_bp.route('/api/changelog')
def get_changelog():
    """获取更新日志（支持source参数）

    参数:
        source: all(默认)|manual|git
    """
    source = request.args.get('source', 'all').strip()

    if source == 'manual':
        return jsonify({'success': True, 'data': CHANGELOG_MANUAL})

    if source == 'git':
        git_entries = get_git_changelog()
        return jsonify({'success': True, 'data': git_entries})

    # 默认 all: 合并手动+自动
    result = list(CHANGELOG_MANUAL)  # 手动条目在前

    # 收集手动条目已覆盖的日期
    manual_dates = {e['date'] for e in CHANGELOG_MANUAL}

    # 追加git条目（跳过已覆盖的日期）
    git_entries = get_git_changelog()
    for entry in git_entries:
        if entry['date'] not in manual_dates:
            result.append(entry)

    return jsonify({'success': True, 'data': result})
