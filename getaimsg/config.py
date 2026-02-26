"""
配置管理模块 - 从JSON文件加载和管理数据源配置
"""

import json
import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# 配置文件路径 - Skill 使用独立的 config.yaml
CONFIG_DIR = Path(__file__).parent
SOURCES_CONFIG_FILE = CONFIG_DIR / "config.yaml"


@dataclass
class SourceConfig:
    """单个数据源配置"""
    enabled: bool
    name: str
    description: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "name": self.name,
            "description": self.description
        }


@dataclass
class NewsSourceConfig(SourceConfig):
    """新闻网站配置"""
    type: str = "api"  # api 或 scrape
    url: Optional[str] = None
    api_base_url: Optional[str] = None
    fetch_limit: dict[str, int] = field(default_factory=dict)
    cache_ttl: int = 300
    keywords: list[str] = field(default_factory=list)
    selectors: dict[str, str] = field(default_factory=dict)
    ai_filter_enabled: bool = True
    translation_enabled: bool = True
    recent_days: Optional[int] = None  # 只处理最近N天内的数据（如果未设置，则使用 llm.recent_days）


@dataclass
class RSSSourceConfig(SourceConfig):
    """RSS订阅源配置"""
    url: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    ai_filter_enabled: bool = True  # 默认启用AI筛选
    translation_enabled: bool = True


@dataclass
class ArxivSourceConfig(SourceConfig):
    """arXiv分类配置"""
    category: str = ""  # cs.AI, cs.LG等
    tags: list[str] = field(default_factory=list)
    translation_enabled: bool = True


@dataclass
class LLMConfig:
    """大模型API配置"""
    enabled: bool = False
    provider: str = "deepseek"  # deepseek, openai, etc.
    api_key: str = ""
    api_url: str = ""
    model_name: str = "deepseek-chat"
    max_tokens: int = 1000
    temperature: float = 0.3
    # 控制对LLM请求时仅处理最近多少天内的数据（如 HackerNews / RSS / arXiv）
    recent_days: int = 7


@dataclass
class SchedulerConfig:
    """单个数据源调度配置"""
    enabled: bool = False
    time: str = "09:00"
    max_results: int = 10


@dataclass
class GlobalSettings:
    """全局设置"""
    default_cache_ttl: int = 300
    default_fetch_limit: int = 10
    max_fetch_limit: int = 50
    request_timeout: int = 30
    user_agent: str = "Mozilla/5.0 (compatible; MsgSkill/1.0)"
    scheduler: dict[str, Any] = field(default_factory=dict)
    maintenance: dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """配置管理器 - 单例模式"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[dict[str, Any]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.reload()
    
    def reload(self) -> None:
        """重新加载配置文件"""
        if not SOURCES_CONFIG_FILE.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {SOURCES_CONFIG_FILE}\n"
                f"请确保 config.yaml 文件存在"
            )
        
        with open(SOURCES_CONFIG_FILE, 'r', encoding='utf-8') as f:
            if SOURCES_CONFIG_FILE.suffix in ['.yaml', '.yml']:
                self._config = yaml.safe_load(f) or {}
                # 适配 YAML 格式：将扁平结构转换为嵌套结构
                if "sources" not in self._config:
                    self._config["sources"] = {}
                    if "hackernews" in self._config:
                        self._config["sources"]["news"] = {"hackernews": self._config.pop("hackernews")}
                    if "rss" in self._config:
                        rss_config = self._config.pop("rss")
                        feeds = rss_config.pop("feeds", [])
                        # 将 feeds 列表转换为字典格式
                        feeds_dict = {}
                        for feed in feeds:
                            feed_name = feed.get("name", "").lower().replace(" ", "_")
                            feeds_dict[feed_name] = feed
                        self._config["sources"]["rss"] = feeds_dict
                    if "github" in self._config:
                        github_config = self._config.pop("github")
                        # 添加 fetch_limit 适配
                        if "max_results" in github_config:
                            github_config["fetch_limit"] = {
                                "default": github_config.pop("max_results", 20),
                                "max": 50
                            }
                        self._config["sources"]["github"] = {"trending_daily": github_config}
                    if "arxiv" in self._config:
                        arxiv_config = self._config.pop("arxiv")
                        categories = arxiv_config.pop("categories", [])
                        self._config["sources"]["arxiv"] = {}
                        for cat in categories:
                            cat_key = cat.get("key", "").replace(".", "_")
                            self._config["sources"]["arxiv"][cat_key] = cat
            else:
                self._config = json.load(f)
    
    @property
    def version(self) -> str:
        """配置文件版本"""
        return self._config.get("version", "unknown")
    
    @property
    def global_settings(self) -> GlobalSettings:
        """获取全局设置"""
        settings = self._config.get("global_settings", {})
        return GlobalSettings(**settings)
    
    def get_scheduler_config(self, source: str) -> Optional[SchedulerConfig]:
        """
        获取指定数据源的调度配置
        
        Args:
            source: 数据源名称 (arxiv, hackernews, rss, github)
            
        Returns:
            调度配置对象或None
        """
        scheduler_settings = self.global_settings.scheduler
        source_config = scheduler_settings.get("sources", {}).get(source, {})
        
        if not source_config:
            return None
            
        return SchedulerConfig(
            enabled=source_config.get("enabled", False),
            time=source_config.get("time", "09:00"),
            max_results=source_config.get("max_results", 10)
        )
    
    def get_llm_config(self) -> LLMConfig:
        """
        获取大模型API配置
        
        Returns:
            LLM配置对象
        """
        llm_config = self._config.get("llm", {})
        if not llm_config:
            return LLMConfig(enabled=False)
        
        return LLMConfig(
            enabled=llm_config.get("enabled", False),
            provider=llm_config.get("provider", "deepseek"),
            api_key=llm_config.get("api_key", ""),
            api_url=llm_config.get("api_url", ""),
            model_name=llm_config.get("model_name", "deepseek-chat"),
            max_tokens=llm_config.get("max_tokens", 1000),
            temperature=llm_config.get("temperature", 0.3),
            recent_days=int(llm_config.get("recent_days", 7) or 7),
        )
    
    # ===== 新闻源相关 =====
    
    def get_news_sources(self, enabled_only: bool = True) -> dict[str, NewsSourceConfig]:
        """
        获取所有新闻源配置
        
        Args:
            enabled_only: 是否仅返回启用的源
            
        Returns:
            新闻源配置字典
        """
        news_sources = self._config.get("sources", {}).get("news", {})
        result = {}
        
        for key, config in news_sources.items():
            if enabled_only and not config.get("enabled", True):
                continue
            
            result[key] = NewsSourceConfig(
                enabled=config.get("enabled", True),
                name=config.get("name", key),
                description=config.get("description", ""),
                type=config.get("type", "api"),
                url=config.get("url"),
                api_base_url=config.get("api_base_url"),
                fetch_limit=config.get("fetch_limit", {}),
                cache_ttl=config.get("cache_ttl", 300),
                keywords=config.get("keywords", []),
                selectors=config.get("selectors", {}),
                ai_filter_enabled=config.get("ai_filter_enabled", True),
                translation_enabled=config.get("translation_enabled", True),
                recent_days=config.get("recent_days")
            )
        
        return result
    
    def get_news_source(self, source_key: str) -> Optional[NewsSourceConfig]:
        """
        获取单个新闻源配置
        
        Args:
            source_key: 源的键名（如 'hackernews'）
            
        Returns:
            新闻源配置或None
        """
        sources = self.get_news_sources(enabled_only=False)
        return sources.get(source_key)
    
    # ===== RSS源相关 =====
    
    def get_rss_sources(self, enabled_only: bool = True) -> dict[str, RSSSourceConfig]:
        """
        获取所有RSS源配置
        
        Args:
            enabled_only: 是否仅返回启用的源
            
        Returns:
            RSS源配置字典
        """
        rss_sources = self._config.get("sources", {}).get("rss", {})
        result = {}
        
        for key, config in rss_sources.items():
            if enabled_only and not config.get("enabled", True):
                continue
            
            result[key] = RSSSourceConfig(
                enabled=config.get("enabled", True),
                name=config.get("name", key),
                description=config.get("description", ""),
                url=config.get("url", ""),
                category=config.get("category", ""),
                tags=config.get("tags", []),
                ai_filter_enabled=config.get("ai_filter_enabled", True),  # 默认启用
                translation_enabled=config.get("translation_enabled", True)
            )
        
        return result
    
    def get_rss_source(self, source_key: str) -> Optional[RSSSourceConfig]:
        """
        获取单个RSS源配置
        
        Args:
            source_key: 源的键名
            
        Returns:
            RSS源配置或None
        """
        sources = self.get_rss_sources(enabled_only=False)
        return sources.get(source_key)
    
    def get_rss_feed_urls(self) -> dict[str, str]:
        """
        获取所有启用的RSS源URL
        
        Returns:
            {源名称: URL} 字典
        """
        sources = self.get_rss_sources(enabled_only=True)
        return {config.name: config.url for config in sources.values()}
    
    # ===== arXiv相关 =====
    
    def get_arxiv_categories(self, enabled_only: bool = True) -> dict[str, ArxivSourceConfig]:
        """
        获取所有arXiv分类配置
        
        Args:
            enabled_only: 是否仅返回启用的分类
            
        Returns:
            arXiv分类配置字典
        """
        arxiv_sources = self._config.get("sources", {}).get("arxiv", {})
        result = {}
        
        for key, config in arxiv_sources.items():
            if enabled_only and not config.get("enabled", True):
                continue
            
            result[key] = ArxivSourceConfig(
                enabled=config.get("enabled", True),
                name=config.get("name", key),
                description=config.get("description", ""),
                category=config.get("category", ""),
                tags=config.get("tags", []),
                translation_enabled=config.get("translation_enabled", True)
            )
        
        return result
    
    def get_arxiv_category_mapping(self) -> dict[str, str]:
        """
        获取arXiv分类代码到名称的映射
        
        Returns:
            {分类代码: 分类名称} 字典
        """
        categories = self.get_arxiv_categories(enabled_only=True)
        return {config.category: config.name for config in categories.values()}
    
    # ===== GitHub相关 =====
    
    def get_github_sources(self, enabled_only: bool = True) -> dict[str, NewsSourceConfig]:
        """
        获取所有GitHub源配置
        
        Args:
            enabled_only: 是否仅返回启用的源
            
        Returns:
            GitHub源配置字典
        """
        github_sources = self._config.get("sources", {}).get("github", {})
        result = {}
        
        for key, config in github_sources.items():
            if enabled_only and not config.get("enabled", True):
                continue
            
            result[key] = NewsSourceConfig(
                enabled=config.get("enabled", True),
                name=config.get("name", key),
                description=config.get("description", ""),
                type=config.get("type", "api"),
                api_base_url=config.get("api_base_url"),
                fetch_limit=config.get("fetch_limit", {}),
                cache_ttl=config.get("cache_ttl", 3600),
                keywords=config.get("topics", []) if "topics" in config else [],
                ai_filter_enabled=config.get("ai_filter_enabled", True),
                translation_enabled=config.get("translation_enabled", True)
            )
        
        return result
    
    def get_github_source(self, source_key: str) -> Optional[NewsSourceConfig]:
        """
        获取单个GitHub源配置
        
        Args:
            source_key: 源的键名
            
        Returns:
            GitHub源配置或None
        """
        sources = self.get_github_sources(enabled_only=False)
        return sources.get(source_key)
    
    # ===== 工具方法 =====
    
    def list_all_sources(self) -> dict[str, Any]:
        """
        列出所有数据源的摘要信息
        
        Returns:
            所有源的统计信息
        """
        news = self.get_news_sources(enabled_only=False)
        rss = self.get_rss_sources(enabled_only=False)
        arxiv = self.get_arxiv_categories(enabled_only=False)
        
        return {
            "news": {
                "total": len(news),
                "enabled": sum(1 for s in news.values() if s.enabled),
                "sources": list(news.keys())
            },
            "rss": {
                "total": len(rss),
                "enabled": sum(1 for s in rss.values() if s.enabled),
                "sources": list(rss.keys())
            },
            "arxiv": {
                "total": len(arxiv),
                "enabled": sum(1 for s in arxiv.values() if s.enabled),
                "categories": list(arxiv.keys())
            }
        }
    
    def export_config(self, output_file: Path) -> None:
        """
        导出当前配置到文件
        
        Args:
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)
    
    def get_source_config(self, source_key: str) -> Optional[SourceConfig]:
        """
        通用方法：根据数据源键名获取配置
        
        Args:
            source_key: 数据源键名，格式为 "category.source_name"
                       (如 "news.hackernews", "rss.mit_tech_review")
            
        Returns:
            数据源配置对象或None
        """
        parts = source_key.split('.')
        if len(parts) != 2:
            return None
            
        category, name = parts
        
        if category == "news":
            return self.get_news_source(name)
        elif category == "rss":
            return self.get_rss_source(name)
        elif category == "arxiv":
            # 修正：直接获取arXiv分类配置
            categories = self.get_arxiv_categories(enabled_only=False)
            return categories.get(name)
        elif category == "github":
            return self.get_github_source(name)
        else:
            return None
    
    # Skill 不需要 Notion 同步功能，已移除相关配置和文件


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config() -> None:
    """重新加载配置"""
    global _config_manager
    if _config_manager is not None:
        _config_manager.reload()
