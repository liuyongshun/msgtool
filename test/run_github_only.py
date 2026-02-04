#!/usr/bin/env python3
"""
运行GitHub数据源测试
功能：仅运行GitHub趋势数据抓取
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.msgskill.tools.github_fetcher import fetch_github_trending
from src.msgskill.utils.logger import logger
from src.msgskill.output import get_output_manager

async def main():
    """运行GitHub数据源测试"""
    logger.info("🚀 开始GitHub数据源测试...")
    
    try:
        # 运行GitHub抓取
        start_time = datetime.now()
        result = await fetch_github_trending(limit=50)  # 限制为50个项目测试
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        if result.success:
            logger.info(f"✅ GitHub抓取成功！")
            logger.info(f"   项目数量: {result.total_count}")
            logger.info(f"   耗时: {elapsed:.2f}秒")
            
            # 保存输出
            output_manager = get_output_manager()
            output_file = output_manager.save_result(result)
            logger.info(f"   输出文件: {output_file.relative_to(output_manager.base_dir.parent)}")
            
            # 显示前5个项目摘要
            logger.info("📋 前5个项目摘要:")
            for i, item in enumerate(result.items[:5]):
                logger.info(f"   {i+1}. {item.title}")
                logger.info(f"     摘要: {item.summary[:100]}...")
                logger.info(f"     URL: {item.source_url}")
                logger.info(f"     标签: {', '.join(item.tags[:3]) if item.tags else '无'}")
                logger.info("")
                
        else:
            logger.error(f"❌ GitHub抓取失败: {result.error}")
            
    except Exception as e:
        logger.error(f"❌ GitHub测试异常: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())