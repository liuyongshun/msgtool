"""
Output数据预览服务器
提供Flask API用于动态预览output目录下的数据文件
"""
import os
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, send_from_directory, request
from flask_cors import CORS
from datetime import datetime

def parse_date_string(date_str):
    """解析各种格式的日期字符串，返回毫秒时间戳用于排序（参考前端formatToBeijingTime逻辑）"""
    if not date_str:
        return 0  # 使用0作为最小时间戳
    
    try:
        # 处理RSS格式时间 (Mon, 09 Feb 2026 02:28:48 GMT)
        if date_str.endswith(' GMT'):
            date_str_with_tz = date_str.replace(' GMT', ' +0000')
            dt = datetime.strptime(date_str_with_tz, '%a, %d %b %Y %H:%M:%S %z')
            # GMT时间转换为东八区：+8小时
            return int((dt.timestamp() + 8 * 3600) * 1000)
        
        # 处理ISO格式时间 (2026-02-09T20:39:28)
        elif 'T' in date_str:
            # 如果后端已确保时间正确，直接解析
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00') if date_str.endswith('Z') else date_str)
            return int(dt.timestamp() * 1000)
        
        # 其他格式直接尝试解析
        else:
            dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S')
            return int(dt.timestamp() * 1000)
            
    except (ValueError, AttributeError):
        # 如果解析失败，返回0作为最小时间戳
        return 0

# 获取项目根目录
import sys
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, 
            static_folder=str(BASE_DIR / 'static'),
            static_url_path='/static')
CORS(app)

OUTPUT_DIR = BASE_DIR / 'output' / 'daily'

# 导入GitHub数据库模块
from src.msgskill.utils.github_db_new import get_github_db
from src.msgskill.utils.notion_sync import get_notion_sync
from src.msgskill.models import ArticleItem
from pydantic import ValidationError

# 允许的 story_type 枚举值（与 ArticleItem 定义保持一致）
ALLOWED_STORY_TYPES = {"top", "new", "best", "pushed", "created", "stars"}

@app.route('/')
def index():
    """主页面"""
    return send_from_directory(str(BASE_DIR / 'templates'), 'output_preview.html')

@app.route('/api/github/database')
def get_github_database():
    """获取GitHub数据库中的所有AI项目数据"""
    try:
        referer = request.headers.get('Referer', '直接访问')
        user_agent = request.headers.get('User-Agent', 'Unknown')
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GitHub数据库API] 📊 收到请求")
        print(f"  来源: {referer}")
        print(f"  用户代理: {user_agent[:50]}...")
        
        # 直接从 github_projects.json 文件读取数据（支持两种格式）
        github_file = BASE_DIR / 'output' / 'github' / 'github_projects.json'
        items = []
        total_projects = 0
        ai_projects = 0
        whitelist_projects = 0
        
        if github_file.exists():
            with open(github_file, 'r', encoding='utf-8') as f:
                all_projects = json.load(f)
            
            total_projects = len(all_projects)
            
            # 处理两种数据格式
            for project_key, project_data in all_projects.items():
                # 格式1：ArticleItem格式（由 _save_github_items_to_file 保存）
                if 'source_url' in project_data and 'title' in project_data:
                    # 这是 ArticleItem 格式，直接使用
                    ai_score = project_data.get('ai_score', 0.0) or 0.0
                    # 统一口径：仅当 ai_score > 0 时视为 AI 项目
                    is_ai_project_flag = ai_score > 0.0
                    if is_ai_project_flag:
                        ai_projects += 1
                    item = {
                        'id': project_key,
                        'title': project_data.get('title', ''),
                        'summary': project_data.get('summary', ''),
                        'source_url': project_data.get('source_url', ''),
                        'published_date': project_data.get('published_date', ''),
                        'source_type': project_data.get('source_type', 'github'),
                        'article_tag': project_data.get('article_tag', ''),
                        'author': project_data.get('author', ''),
                        'score': project_data.get('score', 0),
                        'tags': project_data.get('tags', []),
                        'story_type': project_data.get('story_type', ''),
                        'ai_score': ai_score,
                        'ai_reason': project_data.get('ai_reason', ''),
                        'language': '',  # ArticleItem格式可能没有language字段
                        'is_ai_project': is_ai_project_flag,
                        '_from_database': True
                    }
                    items.append(item)
                
                # 格式2：github_db_new格式（包含status字段）
                elif 'status' in project_data:
                    status = project_data.get('status', 'crawled')
                    if status in ['ai_screened', 'whitelisted']:
                        if status == 'ai_screened':
                            ai_projects += 1
                        elif status == 'whitelisted':
                            whitelist_projects += 1
                        
                        item = {
                            'id': project_key,
                            'title': f"{project_data.get('full_name', '')}: {project_data.get('name', '')}",
                            'summary': project_data.get('description', '') or f"GitHub项目: {project_data.get('name', '')}",
                            'source_url': project_data.get('html_url', ''),
                            'published_date': project_data.get('created_at', project_data.get('crawled_at', project_data.get('added_at', ''))),
                            'source_type': 'github',
                            'article_tag': 'tools',
                            'author': project_data.get('owner', {}).get('login', '').split('/')[0] if '/' in project_data.get('owner', {}).get('login', '') else project_data.get('owner', {}).get('login', ''),
                            'score': project_data.get('stargazers_count', 0),
                            'tags': project_data.get('topics', []),
                            'story_type': 'database',
                            'ai_score': project_data.get('ai_score', 0.0),
                            'ai_reason': project_data.get('ai_reason', ''),
                            'language': project_data.get('language', ''),
                            # 旧 github_db_new 格式：status 为 ai_screened / whitelisted 的项目视为 AI 项目
                            'is_ai_project': True,
                            '_from_database': True
                        }
                        items.append(item)
        
        # 排序规则：
        # 1. AI 项目（is_ai_project=True 或 ai_score>0）在前
        # 2. 同类内部按创建时间倒序
        for item in items:
            # 兼容：如果没带 is_ai_project，但 ai_score>0，则视为AI项目
            if 'is_ai_project' not in item:
                item['is_ai_project'] = (item.get('ai_score', 0.0) or 0.0) > 0.0
        items.sort(
            key=lambda x: (
                1 if x.get('is_ai_project') else 0,
                parse_date_string(x.get('published_date', ''))
            ),
            reverse=True
        )
        
        return jsonify({
            'success': True,
            'data': {
                'source_name': 'GitHub数据库（AI项目）',
                'source_type': 'github',
                'fetched_at': datetime.now().isoformat(),
                'total_count': len(items),
                'items': items,
                'database_info': {
                    'total_projects': total_projects,
                    'ai_projects': ai_projects,
                    'whitelist_projects': whitelist_projects
                }
            },
            'from_database': True,
            'merged_count': len(items)
        })
        
    except Exception as e:
        print(f"加载GitHub数据库数据失败: {e}")
        return jsonify({'error': f'加载GitHub数据库失败: {str(e)}'}), 500

@app.route('/api/dates')
def get_dates():
    """获取所有可用的日期列表"""
    try:
        if not OUTPUT_DIR.exists():
            return jsonify({'error': 'output目录不存在', 'dates': []}), 404
        
        dates = [d.name for d in OUTPUT_DIR.iterdir() if d.is_dir()]
        dates.sort(reverse=True)
        
        return jsonify({
            'success': True,
            'dates': dates,
            'count': len(dates)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'dates': []}), 500


@app.route('/api/notion/sync', methods=['POST'])
def sync_to_notion():
    """同步单条数据到 Notion（手动触发，按 item 粒度）"""
    try:
        payload = request.get_json(force=True) or {}
        data_type = payload.get('type')
        item_data = payload.get('item') or {}

        notion_sync = get_notion_sync()
        if not notion_sync or not notion_sync.enabled:
            return jsonify({'success': False, 'error': 'Notion 同步未启用，请检查 config/sources.json 中的 notion_sync 配置'}), 400

        if data_type not in ['arxiv', 'hackernews', 'rss', 'github', 'github-db']:
            return jsonify({'success': False, 'error': f'不支持的数据类型: {data_type}'}), 400

        # 构造 ArticleItem
        article: ArticleItem
        try:
            if data_type in ['github', 'hackernews', 'arxiv']:
                # 这三类在预览数据中已经基本是 ArticleItem 结构
                article = ArticleItem(
                    title=item_data.get('title', ''),
                    summary=(item_data.get('summary', '') or '')[:300],
                    source_url=item_data.get('source_url', ''),
                    published_date=item_data.get('published_date'),
                    source_type=item_data.get('source_type', data_type),
                    article_tag=item_data.get('article_tag', 'AI资讯'),
                    author=item_data.get('author'),
                    score=item_data.get('score'),
                    comments_count=item_data.get('comments_count'),
                    tags=item_data.get('tags', []),
                    # story_type 只接受限定值，其它情况一律置为 None，避免校验错误
                    story_type=item_data.get('story_type') if item_data.get('story_type') in ALLOWED_STORY_TYPES else None,
                    ai_score=item_data.get('ai_score')
                )
            elif data_type == 'github-db':
                # GitHub数据库视为github源
                article = ArticleItem(
                    title=item_data.get('title', ''),
                    summary=(item_data.get('summary', '') or '')[:300],
                    source_url=item_data.get('source_url', ''),
                    published_date=item_data.get('published_date'),
                    source_type='github',
                    article_tag=item_data.get('article_tag', 'AI工具'),
                    author=item_data.get('author'),
                    score=item_data.get('score'),
                    comments_count=None,
                    tags=item_data.get('tags', []),
                    # 数据库视图不区分 story_type，统一置为 None
                    story_type=None,
                    ai_score=item_data.get('ai_score')
                )
            elif data_type == 'rss':
                # RSS项：来自 feed.items
                article = ArticleItem(
                    title=item_data.get('title', ''),
                    summary=(item_data.get('summary', '') or '')[:300],
                    source_url=item_data.get('link', ''),
                    published_date=item_data.get('published'),
                    source_type='rss',
                    article_tag=item_data.get('article_tag', 'AI资讯'),
                    author=item_data.get('author'),
                    score=None,
                    comments_count=None,
                    tags=item_data.get('tags', []),
                    story_type=None,
                    ai_score=item_data.get('ai_score')
                )
        except ValidationError as e:
            return jsonify({'success': False, 'error': f'数据格式不合法: {str(e)}'}), 400

        # 执行单条同步
        result = notion_sync.sync_items([article], skip_existing=True)
        synced = result.get('synced', 0)

        if synced == 0:
            return jsonify({'success': True, 'message': '该条数据已存在于 Notion（未重复创建）'})

        return jsonify({'success': True, 'message': '已同步 1 条数据到 Notion'})

    except Exception as e:
        print(f"Notion 手动同步失败: {e}")
        return jsonify({'success': False, 'error': f'Notion 同步失败: {str(e)}'}), 500

@app.route('/api/data/<date>/<data_type>')
def get_data(date, data_type):
    """获取指定日期和类型的数据 - 合并所有同类型文件"""
    try:
        referer = request.headers.get('Referer', '直接访问')
        user_agent = request.headers.get('User-Agent', 'Unknown')
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [数据API] 📄 收到请求")
        print(f"  日期: {date}, 类型: {data_type}")
        print(f"  来源: {referer}")
        print(f"  用户代理: {user_agent[:50]}...")
        date_dir = OUTPUT_DIR / date
        if not date_dir.exists():
            return jsonify({'error': f'日期目录不存在: {date}'}), 404
        
        # 查找匹配的文件
        file_pattern = f"{data_type}_*.json"
        files = list(date_dir.glob(file_pattern))
        
        if not files:
            return jsonify({'error': f'未找到{data_type}数据文件'}), 404
        
        # 按文件名排序（包含时间戳）
        files.sort(reverse=True)
        
        # 合并所有文件的数据
        merged_data = {
            'source_name': '',
            'source_type': data_type,
            'fetched_at': '',
            'total_count': 0
        }
        
        # 根据数据类型设置不同的合并字段
        if data_type == 'arxiv':
            merged_data['papers'] = []
            merged_data['count'] = 0
            merged_data['category_name'] = '多分类合并'
        elif data_type in ['hackernews', 'github']:
            merged_data['items'] = []
            # GitHub有total_count，HackerNews有total_count
        elif data_type == 'rss':
            merged_data['feeds'] = {}
            merged_data['feeds_count'] = 0
            merged_data['total_items'] = 0
        
        # 遍历所有文件并合并数据
        all_items = []
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                # 更新基本元数据
                merged_data['source_name'] = file_data.get('source_name', merged_data['source_name'])
                merged_data['fetched_at'] = max(
                    merged_data.get('fetched_at', ''),
                    file_data.get('fetched_at', '')
                )
                
                # 合并具体数据
                if data_type == 'arxiv' and 'papers' in file_data:
                    merged_data['papers'].extend(file_data['papers'])
                    merged_data['count'] += len(file_data['papers'])
                    
                elif data_type in ['hackernews', 'github'] and 'items' in file_data:
                    merged_data['items'].extend(file_data['items'])
                    merged_data['total_count'] += len(file_data['items'])
                    all_items.extend(file_data['items'])
                    
                elif data_type == 'rss' and 'feeds' in file_data:
                    # 合并RSS源
                    for feed_url, feed_data in file_data['feeds'].items():
                        if feed_url not in merged_data['feeds']:
                            merged_data['feeds'][feed_url] = feed_data
                            merged_data['feeds_count'] += 1
                        else:
                            # 合并同一源的文章
                            existing_feed = merged_data['feeds'][feed_url]
                            if 'items' in feed_data:
                                existing_items = existing_feed.get('items', [])
                                existing_items.extend(feed_data['items'])
                                existing_feed['items'] = existing_items
                    
                    merged_data['total_items'] = sum(
                        len(feed.get('items', [])) for feed in merged_data['feeds'].values()
                    )
                    
            except Exception as e:
                print(f"读取文件 {file.name} 时出错: {e}")
                continue
        
        # 对GitHub和HackerNews数据进行去重（基于source_url）
        if data_type in ['github', 'hackernews'] and merged_data['items']:
            seen_urls = set()
            unique_items = []
            for item in merged_data['items']:
                if 'source_url' in item and item['source_url'] not in seen_urls:
                    seen_urls.add(item['source_url'])
                    unique_items.append(item)
            
            # 按时间排序：最新的在最前
            unique_items.sort(key=lambda x: parse_date_string(x.get('published_date', '')), reverse=True)
            merged_data['items'] = unique_items
            merged_data['total_count'] = len(unique_items)
        
        # 对RSS数据按发布时间排序
        elif data_type == 'rss' and merged_data['feeds']:
            for feed_url, feed_data in merged_data['feeds'].items():
                items = feed_data.get('items', [])
                items.sort(key=lambda x: parse_date_string(x.get('published', '')), reverse=True)
                feed_data['items'] = items
        
        # 对arXiv数据按发布时间排序
        elif data_type == 'arxiv' and merged_data['papers']:
            merged_data['papers'].sort(key=lambda x: parse_date_string(x.get('published', '')), reverse=True)
        
        return jsonify({
            'success': True,
            'data': merged_data,
            'total_files': len(files),
            'all_files': [f.name for f in files],
            'merged_count': merged_data.get('count', merged_data.get('total_count', 0))
        })
    except json.JSONDecodeError as e:
        return jsonify({'error': f'JSON解析错误: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<date>')
def get_files(date):
    """获取指定日期下所有可用的数据类型"""
    try:
        date_dir = OUTPUT_DIR / date
        if not date_dir.exists():
            return jsonify({'error': f'日期目录不存在: {date}', 'files': []}), 404
        
        files = {}
        for file in date_dir.glob('*.json'):
            # 从文件名中提取数据类型
            name_parts = file.stem.split('_')
            if len(name_parts) >= 1:
                data_type = name_parts[0]
                files[data_type] = file.name
        
        return jsonify({
            'success': True,
            'date': date,
            'files': files,
            'types': list(files.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e), 'files': []}), 500

def main():
    """启动服务器"""
    import sys
    import io
    
    # Fix Windows console encoding issue
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    port = 5001  # 改用5001端口
    print("=" * 60)
    print("Output数据预览服务器启动中...")
    print("=" * 60)
    print(f"数据目录: {OUTPUT_DIR.absolute()}")
    print(f"访问地址: http://localhost:{port}")
    print("=" * 60)
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == '__main__':
    main()