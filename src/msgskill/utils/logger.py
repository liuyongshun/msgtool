"""
日志输出工具 (Logger)

功能: 提供统一的日志输出接口，用于输出执行状态和错误信息
"""

import sys
from datetime import datetime
from typing import Optional


class Logger:
    """简单的日志输出类"""
    
    @staticmethod
    def debug(message: str):
        """输出调试信息（静默模式，后台运行时减少输出）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 🔧 {message}", file=sys.stdout)
    
    @staticmethod
    def info(message: str):
        """输出信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ℹ️  {message}", file=sys.stdout)
    
    @staticmethod
    def success(message: str):
        """输出成功信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ✅ {message}", file=sys.stdout)
    
    @staticmethod
    def warning(message: str):
        """输出警告信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ⚠️  {message}", file=sys.stderr)
    
    @staticmethod
    def error(message: str):
        """输出错误信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ❌ {message}", file=sys.stderr)
    
    @staticmethod
    def source_success(source_name: str, count: int):
        """输出数据源成功信息"""
        Logger.success(f"{source_name}: 成功抓取 {count} 条数据")
    
    @staticmethod
    def source_error(source_name: str, error: str):
        """输出数据源失败信息"""
        Logger.error(f"{source_name}: 抓取失败 - {error}")
    
    @staticmethod
    def source_skipped(source_name: str, reason: str):
        """输出数据源跳过信息"""
        Logger.warning(f"{source_name}: 跳过 - {reason}")


# 创建全局logger实例
logger = Logger()
