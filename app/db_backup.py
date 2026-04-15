# -*- coding: utf-8 -*-
"""
数据库自动备份模块
- 定时备份 SQLite 数据库文件到 backups/ 目录
- 支持备份保留数量轮转
- 提供 API 查询/下载/手动触发备份
"""

import os
import shutil
import time
import threading
import json
from datetime import datetime
from flask import jsonify, request, send_file

# 全局变量
_backup_thread = None
_backup_running = False
_backup_interval_hours = 24  # 默认每24小时备份一次
_backup_keep_count = 30      # 默认保留30个备份


def get_backup_dir(base_path):
    """获取备份目录路径"""
    backup_dir = os.path.join(base_path, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def get_db_path(base_path):
    """获取数据库文件路径"""
    return os.path.join(base_path, 'instance', 'workload.db')


def create_backup(base_path, note=''):
    """
    执行一次数据库备份
    返回: (success: bool, info: dict)
    """
    db_path = get_db_path(base_path)
    backup_dir = get_backup_dir(base_path)

    if not os.path.exists(db_path):
        return False, {'error': '数据库文件不存在'}

    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'workload_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)

        # 复制数据库文件（SQLite安全复制方式）
        shutil.copy2(db_path, backup_path)

        # 获取文件大小
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)

        # 写入备份元信息
        meta = {
            'timestamp': datetime.now().isoformat(),
            'filename': backup_filename,
            'size_mb': round(size_mb, 2),
            'note': note,
            'source_db': db_path
        }
        meta_path = os.path.join(backup_dir, f'{backup_filename}.meta')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # 清理旧备份（轮转）
        rotate_backups(backup_dir)

        print(f"[备份] 创建成功: {backup_filename} ({size_mb:.2f} MB)")
        return True, {
            'filename': backup_filename,
            'size_mb': round(size_mb, 2),
            'timestamp': datetime.now().isoformat(),
            'note': note
        }
    except Exception as e:
        print(f"[备份] 创建失败: {e}")
        return False, {'error': str(e)}


def rotate_backups(backup_dir, keep_count=None):
    """
    清理旧备份，只保留最近的 keep_count 个
    """
    if keep_count is None:
        keep_count = _backup_keep_count

    # 找出所有 .db 文件（排除 .db.meta）
    backups = []
    for f in os.listdir(backup_dir):
        if f.endswith('.db') and not f.endswith('.meta'):
            full_path = os.path.join(backup_dir, f)
            backups.append((full_path, os.path.getmtime(full_path)))

    # 按修改时间排序（新的在前）
    backups.sort(key=lambda x: x[1], reverse=True)

    # 删除超出保留数量的旧备份
    if len(backups) > keep_count:
        for path, _ in backups[keep_count:]:
            try:
                # 同时删除 .meta 文件
                if os.path.exists(path + '.meta'):
                    os.remove(path + '.meta')
                os.remove(path)
                print(f"[备份] 已清理旧备份: {os.path.basename(path)}")
            except Exception as e:
                print(f"[备份] 清理失败: {e}")


def list_backups(base_path):
    """列出所有备份文件"""
    backup_dir = get_backup_dir(base_path)
    backups = []

    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith('.db') and not f.endswith('.meta'):
            full_path = os.path.join(backup_dir, f)
            meta_path = full_path + '.meta'

            info = {
                'filename': f,
                'size_mb': round(os.path.getsize(full_path) / (1024 * 1024), 2),
                'mtime': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
                'note': ''
            }

            # 读取元信息
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as mf:
                        meta = json.load(mf)
                        info['note'] = meta.get('note', '')
                        info['timestamp'] = meta.get('timestamp', info['mtime'])
                except:
                    pass

            backups.append(info)

    return backups


def get_backup_info(base_path):
    """获取备份状态摘要"""
    backup_dir = get_backup_dir(base_path)
    backups = list_backups(base_path)
    db_path = get_db_path(base_path)

    db_size = 0
    if os.path.exists(db_path):
        db_size = round(os.path.getsize(db_path) / (1024 * 1024), 2)

    return {
        'db_size_mb': db_size,
        'backup_count': len(backups),
        'last_backup': backups[0]['timestamp'] if backups else None,
        'interval_hours': _backup_interval_hours,
        'keep_count': _backup_keep_count,
        'auto_backup_running': _backup_running
    }


# ============================================================
# 后台自动备份线程
# ============================================================

def _auto_backup_loop(base_path):
    """后台线程：定时执行自动备份"""
    global _backup_running
    _backup_running = True

    print(f"[备份] 自动备份已启动，间隔: {_backup_interval_hours} 小时，保留: {_backup_keep_count} 个")

    while _backup_running:
        # 等待指定小时数（每分钟检查一次是否需要停止）
        for _ in range(_backup_interval_hours * 60):
            if not _backup_running:
                break
            time.sleep(60)

        if not _backup_running:
            break

        # 执行备份
        try:
            success, info = create_backup(base_path, note='自动备份')
            if not success:
                print(f"[备份] 自动备份失败: {info.get('error', '未知错误')}")
        except Exception as e:
            print(f"[备份] 自动备份异常: {e}")

    _backup_running = False
    print("[备份] 自动备份线程已停止")


def start_auto_backup(base_path, interval_hours=24, keep_count=30):
    """
    启动后台自动备份线程
    interval_hours: 备份间隔（小时），默认24
    keep_count: 保留备份数量，默认30
    """
    global _backup_thread, _backup_interval_hours, _backup_keep_count, _backup_running

    _backup_interval_hours = interval_hours
    _backup_keep_count = keep_count

    if _backup_thread and _backup_thread.is_alive():
        print("[备份] 自动备份已在运行中")
        return

    _backup_thread = threading.Thread(
        target=_auto_backup_loop,
        args=(base_path,),
        daemon=True
    )
    _backup_thread.start()


def stop_auto_backup():
    """停止自动备份线程"""
    global _backup_running
    _backup_running = False


# ============================================================
# Flask API 路由
# ============================================================

def register_backup_routes(app, base_path):
    """注册备份相关的API路由"""

    @app.route('/api/backup/db/status', methods=['GET'])
    def backup_status():
        """获取备份状态"""
        return jsonify({'success': True, 'data': get_backup_info(base_path)})

    @app.route('/api/backup/db/list', methods=['GET'])
    def backup_list():
        """列出所有备份"""
        backups = list_backups(base_path)
        return jsonify({'success': True, 'data': backups})

    @app.route('/api/backup/db/create', methods=['POST'])
    def backup_create():
        """手动创建备份"""
        data = request.get_json() or {}
        note = data.get('note', '手动备份')
        success, info = create_backup(base_path, note=note)
        if success:
            return jsonify({'success': True, 'data': info})
        else:
            return jsonify({'success': False, 'error': info.get('error', '备份失败')}), 500

    @app.route('/api/backup/db/download/<filename>', methods=['GET'])
    def backup_download(filename):
        """下载备份文件"""
    # 安全检查：防止路径穿越
        safe_name = os.path.basename(filename)
        if not safe_name.endswith('.db'):
            return jsonify({'success': False, 'error': '无效的文件名'}), 400

        backup_dir = get_backup_dir(base_path)
        file_path = os.path.join(backup_dir, safe_name)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=safe_name,
            mimetype='application/octet-stream'
        )

    @app.route('/api/backup/db/delete/<filename>', methods=['DELETE'])
    def backup_delete(filename):
        """删除备份文件"""
        safe_name = os.path.basename(filename)
        if not safe_name.endswith('.db'):
            return jsonify({'success': False, 'error': '无效的文件名'}), 400

        backup_dir = get_backup_dir(base_path)
        file_path = os.path.join(backup_dir, safe_name)
        meta_path = file_path + '.meta'

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)
            return jsonify({'success': True, 'message': '删除成功'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/backup/db/restore/<filename>', methods=['POST'])
    def backup_restore_db(filename):
        """从备份恢复数据库（危险操作！）"""
        safe_name = os.path.basename(filename)
        if not safe_name.endswith('.db'):
            return jsonify({'success': False, 'error': '无效的文件名'}), 400

        backup_dir = get_backup_dir(base_path)
        backup_path = os.path.join(backup_dir, safe_name)
        db_path = get_db_path(base_path)

        if not os.path.exists(backup_path):
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404

        try:
            # 先把当前数据库备份为安全副本
            safety_copy = db_path + '.pre_restore'
            if os.path.exists(db_path):
                shutil.copy2(db_path, safety_copy)

            # 从备份恢复
            shutil.copy2(backup_path, db_path)

            print(f"[备份] 已从 {safe_name} 恢复数据库")
            return jsonify({
                'success': True,
                'message': f'已从备份 {safe_name} 恢复数据库',
                'safety_copy': safety_copy
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    print("[备份] API路由已注册: /api/backup/db/*")
