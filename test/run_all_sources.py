#!/usr/bin/env python3
"""
一键执行所有数据源同步脚本
功能：同时运行四个数据源的同步任务，并生成详细的执行报告

使用方式：
python test/run_all_sources.py         # 标准运行
python test/run_all_sources.py --fast  # 快速模式（减少数据量）
python test/run_all_sources.py --debug # 调试模式（详细日志）
"""

import asyncio
import argparse
import sys
import time
from datetime import datetime
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.msgskill.tools.arxiv_fetcher import fetch_arxiv_papers, ARXIV_CATEGORIES
    from src.msgskill.tools.news_scraper import fetch_ai_news
    from src.msgskill.tools.rss_reader import fetch_rss_feeds
    from src.msgskill.tools.github_fetcher import fetch_github_trending
    from src.msgskill.utils.logger import logger
    from src.msgskill.config import get_config
    from src.msgskill.output import get_output_manager
    from src.msgskill.models import FetchResult
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)


class AllSourcesRunner:
    """一键运行所有数据源同步器"""
    
    def __init__(self, fast_mode=False, debug_mode=False):
        self.fast_mode = fast_mode
        self.debug_mode = debug_mode
        self.config_manager = get_config()
        self.settings = self.config_manager.global_settings
        
        # 初始化输出管理器
        self.output_manager = get_output_manager()
        
        self.results = {
            "start_time": datetime.now().isoformat(),
            "sources": {},
            "total_sources": 0,
            "succeeded": 0,
            "failed": 0,
            "elapsed_time": 0,
            "output_files": []  # 记录生成的文件
        }
    
    async def run_arxiv(self):
        """运行arXiv论文同步"""
        source_name = "arxiv"
        logger.info(f"🚀 开始同步arXiv论文...")
        
        # 从配置文件读取max_results，快速模式使用较小值测试
        config_max = self.settings.scheduler.get("sources", {}).get("arxiv", {}).get("max_results", 50)
        max_results = min(10, config_max) if self.fast_mode else config_max
        
        try:
            start_time = time.time()
            result = await fetch_arxiv_papers(category="cs.AI", max_results=max_results)
            elapsed = time.time() - start_time
            
            # 处理不同的返回格式
            if isinstance(result, dict):
                success = "error" not in result
                count = result.get("count", 0) if success else 0
                error_msg = result.get("error", None) if not success else None
            else:
                success = getattr(result, "success", False)
                count = getattr(result, "count", 0) if success else 0
                error_msg = getattr(result, "error", None) if not success else None
            
            self.results["sources"][source_name] = {
                "success": success,
                "count": count,
                "elapsed": round(elapsed, 2),
                "error": error_msg
            }
            
            # 保存结果到文件
            if success:
                try:
                    # 如果是字典，需要转换为FetchResult或直接保存
                    if isinstance(result, dict):
                        # 手动创建输出文件
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = self.output_manager.get_daily_dir() / f"arxiv_{timestamp}.json"
                        self.output_manager._write_json(output_file, result)
                        output_info = f" | 输出: {output_file.relative_to(self.output_manager.base_dir.parent)}"
                        self.results["output_files"].append(str(output_file))
                    elif hasattr(result, 'source_type'):
                        output_file = self.output_manager.save_result(result)
                        output_info = f" | 输出: {output_file.relative_to(self.output_manager.base_dir.parent)}"
                        self.results["output_files"].append(str(output_file))
                    else:
                        output_info = ""
                except Exception as save_error:
                    output_info = f" | 输出失败: {save_error}"
                    logger.error(f"❌ 保存{source_name}结果失败: {save_error}")
            else:
                output_info = ""
            
            if success:
                logger.info(f"✅ arXiv同步成功: {count}篇论文 ({elapsed:.2f}s){output_info}")
                self.results["succeeded"] += 1
            else:
                logger.error(f"❌ arXiv同步失败: {error_msg}")
                self.results["failed"] += 1
                
        except Exception as e:
            logger.error(f"❌ arXiv同步异常: {str(e)}")
            self.results["sources"][source_name] = {
                "success": False,
                "count": 0,
                "elapsed": 0,
                "error": str(e)
            }
            self.results["failed"] += 1
    
    async def run_hackernews(self):
        """运行HackerNews同步"""
        source_name = "hackernews"
        logger.info(f"🚀 开始同步HackerNews...")
        
        # 从配置文件读取max_results，快速模式使用较小值测试
        config_max = self.settings.scheduler.get("sources", {}).get("hackernews", {}).get("max_results", 50)
        max_results = min(10, config_max) if self.fast_mode else config_max
        
        try:
            start_time = time.time()
            result = await fetch_ai_news(source="hackernews", limit=max_results)
            elapsed = time.time() - start_time
            
            self.results["sources"][source_name] = {
                "success": result.success,
                "count": result.total_count if result.success else 0,
                "elapsed": round(elapsed, 2),
                "error": result.error if not result.success else None
            }
            
            # 保存结果到文件
            if result.success and hasattr(result, 'source_type'):
                try:
                    output_file = self.output_manager.save_result(result)
                    output_info = f" | 输出: {output_file.relative_to(self.output_manager.base_dir.parent)}"
                    self.results["output_files"].append(str(output_file))
                except Exception as save_error:
                    output_info = f" | 输出失败: {save_error}"
                    logger.error(f"❌ 保存HackerNews结果失败: {save_error}")
            else:
                output_info = ""
            
            if result.success:
                logger.info(f"✅ HackerNews同步成功: {result.total_count}条新闻 ({elapsed:.2f}s){output_info}")
                self.results["succeeded"] += 1
            else:
                logger.error(f"❌ HackerNews同步失败: {result.error}")
                self.results["failed"] += 1
                
        except Exception as e:
            logger.error(f"❌ HackerNews同步异常: {str(e)}")
            self.results["sources"][source_name] = {
                "success": False,
                "count": 0,
                "elapsed": 0,
                "error": str(e)
            }
            self.results["failed"] += 1
    
    async def run_rss(self):
        """运行RSS源同步"""
        source_name = "rss"
        logger.info(f"🚀 开始同步RSS订阅源...")
        
        # 从配置文件读取max_results，快速模式使用较小值测试
        config_max = self.settings.scheduler.get("sources", {}).get("rss", {}).get("max_results", 20)
        max_results = min(15, config_max) if self.fast_mode else config_max
        
        try:
            config_manager = get_config()
            rss_urls = config_manager.get_rss_feed_urls()
            
            if not rss_urls:
                logger.warning("⚠️ 没有可用的RSS订阅源")
                return
            
            # 快速模式下只取前3个源测试
            if self.fast_mode:
                test_urls = {k: rss_urls[k] for k in list(rss_urls.keys())[:3]}
                logger.info(f"快速模式: 测试 {len(test_urls)} 个RSS源")
            else:
                test_urls = rss_urls
            
            start_time = time.time()
            result = await fetch_rss_feeds(
                feed_urls=list(test_urls.values()),
                limit=max_results
            )
            elapsed = time.time() - start_time
            
            # 处理不同的返回格式
            if isinstance(result, dict):
                success = "error" not in result
                total_items = sum(len(feed.get("items", [])) for feed in result.get("feeds", {}).values()) if success else 0
                feeds_count = len(result.get("feeds", {})) if success else 0
                error_msg = result.get("error", None) if not success else None
            else:
                success = getattr(result, "success", False)
                feeds_dict = getattr(result, "feeds", {})
                total_items = sum(len(feed.get("items", [])) for feed in feeds_dict.values()) if success else 0
                feeds_count = len(feeds_dict) if success else 0
                error_msg = getattr(result, "error", None) if not success else None
            
            self.results["sources"][source_name] = {
                "success": success,
                "count": total_items,
                "sources_count": len(test_urls),
                "elapsed": round(elapsed, 2),
                "error": error_msg
            }
            
            # 保存结果到文件
            if success:
                try:
                    # 如果是字典，需要手动保存
                    if isinstance(result, dict):
                        # 手动创建输出文件
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = self.output_manager.get_daily_dir() / f"rss_{timestamp}.json"
                        self.output_manager._write_json(output_file, result)
                        output_info = f" | 输出: {output_file.relative_to(self.output_manager.base_dir.parent)}"
                        self.results["output_files"].append(str(output_file))
                    elif hasattr(result, 'source_type'):
                        output_file = self.output_manager.save_result(result)
                        output_info = f" | 输出: {output_file.relative_to(self.output_manager.base_dir.parent)}"
                        self.results["output_files"].append(str(output_file))
                    else:
                        output_info = ""
                except Exception as save_error:
                    output_info = f" | 输出失败: {save_error}"
                    logger.error(f"❌ 保存RSS结果失败: {save_error}")
            else:
                output_info = ""
            
            if success:
                logger.info(f"✅ RSS同步成功: {total_items}条内容，来自{feeds_count}个源 ({elapsed:.2f}s){output_info}")
                self.results["succeeded"] += 1
            else:
                logger.error(f"❌ RSS同步失败: {error_msg}")
                self.results["failed"] += 1
                
        except Exception as e:
            logger.error(f"❌ RSS同步异常: {str(e)}")
            self.results["sources"][source_name] = {
                "success": False,
                "count": 0,
                "sources_count": 0,
                "elapsed": 0,
                "error": str(e)
            }
            self.results["failed"] += 1
    
    async def run_github(self):
        """运行GitHub趋势同步"""
        source_name = "github"
        logger.info(f"🚀 开始同步GitHub趋势...")
        
        # 从配置文件读取max_results，快速模式使用较小值测试
        config_max = self.settings.scheduler.get("sources", {}).get("github", {}).get("max_results", 100)
        max_results = min(15, config_max) if self.fast_mode else config_max
        
        try:
            start_time = time.time()
            result = await fetch_github_trending(limit=max_results)
            elapsed = time.time() - start_time
            
            self.results["sources"][source_name] = {
                "success": result.success,
                "count": result.total_count if result.success else 0,
                "elapsed": round(elapsed, 2),
                "error": result.error if not result.success else None
            }
            
            # 保存结果到文件
            if result.success and hasattr(result, 'source_type'):
                try:
                    output_file = self.output_manager.save_result(result)
                    output_info = f" | 输出: {output_file.relative_to(self.output_manager.base_dir.parent)}"
                    self.results["output_files"].append(str(output_file))
                except Exception as save_error:
                    output_info = f" | 输出失败: {save_error}"
                    logger.error(f"❌ 保存GitHub结果失败: {save_error}")
            else:
                output_info = ""
            
            if result.success:
                logger.info(f"✅ GitHub同步成功: {result.total_count}个趋势项目 ({elapsed:.2f}s){output_info}")
                self.results["succeeded"] += 1
            else:
                logger.error(f"❌ GitHub同步失败: {result.error}")
                self.results["failed"] += 1
                
        except Exception as e:
            logger.error(f"❌ GitHub同步异常: {str(e)}")
            self.results["sources"][source_name] = {
                "success": False,
                "count": 0,
                "elapsed": 0,
                "error": str(e)
            }
            self.results["failed"] += 1
    
    async def run_all(self):
        """运行所有数据源同步"""
        logger.info("📋 开始执行所有数据源同步任务...")
        
        tasks = [
            self.run_arxiv(),
            self.run_hackernews(),
            self.run_rss(),
            self.run_github()
        ]
        
        # 并行执行所有任务，不捕获异常以便调试
        await asyncio.gather(*tasks)
        
        # 计算总时间
        total_time = datetime.now().timestamp() - datetime.fromisoformat(self.results["start_time"]).timestamp()
        self.results["elapsed_time"] = round(total_time, 2)
        self.results["total_sources"] = len(self.results["sources"])
        
        return self.results
    
    def print_summary(self):
        """打印执行摘要"""
        print("\n" + "="*60)
        print("📊 所有数据源同步结果摘要")
        print("="*60)
        
        for source, result in self.results["sources"].items():
            status = "✅ 成功" if result["success"] else "❌ 失败"
            count_info = f"({result['count']}条)"
            if source == "rss" and "sources_count" in result:
                count_info = f"({result['count']}条，{result['sources_count']}个源)"
            
            print(f"{source.upper():<12} {status:<8} {count_info:<15} {result['elapsed']}s")
            if not result["success"] and result["error"]:
                print(f"          错误: {result['error']}")
        
        print("-"*60)
        print(f"总计: {self.results['succeeded']}/{self.results['total_sources']} 个源成功")
        print(f"耗时: {self.results['elapsed_time']}秒")
        
        # 显示输出文件信息
        if self.results["output_files"]:
            print(f"输出文件: {len(self.results['output_files'])} 个")
            for file_path in self.results["output_files"]:
                relative_path = os.path.relpath(file_path, self.output_manager.base_dir.parent)
                print(f"  📄 {relative_path}")
        
        if self.results['succeeded'] == self.results['total_sources']:
            print("🎉 所有数据源同步成功！")
        else:
            print("⚠️  有部分数据源同步失败，请检查日志")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="一键运行所有数据源同步")
    parser.add_argument("--fast", action="store_true", help="快速模式（减少数据量）")
    parser.add_argument("--debug", action="store_true", help="调试模式（详细日志）")
    
    args = parser.parse_args()
    
    print(f"🚀 MsgSkill - 一键运行所有数据源同步")
    print(f"模式: {'快速' if args.fast else '标准'}{' + 调试' if args.debug else ''}")
    print("="*50)
    
    try:
        runner = AllSourcesRunner(fast_mode=args.fast, debug_mode=args.debug)
        results = await runner.run_all()
        runner.print_summary()
        
        # 退出码：所有成功返回0，有失败返回1
        exit_code = 0 if results['succeeded'] == results['total_sources'] else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n⏹️  用户中断执行")
        sys.exit(130)
    except Exception as e:
        print(f"💥 脚本执行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())