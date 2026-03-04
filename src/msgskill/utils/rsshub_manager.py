"""
RSSHub 服务管理器

功能：自动管理 RSSHub Docker 容器的启动、停止和健康检查
"""

import subprocess
import time
import httpx
from typing import Optional
from .logger import logger


class RSSHubManager:
    """RSSHub Docker 容器管理器"""
    
    def __init__(self, container_name: str = "msgtool-rsshub", port: int = 8878):
        self.container_name = container_name
        self.port = port
        self.base_url = f"http://localhost:{port}"
    
    def is_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def is_container_running(self) -> bool:
        """检查容器是否正在运行"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return self.container_name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def is_port_in_use(self) -> bool:
        """检查端口是否被占用"""
        try:
            response = httpx.get(f"{self.base_url}/", timeout=2)
            # 如果能访问，说明端口被占用（可能是其他 RSSHub 实例）
            return True
        except httpx.ConnectError:
            # 连接失败，端口可能未被占用，或者服务未启动
            return False
        except Exception:
            # 其他异常，保守处理，认为端口可能被占用
            return True
    
    def is_service_healthy(self, timeout: int = 5) -> bool:
        """检查 RSSHub 服务是否健康（可访问）"""
        try:
            response = httpx.get(f"{self.base_url}/", timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False
    
    def start_container(self, wait_healthy: bool = True, max_wait: int = 60) -> bool:
        """
        启动 RSSHub 容器
        
        Args:
            wait_healthy: 是否等待服务健康
            max_wait: 最大等待时间（秒）
        
        Returns:
            是否成功启动
        """
        if not self.is_docker_available():
            logger.warning("Docker 不可用，无法启动 RSSHub 容器")
            return False
        
        if self.is_container_running():
            logger.info(f"RSSHub 容器 {self.container_name} 已在运行")
            if wait_healthy:
                return self._wait_for_healthy(max_wait)
            return True
        
        # 检查端口是否被占用（可能是其他进程）
        if self.is_port_in_use():
            # 如果端口被占用但服务健康，说明 RSSHub 已经在运行（可能是手动启动的）
            if self.is_service_healthy(timeout=3):
                logger.info(f"检测到端口 {self.port} 已有 RSSHub 服务在运行，直接使用")
                return True
            
            logger.warning(f"端口 {self.port} 已被占用，但服务不可访问")
            logger.warning("   可能原因：")
            logger.warning("   1. 其他服务占用了该端口")
            logger.warning("   2. RSSHub 服务正在启动中")
            logger.warning(f"   提示: 可以手动停止占用端口的进程，或修改 docker-compose.yml 中的端口映射")
            
            # 检查是否是其他容器占用了端口
            try:
                result = subprocess.run(
                    ["docker", "ps", "--format", "{{.Names}}: {{.Ports}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if f":{self.port}->" in result.stdout:
                    logger.info("   检测到 Docker 容器占用了该端口")
            except Exception:
                pass
            
            return False
        
        logger.info(f"正在启动 RSSHub 容器 {self.container_name}...")
        
        try:
            # 尝试使用 docker compose（新版本）或 docker-compose（旧版本）
            compose_cmd = None
            
            # 先尝试 docker compose（新版本）
            try:
                result = subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    compose_cmd = ["docker", "compose"]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # 如果新版本不可用，尝试 docker-compose（旧版本）
            if not compose_cmd:
                try:
                    result = subprocess.run(
                        ["docker-compose", "--version"],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        compose_cmd = ["docker-compose"]
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            
            if not compose_cmd:
                logger.error("未找到 docker-compose 或 docker compose 命令")
                return False
            
            # 使用 docker compose 启动
            result = subprocess.run(
                compose_cmd + ["up", "-d", "rsshub"],
                cwd=".",
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = result.stderr
                logger.error(f"启动 RSSHub 容器失败: {error_msg}")
                
                # 检查是否是端口占用错误
                if "port is already allocated" in error_msg or "address already in use" in error_msg:
                    logger.warning(f"端口 {self.port} 已被占用")
                    logger.warning("   解决方案：")
                    logger.warning(f"   1. 检查是否有其他 RSSHub 容器在运行: docker ps | grep rsshub")
                    logger.warning(f"   2. 停止占用端口的容器: docker stop <container_name>")
                    logger.warning(f"   3. 或修改 docker-compose.yml 中的端口映射（如改为 8879:1200）")
                
                return False
            
            logger.info("RSSHub 容器启动命令已执行")
            
            if wait_healthy:
                return self._wait_for_healthy(max_wait)
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("启动 RSSHub 容器超时")
            return False
        except FileNotFoundError:
            logger.error("Docker Compose 命令未找到，请确保已安装 Docker 和 Docker Compose")
            return False
        except Exception as e:
            logger.error(f"启动 RSSHub 容器时出错: {str(e)}")
            return False
    
    def _wait_for_healthy(self, max_wait: int = 60) -> bool:
        """等待服务健康"""
        logger.info(f"等待 RSSHub 服务就绪（最多 {max_wait} 秒）...")
        
        start_time = time.time()
        check_interval = 2
        
        while time.time() - start_time < max_wait:
            if self.is_service_healthy():
                elapsed = int(time.time() - start_time)
                logger.info(f"RSSHub 服务已就绪（耗时 {elapsed} 秒）")
                return True
            
            time.sleep(check_interval)
            logger.debug(f"等待 RSSHub 服务就绪... ({int(time.time() - start_time)}/{max_wait} 秒)")
        
        logger.warning(f"RSSHub 服务在 {max_wait} 秒内未就绪，但容器可能仍在启动中")
        return False
    
    def stop_container(self) -> bool:
        """停止 RSSHub 容器"""
        if not self.is_container_running():
            logger.info(f"RSSHub 容器 {self.container_name} 未运行")
            return True
        
        logger.info(f"正在停止 RSSHub 容器 {self.container_name}...")
        
        try:
            # 尝试使用 docker compose（新版本）或 docker-compose（旧版本）
            compose_cmd = None
            
            # 先尝试 docker compose（新版本）
            try:
                result = subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    compose_cmd = ["docker", "compose"]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # 如果新版本不可用，尝试 docker-compose（旧版本）
            if not compose_cmd:
                try:
                    result = subprocess.run(
                        ["docker-compose", "--version"],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        compose_cmd = ["docker-compose"]
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            
            if not compose_cmd:
                logger.error("未找到 docker-compose 或 docker compose 命令")
                return False
            
            result = subprocess.run(
                compose_cmd + ["stop", "rsshub"],
                cwd=".",
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"停止 RSSHub 容器失败: {result.stderr}")
                return False
            
            logger.info("RSSHub 容器已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止 RSSHub 容器时出错: {str(e)}")
            return False
    
    def ensure_running(self) -> bool:
        """
        确保 RSSHub 容器正在运行（如果未运行则启动）
        
        Returns:
            是否成功（运行中或已启动）
        """
        if self.is_container_running() and self.is_service_healthy():
            return True
        
        return self.start_container(wait_healthy=True)


# 全局单例
_rsshub_manager: Optional[RSSHubManager] = None


def get_rsshub_manager() -> RSSHubManager:
    """获取 RSSHub 管理器单例"""
    global _rsshub_manager
    if _rsshub_manager is None:
        _rsshub_manager = RSSHubManager()
    return _rsshub_manager
