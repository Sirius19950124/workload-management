# -*- coding: utf-8 -*-
"""操作日志统一装饰器

用法:
    @log_op('import', '导入Excel')
    def import_excel():
        ...

    @log_op('delete', '删除记录')
    def delete_item(id):
        ...
"""

import functools
import time
from flask import request, g
from app.api.operation_log_bp import log_operation


def log_op(log_type, detail=None):
    """操作日志装饰器

    Args:
        log_type: 操作类型 (create/update/delete/import/export/backup/restore/setting/other)
        detail: 固定描述字符串，或None（自动从endpoint名生成）
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            start = time.time()
            g._op_log_type = log_type
            try:
                result = f(*args, **kwargs)
                elapsed = round((time.time() - start) * 1000)
                # 构建detail
                if detail:
                    desc = detail
                else:
                    endpoint = request.endpoint or f.__name__
                    method = request.method if request else '?'
                    desc = f'{method} {endpoint}'
                log_operation(log_type, f'{desc} ({elapsed}ms)')
                return result
            except Exception as e:
                elapsed = round((time.time() - start) * 1000)
                ep = request.endpoint or f.__name__
                log_operation('other', f'[异常] {ep}: {str(e)} ({elapsed}ms)')
                raise
        return wrapped
    return decorator
