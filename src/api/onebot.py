"""
OneBot API 封装模块
"""
from typing import Any, Dict, List, Optional
import requests
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OneBotAPI:
    """OneBot API 客户端"""
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5700,
        access_token: str = "",
        timeout: int = 30
    ):
        """
        初始化 OneBot API 客户端
        
        Args:
            host: OneBot 服务地址
            port: OneBot 服务端口
            access_token: 访问令牌
            timeout: 请求超时时间
        """
        self.base_url = f"http://{host}:{port}"
        self.access_token = access_token
        self.timeout = timeout
        self.headers = {}
        
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"
        
        logger.info(f"OneBot API 客户端已初始化: {self.base_url}")
    
    async def _call_api(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调用 OneBot API
        
        Args:
            endpoint: API 端点
            params: 请求参数
            
        Returns:
            API 响应数据
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.post(
                url,
                json=params or {},
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "failed":
                error_msg = result.get("msg", "Unknown error")
                logger.error(f"API 调用失败: {endpoint} - {error_msg}")
                raise Exception(f"API Error: {error_msg}")
            
            return result.get("data", {})
            
        except requests.RequestException as e:
            logger.error(f"HTTP 请求错误: {endpoint} - {str(e)}")
            raise
        except Exception as e:
            logger.error(f"API 调用异常: {endpoint} - {str(e)}")
            raise
    
    # ==================== 群组相关 API ====================
    
    async def get_group_list(self, no_cache: bool = False) -> List[Dict[str, Any]]:
        """
        获取群列表
        
        Args:
            no_cache: 是否不使用缓存
            
        Returns:
            群列表
        """
        logger.info("获取群列表")
        return await self._call_api("get_group_list", {"no_cache": no_cache})
    
    async def get_group_info(
        self,
        group_id: int,
        no_cache: bool = False
    ) -> Dict[str, Any]:
        """
        获取群信息
        
        Args:
            group_id: 群号
            no_cache: 是否不使用缓存
            
        Returns:
            群信息
        """
        logger.info(f"获取群信息: {group_id}")
        return await self._call_api(
            "get_group_info",
            {"group_id": group_id, "no_cache": no_cache}
        )
    
    async def get_group_member_list(
        self,
        group_id: int,
        no_cache: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取群成员列表
        
        Args:
            group_id: 群号
            no_cache: 是否不使用缓存
            
        Returns:
            群成员列表
        """
        logger.info(f"获取群成员列表: {group_id}")
        return await self._call_api(
            "get_group_member_list",
            {"group_id": group_id, "no_cache": no_cache}
        )
    
    async def get_group_member_info(
        self,
        group_id: int,
        user_id: int,
        no_cache: bool = False
    ) -> Dict[str, Any]:
        """
        获取群成员信息
        
        Args:
            group_id: 群号
            user_id: QQ 号
            no_cache: 是否不使用缓存
            
        Returns:
            群成员信息
        """
        logger.debug(f"获取群成员信息: {group_id}/{user_id}")
        return await self._call_api(
            "get_group_member_info",
            {
                "group_id": group_id,
                "user_id": user_id,
                "no_cache": no_cache
            }
        )
    
    async def send_group_msg(
        self,
        group_id: int,
        message: str,
        auto_escape: bool = False
    ) -> Dict[str, Any]:
        """
        发送群消息
        
        Args:
            group_id: 群号
            message: 消息内容
            auto_escape: 是否作为纯文本发送
            
        Returns:
            消息 ID 等信息
        """
        logger.info(f"发送群消息: {group_id} - {message[:50]}...")
        return await self._call_api(
            "send_group_msg",
            {
                "group_id": group_id,
                "message": message,
                "auto_escape": auto_escape
            }
        )
    
    async def set_group_card(
        self,
        group_id: int,
        user_id: int,
        card: str
    ) -> None:
        """
        设置群名片
        
        Args:
            group_id: 群号
            user_id: QQ 号
            card: 群名片内容
        """
        logger.info(f"设置群名片: {group_id}/{user_id} -> {card}")
        await self._call_api(
            "set_group_card",
            {
                "group_id": group_id,
                "user_id": user_id,
                "card": card
            }
        )
    
    async def set_group_name(
        self,
        group_id: int,
        group_name: str
    ) -> None:
        """
        设置群名
        
        Args:
            group_id: 群号
            group_name: 新群名
        """
        logger.info(f"设置群名: {group_id} -> {group_name}")
        await self._call_api(
            "set_group_name",
            {
                "group_id": group_id,
                "group_name": group_name
            }
        )
    
    async def set_group_admin(
        self,
        group_id: int,
        user_id: int,
        enable: bool = True
    ) -> None:
        """
        设置群管理员
        
        Args:
            group_id: 群号
            user_id: QQ 号
            enable: True 为设置，False 为取消
        """
        logger.info(f"设置群管理员: {group_id}/{user_id} - {enable}")
        await self._call_api(
            "set_group_admin",
            {
                "group_id": group_id,
                "user_id": user_id,
                "enable": enable
            }
        )
    
    async def set_group_special_title(
        self,
        group_id: int,
        user_id: int,
        special_title: str,
        duration: int = -1
    ) -> None:
        """
        设置群专属头衔
        
        Args:
            group_id: 群号
            user_id: QQ 号
            special_title: 专属头衔
            duration: 有效期（秒），-1 为永久
        """
        logger.info(f"设置专属头衔: {group_id}/{user_id} -> {special_title}")
        await self._call_api(
            "set_group_special_title",
            {
                "group_id": group_id,
                "user_id": user_id,
                "special_title": special_title,
                "duration": duration
            }
        )
    
    # ==================== 账号相关 API ====================
    
    async def get_login_info(self) -> Dict[str, Any]:
        """
        获取登录号信息
        
        Returns:
            登录号信息
        """
        logger.info("获取登录号信息")
        return await self._call_api("get_login_info")
    
    async def get_stranger_info(
        self,
        user_id: int,
        no_cache: bool = False
    ) -> Dict[str, Any]:
        """
        获取陌生人信息
        
        Args:
            user_id: QQ 号
            no_cache: 是否不使用缓存
            
        Returns:
            用户信息
        """
        logger.debug(f"获取陌生人信息: {user_id}")
        return await self._call_api(
            "get_stranger_info",
            {
                "user_id": user_id,
                "no_cache": no_cache
            }
        )
    
    async def get_friend_list(self) -> List[Dict[str, Any]]:
        """
        获取好友列表
        
        Returns:
            好友列表
        """
        logger.info("获取好友列表")
        return await self._call_api("get_friend_list")
    
    # ==================== 系统相关 API ====================
    
    async def get_status(self) -> Dict[str, Any]:
        """
        获取运行状态
        
        Returns:
            运行状态
        """
        logger.debug("获取运行状态")
        return await self._call_api("get_status")
    
    async def get_version_info(self) -> Dict[str, Any]:
        """
        获取版本信息
        
        Returns:
            版本信息
        """
        logger.info("获取版本信息")
        return await self._call_api("get_version_info")


# 便捷函数
async def create_onebot_client(
    host: str = "127.0.0.1",
    port: int = 5700,
    access_token: str = "",
    timeout: int = 30
) -> OneBotAPI:
    """创建 OneBot 客户端"""
    return OneBotAPI(host, port, access_token, timeout)
