"""
Skill 独立配置加载工具
从 config.yaml 读取配置，不依赖主项目配置
"""

import yaml
from pathlib import Path
from typing import Any, Optional, Dict, List


class SkillConfig:
    """Skill 配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径：agent_skill/config.yaml
            script_dir = Path(__file__).parent.parent
            config_path = script_dir / "config.yaml"
        else:
            config_path = Path(config_path)
        
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"加载配置文件失败: {str(e)}")
    
    def get_arxiv_config(self) -> Dict[str, Any]:
        """获取 arXiv 配置"""
        return self._config.get("arxiv", {})
    
    def get_arxiv_categories(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取 arXiv 分类列表
        
        Args:
            enabled_only: 是否只返回启用的分类
        
        Returns:
            分类列表
        """
        arxiv_config = self.get_arxiv_config()
        categories = arxiv_config.get("categories", [])
        
        if enabled_only:
            return [cat for cat in categories if cat.get("enabled", True)]
        return categories
    
    def get_hackernews_config(self) -> Dict[str, Any]:
        """获取 HackerNews 配置"""
        return self._config.get("hackernews", {})
    
    def get_rss_config(self) -> Dict[str, Any]:
        """获取 RSS 配置"""
        return self._config.get("rss", {})
    
    def get_rss_feeds(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取 RSS 订阅源列表
        
        Args:
            enabled_only: 是否只返回启用的订阅源
        
        Returns:
            订阅源列表
        """
        rss_config = self.get_rss_config()
        feeds = rss_config.get("feeds", [])
        
        if enabled_only:
            return [feed for feed in feeds if feed.get("enabled", True)]
        return feeds
    
    def get_github_config(self) -> Dict[str, Any]:
        """获取 GitHub 配置"""
        return self._config.get("github", {})
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取 LLM 配置"""
        return self._config.get("llm", {})
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        return self._config.get("global", {})
    
    def is_source_enabled(self, source: str) -> bool:
        """
        检查数据源是否启用
        
        Args:
            source: 数据源名称 (arxiv, hackernews, rss, github)
        
        Returns:
            是否启用
        """
        source_config = self._config.get(source, {})
        return source_config.get("enabled", False)


# 全局配置实例
_config_instance: Optional[SkillConfig] = None


def get_config(config_path: Optional[str] = None) -> SkillConfig:
    """
    获取配置管理器实例（单例模式）
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
    
    Returns:
        SkillConfig 实例
    """
    global _config_instance
    
    if _config_instance is None or config_path is not None:
        _config_instance = SkillConfig(config_path)
    
    return _config_instance
