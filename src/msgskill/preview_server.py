"""
Output数据预览服务器
提供Flask API用于动态预览output目录下的数据文件
"""
import os
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, send_from_directory
from flask_cors import CORS

# 获取项目根目录
import sys
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, 
            static_folder=str(BASE_DIR / 'static'),
            static_url_path='/static')
CORS(app)

OUTPUT_DIR = BASE_DIR / 'output' / 'daily'

@app.route('/')
def index():
    """主页面"""
    return send_from_directory(str(BASE_DIR / 'templates'), 'output_preview.html')

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

@app.route('/api/data/<date>/<data_type>')
def get_data(date, data_type):
    """获取指定日期和类型的数据 - 合并所有同类型文件"""
    try:
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
            unique_items.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            merged_data['items'] = unique_items
            merged_data['total_count'] = len(unique_items)
        
        # 对RSS数据按发布时间排序
        elif data_type == 'rss' and merged_data['feeds']:
            for feed_url, feed_data in merged_data['feeds'].items():
                items = feed_data.get('items', [])
                items.sort(key=lambda x: x.get('published', ''), reverse=True)
                feed_data['items'] = items
        
        # 对arXiv数据按发布时间排序
        elif data_type == 'arxiv' and merged_data['papers']:
            merged_data['papers'].sort(key=lambda x: x.get('published', ''), reverse=True)
        
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