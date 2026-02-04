# GitHub Actions Workflows 说明

本目录包含用于自动化数据同步的GitHub Actions工作流配置。

## 📋 工作流列表

### 1. 📚 arxiv-sync.yml - arXiv论文同步
**运行频率**: 每天北京时间9:00（UTC 1:00）

**功能**:
- 同步13个arXiv分类的最新AI论文
- 自动翻译标题和摘要
- 每个分类默认获取20篇论文（周一自动增加到30篇）

**手动触发**:
```bash
# 在GitHub网页: Actions -> 📚 Sync arXiv Papers Daily -> Run workflow
# 可自定义每个分类获取的论文数量
```

**环境变量**:
- `DEEPSEEK_API_KEY`: DeepSeek API密钥（用于翻译）

---

### 2. 📰 rss-sync.yml - RSS源同步
**运行频率**: 每天3次
- 北京时间 6:00 (UTC 22:00)
- 北京时间 12:00 (UTC 4:00)
- 北京时间 18:00 (UTC 10:00)

**功能**:
- 验证所有RSS源的连通性
- 检查数据质量
- 生成验证报告

**手动触发**:
```bash
# 在GitHub网页: Actions -> 📰 Sync RSS Feeds -> Run workflow
```

---

## ⚙️ 配置说明

### 必需的Secrets配置

在 GitHub 仓库设置中添加以下 Secrets:

1. **DEEPSEEK_API_KEY**
   - 路径: Settings -> Secrets and variables -> Actions -> New repository secret
   - 名称: `DEEPSEEK_API_KEY`
   - 值: 你的DeepSeek API密钥

### 如何添加Secrets

```bash
# 1. 进入你的GitHub仓库
# 2. 点击 Settings
# 3. 左侧菜单选择 Secrets and variables -> Actions
# 4. 点击 New repository secret
# 5. 添加:
#    Name: DEEPSEEK_API_KEY
#    Secret: sk-your-api-key-here
# 6. 点击 Add secret
```

---

## 📊 查看运行结果

### 方法1: GitHub Actions页面
1. 进入仓库的 **Actions** 标签
2. 选择对应的workflow
3. 点击最近的运行记录
4. 查看日志和下载Artifacts

### 方法2: 下载Artifacts
运行完成后会自动上传日志文件到Artifacts，保留7天:
- `arxiv-sync-logs-<编号>`: arXiv同步日志
- `rss-validation-<编号>`: RSS验证结果

---

## 🔧 本地测试

在提交到GitHub之前，可以本地测试workflow中的命令:

```bash
# 测试arXiv同步
python src/msgskill/scheduler.py --once --limit 5

# 测试RSS验证
python test/validate_sources.py
```

---

## 📈 费用说明

### GitHub Actions免费额度
- **公开仓库**: 完全免费，无限制
- **私有仓库**: 每月2000分钟免费

### 预计消耗 (私有仓库)
```
arXiv同步:  每日1次 × 10分钟 = 300分钟/月
RSS验证:    每日3次 × 3分钟 = 270分钟/月
--------------------------------------------
总计:       约570分钟/月
```

✅ **完全在免费额度内!**

---

## 🚀 启用/禁用工作流

### 禁用某个工作流
1. 进入 Actions 标签
2. 选择要禁用的workflow
3. 点击右上角 "..." -> Disable workflow

### 修改运行频率
编辑对应的 `.yml` 文件中的 `cron` 表达式:

```yaml
schedule:
  # 语法: 分 时 日 月 星期
  - cron: '0 1 * * *'  # 每天UTC 1:00 (北京时间9:00)
```

**Cron表达式工具**: https://crontab.guru/

---

## 📧 通知设置 (可选)

### 失败时接收邮件通知
GitHub默认会在workflow失败时发送邮件通知到你的GitHub注册邮箱。

### 自定义通知 (高级)
可以添加额外的通知步骤，如:
- Slack通知
- 企业微信通知
- Telegram通知

参考: https://github.com/marketplace?type=actions&query=notify

---

## ⚠️ 注意事项

1. **API密钥安全**: 
   - 永远不要在代码中硬编码API密钥
   - 使用GitHub Secrets管理敏感信息

2. **运行频率**: 
   - 避免过于频繁的运行，可能触发API限制
   - 遵守各数据源的使用条款

3. **日志管理**: 
   - Artifacts默认保留7天
   - 重要日志需要及时下载保存

4. **错误处理**: 
   - 工作流失败会发送邮件通知
   - 检查日志找到失败原因

---

## 🔗 相关资源

- [GitHub Actions文档](https://docs.github.com/actions)
- [Workflow语法参考](https://docs.github.com/actions/reference/workflow-syntax-for-github-actions)
- [Cron表达式生成器](https://crontab.guru/)