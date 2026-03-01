# -*- coding: utf-8 -*-
"""
康复科治疗师工作量管理系统 - 独立运行入口
用于 PyInstaller 打包

使用 waitress 作为生产服务器
"""

import sys
import os
import webbrowser
import threading
import time
import signal

# 设置控制台编码
if sys.platform == 'win32' and sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# 确保能找到 app 模块
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后运行
    BASE_DIR = os.path.dirname(sys.executable)
    os.chdir(BASE_DIR)

from app import create_app
from flask import jsonify, request

# Global flag for shutdown
shutdown_requested = False

def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)
    try:
        webbrowser.open('http://localhost:5001')
    except:
        pass

def shutdown_server():
    """关闭服务器"""
    global shutdown_requested
    shutdown_requested = True
    # Give time for response to be sent
    time.sleep(0.5)
    os._exit(0)

def main():
    global shutdown_requested
    app = create_app()

    # Add shutdown endpoint (GET for checking, POST for actual shutdown)
    @app.route('/api/system/shutdown', methods=['GET', 'POST'])
    def api_shutdown():
        """关闭服务器API"""
        if request.method == 'GET':
            # GET request just checks if endpoint exists (standalone mode)
            return jsonify({'success': True, 'standalone': True})
        # POST request actually shuts down
        threading.Thread(target=shutdown_server, daemon=True).start()
        return jsonify({'success': True, 'message': 'Server shutting down...'})

    print("")
    print("=" * 60)
    print("  康复科治疗师工作量管理系统 V7.3.0")
    print("=" * 60)
    print("")
    print("  访问地址: http://localhost:5001")
    print("")
    print("  按 Ctrl+C 停止服务")
    print("=" * 60)
    print("")

    # 在新线程中打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # 使用 waitress 作为生产服务器
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=5001, threads=4)
    except ImportError:
        # 如果没有 waitress，回退到 Flask 开发服务器
        print("[警告] waitress 未安装，使用 Flask 开发服务器")
        app.run(host='0.0.0.0', port=5001, debug=False)

if __name__ == '__main__':
    main()
