"""
GitHub项目数据库管理器 - 重构版本 (单一文件设计)
基于状态字段的统一数据库管理

功能：
- 统一管理GitHub项目的持久化存储
- 智能状态管理：crawled → ai_screened → whitelisted
- 减少重复的AI筛选调用
- 提供快速的项目查询功能
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import hashlib

from .logger import logger


class GitHubProjectDB:
    """GitHub项目数据库管理器 (单一文件版本)"""
    
    def __init__(self, db_dir: Optional[Path] = None):
        """
        初始化数据库管理器
        
        Args:
            db_dir: 数据库目录，默认 output/github/
        """
        if db_dir is None:
            # 默认使用项目根目录下的 output/github/
            db_dir = Path(__file__).parent.parent.parent.parent / "output" / "github"
        
        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # 单一数据库文件路径
        self.projects_file = self.db_dir / "github_projects.json"
        
        # 当前已加载的数据
        self.projects: Dict[str, Dict] = {}
        
        # 加载现有数据库
        self._load_database()
    
    def _load_database(self) -> None:
        """加载数据库文件"""
        try:
            # 首先尝试加载新格式的单一文件
            if self.projects_file.exists():
                with open(self.projects_file, 'r', encoding='utf-8') as f:
                    self.projects = json.load(f)
                logger.info(f"✅ 加载GitHub项目数据库: {len(self.projects)} 个项目")
            else:
                # 如果新格式文件不存在，检查是否有旧格式文件需要迁移
                self.projects = {}
                if (self.db_dir / "all_projects.json").exists():
                    logger.warning("📋 检测到旧格式数据库文件，请运行迁移脚本")
                else:
                    logger.info("✅ GitHub项目数据库为空，将创建新数据库")
        
        except Exception as e:
            logger.error(f"❌ 加载GitHub数据库失败: {e}")
            # 初始化空数据库
            self.projects = {}
    
    def _save_database(self) -> None:
        """保存数据库到文件"""
        try:
            with open(self.projects_file, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存数据库失败 {self.projects_file}: {e}")
    
    def _generate_project_id(self, repo: Dict) -> str:
        """为GitHub项目生成唯一标识符（统一使用source_url作为key）"""
        # 优先使用html_url作为key（与_save_github_items_to_file保持一致）
        html_url = repo.get("html_url", "")
        if html_url:
            return html_url
        
        # 备用：使用项目ID
        repo_id = str(repo.get("id", ""))
        if repo_id:
            return f"github_{repo_id}"
        
        # 备用：使用项目全名生成hash
        full_name = repo.get("full_name", "")
        if full_name:
            return f"github_{hashlib.md5(full_name.encode()).hexdigest()[:8]}"
        
        # 最后备用：随机生成
        return f"github_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"
    
    def project_exists(self, repo: Dict) -> bool:
        """
        检查项目是否已存在
        
        Args:
            repo: GitHub项目数据
            
        Returns:
            bool: 项目是否已存在
        """
        project_id = self._generate_project_id(repo)
        return project_id in self.projects
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        """
        获取项目信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            Optional[Dict]: 项目信息，如果不存在返回None
        """
        return self.projects.get(project_id)
    
    def is_whitelisted(self, repo: Dict) -> bool:
        """
        检查项目是否在白名单中（过期自动处理）
        
        Args:
            repo: GitHub项目数据
            
        Returns:
            bool: 是否在白名单中且未过期
        """
        project_id = self._generate_project_id(repo)
        
        if project_id not in self.projects:
            return False
        
        project = self.projects[project_id]
        status = project.get("status", "crawled")
        
        # 检查白名单状态
        if status == "whitelisted":
            # 检查是否过期
            whitelisted_until = project.get("whitelisted_until")
            if whitelisted_until:
                try:
                    expiry_time = datetime.fromisoformat(whitelisted_until.replace('Z', '+00:00'))
                    if datetime.now() < expiry_time:
                        return True
                    else:
                        # 白名单已过期，更新状态
                        project["status"] = "expired"
                        project["whitelisted_until"] = None
                        self._save_database()
                        logger.debug(f"🔁 白名单已过期: {project_id}")
                except Exception:
                    # 如果时间解析失败，保守起见认为已过期
                    project["status"] = "expired"
                    self._save_database()
        
        return False
    
    def get_whitelisted_projects(self) -> Dict[str, Dict]:
        """
        获取当前有效的白名单项目
        
        Returns:
            Dict[str, Dict]: 白名单项目字典
        """
        valid_projects = {}
        now = datetime.now()
        
        for project_id, project in self.projects.items():
            status = project.get("status", "crawled")
            
            if status == "whitelisted":
                whitelisted_until = project.get("whitelisted_until")
                if whitelisted_until:
                    try:
                        expiry_time = datetime.fromisoformat(whitelisted_until.replace('Z', '+00:00'))
                        if now < expiry_time:
                            valid_projects[project_id] = project
                    except Exception:
                        # 时间解析失败，跳过
                        continue
        
        return valid_projects
    
    def get_ai_projects(self) -> Dict[str, Dict]:
        """
        获取所有AI相关的项目（包括白名单和已筛选的）
        
        Returns:
            Dict[str, Dict]: AI项目字典
        """
        ai_projects = {}
        
        for project_id, project in self.projects.items():
            status = project.get("status", "crawled")
            if status in ["ai_screened", "whitelisted"]:
                ai_projects[project_id] = project
        
        return ai_projects
    
    def add_project(self, repo: Dict, status: str = "crawled", ai_score: float = 0.0, ai_reason: str = "") -> str:
        """
        添加或更新项目
        
        Args:
            repo: GitHub项目数据
            status: 项目状态 (crawled/ai_screened/whitelisted)
            ai_score: AI评分 (0.0-1.0)
            ai_reason: AI筛选原因
            
        Returns:
            str: 项目ID
        """
        project_id = self._generate_project_id(repo)
        now = datetime.now().isoformat()
        
        # 基础项目信息
        project_data = {
            # 项目基础信息
            "repo_id": repo.get("id"),
            "full_name": repo.get("full_name"),
            "name": repo.get("name"),
            "description": repo.get("description"),
            "html_url": repo.get("html_url"),
            "stargazers_count": repo.get("stargazers_count", 0),
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "trend_type": repo.get("trend_type"),
            "language_query": repo.get("language_query"),
            
            # 状态管理字段
            "status": status,
            "ai_score": ai_score,
            "ai_reason": ai_reason,
            "crawled_at": repo.get("added_at", now),
            "last_screened_at": None,
            "last_seen": now
        }
        
        # 如果是白名单状态，设置过期时间
        if status == "whitelisted":
            project_data["whitelisted_until"] = (now + timedelta(days=30)).isoformat()
            project_data["last_screened_at"] = now
        
        # 如果是AI筛选状态，记录筛选时间
        elif status == "ai_screened":
            project_data["last_screened_at"] = now
        
        # 更新或创建项目
        if project_id in self.projects:
            # 更新现有项目，保留重要字段
            existing = self.projects[project_id]
            project_data["crawled_at"] = existing.get("crawled_at", project_data["crawled_at"])
            
            # 如果状态没有改变为更高级别，保留原有状态
            status_hierarchy = {"crawled": 0, "ai_screened": 1, "whitelisted": 2}
            current_priority = status_hierarchy.get(existing.get("status", "crawled"), 0)
            new_priority = status_hierarchy.get(status, 0)
            
            if new_priority <= current_priority:
                # 旧数据里可能没有status字段，这里要做兼容处理
                project_data["status"] = existing.get("status", project_data.get("status", "crawled"))
                project_data["ai_score"] = existing.get("ai_score", ai_score)
                project_data["ai_reason"] = existing.get("ai_reason", ai_reason)
                if existing.get("whitelisted_until"):
                    project_data["whitelisted_until"] = existing["whitelisted_until"]
        
        self.projects[project_id] = project_data
        self._save_database()
        
        logger.debug(f"📝 更新项目: {project_id} ({status})")
        return project_id
    
    def mark_as_ai_screened(self, repo: Dict, ai_score: float, ai_reason: str = "") -> str:
        """
        标记项目为AI筛选通过
        
        Args:
            repo: GitHub项目数据
            ai_score: AI评分
            ai_reason: 筛选原因
            
        Returns:
            str: 项目ID
        """
        return self.add_project(repo, "ai_screened", ai_score, ai_reason)
    
    def mark_as_whitelisted(self, repo: Dict, ai_score: float, ai_reason: str = "") -> str:
        """
        标记项目为白名单（30天缓存）
        
        Args:
            repo: GitHub项目数据
            ai_score: AI评分
            ai_reason: 筛选原因
            
        Returns:
            str: 项目ID
        """
        return self.add_project(repo, "whitelisted", ai_score, ai_reason)
    
    def cleanup_expired_projects(self, days: int = 90) -> int:
        """
        清理过期项目（超过指定天数未活跃）
        
        Args:
            days: 过期天数阈值
            
        Returns:
            int: 清理的项目数量
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()
        
        cleaned_count = 0
        project_ids_to_remove = []
        
        # 找出过期项目
        for project_id, project_data in self.projects.items():
            last_seen = project_data.get("last_seen", "")
            if last_seen < cutoff_iso:
                project_ids_to_remove.append(project_id)
        
        # 执行清理
        for project_id in project_ids_to_remove:
            self.projects.pop(project_id)
            cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_database()
            logger.info(f"🗑️ 清理了 {cleaned_count} 个超过 {days} 天的旧项目")
        
        return cleaned_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            "total_projects": len(self.projects),
            "status_counts": {},
            "languages": {},
            "trend_types": {}
        }
        
        for project in self.projects.values():
            # 统计状态
            status = project.get("status", "unknown")
            stats["status_counts"][status] = stats["status_counts"].get(status, 0) + 1
            
            # 统计语言
            language = project.get("language", "unknown")
            stats["languages"][language] = stats["languages"].get(language, 0) + 1
            
            # 统计趋势类型
            trend_type = project.get("trend_type", "unknown")
            stats["trend_types"][trend_type] = stats["trend_types"].get(trend_type, 0) + 1
        
        return stats


# 全局GitHub数据库实例
_github_db: Optional[GitHubProjectDB] = None


def get_github_db() -> GitHubProjectDB:
    """获取全局GitHub数据库实例"""
    global _github_db
    if _github_db is None:
        _github_db = GitHubProjectDB()
    return _github_db


def reset_github_db() -> None:
    """重置GitHub数据库（用于测试）"""
    global _github_db
    _github_db = None