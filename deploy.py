# -*- coding: utf-8 -*-
"""
云托管快速部署脚本
"""

import os
import shutil
import sys

# 设置控制台编码
if sys.platform == 'win32' and sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')

def prepare_cloud_deployment():
    """准备云托管部署文件"""
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cloud_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=" * 60)
    print("准备云托管部署文件")
    print("=" * 60)
    
    # 1. 复制必要的文件到 cloud 目录
    dirs_to_copy = ['app/api', 'app/templates', 'static']
    
    for item in dirs_to_copy:
        src = os.path.join(base_dir, item)
        dst = os.path.join(cloud_dir, item)
        
        if os.path.exists(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"[OK] 复制目录: {item}")
        else:
            print(f"[SKIP] 跳过（不存在）: {item}")
    
    # 2. 复制 models.py
    src_models = os.path.join(base_dir, 'app', 'models.py')
    dst_models = os.path.join(cloud_dir, 'app', 'models.py')
    if os.path.exists(src_models):
        shutil.copy2(src_models, dst_models)
        print(f"[OK] 复制文件: app/models.py")
    
    # 3. 创建 .gitignore
    gitignore_content = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
*.db
instance/
uploads/
.env
.idea/
.vscode/
*.log
"""
    with open(os.path.join(cloud_dir, '.gitignore'), 'w') as f:
        f.write(gitignore_content.strip())
    print("[OK] 创建 .gitignore")
    
    # 4. 显示部署清单
    print("\n部署文件清单：")
    print("- cloud/app/__init__.py  (云版本)")
    print("- cloud/app/models.py")
    print("- cloud/app/api/")
    print("- cloud/app/templates/")
    print("- cloud/static/")
    print("- cloud/config.py")
    print("- cloud/run.py")
    print("- cloud/requirements.txt")
    print("- cloud/Dockerfile")
    print("- cloud/cloudbaserc.json")
    
    print("=" * 60)
    print("准备完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. cd cloud")
    print("2. git init")
    print("3. git add .")
    print("4. git commit -m '准备部署到云托管'")
    print("5. 创建 GitHub 仓库并推送")
    print("6. 在微信云托管中连接 GitHub 仓库并部署")
    print("\n详细步骤请查看 DEPLOY.md")


if __name__ == '__main__':
    prepare_cloud_deployment()
