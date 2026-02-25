# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统
启动脚本
"""

import sys
import os

# 设置控制台编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("康复科治疗师工作量管理系统")
    print("=" * 60)
    print("访问地址: http://localhost:5001")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=5001)
