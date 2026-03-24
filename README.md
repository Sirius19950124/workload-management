# 工作量管理系统 - 云托管版本

## 快速开始

### 1. 准备部署文件

```bash
cd cloud
python deploy.py
```

### 2. 推送到 GitHub

```bash
git init
git add .
git commit -m "准备部署到云托管"
git remote add origin https://github.com/你的用户名/workload-management.git
git push -u origin main
```

### 3. 在微信云托管部署

1. 访问 https://cloud.weixin.qq.com
2. 创建服务 → 连接 GitHub 仓库
3. 选择这个仓库
4. 点击部署

### 4. 创建数据库

在云托管控制台创建 MySQL 数据库，并绑定到服务。

## 详细文档

请查看 [DEPLOY.md](DEPLOY.md)

## 文件结构

```
cloud/
├── app/                  # 应用代码
│   ├── __init__.py       # 云版本启动文件
│   ├── models.py         # 数据模型
│   ├── api/              # API 接口
│   └── templates/        # 前端模板
├── static/               # 静态文件
├── config.py             # 配置文件
├── run.py                # 启动脚本
├── requirements.txt      # 依赖包
├── Dockerfile            # Docker 配置
├── cloudbaserc.json      # 云托管配置
├── deploy.py             # 部署准备脚本
└── DEPLOY.md             # 详细部署文档
```

## 费用

- **免费额度**：10万次调用/月，1GB数据库，5GB流量
- **你的场景**：10个治疗师，每天100次操作 = 3万次/月
- **结论**：完全够用，免费！

## 后续

- 对接小程序：小程序直接调用 API
- 数据迁移：从旧系统导入数据
- 功能扩展：预约、病历图片等
