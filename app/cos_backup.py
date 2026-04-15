# -*- coding: utf-8 -*-
"""
腾讯云 COS 自动备份模块
- 将 SQLite 数据库自动上传到 COS 对象存储
- 容器销毁/重建后数据依然安全
- 支持本地+COS双重备份

使用前需要：
1. 腾讯云控制台创建存储桶（Bucket）
2. 获取 SecretId 和 SecretKey
3. 设置环境变量或修改下方配置
"""

import os
import time
import threading
from datetime import datetime
from flask import jsonify, request

# ============================================================
# 配置（优先从环境变量读取，方便Docker部署时设置）
# ============================================================
COS_CONFIG = {
    'enabled': False,  # 是否启用COS备份，设为True并填写下面的信息
    'secret_id': os.environ.get('COS_SECRET_ID', ''),
    'secret_key': os.environ.get('COS_SECRET_KEY', ''),
    'region': os.environ.get('COS_REGION', 'ap-shanghai'),       # 存储桶地域，如 ap-shanghai/ap-guangzhou
    'bucket': os.environ.get('COS_BUCKET', ''),                   # 存储桶名称，如 workload-backup-1234567890
    'prefix': os.environ.get('COS_PREFIX', 'db-backups/'),        # 对象键前缀
    'interval_hours': int(os.environ.get('COS_BACKUP_INTERVAL', '24')),  # 上传间隔(小时)
    'keep_count': int(os.environ.get('COS_KEEP_COUNT', '30')),           # COS上保留数量
}

_cos_thread = None
_cos_running = False


def is_configured():
    """检查COS是否已正确配置"""
    c = COS_CONFIG
    return bool(
        c['enabled'] and
        c['secret_id'] and
        c['secret_key'] and
        c['bucket']
    )


def _get_cos_client():
    """延迟导入cos SDK（避免没安装时报错）"""
    try:
        from qcloud_cos import CosConfig, CosS3Client
        conf = CosConfig(
            Region=COS_CONFIG['region'],
            SecretId=COS_CONFIG['secret_id'],
            SecretKey=COS_CONFIG['secret_key'],
        )
        return CosS3Client(conf)
    except ImportError:
        print("[COS] 警告：未安装 cos-sdk，请运行 pip install cos-python-sdk-v5")
        return None
    except Exception as e:
        print(f"[COS] 客户端创建失败: {e}")
        return None


def upload_to_cos(local_path, remote_name):
    """
    上传文件到COS
    返回: (success, url_or_error)
    """
    client = _get_cos_client()
    if not client:
        return False, 'COS客户端不可用'

    key = COS_CONFIG['prefix'] + remote_name

    try:
        client.upload_file(
            Bucket=COS_CONFIG['bucket'],
            LocalFilePath=local_path,
            Key=key,
        )
        # 构建下载URL
        url = f"https://{COS_CONFIG['bucket']}.cos.{COS_CONFIG['region']}.myqcloud.com/{key}"
        print(f"[COS] 上传成功: {remote_name} -> {key}")
        return True, url
    except Exception as e:
        print(f"[COS] 上传失败: {e}")
        return False, str(e)


def list_cos_backups():
    """列出COS上的所有备份"""
    client = _get_cos_client()
    if not client:
        return []

    prefix = COS_CONFIG['prefix']
    try:
        response = client.list_objects(
            Bucket=COS_CONFIG['bucket'],
            Prefix=prefix,
            MaxKeys=200,
        )
        backups = []
        if 'Contents' in response:
            for obj in response['Contents']:
                name = obj['Key'].replace(prefix, '')
                backups.append({
                    'filename': name,
                    'size_mb': round(obj['Size'] / (1024 * 1024), 2),
                    'last_modified': obj['LastModified'].isoformat() if hasattr(obj['LastModified'], 'isoformat') else str(obj['LastModified']),
                    'url': f"https://{COS_CONFIG['bucket']}.cos.{COS_CONFIG['region']}.myqcloud.com/{obj['Key']}",
                })
        return sorted(backups, key=lambda x: x['last_modified'], reverse=True)
    except Exception as e:
        print(f"[COS] 列表获取失败: {e}")
        return []


def delete_cos_backup(filename):
    """删除COS上的指定备份"""
    client = _get_cos_client()
    if not client:
        return False, 'COS客户端不可用'

    key = COS_CONFIG['prefix'] + filename
    try:
        client.delete_object(Bucket=COS_CONFIG['bucket'], Key=key)
        print(f"[COS] 已删除: {filename}")
        return True, '删除成功'
    except Exception as e:
        return False, str(e)


def rotate_cos_backups():
    """清理COS上超出保留数量的旧备份"""
    keep = COS_CONFIG['keep_count']
    backups = list_cos_backups()

    if len(backups) <= keep:
        return

    for old in backups[keep:]:
        delete_cos_backup(old['filename'])


def get_cos_status():
    """获取COS备份状态"""
    if not is_configured():
        return {
            'configured': False,
            'reason': '未配置' if not COS_CONFIG['enabled'] else ('缺少SecretId/Key/Bucket'),
            'backup_count': 0,
            'last_upload': None,
        }

    backups = list_cos_backups()
    return {
        'configured': True,
        'bucket': COS_CONFIG['bucket'],
        'region': COS_CONFIG['region'],
        'backup_count': len(backups),
        'last_upload': backups[0]['last_modified'] if backups else None,
        'running': _cos_running,
        'interval_hours': COS_CONFIG['interval_hours'],
    }


# ============================================================
# 后台线程：定时上传备份到COS
# ============================================================

def _cos_upload_loop(db_backup_module, base_path):
    """后台线程：定期将数据库备份上传到COS"""
    global _cos_running
    _cos_running = True

    interval = COS_CONFIG['interval_hours'] * 3600  # 转换为秒

    print(f"[COS] 自动备份已启动，间隔: {COS_CONFIG['interval_hours']}小时，目标: {COS_CONFIG['bucket']}")

    # 启动时先执行一次
    _do_cos_upload(db_backup_module, base_path)

    while _cos_running:
        # 每分钟检查一次是否该停止
        for _ in range(interval // 60):
            if not _cos_running:
                break
            time.sleep(60)

        if not _cos_running:
            break

        _do_cos_upload(db_backup_module, base_path)

    _cos_running = False
    print("[COS] 自动备份线程已停止")


def _do_cos_upload(db_backup_module, base_path):
    """执行一次：本地备份 → 上传COS → 清理旧备份"""
    try:
        # 1. 先在本地创建备份
        success, info = db_backup_module.create_backup(base_path, note='COS自动备份')
        if not success:
            print(f"[COS] 本地备份失败，跳过上传: {info.get('error')}")
            return

        local_path = os.path.join(
            db_backup_module.get_backup_dir(base_path),
            info['filename']
        )

        # 2. 上传到COS
        success, result = upload_to_cos(local_path, info['filename'])
        if success:
            print(f"[COS] 上传成功: {info['filename']} -> {result}")

            # 3. 清理旧的COS备份
            rotate_cos_backups()
        else:
            print(f"[COS] 上传失败: {result}")

    except Exception as e:
        print(f"[COS] 自动备份异常: {e}")


def start_cos_auto_backup(db_backup_module, base_path):
    """启动COS自动备份"""
    global _cos_thread

    if not is_configured():
        print("[COS] 未配置，跳过启动。请在环境变量中设置 COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET")
        return

    if _cos_thread and _cos_thread.is_alive():
        print("[COS] 已在运行中")
        return

    _cos_thread = threading.Thread(
        target=_cos_upload_loop,
        args=(db_backup_module, base_path),
        daemon=True,
    )
    _cos_thread.start()
    print("[COS] 数据库云端备份已启用 ✅")


# ============================================================
# Flask API 路由
# ============================================================

def register_cos_routes(app):
    """注册COS相关的API路由"""

    @app.route('/api/cos/status', methods=['GET'])
    def cos_status():
        """获取COS备份状态"""
        return jsonify({'success': True, 'data': get_cos_status()})

    @app.route('/api/cos/list', methods=['GET'])
    def cos_list():
        """列出COS上的备份"""
        if not is_configured():
            return jsonify({'success': False, 'error': 'COS未配置'}), 400
        return jsonify({'success': True, 'data': list_cos_backups()})

    @app.route('/api/cos/upload', methods=['POST'])
    def cos_manual_upload():
        """手动触发一次COS上传"""
        if not is_configured():
            return jsonify({'success': False, 'error': 'COS未配置'}), 400

        import db_backup as db_backup_module
        base_path = app._base_path

        success, info = db_backup_module.create_backup(base_path, note='手动COS上传')
        if not success:
            return jsonify({'success': False, 'error': info.get('error')}), 500

        local_path = os.path.join(db_backup_module.get_backup_dir(base_path), info['filename'])
        ok, result = upload_to_cos(local_path, info['filename'])

        if ok:
            return jsonify({'success': True, 'data': {'filename': info['filename'], 'url': result}})
        return jsonify({'success': False, 'error': result}), 500

    @app.route('/api/cos/delete/<filename>', methods=['DELETE'])
    def cos_delete(filename):
        """删除COS上的备份"""
        safe_name = os.path.basename(filename)
        ok, msg = delete_cos_backup(safe_name)
        if ok:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': msg}), 500

    print("[COS] API路由已注册: /api/cos/*")
