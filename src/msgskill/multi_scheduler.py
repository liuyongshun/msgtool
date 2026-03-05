"""
多数据源定时任务调度器 - 支持配置化开启本地定时任务

功能：
- 支持配置化开启arXiv、HackerNews、RSS、GitHub的定时同步
- 每个数据源可独立配置启用状态、时间和频率
- 记录详细的同步日志和统计信息
- 支持全局开关控制
"""

import asyncio
import json
import schedule
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

try:
    # 包内导入（当作为模块使用时）
    from .tools.arxiv_fetcher import fetch_arxiv_papers, ARXIV_CATEGORIES
    from .tools.news_scraper import fetch_ai_news
    from .tools.rss_reader import fetch_rss_feeds
    from .tools.github_fetcher import fetch_github_trending
    from .utils.logger import logger
    from .config import get_config
    from .output import get_output_manager
    from .utils.rsshub_manager import get_rsshub_manager
    from .utils.wechat_topic_evaluator import get_wechat_topic_evaluator
except ImportError:
    # 直接运行时的导入（从项目根目录）
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.msgskill.tools.arxiv_fetcher import fetch_arxiv_papers, ARXIV_CATEGORIES
    from src.msgskill.tools.news_scraper import fetch_ai_news
    from src.msgskill.tools.rss_reader import fetch_rss_feeds
    from src.msgskill.tools.github_fetcher import fetch_github_trending
    from src.msgskill.utils.logger import logger
    from src.msgskill.config import get_config
    from src.msgskill.output import get_output_manager
    from src.msgskill.utils.rsshub_manager import get_rsshub_manager
    from src.msgskill.utils.wechat_topic_evaluator import get_wechat_topic_evaluator


class MultiSourceScheduler:
    """多数据源调度器 - 支持配置化定时任务"""
    
    def __init__(self):
        """
        初始化调度器（从配置加载设置）
        """
        config_manager = get_config()
        self.settings = config_manager.global_settings
        self.scheduler_enabled = self.settings.scheduler.get("enabled", False)
        self.sources_config = self.settings.scheduler.get("tasks", {})
        self.output_manager = get_output_manager()
        
        self.sync_stats = {
            "total_syncs": 0,
            "failed_sources": [],
            "success_count": 0,
            "last_sync_time": None
        }
        
        logger.info(f"📅 多源调度器初始化 - 全局启用: {self.scheduler_enabled}")
        if self.scheduler_enabled:
            self._log_schedule_config()
        
        # 检查是否需要 RSSHub，如果需要则启动
        self._ensure_rsshub_if_needed()
    
    def _log_schedule_config(self):
        """记录调度配置信息"""
        logger.info("⏰ 定时任务配置：")
        for source, config in self.sources_config.items():
            if config.get("enabled", False):
                logger.info(f"   ✅ {source}: {config.get('time', '未设置')} (最多{config.get('max_results', 10)}条)")
            else:
                logger.info(f"   ❌ {source}: 已禁用")
    
    def _needs_rsshub(self) -> bool:
        """检查配置中是否有使用 RSSHub 的 RSS 源"""
        try:
            config_manager = get_config()
            rss_sources = config_manager.get_rss_sources(enabled_only=True)
            
            for source_config in rss_sources.values():
                url = source_config.url
                if url and "localhost:8878" in url:
                    return True
            return False
        except Exception as e:
            logger.warning(f"检查 RSSHub 需求时出错: {str(e)}")
            return False
    
    def _ensure_rsshub_if_needed(self):
        """如果需要 RSSHub，确保它正在运行"""
        if not self._needs_rsshub():
            return
        
        logger.info("🔍 检测到配置中使用了 RSSHub 源，正在检查 RSSHub 服务...")
        
        try:
            rsshub_manager = get_rsshub_manager()
            if rsshub_manager.ensure_running():
                logger.info("✅ RSSHub 服务已就绪")
            else:
                logger.warning("⚠️ RSSHub 服务启动失败，RSS 源可能无法正常工作")
                logger.warning("   提示: 请确保已安装 Docker 和 Docker Compose")
        except Exception as e:
            logger.warning(f"⚠️ 启动 RSSHub 时出错: {str(e)}")
            logger.warning("   RSS 源可能无法正常工作，请手动启动 RSSHub 或检查 Docker 环境")
    
    async def sync_arxiv(self, max_results: int = 20):
        """同步arXiv论文"""
        logger.info(f"📄 开始同步arXiv论文 - 最多{max_results}篇/分类")
        
        try:
            # 加载配置，检查哪些分类启用
            config_manager = get_config()
            arxiv_config = config_manager.get_arxiv_categories(enabled_only=False)
            
            total_papers = 0
            failed_categories = []
            
            # === 输出：一天一个 arxiv 汇总文件，分类作为“批次”增量写回 ===
            daily_dir = self.output_manager.get_daily_dir()
            daily_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y%m%d")
            output_file = daily_dir / f"arxiv_{date_str}.json"

            # 读取或初始化当日汇总结构
            if output_file.exists():
                try:
                    with open(output_file, "r", encoding="utf-8") as f:
                        aggregated_data = json.load(f)
                except Exception:
                    aggregated_data = {
                        "source": "arXiv",
                        "fetched_at": datetime.now().isoformat(),
                        "total_categories": 0,
                        "total_count": 0,
                        "papers": [],
                    }
            else:
                aggregated_data = {
                    "source": "arXiv",
                    "fetched_at": datetime.now().isoformat(),
                    "total_categories": 0,
                    "total_count": 0,
                    "papers": [],
                }

            existing_papers = aggregated_data.get("papers", [])
            existing_ids = {p.get("id") for p in existing_papers if p.get("id")}
            
            for category_key, category_name in ARXIV_CATEGORIES.items():
                # 将类别键转换为配置键（cs.AI -> cs_ai）
                config_key = category_key.replace(".", "_").lower()
                category_config = arxiv_config.get(config_key)
                
                # 检查是否启用
                if category_config and not category_config.enabled:
                    logger.info(f"跳过禁用的分类: {category_name}")
                    continue
                
                try:
                    # 获取周一标志（周一需要获取更多论文，因为包含周末积累）
                    is_monday = datetime.now().weekday() == 0
                    fetch_limit = max_results * 1.5 if is_monday else max_results
                    
                    logger.info(f"同步分类: {category_name} ({category_key}) - 最多{int(fetch_limit)}篇")
                    
                    result = await fetch_arxiv_papers(
                        category=category_key,
                        max_results=int(fetch_limit)
                    )
                    
                    if "error" in result:
                        logger.error(f"同步失败 {category_name}: {result['error']}")
                        failed_categories.append(category_key)
                    else:
                        new_papers = result.get("papers", []) or []
                        paper_count = len(new_papers)
                        total_papers += paper_count

                        # 合并到当日汇总（按 id 去重）
                        added = 0
                        for paper in new_papers:
                            pid = paper.get("id")
                            if pid and pid in existing_ids:
                                continue
                            existing_papers.append(paper)
                            if pid:
                                existing_ids.add(pid)
                            added += 1

                        aggregated_data["papers"] = existing_papers
                        aggregated_data["total_count"] = len(existing_papers)
                        aggregated_data["total_categories"] = aggregated_data.get("total_categories", 0) + 1
                        aggregated_data["fetched_at"] = datetime.now().isoformat()

                        # 每处理完一个分类就写回文件，保证中途异常不会丢失已抓取的数据
                        self.output_manager._write_json(output_file, aggregated_data)
                        logger.info(
                            f"✅ {category_name}: 本次获取{paper_count}篇，新增{added}篇 (当日累计{len(existing_papers)}篇) | 输出: {output_file.name}"
                        )
                    
                    # 避免过快请求API
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"同步异常 {category_name}: {str(e)}")
                    failed_categories.append(category_key)
            
            # 更新统计信息
            self.sync_stats["success_count"] += 1
            if failed_categories:
                self.sync_stats["failed_sources"].extend(
                    [f"arxiv_{cat}" for cat in failed_categories])
            
            logger.info(
                f"✅ arXiv同步完成: 本轮共抓取{total_papers}篇论文，当日文件累计{len(aggregated_data.get('papers', []))}篇，失败{len(failed_categories)}个分类 | 文件: {output_file.name}"
            )
            
        except Exception as e:
            logger.error(f"arXiv同步总体失败: {str(e)}")
            self.sync_stats["failed_sources"].append("arxiv_all")
    
    async def sync_hackernews(self, max_results: int = 15):
        """同步HackerNews新闻"""
        logger.info(f"📰 开始同步HackerNews - 最多{max_results}条")
        
        try:
            result = await fetch_ai_news(
                source="hackernews",
                limit=max_results
            )
            
            if result.success:
                logger.info(f"✅ HackerNews同步完成: {result.total_count}条新闻")

                # 可选：根据配置决定是否自动同步到Notion
                try:
                    config_manager = get_config()
                    notion_cfg = config_manager.get_notion_config() or {}
                    auto_sync_cfg = notion_cfg.get("auto_sync", {})
                    hn_auto = bool(auto_sync_cfg.get("hackernews", False))
                    
                    if hn_auto:
                        self._sync_hackernews_items_to_notion(result.items)
                except Exception as notion_error:
                    logger.debug(f"HackerNews Notion自动同步检查失败: {notion_error}")

                self.sync_stats["success_count"] += 1
            else:
                logger.error(f"❌ HackerNews同步失败: {result.error}")
                self.sync_stats["failed_sources"].append("hackernews")
                
        except Exception as e:
            logger.error(f"❌ HackerNews同步异常: {str(e)}")
            self.sync_stats["failed_sources"].append("hackernews")
    
    async def sync_rss(self, max_results: int = 10):
        """同步RSS订阅源"""
        logger.info(f"📺 开始同步RSS订阅 - 最多{max_results}条/源")
        
        try:
            config_manager = get_config()
            rss_urls = config_manager.get_rss_feed_urls()
            
            if not rss_urls:
                logger.warning("⚠️ 没有可用的RSS订阅源")
                return
            
            logger.info(f"同步 {len(rss_urls)} 个RSS源")
            result = await fetch_rss_feeds(
                feed_urls=list(rss_urls.values()),
                limit=max_results
            )
            
            # fetch_rss_feeds 返回的是字典，不是对象
            if isinstance(result, dict):
                total_items = result.get("total_items", 0)
                feeds_count = result.get("feeds_count", 0)
                errors_count = result.get("errors_count", 0)
                
                # 保存RSS数据到文件（当天追加到同一个文件）
                try:
                    daily_dir = self.output_manager.get_daily_dir()
                    # 确保目录存在
                    daily_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 查找当天是否已有RSS文件
                    existing_files = list(daily_dir.glob("rss_*.json"))
                    
                    if existing_files:
                        # 使用最新的文件
                        existing_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        output_file = existing_files[0]
                        
                        # 读取并追加
                        with open(output_file, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        
                        # RSS返回格式是 {feeds: {feed1: {items: []}, feed2: {items: []}}}
                        # 需要从所有feeds中提取items
                        new_feeds = result.get("feeds", {})
                        new_items = []
                        for feed_name, feed_data in new_feeds.items():
                            if isinstance(feed_data, dict):
                                feed_items = feed_data.get("items", [])
                                new_items.extend(feed_items)
                        
                        # 合并到existing_data的feeds结构中
                        existing_feeds = existing_data.get("feeds", {})
                        
                        # 合并每个feed的items（去重）
                        for feed_name, new_feed_data in new_feeds.items():
                            if feed_name in existing_feeds:
                                # 已存在该feed，合并items
                                existing_feed = existing_feeds[feed_name]
                                existing_items = existing_feed.get("items", [])
                                new_items = new_feed_data.get("items", [])
                                
                                # 去重（基于link）
                                existing_links = {item.get("link") for item in existing_items}
                                for item in new_items:
                                    if item.get("link") not in existing_links:
                                        existing_items.append(item)
                                
                                # 更新items和计数
                                existing_feed["items"] = existing_items
                                existing_feed["items_count"] = len(existing_items)
                                existing_feed["updated"] = datetime.now().isoformat()
                            else:
                                # 新feed，直接添加
                                existing_feeds[feed_name] = new_feed_data
                        
                        existing_data["feeds"] = existing_feeds
                        
                        # 重新计算总items数量（从所有feeds中统计）
                        total_count = 0
                        for feed_name, feed_data in existing_feeds.items():
                            if isinstance(feed_data, dict):
                                total_count += len(feed_data.get("items", []))
                        
                        existing_data["total_items"] = total_count
                        existing_data["updated_at"] = datetime.now().isoformat()
                        
                        self.output_manager._write_json(output_file, existing_data)
                        
                        # 同步新增的items到Notion
                        if new_items:
                            self._sync_rss_items_to_notion(new_items)
                        
                        if errors_count > 0:
                            logger.warning(f"⚠️ RSS同步部分失败: 追加{total_items}条 (累计{total_count}条)，{errors_count}个源失败 | 输出: {output_file.name}")
                        else:
                            logger.info(f"✅ RSS同步完成: 追加{total_items}条 (累计{total_count}条) | 输出: {output_file.name}")
                    else:
                        # 创建新文件
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = daily_dir / f"rss_{timestamp}.json"
                        self.output_manager._write_json(output_file, result)
                        
                        # 同步所有items到Notion
                        all_items = []
                        for feed_name, feed_data in result.get("feeds", {}).items():
                            if isinstance(feed_data, dict):
                                all_items.extend(feed_data.get("items", []))
                        if all_items:
                            self._sync_rss_items_to_notion(all_items)
                        
                        if errors_count > 0:
                            logger.warning(f"⚠️ RSS同步部分失败: {total_items}条内容，来自{feeds_count}个源，{errors_count}个源失败 | 输出: {output_file.name}")
                        else:
                            logger.info(f"✅ RSS同步完成: {total_items}条内容，来自{feeds_count}个源 | 输出: {output_file.name}")
                    
                    self.sync_stats["success_count"] += 1
                except Exception as save_error:
                    logger.error(f"❌ 保存RSS结果失败: {save_error}")
                    self.sync_stats["failed_sources"].append("rss_save")
            else:
                logger.error(f"❌ RSS同步失败: 返回数据格式错误")
                self.sync_stats["failed_sources"].append("rss")
                
        except Exception as e:
            logger.error(f"❌ RSS同步异常: {str(e)}")
            self.sync_stats["failed_sources"].append("rss")
    
    def _sync_rss_items_to_notion(self, items: list) -> None:
        """
        将RSS items同步到Notion（受配置开关控制）
        
        Args:
            items: RSS items列表（字典格式）
        """
        try:
            # 根据配置判断是否开启 RSS 自动同步
            config_manager = get_config()
            notion_cfg = config_manager.get_notion_config() or {}
            auto_sync_cfg = notion_cfg.get("auto_sync", {})
            rss_auto = bool(auto_sync_cfg.get("rss", False))
            
            if not rss_auto:
                logger.debug("RSS Notion自动同步已在配置中关闭，跳过同步")
                return

            try:
                from .utils.notion_sync import get_notion_sync
                from .models import ArticleItem
            except ImportError:
                from src.msgskill.utils.notion_sync import get_notion_sync
                from src.msgskill.models import ArticleItem
            
            notion_sync = get_notion_sync()
            if not notion_sync or not notion_sync.enabled:
                return
            
            # 转换RSS items为ArticleItem
            article_items = []
            for item in items:
                try:
                    # RSS格式: {title, link, summary, published, author, tags, ai_score}
                    article = ArticleItem(
                        title=item.get("title", ""),
                        summary=item.get("summary", "")[:300],  # 限制长度
                        source_url=item.get("link", ""),
                        published_date=item.get("published"),
                        source_type="rss",
                        article_tag=item.get("article_tag", "AI资讯"),
                        author=item.get("author"),
                        tags=item.get("tags", []),
                        ai_score=item.get("ai_score")
                    )
                    article_items.append(article)
                except Exception as e:
                    logger.debug(f"跳过无效的RSS item: {e}")
                    continue
            
            if article_items:
                result = notion_sync.sync_items(article_items, skip_existing=True)
                if result.get("synced", 0) > 0:
                    logger.info(f"📝 已同步 {result['synced']} 条RSS内容到Notion")
        except Exception as e:
            logger.debug(f"RSS Notion同步失败: {e}")

    def _sync_github_items_to_notion(self, items: list) -> None:
        """
        将GitHub items同步到Notion（受配置开关控制）
        
        items 可能是 ArticleItem 列表或 dict 列表
        """
        try:
            try:
                from .utils.notion_sync import get_notion_sync
                from .models import ArticleItem
            except ImportError:
                from src.msgskill.utils.notion_sync import get_notion_sync
                from src.msgskill.models import ArticleItem
            
            notion_sync = get_notion_sync()
            if not notion_sync or not notion_sync.enabled:
                return
            
            article_items = []
            for item in items or []:
                try:
                    if isinstance(item, ArticleItem):
                        article_items.append(item)
                    elif isinstance(item, dict):
                        article_items.append(ArticleItem(**item))
                except Exception as e:
                    logger.debug(f"跳过无效的GitHub item: {e}")
                    continue
            
            if article_items:
                result = notion_sync.sync_items(article_items, skip_existing=True)
                if result.get("synced", 0) > 0:
                    logger.info(f"📝 已同步 {result['synced']} 条GitHub项目到Notion")
        except Exception as e:
            logger.debug(f"GitHub Notion同步失败: {e}")

    def _sync_hackernews_items_to_notion(self, items: list) -> None:
        """
        将HackerNews items同步到Notion（受配置开关控制）
        
        items 可能是 ArticleItem 列表或 dict 列表
        """
        try:
            try:
                from .utils.notion_sync import get_notion_sync
                from .models import ArticleItem
            except ImportError:
                from src.msgskill.utils.notion_sync import get_notion_sync
                from src.msgskill.models import ArticleItem

            notion_sync = get_notion_sync()
            if not notion_sync or not notion_sync.enabled:
                return

            article_items = []
            for item in items or []:
                try:
                    if isinstance(item, ArticleItem):
                        article_items.append(item)
                    elif isinstance(item, dict):
                        article_items.append(ArticleItem(**item))
                except Exception as e:
                    logger.debug(f"跳过无效的HackerNews item: {e}")
                    continue

            if article_items:
                result = notion_sync.sync_items(article_items, skip_existing=True)
                if result.get("synced", 0) > 0:
                    logger.info(f"📝 已同步 {result['synced']} 条HackerNews内容到Notion")
        except Exception as e:
            logger.debug(f"HackerNews Notion同步失败: {e}")
    
    async def sync_github(self, max_results: int = 20):
        """同步GitHub趋势项目"""
        logger.info(f"🐙 开始同步GitHub趋势 - 最多{max_results}个项目")
        
        try:
            result = await fetch_github_trending(limit=max_results)
            
            if result.success:
                logger.info(f"✅ GitHub同步完成: {result.total_count}个趋势项目")
                
                # 可选：根据配置决定是否自动同步到Notion
                try:
                    config_manager = get_config()
                    notion_cfg = config_manager.get_notion_config() or {}
                    auto_sync_cfg = notion_cfg.get("auto_sync", {})
                    github_auto = bool(auto_sync_cfg.get("github", False))
                    
                    if github_auto:
                        self._sync_github_items_to_notion(result.items)
                except Exception as notion_error:
                    logger.debug(f"GitHub Notion自动同步检查失败: {notion_error}")
                
                self.sync_stats["success_count"] += 1
            else:
                logger.error(f"❌ GitHub同步失败: {result.error}")
                self.sync_stats["failed_sources"].append("github")
                
        except Exception as e:
            logger.error(f"❌ GitHub同步异常: {str(e)}")
            self.sync_stats["failed_sources"].append("github")
    
    async def sync_wechat_topics(self):
        """评估当日公众号选题（RSS + HackerNews 数据）"""
        logger.info("📱 开始公众号选题评估任务...")
        try:
            evaluator = get_wechat_topic_evaluator()
            result = await evaluator.evaluate()
            selected = result.get("selected_count", 0)
            total = result.get("total_evaluated", 0)
            logger.info(f"✅ 公众号选题评估完成：共评估 {total} 条，筛选出 {selected} 条推荐选题")
            self.sync_stats["success_count"] += 1
        except Exception as e:
            logger.error(f"❌ 公众号选题评估异常: {str(e)}")
            self.sync_stats["failed_sources"].append("wechat_topics")
    
    def create_sync_job(self, source_name: str, sync_func):
        """创建同步任务包装器"""
        def wrapper():
            logger.info(f"🚀 执行{source_name}定时同步...")
            asyncio.run(sync_func())
        return wrapper
    
    def start(self):
        """启动调度器"""
        if not self.scheduler_enabled:
            logger.warning("⚠️ 调度器全局禁用，如需启用请修改配置")
            return
        
        # 确保 RSSHub 运行（如果需要）
        self._ensure_rsshub_if_needed()
        
        logger.info("🚀 多源调度器启动")
        logger.info("💡 提示: 如需启动时立即执行一次，请使用 --once 参数")
        
        # 设置定时任务
        scheduled_count = 0
        
        for source, config in self.sources_config.items():
            if config.get("enabled", False):
                time_config = config.get("time")
                max_results = config.get("max_results", 10)
                
                if not time_config:
                    logger.warning(f"⚠️ {source}已启用但未设置时间，跳过")
                    continue
                
                # 支持单个时间字符串或时间数组
                if isinstance(time_config, str):
                    time_list = [time_config]
                elif isinstance(time_config, list):
                    time_list = time_config
                else:
                    logger.warning(f"⚠️ {source}的时间配置格式错误，跳过")
                    continue
                
                # 根据源类型选择同步函数
                sync_func = None
                if source == "arxiv":
                    sync_func = lambda mr=max_results: self.sync_arxiv(mr)
                elif source == "hackernews":
                    sync_func = lambda mr=max_results: self.sync_hackernews(mr)
                elif source == "rss":
                    sync_func = lambda mr=max_results: self.sync_rss(mr)
                elif source == "github":
                    sync_func = lambda mr=max_results: self.sync_github(mr)
                elif source == "wechat_topics":
                    sync_func = lambda: self.sync_wechat_topics()
                
                if sync_func:
                    # 为每个时间点创建一个任务
                    for time_str in time_list:
                        job = schedule.every().day.at(time_str).do(self.create_sync_job(source, sync_func))
                        scheduled_count += 1
                        next_run = job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else '未知'
                        logger.info(f"⏰ 已安排{source}任务: {time_str} (下次执行: {next_run})")
                    
                    # 日志显示所有时间点
                    times_display = ", ".join(time_list)
                    logger.info(f"✅ {source}任务配置完成: {times_display}")
        
        if scheduled_count == 0:
            logger.warning("⚠️ 没有可执行的定时任务，请检查配置")
            return
        
        logger.info(f"⏰ 共安排{scheduled_count}个定时任务，等待执行...")
        
        # 运行调度循环
        logger.info("🔄 开始调度循环，每分钟检查一次...")
        current_time = datetime.now()
        logger.info(f"📋 当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 显示所有已注册的任务
        all_jobs = schedule.get_jobs()
        if all_jobs:
            logger.info(f"📋 已注册的任务列表（共 {len(all_jobs)} 个）:")
            for job in all_jobs:
                next_run = job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else '未知'
                job_name = getattr(job.job_func, '__name__', 'unknown')
                logger.info(f"   - {job_name}: 下次执行 {next_run}")
        else:
            logger.warning("⚠️ 没有已注册的定时任务！")
        
        check_count = 0
        while True:
            now = datetime.now()
            check_count += 1
            
            # 每10次检查（约10分钟）输出一次状态
            if check_count % 10 == 0:
                pending_jobs = schedule.get_jobs()
                logger.info(f"⏰ [{now.strftime('%H:%M:%S')}] 调度器运行中，共 {len(pending_jobs)} 个任务")
                for job in pending_jobs:
                    next_run = job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else '未知'
                    logger.info(f"   下次执行: {next_run}")
            
            # 执行到期的任务
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    async def run_all_sources_async(self):
        """异步执行所有已启用的同步任务"""
        tasks = []
        
        for source, config in self.sources_config.items():
            if config.get("enabled", False):
                max_results = config.get("max_results", 10)
                
                if source == "arxiv":
                    tasks.append(self.sync_arxiv(max_results))
                elif source == "hackernews":
                    tasks.append(self.sync_hackernews(max_results))
                elif source == "rss":
                    tasks.append(self.sync_rss(max_results))
                elif source == "github":
                    tasks.append(self.sync_github(max_results))
                elif source == "wechat_topics":
                    tasks.append(self.sync_wechat_topics())
        
        if tasks:
            await asyncio.gather(*tasks)
        else:
            logger.warning("⚠️ 没有启用的同步任务")
    
    def run_once(self):
        """立即执行所有已启用的同步任务（用于测试）"""
        # 确保 RSSHub 运行（如果需要）
        self._ensure_rsshub_if_needed()
        
        logger.info("⚡ 立即执行所有已启用的同步任务...")
        asyncio.run(self.run_all_sources_async())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计信息"""
        return {
            "scheduler_enabled": self.scheduler_enabled,
            "sources_count": len(self.sources_config),
            "enabled_sources": [
                source for source, config in self.sources_config.items() 
                if config.get("enabled", False)
            ],
            "total_syncs": self.sync_stats["total_syncs"],
            "success_count": self.sync_stats["success_count"],
            "failed_sources": self.sync_stats["failed_sources"],
            "last_sync_time": self.sync_stats["last_sync_time"]
        }


def main():
    """主函数 - 启动多源调度器"""
    import argparse
    
    parser = argparse.ArgumentParser(description="多数据源定时同步调度器")
    parser.add_argument("--once", action="store_true", help="立即执行一次同步后退出")
    
    args = parser.parse_args()
    
    scheduler = MultiSourceScheduler()
    
    if args.once:
        scheduler.run_once()
    else:
        scheduler.start()


if __name__ == "__main__":
    main()