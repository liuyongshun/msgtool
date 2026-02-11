"""
输出管理模块 - 处理JSON输出到固定目录结构，支持增量产出
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
from .models import FetchResult, SearchResult


# 默认输出目录结构
DEFAULT_OUTPUT_DIR = Path("output")
OUTPUT_STRUCTURE = {
    "base": DEFAULT_OUTPUT_DIR,
    "daily": DEFAULT_OUTPUT_DIR / "daily"  # 按日期组织
}


class OutputManager:
    """输出管理器 - 管理JSON文件的输出和增量更新"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        初始化输出管理器
        
        Args:
            base_dir: 基础输出目录，默认为项目根目录下的 output/
        """
        if base_dir is None:
            # 默认使用项目根目录下的 output/
            base_dir = Path(__file__).parent.parent.parent / "output"
        
        self.base_dir = Path(base_dir)
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """确保所有必要的目录存在"""
        # 只确保daily目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.get_daily_dir().mkdir(parents=True, exist_ok=True)
    
    def get_daily_dir(self, date: Optional[datetime] = None) -> Path:
        """
        获取按日期组织的目录路径
        
        Args:
            date: 日期对象，默认为今天
            
        Returns:
            日期目录路径，格式: output/daily/YYYY-MM-DD/
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y-%m-%d")
        return self.base_dir / "daily" / date_str
    
    
    def save_result(
        self,
        result: Union[FetchResult, SearchResult],
        filename: Optional[str] = None
    ) -> Path:
        """
        保存抓取结果到文件（仅保存到daily目录）
        
        Args:
            result: 抓取结果对象
            filename: 自定义文件名（不含扩展名），默认使用时间戳
            
        Returns:
            保存的文件路径
        """
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if isinstance(result, FetchResult):
                source_type = result.source_type
                filename = f"{source_type}_{timestamp}"
            else:
                filename = f"search_{timestamp}"
        
        # 准备JSON数据
        json_data = result.model_dump(mode='json', exclude_none=True)
        
        # 保存到日期目录
        daily_dir = self.get_daily_dir()
        daily_dir.mkdir(parents=True, exist_ok=True)
        daily_file = daily_dir / f"{filename}.json"
        self._write_json(daily_file, json_data)
        
        # 可选：自动同步到Notion
        self._auto_sync_to_notion(result)
        
        return daily_file
    
    def save_incremental(
        self,
        result: FetchResult,
        append: bool = True
    ) -> Path:
        """
        增量保存结果（追加到当天的汇总文件）
        
        Args:
            result: 抓取结果对象
            append: 是否追加到现有文件，False则创建新文件
            
        Returns:
            保存的文件路径
        """
        daily_dir = self.get_daily_dir()
        daily_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件名格式: {source_type}_YYYY-MM-DD.json
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{result.source_type}_{date_str}.json"
        file_path = daily_dir / filename
        
        # 读取现有数据或创建新结构
        if append and file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # 追加新结果
            if isinstance(existing_data, list):
                existing_data.append(result.model_dump(mode='json', exclude_none=True))
            else:
                # 如果现有数据是单个对象，转换为列表
                existing_data = [existing_data, result.model_dump(mode='json', exclude_none=True)]
        else:
            # 创建新文件，使用列表格式
            existing_data = [result.model_dump(mode='json', exclude_none=True)]
        
        # 写入文件
        self._write_json(file_path, existing_data)
        
        # 可选：自动同步到Notion
        if isinstance(result, FetchResult):
            self._auto_sync_to_notion(result)
        
        return file_path
    
    def append_items_batch(
        self,
        source_type: str,
        items: list,
        batch_info: Optional[dict] = None
    ) -> Path:
        """
        批量追加items到当天文件（用于增量输出）
        
        适用场景：AI筛选后分批翻译+保存，避免一次性处理导致中途异常丢失所有数据
        
        Args:
            source_type: 数据源类型 (hackernews, github, etc.)
            items: ArticleItem列表
            batch_info: 批次信息（可选），如 {"batch": 1, "total_batches": 10}
            
        Returns:
            保存的文件路径
        """
        daily_dir = self.get_daily_dir()
        daily_dir.mkdir(parents=True, exist_ok=True)
        
        # 查找当天是否已有该source的文件（同一次执行周期内追加到同一个文件）
        existing_files = list(daily_dir.glob(f"{source_type}_*.json"))
        
        # 如果存在当天的文件，使用最新的一个（按修改时间排序）
        if existing_files:
            existing_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            file_path = existing_files[0]
        else:
            # 如果不存在，创建新文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{source_type}_{timestamp}.json"
            file_path = daily_dir / filename
        
        # 读取现有数据或创建新结构
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        else:
            # 创建新文件结构
            existing_data = {
                "success": True,
                "source_name": source_type.title(),
                "source_type": source_type,
                "fetched_at": datetime.now().isoformat(),
                "total_count": 0,
                "items": [],
                "batch_info": batch_info or {}
            }
        
        # 追加items
        for item in items:
            if hasattr(item, 'model_dump'):
                existing_data["items"].append(item.model_dump(mode='json', exclude_none=True))
            elif isinstance(item, dict):
                existing_data["items"].append(item)
        
        # 更新计数
        existing_data["total_count"] = len(existing_data["items"])
        
        # 更新批次信息
        if batch_info:
            existing_data["batch_info"] = batch_info
        
        # 写入文件
        self._write_json(file_path, existing_data)
        
        # 可选：自动同步到Notion（仅同步新增的items）
        if items:
            from ..models import FetchResult
            temp_result = FetchResult(
                success=True,
                source_name=source_type.title(),
                source_type=source_type,
                total_count=len(items),
                fetched_at=datetime.now().isoformat(),
                items=items
            )
            self._auto_sync_to_notion(temp_result)
        
        return file_path
    
    def _auto_sync_to_notion(self, result: Union[FetchResult, 'SearchResult']) -> None:
        """
        自动同步到Notion（如果配置启用）
        
        Args:
            result: FetchResult或SearchResult对象
        """
        try:
            from ..utils.notion_sync import get_notion_sync
            
            notion_sync = get_notion_sync()
            if not notion_sync or not notion_sync.enabled:
                return
            
            # 只同步FetchResult
            if isinstance(result, FetchResult) and result.items:
                sync_result = notion_sync.sync_fetch_result(result, skip_existing=True)
                if sync_result.get("success"):
                    synced = sync_result.get("synced", 0)
                    if synced > 0:
                        logger.info(f"📝 自动同步到Notion: {synced} 条新内容")
        except Exception as e:
            # 静默失败，不影响主流程
            logger.debug(f"Notion自动同步失败: {e}")
    
    def get_daily_summary(self, date: Optional[datetime] = None) -> dict:
        """
        获取指定日期的汇总信息
        
        Args:
            date: 日期对象，默认为今天
            
        Returns:
            汇总信息字典
        """
        daily_dir = self.get_daily_dir(date)
        
        if not daily_dir.exists():
            return {
                "date": date.strftime("%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d"),
                "files": [],
                "total_files": 0
            }
        
        files = list(daily_dir.glob("*.json"))
        return {
            "date": date.strftime("%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d"),
            "files": [f.name for f in files],
            "total_files": len(files),
            "file_paths": [str(f) for f in files]
        }
    
    def _write_json(self, file_path: Path, data: Union[dict, list]) -> None:
        """
        写入JSON文件
        
        Args:
            file_path: 文件路径
            data: 要写入的数据
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_output_structure(self) -> dict[str, str]:
        """
        获取输出目录结构信息
        
        Returns:
            目录结构字典
        """
        return {
            "base": str(self.base_dir),
            "daily": str(self.get_daily_dir())
        }


# 全局输出管理器实例
_output_manager: Optional[OutputManager] = None


def get_output_manager(base_dir: Optional[Path] = None) -> OutputManager:
    """
    获取全局输出管理器实例
    
    Args:
        base_dir: 基础输出目录
        
    Returns:
        输出管理器实例
    """
    global _output_manager
    if _output_manager is None:
        _output_manager = OutputManager(base_dir)
    return _output_manager


def reset_output_manager() -> None:
    """重置全局输出管理器（用于测试）"""
    global _output_manager
    _output_manager = None
