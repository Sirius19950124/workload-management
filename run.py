# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统
云托管启动脚本
"""

import os
import sys

# 设置控制台编码
if sys.platform == 'win32' and sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')

# 加载环境变量（如果有 .env 文件）
from dotenv import load_dotenv
load_dotenv()

from app import create_app

# 创建应用
app = create_app()

if __name__ == '__main__':
    # 获取端口（云托管会设置 PORT 环境变量）
    port = int(os.environ.get('PORT', 5001))
    
    # 获取调试模式
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    print("=" * 60)
    print("康复科治疗师工作量管理系统 - 云托管版")
    print("=" * 60)
    print(f"环境: {os.environ.get('FLASK_ENV', 'production')}")
    print(f"访问地址: http://0.0.0.0:{port}")
    print("=" * 60)
    
    app.run(debug=debug, host='0.0.0.0', port=port)
