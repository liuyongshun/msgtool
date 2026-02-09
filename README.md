# 🤖 MsgSkill - AI信息聚合专家

自动化追踪AI领域最新论文、技术资讯和热门项目，构建个人智能信息流。

## ✨ 特色功能

- **📚 学术追踪**: 自动同步arXiv 13个AI分类最新论文（含中文翻译）
- **📰 资讯精选**: HackerNews热门技术新闻AI筛选
- **📺 媒体监控**: 29个AI相关RSS源内容聚合
- **🐙 项目发现**: GitHub AI趋势项目实时跟踪 + 智能数据库管理
- **⏰ 自动调度**: 支持本地和云端定时任务执行
- **🤖 智能过滤**: DeepSeek AI模型内容相关性判断
- **📊 数据预览**: 美观的Web界面实时预览output数据

## 📋 系统要求

### 必需
- **Python**: 3.10 或更高版本（推荐 3.11）
- **操作系统**: macOS / Linux / Windows
- **磁盘空间**: 至少 500MB（用于依赖和数据存储）
- **网络**: 能够访问互联网（用于数据抓取）

### 可选
- **DeepSeek API Key**: 用于 AI 内容筛选和翻译
  - 获取地址: https://platform.deepseek.com/api_keys
  - 如不配置，将跳过 AI 筛选和翻译功能

---

## ⚡ 快速开始

### 步骤 1：检查 Python 版本

**Linux / macOS:**
```bash
python3 --version
# 应显示 Python 3.10 或更高版本
```

**Windows:**
```cmd
python --version
# 或
py --version
# 应显示 Python 3.10 或更高版本
```

如果版本过低，请先安装/升级 Python：
- **macOS**: `brew install python@3.11`
- **Ubuntu/Debian**: `sudo apt install python3.11`
- **Windows**: 从 [python.org](https://www.python.org/downloads/) 下载安装，安装时勾选 "Add Python to PATH"

### 步骤 2：克隆项目

```bash
git clone https://github.com/your-username/msgskill.git
cd msgskill
```

### 步骤 3：安装依赖

**Linux / macOS:**
```bash
pip3 install -r requirements.txt
```

**Windows:**
```cmd
python -m pip install -r requirements.txt
```

**可能遇到的问题**：
- **Linux/macOS**: 如果提示 `pip3: command not found`，使用 `python3 -m pip install -r requirements.txt`
- **Linux/macOS**: 如果权限不足，加上 `--user` 参数：`pip3 install --user -r requirements.txt`
- **Windows**: 如果提示 `pip` 命令不存在，使用 `python -m pip install -r requirements.txt`
- **Windows**: 如果提示 `python` 命令不存在，尝试使用 `py` 命令（Windows Python Launcher）

### 步骤 4：配置 API 密钥

编辑配置文件：

```bash
config/sources.json
```

找到 `llm` 部分，填入 DeepSeek API 密钥：

```json
{
  "llm": {
    "enabled": true,
    "provider": "deepseek",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxx",
    "api_url": "https://api.deepseek.com/v1/chat/completions",
    "model_name": "deepseek-chat"
  }
}
```

**API 密钥获取**：
1. 访问 https://platform.deepseek.com/
2. 注册/登录账号
3. 进入 "API Keys" 页面
4. 点击 "创建新密钥"
5. 复制密钥并粘贴到配置文件中

**⚠️ 注意**：
- 如果不配置 API 密钥，系统会跳过 AI 筛选和翻译功能
- 仅 arXiv 论文会被抓取，HackerNews、RSS、GitHub 的内容会被全部保留（不筛选）

### 步骤 5：启动服务

#### Linux / macOS

```bash
# 赋予启动脚本执行权限（首次需要）
chmod +x start.sh

# 启动服务
./start.sh
```

#### Windows

**方式 1：使用 PowerShell 脚本（推荐）**

在 PowerShell 中运行：

```powershell
.\start.ps1
```

如果遇到执行策略限制，先运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**方式 2：手动启动（两个终端窗口）**

终端 1 - 启动定时任务：
```cmd
python src\msgskill\multi_scheduler.py
```

终端 2 - 启动预览服务：
```cmd
python src\msgskill\preview_server.py
```

**启动后：**
- 🔄 定时任务自动在后台运行（Windows 会在新窗口显示）
- 🌐 访问 `http://localhost:5001` 预览数据
- 按 `Ctrl+C` 停止预览服务
- 关闭调度器窗口停止定时任务

```

## 📋 数据源配置

在 `config/sources.json` 中管理：

```json
{
  "global_settings": {
    "scheduler": {
      "enabled": true,
      "tasks": {
        "arxiv": {"enabled": true, "time": "11:00", "max_results": 20},
        "hackernews": {"enabled": true, "time": ["10:20", "14:05", "17:20", "20:40"], "max_results": 50},
        "rss": {"enabled": true, "time": ["10:20", "14:05", "17:20", "20:40"], "max_results": 20},
        "github": {"enabled": true, "time": "11:00", "max_results": 100}
      }
    }
  },
  "llm": {
    "enabled": true,
    "provider": "deepseek",
    "api_key": "your-api-key"
  }
}
```

⚠️ **安全提示**：不要将包含真实 API 密钥的 `sources.json` 提交到公开仓库。

### ⚙️ 数据量控制说明

#### `max_results` 参数的作用

| 数据源 | max_results含义 | AI筛选 | 输出策略 |
|--------|----------------|--------|---------|
| **arXiv** | 每个分类最多抓取的论文数 | ✅ 有| 全部保存 |
| **HackerNews** | 控制原始数据抓取上限 | ✅ 有 | **AI筛选后全部保存** |
| **RSS** | 每个RSS源最多抓取的条目数 | ✅ 有 | **AI筛选后全部保存** |
| **GitHub** | 控制每种查询类型的抓取上限 | ✅ 有 | **AI筛选后全部保存** |

#### 重要原则：智能AI筛选与GitHub数据库优化

**GitHub数据库功能**（已重构为单一文件架构）：
- ✅ **智能去重**: 避免重复筛选已存在的项目
- ✅ **单一文件存储**: 项目数据统一保存到 `output/github/github_projects.json`
- ✅ **状态管理**: crawled/ai_screened/whitelisted 三级状态跟踪
- ✅ **自动缓存**: 白名单项目自动缓存30天，大幅节省Token

**HackerNews、RSS、GitHub** 这三个数据源使用了DeepSeek AI进行内容筛选：
- `max_results` **只控制原始数据抓取量**
- **AI筛选后的所有结果都会保存**，不再进行二次限制
- 这样可以避免为AI筛选付费后却丢弃结果的情况

**数据流对比**：

**传统方式**（无数据库）:
1. 从API抓取约300-400个仓库
2. 使用AI模型筛选，保留约80-90个AI相关项目（**消耗token**）
3. 输出所有80-90个筛选结果

**数据库优化后**（启用数据库）:
1. 查询GitHub数据库检查项目是否已存在
2. 已存在的AI项目直接返回，**跳过AI筛选**
3. 新项目进行AI筛选，结果存入数据库
4. **节省70-85%的AI Token使用**

**效果统计**:
- 首次运行: ~25,500 tokens
- 后续运行: ~6,000 tokens (80%命中白名单)
- **节省: 76%**

#### 推荐配置值

```json
{
  "arxiv": { "max_results": 20 },      // 每个分类20篇论文（优化token消耗）
  "hackernews": { "max_results": 50 }, // 原始抓取50条，AI筛选后约30-40条
  "rss": { "max_results": 20 },        // 每个源20条，27个源AI筛选后约200-400条
  "github": { "max_results": 100 }     // 原始抓取约300个，AI筛选后约80-90个
}

**抓取时间安排**（当前配置）：
- **arXiv**：每天 11:00 执行
- **HackerNews**：每天 10:20, 14:05, 17:20, 20:40 执行（共4次）
- **RSS**：每天 10:20, 14:05, 17:20, 20:40 执行（共4次）
- **GitHub**：每天 11:00 执行
```
## 📁 项目结构

```
msgskill/
├── src/msgskill/              # 核心功能模块
│   ├── tools/                # 数据抓取工具
│   │   ├── arxiv_fetcher.py   # arXiv论文抓取
│   │   ├── news_scraper.py    # HackerNews抓取
│   │   ├── rss_reader.py      # RSS源抓取
│   │   └── github_fetcher.py  # GitHub项目抓取
│   ├── utils/                # 工具函数
│   │   ├── logger.py          # 日志工具
│   │   ├── ai_filter.py       # AI筛选
│   │   └── cache.py           # 缓存管理
│   ├── multi_scheduler.py    # 定时任务调度器
│   ├── preview_server.py     # 数据预览服务器
│   └── config.py             # 配置管理
│
├── mcp_server/               # MCP服务器模块（未来扩展）
│   ├── __init__.py
│   └── msgskill_server.py    # 原MCP服务器代码
│
├── agent_skill/              # Agent技能模块（未来扩展）
│   └── __init__.py
│
├── templates/                # HTML模板文件
│   └── output_preview.html   # 数据预览页面
│
├── static/                   # 静态资源
│   ├── css/                  # 样式文件
│   │   └── style.css
│   └── js/                   # JavaScript文件
│       └── preview.js        # 前端交互逻辑
│
├── config/                   # 配置文件
│   ├── sources.json          # 数据源配置
│   └── sources_schema.json   # 配置JSON Schema
│
├── output/                   # 输出数据目录
│   └── daily/               # 按日期存储
│
├── test/                     # 测试脚本
│
├── logs/                     # 日志文件
│   └── scheduler.log         # 调度器日志
│
├── docs/                     # 文档目录
├── .github/workflows/       # GitHub Actions工作流
├── start.sh                  # Linux/macOS 启动脚本
├── start.ps1                 # Windows PowerShell 启动脚本
├── requirements.txt          # Python依赖
└── pyproject.toml           # 项目配置
```

### 核心模块说明

**数据抓取模块** (`src/msgskill/tools/`)
- `arxiv_fetcher.py`: 抓取arXiv最新AI论文
- `news_scraper.py`: 抓取HackerNews热门技术新闻
- `rss_reader.py`: 抓取RSS源的最新文章
- `github_fetcher.py`: 抓取GitHub trending AI项目 + 智能数据库管理

**定时任务模块** (`src/msgskill/multi_scheduler.py`)
- 配置化的定时任务调度
- 支持独立启用/禁用各个数据源
- 自动重试和异常隔离
- 详细的日志记录

**数据预览模块** (`src/msgskill/preview_server.py`)
- Flask Web服务器
- RESTful API接口
- 实时扫描output目录
- 支持按日期和类型查看数据

**前端界面** (`templates/` & `static/`)
- 响应式Web界面
- 基于Tailwind CSS
- 使用htmx实现动态交互
- 支持桌面和移动端

### 未来扩展模块

**MCP Server** (`mcp_server/`)
- 与Claude等AI助手集成
- 提供结构化的AI信息查询接口
- 支持多种MCP工具

**Agent Skill** (`agent_skill/`)
- 自定义AI Agent能力
- 智能信息分析和推荐
- 自动化工作流

### 数据流转

```
数据抓取 → AI筛选 → 存储到output → 预览服务展示
   ↓          ↓           ↓              ↓
 tools/   utils/ai   output/daily   preview_server
         _filter.py    /YYYY-MM-DD        ↓
                                     浏览器访问
```

## 📊 数据预览功能

### 访问地址
启动服务后，浏览器打开：`http://localhost:5001`

### 功能特性
- **📅 日期选择**: 动态扫描output目录，选择不同日期的数据
- **?? 数据分类**: arXiv论文、HackerNews、RSS源、GitHub项目分tab展示
- **🎨 美观UI**: 响应式设计，支持桌面和移动端
- **⚡ 实时加载**: 自动识别可用数据类型，智能禁用不可用tab

## 📚 API访问示例

### MCP API使用
```python
import asyncio
from src.msgskill.tools.arxiv_fetcher import fetch_arxiv_papers

async def main():
    result = await fetch_arxiv_papers(category="cs.AI", max_results=5)
    print(f"获取到{result.count}篇论文")

asyncio.run(main())
```

### 直接调用工具示例
```python
from src.msgskill.multi_scheduler import MultiSourceScheduler

scheduler = MultiSourceScheduler()
scheduler.run_once()  # 立即同步所有数据源
```
## ?? 高级配置

### 定时任务配置
编辑 `config/sources.json` 配置定时任务：
- 启用/禁用各个数据源
- 设置执行时间和频率
- 配置数据抓取量
- AI筛选开关和参数

### 启动方式

#### Linux / macOS

**统一启动** (`start.sh`)
1. 检查并安装依赖
2. 启动定时任务调度器（后台）
3. 启动数据预览服务器（前台）
4. 捕获退出信号，优雅关闭

**单独启动**
```bash
# 仅启动定时任务
python3 src/msgskill/multi_scheduler.py

# 仅启动预览服务
python3 src/msgskill/preview_server.py
```

#### Windows

**统一启动** (`start.ps1`)
1. 检查 Python 和依赖
2. 在新窗口启动定时任务调度器
3. 在当前窗口启动数据预览服务器
4. 按 `Ctrl+C` 停止预览服务，关闭调度器窗口停止定时任务

**单独启动**
```cmd
REM 仅启动定时任务
python src\msgskill\multi_scheduler.py

REM 仅启动预览服务
python src\msgskill\preview_server.py
```

**Windows 注意事项：**
- 如果提示 `python` 命令不存在，尝试使用 `py` 或 `python3`
- PowerShell 脚本可能需要设置执行策略：`Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`
- 预览服务器会在端口 5001 启动，确保端口未被占用

## 🛠️ 维护管理

### 日志管理

日志文件存储在 `logs/` 目录，建议定期清理：

**Linux / macOS:**
```bash
# 清理7天前的日志
./scripts/cleanup_logs.sh

# 手动查看日志
tail -f logs/scheduler.log
```

**Windows:**
```powershell
# 手动查看日志（PowerShell）
Get-Content logs\scheduler.log -Tail 50 -Wait

# 或使用记事本打开
notepad logs\scheduler.log
```

**自动清理**（Linux/macOS 推荐）- 添加到 crontab：
```bash
# 每天凌晨3点自动清理
0 3 * * * /path/to/msgskill/scripts/cleanup_logs.sh
```

**Windows 自动清理** - 使用任务计划程序：
1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（每天凌晨3点）
4. 操作：启动程序 `powershell.exe`
5. 参数：`-File "D:\path\to\msgtool\scripts\cleanup_logs.ps1"`

### 缓存管理

缓存文件存储在 `.cache/` 目录，会自动过期：

**Linux / macOS:**
```bash
# 清理30天前的缓存
./scripts/cleanup_cache.sh

# 一键清理日志和缓存
./scripts/cleanup_all.sh
```

**Windows:**
```powershell
# 手动删除缓存目录
Remove-Item -Path .cache -Recurse -Force

# 或使用批处理脚本（如果存在）
.\scripts\cleanup_cache.bat
```

**缓存类型**：
- GitHub 白名单：30天过期
- arXiv 翻译：24小时过期
- API 结果：10分钟到1小时过期

---

## 🔄 开发指南

### 添加新数据源
1. 在 `src/msgskill/tools/` 创建新的fetcher模块
2. 在 `config/sources.json` 添加配置
3. 在 `multi_scheduler.py` 注册新任务
4. 在 `preview_server.py` 添加API支持
5. 在 `preview.js` 添加渲染逻辑

### 配置文件说明

**`config/sources.json`** - 主配置文件
- 全局调度器开关
- 各数据源的启用状态
- 执行时间配置
- 数据抓取量控制
- LLM配置（DeepSeek API）

**`requirements.txt`** - Python依赖
- Flask, Flask-CORS: Web服务
- schedule: 定时任务
- httpx, beautifulsoup4: 数据抓取
- feedparser: RSS解析
- arxiv: arXiv API
- pydantic: 数据验证

## 📖 文档

- [配置说明](./docs/配置说明.md) - 完整的配置文件说明和最佳实践
- [部署指南](./docs/DEPLOYMENT.md) - 部署和维护管理
- [数据源扩展](./docs/接入方案与扩容指南.md) - 添加新数据源
- [自动化部署](./docs/GITHUB_ACTIONS_INTEGRATED.md) - GitHub Actions配置

## ??️ 技术栈

- **Python 3.10+**: 核心开发语言
- **Flask**: Web服务框架
- **Schedule**: 定时任务调度
- **DeepSeek AI**: 智能内容筛选
- **Tailwind CSS + htmx**: 前端UI框架

---

💡 **提示**: 获取完整的数据源清单和详细配置说明，请查阅 [资源清单](./docs/资源.md)。

**版本**: 3.0.0  
**最后更新**: 2026-02-09