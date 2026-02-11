"""
Notion同步模块 - 将output数据同步到Notion数据库

功能:
    - 将ArticleItem数据写入Notion数据库
    - 支持批量同步
    - 支持去重（基于source_url）
    - 自动创建Notion页面属性

使用前准备:
    1. 在Notion中创建集成，获取Integration Token
    2. 创建数据库，并连接集成
    3. 在config/sources.json中配置notion_sync配置项
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
from ..models import ArticleItem, FetchResult
from ..utils.logger import logger
from ..config import get_config


class NotionSync:
    """Notion同步器 - 将数据同步到Notion数据库"""
    
    def __init__(
        self,
        api_token: str,
        databases: Dict[str, str],
        enabled: bool = True
    ):
        """
        初始化Notion同步器
        
        Args:
            api_token: Notion Integration Token
            databases: 数据源到数据库ID的映射字典，格式: {"github": "database_id", "rss": "database_id", ...}
            enabled: 是否启用同步
        """
        self.api_token = api_token
        self.api_base_url = "https://api.notion.com/v1"
        self.enabled = enabled
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Notion-Version": "2022-06-28",  # Notion API版本
            "Content-Type": "application/json"
        }
        
        # 处理数据库映射，提取ID并转换为UUID格式
        self.databases = {}
        for source_type, db_id_or_url in databases.items():
            if db_id_or_url:
                self.databases[source_type] = self._extract_database_id(db_id_or_url)
        
        # 如果没有配置特定数据源的数据库，使用默认数据库（github）
        self.default_database_id = self.databases.get("github")
    
    def get_database_id(self, source_type: str) -> Optional[str]:
        """
        根据数据源类型获取对应的数据库ID
        
        Args:
            source_type: 数据源类型 (github, rss, hackernews, arxiv)
            
        Returns:
            数据库ID，如果未配置则返回默认数据库ID
        """
        # 优先使用指定数据源的数据库
        database_id = self.databases.get(source_type)
        
        # 如果未配置，使用默认数据库（github）
        if not database_id:
            database_id = self.default_database_id
        
        return database_id
    
    def _extract_database_id(self, database_id_or_url: str) -> str:
        """
        从URL或直接ID中提取数据库ID
        
        Args:
            database_id_or_url: 数据库ID或完整URL
            
        Returns:
            提取的数据库ID（32位字符）
        """
        # 如果是URL格式，提取ID
        if "notion.so" in database_id_or_url:
            # 提取URL中的ID部分
            # 格式: https://www.notion.so/ID?v=...
            parts = database_id_or_url.split("/")
            for part in parts:
                if len(part) == 32 and part.isalnum():
                    return part
            # 如果没找到，尝试从查询参数前提取
            if "?" in database_id_or_url:
                base = database_id_or_url.split("?")[0]
                id_part = base.split("/")[-1]
                if len(id_part) == 32:
                    return id_part
        
        # 如果已经是ID格式，转换为UUID格式（8-4-4-4-12）
        clean_id = database_id_or_url.replace("-", "").strip()
        if len(clean_id) == 32:
            # 转换为UUID格式: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
            return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:]}"
        
        # 如果都不匹配，返回原值（让API调用时暴露错误）
        return database_id_or_url
    
    def _get_field_name(self, field_key: str, source_type: str) -> str:
        """
        根据数据源类型获取字段名称（统一使用英文字段名）
        
        Args:
            field_key: 字段键名 (title, source_url, summary, published_date)
            source_type: 数据源类型
            
        Returns:
            字段名称
        """
        # 字段名称映射（统一使用英文）
        field_mapping = {
            "title": "Title",
            "source_url": "Source URL",
            "summary": "Summary",
            "published_date": "Published Date"
        }
        
        return field_mapping.get(field_key, "")
    
    def _convert_article_to_notion_properties(self, item: ArticleItem) -> Dict[str, Any]:
        """
        将ArticleItem转换为Notion页面属性
        
        Notion数据库字段（统一使用英文）:
        - Title (title): 标题
        - Source URL (url): 链接
        - Summary (rich_text): 摘要
        - Published Date (date): 发布日期
        
        Args:
            item: ArticleItem对象
            
        Returns:
            Notion页面属性字典
        """
        properties = {}
        
        # Title (必需字段)
        title_field = self._get_field_name("title", item.source_type)
        if title_field:
            properties[title_field] = {
                "title": [{"text": {"content": item.title}}]
            }
        
        # Summary
        if item.summary:
            summary_field = self._get_field_name("summary", item.source_type)
            if summary_field:
                properties[summary_field] = {
                    "rich_text": [{"text": {"content": item.summary}}]
                }
        
        # Source URL
        if item.source_url:
            url_field = self._get_field_name("source_url", item.source_type)
            if url_field:
                properties[url_field] = {
                    "url": item.source_url
                }
        
        # Published Date
        if item.published_date:
            try:
                from email.utils import parsedate_to_datetime
                from datetime import datetime
                
                date_str = item.published_date
                # 尝试解析RFC 2822格式（RSS常用格式）
                if "," in date_str and len(date_str) > 20:
                    try:
                        dt = parsedate_to_datetime(date_str)
                        date_str = dt.strftime("%Y-%m-%d")
                    except:
                        # 如果解析失败，尝试ISO格式
                        if "T" in date_str:
                            date_str = date_str.split("T")[0]
                        else:
                            date_str = date_str.split(" ")[0]
                elif "T" in date_str:
                    # ISO格式
                    date_str = date_str.split("T")[0]
                else:
                    # 其他格式，只取日期部分
                    date_str = date_str.split(" ")[0]
                
                # 验证日期格式（YYYY-MM-DD）
                if len(date_str) >= 10 and date_str[4] == "-" and date_str[7] == "-":
                    date_field = self._get_field_name("published_date", item.source_type)
                    if date_field:
                        properties[date_field] = {
                            "date": {"start": date_str[:10]}
                        }
            except Exception:
                pass
        
        return properties
    
    def _check_page_exists(self, source_url: str, database_id: str, source_type: str) -> Optional[str]:
        """
        检查页面是否已存在（基于Source URL去重）
        
        Args:
            source_url: 来源URL
            database_id: 数据库ID
            source_type: 数据源类型（用于获取正确的字段名）
            
        Returns:
            如果存在，返回页面ID；否则返回None
        """
        try:
            # 获取正确的字段名称
            url_field = self._get_field_name("source_url", source_type)
            if not url_field:
                return None
            
            response = httpx.post(
                f"{self.api_base_url}/databases/{database_id}/query",
                headers=self.headers,
                json={
                    "filter": {
                        "property": url_field,
                        "url": {
                            "equals": source_url
                        }
                    }
                },
                timeout=10.0
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                return results[0]["id"]
            return None
        except Exception as e:
            logger.debug(f"检查Notion页面是否存在时出错: {e}")
            return None
    
    def sync_item(self, item: ArticleItem, skip_existing: bool = True) -> bool:
        """
        同步单个ArticleItem到Notion
        
        Args:
            item: ArticleItem对象
            skip_existing: 如果已存在是否跳过
            
        Returns:
            是否成功
        """
        if not self.enabled:
            return False
        
        # 根据数据源类型获取对应的数据库ID
        database_id = self.get_database_id(item.source_type)
        if not database_id:
            logger.warning(f"⚠️ 未配置 {item.source_type} 的数据库ID，跳过同步")
            return False
        
        try:
            # 检查是否已存在
            if skip_existing:
                existing_page_id = self._check_page_exists(item.source_url, database_id, item.source_type)
                if existing_page_id:
                    logger.debug(f"跳过已存在的Notion页面: {item.title[:50]}")
                    return True
            
            # 转换为Notion属性
            properties = self._convert_article_to_notion_properties(item)
            
            # 创建页面
            response = httpx.post(
                f"{self.api_base_url}/pages",
                headers=self.headers,
                json={
                    "parent": {"database_id": database_id},
                    "properties": properties
                },
                timeout=10.0
            )
            response.raise_for_status()
            
            logger.debug(f"✅ 已同步到Notion ({item.source_type}): {item.title[:50]}")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Notion同步失败 (HTTP {e.response.status_code}): {item.title[:50]} - {e.response.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"❌ Notion同步失败: {item.title[:50]} - {str(e)}")
            return False
    
    def sync_items(self, items: List[ArticleItem], skip_existing: bool = True) -> Dict[str, Any]:
        """
        批量同步ArticleItem列表到Notion
        
        Args:
            items: ArticleItem列表
            skip_existing: 如果已存在是否跳过
            
        Returns:
            同步结果统计
        """
        if not self.enabled:
            return {
                "success": False,
                "reason": "Notion同步未启用",
                "total": len(items),
                "synced": 0,
                "skipped": 0,
                "failed": 0
            }
        
        synced = 0
        skipped = 0
        failed = 0
        
        for item in items:
            # 获取该数据源对应的数据库ID
            database_id = self.get_database_id(item.source_type)
            if not database_id:
                failed += 1
                continue
            
            existing_page_id = None
            if skip_existing:
                existing_page_id = self._check_page_exists(item.source_url, database_id, item.source_type)
            
            if existing_page_id:
                skipped += 1
                continue
            
            if self.sync_item(item, skip_existing=False):
                synced += 1
            else:
                failed += 1
        
        return {
            "success": True,
            "total": len(items),
            "synced": synced,
            "skipped": skipped,
            "failed": failed
        }
    
    def sync_fetch_result(self, result: FetchResult, skip_existing: bool = True) -> Dict[str, Any]:
        """
        同步FetchResult到Notion
        
        Args:
            result: FetchResult对象
            skip_existing: 如果已存在是否跳过
            
        Returns:
            同步结果统计
        """
        return self.sync_items(result.items, skip_existing=skip_existing)
    
    def sync_json_file(self, json_file: Path, skip_existing: bool = True) -> Dict[str, Any]:
        """
        从JSON文件同步数据到Notion
        
        Args:
            json_file: JSON文件路径
            skip_existing: 如果已存在是否跳过
            
        Returns:
            同步结果统计
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 处理FetchResult格式（标准格式，包含items数组）
            if isinstance(data, dict) and "items" in data:
                items = []
                for item_data in data.get("items", []):
                    try:
                        item = ArticleItem(**item_data)
                        items.append(item)
                    except Exception as e:
                        logger.warning(f"跳过无效的ArticleItem: {e}")
                        continue
                
                return self.sync_items(items, skip_existing=skip_existing)
            # 处理RSS格式（包含feeds结构）
            elif isinstance(data, dict) and "feeds" in data:
                items = []
                for feed_name, feed_data in data.get("feeds", {}).items():
                    if isinstance(feed_data, dict):
                        feed_items = feed_data.get("items", [])
                        for item_data in feed_items:
                            try:
                                # RSS格式转换为ArticleItem
                                item = ArticleItem(
                                    title=item_data.get("title", ""),
                                    summary=item_data.get("summary", "")[:300],
                                    source_url=item_data.get("link", ""),
                                    published_date=item_data.get("published"),
                                    source_type="rss",
                                    article_tag=item_data.get("article_tag", "AI资讯"),
                                    author=item_data.get("author"),
                                    tags=item_data.get("tags", []),
                                    ai_score=item_data.get("ai_score")
                                )
                                items.append(item)
                            except Exception as e:
                                logger.warning(f"跳过无效的RSS item: {e}")
                                continue
                
                return self.sync_items(items, skip_existing=skip_existing)
            # 处理arXiv格式（包含papers数组）
            elif isinstance(data, dict) and "papers" in data:
                items = []
                for paper in data.get("papers", []):
                    try:
                        # arXiv论文转换为ArticleItem
                        items.append(ArticleItem(
                            title=paper.get("title", ""),
                            summary=paper.get("summary", "")[:300],
                            source_url=paper.get("pdf_url") or paper.get("arxiv_url", ""),
                            published_date=paper.get("published"),
                            source_type="arxiv",
                            article_tag="AI论文",
                            author=", ".join(paper.get("authors", [])),
                            tags=paper.get("categories", []),
                            ai_score=None
                        ))
                    except Exception as e:
                        logger.warning(f"跳过无效的arXiv论文: {e}")
                        continue
                return self.sync_items(items, skip_existing=skip_existing)
            else:
                return {
                    "success": False,
                    "reason": "不支持的JSON格式（需要包含items或feeds字段）",
                    "total": 0,
                    "synced": 0,
                    "skipped": 0,
                    "failed": 0
                }
        except Exception as e:
            logger.error(f"读取JSON文件失败: {e}")
            return {
                "success": False,
                "reason": str(e),
                "total": 0,
                "synced": 0,
                "skipped": 0,
                "failed": 0
            }


def get_notion_sync() -> Optional[NotionSync]:
    """
    从配置获取Notion同步器实例
    
    Returns:
        NotionSync实例，如果未配置则返回None
    """
    try:
        config = get_config()
        notion_config = config.get_notion_config()
        
        if not notion_config or not notion_config.get("enabled"):
            return None
        
        api_token = notion_config.get("api_token")
        if not api_token:
            logger.warning("⚠️ Notion API Token未配置，跳过同步")
            return None
        
        # 获取数据库配置
        databases_config = notion_config.get("databases", {})
        databases = {}
        
        # 提取各数据源的数据库ID
        for source_type in ["github", "rss", "hackernews", "arxiv"]:
            db_config = databases_config.get(source_type, {})
            if isinstance(db_config, dict):
                db_id = db_config.get("database_id", "")
            else:
                # 兼容旧配置格式（直接是字符串）
                db_id = db_config if isinstance(db_config, str) else ""
            
            if db_id:
                databases[source_type] = db_id
        
        # 如果没有配置任何数据库，尝试使用旧的database_id配置（向后兼容）
        if not databases and notion_config.get("database_id"):
            databases["github"] = notion_config.get("database_id")
            logger.info("📝 使用旧配置格式，所有数据源将同步到GitHub数据库")
        
        if not databases:
            logger.warning("⚠️ 未配置任何Notion数据库，跳过同步")
            return None
        
        return NotionSync(
            api_token=api_token,
            databases=databases,
            enabled=notion_config.get("enabled", True)
        )
    except Exception as e:
        logger.warning(f"⚠️ 获取Notion配置失败: {e}")
        return None
