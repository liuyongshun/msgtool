"""
定时任务调度器 - 用于定时同步arXiv论文和其他数据源

功能：
- 支持每日定时同步arXiv论文（默认每天早上9:00）
- 支持灵活的调度配置
- 记录同步日志和统计信息
"""

import asyncio
import schedule
import time
from datetime import datetime
from typing import Optional

from .tools.arxiv_fetcher import fetch_arxiv_papers, ARXIV_CATEGORIES
from .utils.logger import logger
from .config import get_config


class ArxivScheduler:
    """arXiv论文同步调度器"""
    
    def __init__(self, sync_time: str = "09:00", max_results: int = 20):
        """
        初始化调度器
        
        Args:
            sync_time: 同步时间，格式 "HH:MM"（24小时制）
            max_results: 每个分类最多获取的论文数
        """
        self.sync_time = sync_time
        self.max_results = max_results
        self.last_sync_time: Optional[datetime] = None
        self.sync_stats = {
            "total_syncs": 0,
            "total_papers": 0,
            "failed_categories": []
        }
    
    async def sync_all_categories(self):
        """同步所有arXiv分类的论文"""
        logger.info(f"开始同步arXiv论文 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 加载配置，检查哪些分类启用
        config_manager = get_config()
        arxiv_config = config_manager.get_arxiv_categories(enabled_only=False)
        
        total_papers = 0
        failed_categories = []
        
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
                fetch_limit = self.max_results * 1.5 if is_monday else self.max_results
                
                logger.info(f"同步分类: {category_name} ({category_key}) - 最多{int(fetch_limit)}篇")
                
                result = await fetch_arxiv_papers(
                    category=category_key,
                    max_results=int(fetch_limit)
                )
                
                if "error" in result:
                    logger.error(f"同步失败 {category_name}: {result['error']}")
                    failed_categories.append(category_key)
                else:
                    paper_count = result.get("count", 0)
                    total_papers += paper_count
                    logger.info(f"✅ {category_name}: {paper_count} 篇论文")
                
                # 避免过快请求API
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"同步异常 {category_name}: {str(e)}")
                failed_categories.append(category_key)
        
        # 更新统计信息
        self.last_sync_time = datetime.now()
        self.sync_stats["total_syncs"] += 1
        self.sync_stats["total_papers"] += total_papers
        self.sync_stats["failed_categories"] = failed_categories
        
        # 输出统计
        logger.info("=" * 60)
        logger.info(f"📊 同步完成统计:")
        logger.info(f"   总论文数: {total_papers}")
        logger.info(f"   成功分类: {len(ARXIV_CATEGORIES) - len(failed_categories)}/{len(ARXIV_CATEGORIES)}")
        if failed_categories:
            logger.warning(f"   失败分类: {', '.join(failed_categories)}")
        logger.info("=" * 60)
    
    def sync_job(self):
        """同步任务包装器（用于schedule库）"""
        asyncio.run(self.sync_all_categories())
    
    def start(self):
        """启动调度器"""
        logger.info(f"🚀 arXiv调度器启动")
        logger.info(f"   同步时间: 每天 {self.sync_time}")
        logger.info(f"   获取数量: 每个分类最多{self.max_results}篇（周一1.5倍）")
        logger.info(f"   分类总数: {len(ARXIV_CATEGORIES)}")
        
        # 设置定时任务
        schedule.every().day.at(self.sync_time).do(self.sync_job)
        
        logger.info("⏰ 等待下次同步...")
        logger.info(f"   下次同步: 今天 {self.sync_time}")
        
        # 运行调度循环
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def run_once(self):
        """立即执行一次同步（用于测试）"""
        logger.info("⚡ 立即执行一次同步...")
        self.sync_job()
    
    def get_stats(self) -> dict:
        """获取同步统计信息"""
        return {
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "total_syncs": self.sync_stats["total_syncs"],
            "total_papers": self.sync_stats["total_papers"],
            "failed_categories": self.sync_stats["failed_categories"],
            "sync_time": self.sync_time,
            "max_results": self.max_results
        }


def main():
    """主函数 - 启动调度器"""
    import argparse
    
    parser = argparse.ArgumentParser(description="arXiv论文同步调度器")
    parser.add_argument("--time", default="09:00", help="同步时间（HH:MM格式）")
    parser.add_argument("--limit", type=int, default=20, help="每个分类最多获取论文数")
    parser.add_argument("--once", action="store_true", help="立即执行一次同步后退出")
    
    args = parser.parse_args()
    
    scheduler = ArxivScheduler(sync_time=args.time, max_results=args.limit)
    
    if args.once:
        scheduler.run_once()
    else:
        scheduler.start()


if __name__ == "__main__":
    main()