# 云托管部署指南

## 一、准备工作

### 1. 注册微信小程序
1. 访问 https://mp.weixin.qq.com
2. 注册小程序账号（企业认证，300元/年）
3. 准备材料：
   - 营业执照
   - 医疗机构执业许可证
   - 法人身份证
   - 银行卡（个体户用个人卡，公司用对公账户）

### 2. 开通云托管
1. 登录微信小程序后台
2. 进入「云开发」→「云托管」
3. 开通服务（选择免费版）

---

## 二、创建 MySQL 数据库

### 在云托管控制台：
1. 进入「云托管」→「资源」→「数据库」
2. 创建 MySQL 数据库
3. 选择配置（免费版够用）
4. 记录连接信息（会自动注入到环境变量）

---

## 三、部署代码

### 方式1：GitHub 自动部署（推荐）

1. **上传代码到 GitHub**
   ```bash
   cd workload_management（3-23版本）
   git init
   git add .
   git commit -m "准备云托管部署"
   git remote add origin https://github.com/你的用户名/workload-management.git
   git push -u origin main
   ```

2. **在云托管创建服务**
   - 进入「云托管」→「新建服务」
   - 选择「GitHub」
   - 授权并选择你的仓库
   - 配置：
     - CPU: 0.5核
     - 内存: 512MB
     - 实例: 0-5（按需扩缩）
   - 点击「部署」

3. **绑定数据库**
   - 服务创建后，进入「服务配置」
   - 添加 MySQL 数据库连接
   - 环境变量会自动注入

### 方式2：本地上传

1. **安装云托管 CLI**
   ```bash
   npm install -g @cloudbase/cli
   ```

2. **登录**
   ```bash
   tcb login
   ```

3. **部署**
   ```bash
   cd workload_management（3-23版本）
   tcb framework deploy
   ```

---

## 四、配置域名

### 1. 获取默认域名
- 云托管会自动分配一个域名
- 格式：`https://xxx.ap-shanghai.run.tcloudbase.com`

### 2. 绑定自定义域名（可选）
- 进入「服务配置」→「域名配置」
- 添加你的域名
- 配置 DNS 解析
- 申请 SSL 证书（免费）

---

## 五、验证部署

### 1. 访问测试
- 浏览器打开：`https://你的域名/`
- 应该看到工作量管理页面

### 2. 健康检查
- 访问：`https://你的域名/health`
- 应该返回：`{"status": "ok"}`

---

## 六、数据迁移（如有旧数据）

### 从 SQLite 导出数据
```bash
# 在原程序目录
python -c "
from app import create_app, db
from app.models import *
import json

app = create_app()
with app.app_context():
    # 导出治疗师
    therapists = [t.to_dict() for t in WorkloadTherapist.query.all()]
    with open('therapists.json', 'w') as f:
        json.dump(therapists, f, ensure_ascii=False)
    
    # 导出治疗项目
    items = [i.to_dict() for i in WorkloadTreatmentItem.query.all()]
    with open('items.json', 'w') as f:
        json.dump(items, f, ensure_ascii=False)
    
    # 导出记录
    records = [r.to_dict() for r in WorkloadRecord.query.all()]
    with open('records.json', 'w') as f:
        json.dump(records, f, ensure_ascii=False)
    
    print('导出完成')
"
```

### 导入到云托管
```bash
# 修改导入脚本连接云数据库
python -c "
import json
import pymysql

# 连接云数据库（从云托管控制台获取连接信息）
conn = pymysql.connect(
    host='你的MySQL地址',
    port=3306,
    user='root',
    password='你的密码',
    database='workload',
    charset='utf8mb4'
)

cursor = conn.cursor()

# 导入数据...
# （具体导入逻辑根据需要编写）

conn.commit()
conn.close()
print('导入完成')
"
```

---

## 七、费用估算

### 免费额度（每月）
- 10 万次调用
- 0.5GB 内存 × 1000 小时
- 1GB 数据库
- 5GB 流量

### 你的使用场景（10个治疗师）
- 每人每天 100 次操作 → 3 万次/月
- 完全在免费额度内

### 超出后费用
- 数据库扩容：约 20元/GB/月
- 内存扩容：约 30元/0.5GB/月
- 流量超出：约 0.8元/GB

---

## 八、后续对接小程序

### 小程序端调用示例
```javascript
// 小程序 app.js
App({
  globalData: {
    apiBase: 'https://你的域名'
  }
})

// 页面中调用
const app = getApp()

wx.request({
  url: `${app.globalData.apiBase}/api/treatments`,
  method: 'GET',
  success: (res) => {
    console.log('治疗项目列表:', res.data)
  }
})
```

### 需要添加的 API
1. `/api/mini/login` - 小程序登录
2. `/api/mini/records` - 治疗记录（患者查看）
3. `/api/mini/appointments` - 预约列表
4. `/api/mini/profile` - 个人信息

---

## 九、常见问题

### Q: 部署后访问 502？
A: 检查日志，可能是数据库连接失败。确保 MySQL 已创建并绑定。

### Q: 数据丢失？
A: 云托管数据库是持久化的，不会丢。上传的文件存在 /tmp，重启会丢失，建议配置对象存储。

### Q: 如何查看日志？
A: 云托管控制台 → 服务 → 日志

### Q: 如何更新代码？
A: 推送到 GitHub，云托管会自动重新部署

---

## 十、技术支持

- 微信云托管文档：https://developers.weixin.qq.com/miniprogram/dev/wxcloud/
- Flask 文档：https://flask.palletsprojects.com/
- 遇到问题可以问我
