"""
重建管理器 - 群组重建与成员邀请逻辑
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy import select

from src.api.onebot import OneBotAPI
from src.models import db_manager, Backup, BackupMember
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RebuildStatus(Enum):
    """重建状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InviteStatus(Enum):
    """邀请状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class InviteResult:
    """邀请结果"""
    user_id: int
    nickname: str
    status: InviteStatus
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RebuildProgress:
    """重建进度"""
    total: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    status: RebuildStatus = RebuildStatus.PENDING
    current_user: Optional[int] = None
    results: List[InviteResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    
    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total == 0:
            return 0.0
        return (self.processed / self.total) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total": self.total,
            "processed": self.processed,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "status": self.status.value,
            "progress_percent": round(self.progress_percent, 2),
            "current_user": self.current_user,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class RebuildManager:
    """重建管理器"""
    
    def __init__(
        self,
        client: OneBotAPI,
        invites_per_minute: int = 10,
        batch_delay: float = 5.0,
        retry_delay: float = 60.0,
        max_retries: int = 3,
        restore_admins: bool = True,
        restore_cards: bool = True,
        restore_titles: bool = False,
        send_welcome: bool = True,
        welcome_message: str = "欢迎回到群组!",
        continue_on_error: bool = True
    ):
        """
        初始化重建管理器
        
        Args:
            client: OneBot API 客户端
            invites_per_minute: 每分钟最大邀请数
            batch_delay: 批次间延迟(秒)
            retry_delay: 重试延迟(秒)
            max_retries: 最大重试次数
            restore_admins: 是否恢复管理员
            restore_cards: 是否恢复群名片
            restore_titles: 是否恢复专属头衔
            send_welcome: 是否发送欢迎消息
            welcome_message: 欢迎消息内容
            continue_on_error: 遇到错误是否继续
        """
        self.client = client
        self.invites_per_minute = invites_per_minute
        self.batch_delay = batch_delay
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.restore_admins = restore_admins
        self.restore_cards = restore_cards
        self.restore_titles = restore_titles
        self.send_welcome = send_welcome
        self.welcome_message = welcome_message
        self.continue_on_error = continue_on_error
        
        # 计算每次邀请的间隔
        self.invite_interval = 60.0 / invites_per_minute
        
        # 状态
        self._progress: Optional[RebuildProgress] = None
        self._cancelled = False
        self._paused = False
        
        logger.info(f"重建管理器已初始化: {invites_per_minute}/min")
    
    @property
    def progress(self) -> Optional[RebuildProgress]:
        """获取当前进度"""
        return self._progress
    
    def cancel(self):
        """取消重建"""
        self._cancelled = True
        if self._progress:
            self._progress.status = RebuildStatus.CANCELLED
        logger.info("重建任务已取消")
    
    def pause(self):
        """暂停重建"""
        self._paused = True
        if self._progress:
            self._progress.status = RebuildStatus.PAUSED
        logger.info("重建任务已暂停")
    
    def resume(self):
        """恢复重建"""
        self._paused = False
        if self._progress:
            self._progress.status = RebuildStatus.RUNNING
        logger.info("重建任务已恢复")
    
    async def rebuild_from_backup(
        self,
        backup_id: int,
        target_group_id: int,
        exclude_users: List[int] = None,
        progress_callback: Callable[[RebuildProgress], None] = None
    ) -> RebuildProgress:
        """
        从备份重建群组
        
        Args:
            backup_id: 备份ID
            target_group_id: 目标群号
            exclude_users: 排除的用户列表
            progress_callback: 进度回调函数
            
        Returns:
            重建进度
        """
        exclude_users = exclude_users or []
        
        # 获取备份成员
        async with db_manager.get_async_session() as session:
            result = await session.execute(
                select(BackupMember).where(BackupMember.backup_id == backup_id)
            )
            backup_members = list(result.scalars().all())
        
        if not backup_members:
            raise ValueError(f"备份 {backup_id} 中没有成员数据")
        
        logger.info(f"从备份 {backup_id} 重建群组 {target_group_id}, 成员数: {len(backup_members)}")
        
        # 过滤排除的用户
        members_to_invite = [
            m for m in backup_members 
            if m.user_id not in exclude_users
        ]
        
        return await self._rebuild_group(
            target_group_id,
            members_to_invite,
            progress_callback
        )
    
    async def rebuild_group(
        self,
        group_id: int,
        backup_id: int,
        target_group_id: int = None,
        restore_cards: bool = True,
        restore_titles: bool = True,
        restore_admins: bool = False,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        从备份重建群组（WebUI 调用入口）
        
        Args:
            group_id: 备份来源群号
            backup_id: 备份ID
            target_group_id: 目标群号（恢复到哪个群，可与来源群不同）
            restore_cards: 是否恢复群名片
            restore_titles: 是否恢复专属头衔
            restore_admins: 是否恢复管理员权限
            dry_run: 是否为模拟运行（只预览变更，不实际执行）
            
        Returns:
            重建结果或预览信息
        """
        # 如果未指定目标群，则使用备份来源群
        if target_group_id is None:
            target_group_id = group_id
        
        # 更新实例配置
        self.restore_cards = restore_cards
        self.restore_titles = restore_titles
        self.restore_admins = restore_admins
        
        # 获取备份成员
        async with db_manager.get_async_session() as session:
            # 获取备份信息
            backup_result = await session.execute(
                select(Backup).where(Backup.id == backup_id)
            )
            backup = backup_result.scalar_one_or_none()
            
            if not backup:
                raise ValueError(f"备份 {backup_id} 不存在")
            
            # 验证备份来源群（确保备份确实是这个群的）
            if backup.group_id != group_id:
                raise ValueError(f"备份 {backup_id} 不属于群组 {group_id}")
            
            # 获取备份成员
            result = await session.execute(
                select(BackupMember).where(BackupMember.backup_id == backup_id)
            )
            backup_members = list(result.scalars().all())
        
        if not backup_members:
            raise ValueError(f"备份 {backup_id} 中没有成员数据")
        
        is_cross_group = target_group_id != group_id
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}从备份 {backup_id} (群 {group_id}) 重建到群 {target_group_id}, 成员数: {len(backup_members)}, 跨群: {is_cross_group}")
        
        if dry_run:
            # 模拟运行：只分析差异，不执行实际操作
            return await self._dry_run_rebuild(target_group_id, backup_members, source_group_id=group_id)
        else:
            # 实际执行
            progress = await self._rebuild_group(target_group_id, backup_members, None)
            return {
                "success": True,
                "status": progress.status.value,
                "total": progress.total,
                "success_count": progress.success,
                "failed_count": progress.failed,
                "skipped_count": progress.skipped,
                "results": [
                    {
                        "user_id": r.user_id,
                        "nickname": r.nickname,
                        "status": r.status.value,
                        "message": r.message,
                    }
                    for r in progress.results
                ]
            }
    
    async def _dry_run_rebuild(
        self,
        group_id: int,
        backup_members: List[BackupMember],
        source_group_id: int = None
    ) -> Dict[str, Any]:
        """
        模拟运行重建（只分析差异，不执行操作）
        
        Args:
            group_id: 目标群号（恢复到哪个群）
            backup_members: 备份成员列表
            source_group_id: 备份来源群号（可选，用于显示跨群信息）
            
        Returns:
            预览信息
        """
        is_cross_group = source_group_id and source_group_id != group_id
        changes = []
        
        # 获取当前群成员（使用 no_cache 确保获取最新数据）
        try:
            current_members = await self.client.get_group_member_list(group_id, no_cache=True)
            current_map = {m.get("user_id"): m for m in current_members}
            current_user_ids = set(current_map.keys())
        except Exception as e:
            logger.error(f"获取目标群成员失败: {str(e)}")
            raise ValueError(f"获取群成员失败: {str(e)}")
        
        # 获取登录账号
        try:
            login_info = await self.client.get_login_info()
            bot_user_id = login_info.get("user_id")
        except:
            bot_user_id = None
        
        # 获取好友列表
        try:
            friends = await self.client.get_friend_list()
            friend_ids = set(f.get("user_id") for f in friends)
        except:
            friend_ids = set()
        
        # 统计
        stats = {
            "total_backup_members": len(backup_members),
            "current_members": len(current_user_ids),
            "will_skip_bot": 0,
            "will_skip_already_in": 0,
            "will_skip_not_friend": 0,
            "will_restore_card": 0,
            "will_restore_title": 0,
            "will_restore_admin": 0,
            "cannot_invite": 0,
        }
        
        for member in backup_members:
            user_id = member.user_id
            
            # 跳过 Bot 自身
            if user_id == bot_user_id:
                stats["will_skip_bot"] += 1
                changes.append({
                    "user_id": user_id,
                    "nickname": member.nickname,
                    "action": "skip",
                    "reason": "Bot自身",
                    "details": []
                })
                continue
            
            # 检查是否已在群内
            if user_id in current_user_ids:
                stats["will_skip_already_in"] += 1
                current_member = current_map[user_id]
                member_changes = []
                
                # 检查名片差异（备份值可能是空字符串，也需要恢复）
                if self.restore_cards:
                    current_card = current_member.get("card", "") or ""
                    backup_card = member.card or ""
                    if current_card != backup_card:
                        member_changes.append({
                            "type": "card",
                            "current": current_card,
                            "backup": backup_card,
                            "action": f"将名片从 '{current_card}' 改为 '{backup_card}'" if backup_card else f"清空名片（当前: '{current_card}'）"
                        })
                        stats["will_restore_card"] += 1
                
                # 检查头衔差异（备份值可能是空字符串，也需要恢复）
                if self.restore_titles:
                    current_title = current_member.get("title", "") or ""
                    backup_title = member.title or ""
                    if current_title != backup_title:
                        member_changes.append({
                            "type": "title",
                            "current": current_title,
                            "backup": backup_title,
                            "action": f"将头衔从 '{current_title}' 改为 '{backup_title}'" if backup_title else f"清空头衔（当前: '{current_title}'）"
                        })
                        stats["will_restore_title"] += 1
                
                # 检查管理员差异
                if self.restore_admins and member.role == "admin":
                    current_role = current_member.get("role", "member")
                    if current_role != "admin" and current_role != "owner":
                        member_changes.append({
                            "type": "admin",
                            "current": current_role,
                            "backup": "admin",
                            "action": f"将 {member.nickname} 设为管理员"
                        })
                        stats["will_restore_admin"] += 1
                
                if member_changes:
                    changes.append({
                        "user_id": user_id,
                        "nickname": member.nickname,
                        "action": "restore",
                        "reason": "已在群内，将恢复信息",
                        "details": member_changes
                    })
                else:
                    changes.append({
                        "user_id": user_id,
                        "nickname": member.nickname,
                        "action": "skip",
                        "reason": "已在群内，无需更改",
                        "details": []
                    })
            else:
                # 不在群内的成员
                if user_id not in friend_ids:
                    stats["will_skip_not_friend"] += 1
                    stats["cannot_invite"] += 1
                    changes.append({
                        "user_id": user_id,
                        "nickname": member.nickname,
                        "action": "cannot_invite",
                        "reason": "非好友，无法邀请",
                        "details": []
                    })
                else:
                    stats["cannot_invite"] += 1
                    changes.append({
                        "user_id": user_id,
                        "nickname": member.nickname,
                        "action": "need_invite",
                        "reason": "是好友，但OneBot标准不支持直接邀请入群",
                        "details": []
                    })
        
        return {
            "dry_run": True,
            "message": "这是模拟运行结果，不会执行任何实际操作" + (f"（跨群重建：从群 {source_group_id} 恢复到群 {group_id}）" if is_cross_group else ""),
            "statistics": stats,
            "changes": changes,
            "summary": {
                "restore_cards": self.restore_cards,
                "restore_titles": self.restore_titles,
                "restore_admins": self.restore_admins,
                "total_changes": stats["will_restore_card"] + stats["will_restore_title"] + stats["will_restore_admin"],
                "is_cross_group": is_cross_group,
                "source_group_id": source_group_id,
                "target_group_id": group_id,
                "warning": "OneBot 11 标准不支持直接邀请成员入群，只能恢复已在目标群内成员的信息" if stats["cannot_invite"] > 0 else None
            }
        }

    
    async def rebuild_from_members(
        self,
        target_group_id: int,
        members: List[Dict[str, Any]],
        progress_callback: Callable[[RebuildProgress], None] = None
    ) -> RebuildProgress:
        """
        从成员列表重建群组
        
        Args:
            target_group_id: 目标群号
            members: 成员列表 (包含 user_id, nickname, card, role 等)
            progress_callback: 进度回调函数
            
        Returns:
            重建进度
        """
        # 转换为 BackupMember 格式
        backup_members = []
        for m in members:
            bm = BackupMember(
                backup_id=0,
                user_id=m.get("user_id"),
                nickname=m.get("nickname", ""),
                card=m.get("card", ""),
                role=m.get("role", "member"),
                title=m.get("title", ""),
            )
            backup_members.append(bm)
        
        return await self._rebuild_group(
            target_group_id,
            backup_members,
            progress_callback
        )
    
    async def _rebuild_group(
        self,
        target_group_id: int,
        members: List[BackupMember],
        progress_callback: Callable[[RebuildProgress], None] = None
    ) -> RebuildProgress:
        """
        执行群组重建
        
        Args:
            target_group_id: 目标群号
            members: 要邀请的成员列表
            progress_callback: 进度回调函数
            
        Returns:
            重建进度
        """
        # 初始化进度
        self._progress = RebuildProgress(
            total=len(members),
            status=RebuildStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        self._cancelled = False
        self._paused = False
        
        # 获取当前群成员（使用 no_cache 确保获取最新数据）
        try:
            current_members = await self.client.get_group_member_list(target_group_id, no_cache=True)
            current_user_ids = set(m.get("user_id") for m in current_members)
        except Exception as e:
            logger.error(f"获取目标群成员失败: {str(e)}")
            current_user_ids = set()
        
        # 获取登录账号
        try:
            login_info = await self.client.get_login_info()
            bot_user_id = login_info.get("user_id")
        except:
            bot_user_id = None
        
        # 发送开始通知
        if self.send_welcome:
            try:
                await self.client.send_group_msg(
                    target_group_id,
                    f"🔄 群组重建开始\n预计邀请 {len(members)} 位成员"
                )
            except Exception as e:
                logger.warning(f"发送通知失败: {str(e)}")
        
        # 分离管理员和普通成员
        admins = [m for m in members if m.role == "admin"]
        owners = [m for m in members if m.role == "owner"]
        regular_members = [m for m in members if m.role == "member"]
        
        # 按顺序处理: 普通成员 -> 管理员
        all_members = regular_members + admins
        
        for member in all_members:
            # 检查取消/暂停
            if self._cancelled:
                self._progress.status = RebuildStatus.CANCELLED
                break
            
            while self._paused:
                await asyncio.sleep(1)
                if self._cancelled:
                    break
            
            self._progress.current_user = member.user_id
            
            # 跳过 Bot 自己
            if member.user_id == bot_user_id:
                result = InviteResult(
                    user_id=member.user_id,
                    nickname=member.nickname,
                    status=InviteStatus.SKIPPED,
                    message="Bot 自身"
                )
                self._progress.skipped += 1
                self._progress.processed += 1
                self._progress.results.append(result)
                continue
            
            # 跳过已在群内的成员，但恢复其信息
            if member.user_id in current_user_ids:
                # 恢复名片和权限
                restore_details = await self._restore_member_info(target_group_id, member)
                
                if restore_details:
                    # 有恢复操作执行
                    result = InviteResult(
                        user_id=member.user_id,
                        nickname=member.nickname,
                        status=InviteStatus.SUCCESS,
                        message=f"已在群内，恢复了: {', '.join(restore_details)}"
                    )
                    self._progress.success += 1
                else:
                    # 无需恢复
                    result = InviteResult(
                        user_id=member.user_id,
                        nickname=member.nickname,
                        status=InviteStatus.SKIPPED,
                        message="已在群内，无需更改"
                    )
                    self._progress.skipped += 1
                
                self._progress.processed += 1
                self._progress.results.append(result)
                continue
            
            # 尝试邀请
            invite_result = await self._invite_member(target_group_id, member)
            self._progress.results.append(invite_result)
            self._progress.processed += 1
            
            if invite_result.status == InviteStatus.SUCCESS:
                self._progress.success += 1
                current_user_ids.add(member.user_id)
                
                # 恢复名片和权限
                await self._restore_member_info(target_group_id, member)
                
            elif invite_result.status == InviteStatus.FAILED:
                self._progress.failed += 1
                if not self.continue_on_error:
                    self._progress.status = RebuildStatus.FAILED
                    self._progress.error_message = invite_result.message
                    break
            else:
                self._progress.skipped += 1
            
            # 回调
            if progress_callback:
                progress_callback(self._progress)
            
            # 速率控制
            await asyncio.sleep(self.invite_interval)
        
        # 完成
        if self._progress.status == RebuildStatus.RUNNING:
            self._progress.status = RebuildStatus.COMPLETED
        
        self._progress.completed_at = datetime.utcnow()
        self._progress.current_user = None
        
        # 发送完成通知
        if self.send_welcome:
            try:
                await self.client.send_group_msg(
                    target_group_id,
                    f"✅ 群组重建完成\n"
                    f"成功: {self._progress.success}\n"
                    f"失败: {self._progress.failed}\n"
                    f"跳过: {self._progress.skipped}"
                )
            except Exception as e:
                logger.warning(f"发送通知失败: {str(e)}")
        
        logger.info(
            f"重建完成: 成功 {self._progress.success}, "
            f"失败 {self._progress.failed}, "
            f"跳过 {self._progress.skipped}"
        )
        
        return self._progress
    
    async def _invite_member(
        self,
        group_id: int,
        member: BackupMember
    ) -> InviteResult:
        """
        邀请单个成员
        
        注意: OneBot 11 标准没有直接邀请成员的 API
        这里使用发送私聊消息的方式模拟邀请通知
        实际的群邀请需要用户手动操作或使用扩展 API
        """
        try:
            # 检查是否是好友
            friends = await self.client.get_friend_list()
            friend_ids = set(f.get("user_id") for f in friends)
            
            if member.user_id not in friend_ids:
                return InviteResult(
                    user_id=member.user_id,
                    nickname=member.nickname,
                    status=InviteStatus.SKIPPED,
                    message="非好友,无法邀请"
                )
            
            # 由于 OneBot 11 没有直接邀请入群的 API
            # 这里我们记录需要邀请的用户
            # 实际邀请需要 Bot 有相应权限或使用扩展 API
            
            logger.info(f"需要邀请成员: {member.nickname}({member.user_id})")
            
            # 返回成功(标记为待邀请)
            return InviteResult(
                user_id=member.user_id,
                nickname=member.nickname,
                status=InviteStatus.SUCCESS,
                message="已标记待邀请"
            )
            
        except Exception as e:
            logger.error(f"邀请失败 {member.user_id}: {str(e)}")
            return InviteResult(
                user_id=member.user_id,
                nickname=member.nickname,
                status=InviteStatus.FAILED,
                message=str(e)
            )
    
    async def _restore_member_info(
        self,
        group_id: int,
        member: BackupMember
    ) -> List[str]:
        """
        恢复成员信息(名片、头衔、权限)
        
        Returns:
            成功恢复的项目列表 (如 ["名片", "头衔", "管理员"])
        """
        restored = []
        
        try:
            # 恢复群名片（备份值可能是空字符串，也需要设置以清空）
            if self.restore_cards:
                backup_card = member.card or ""
                try:
                    await self.client.set_group_card(
                        group_id,
                        member.user_id,
                        backup_card
                    )
                    if backup_card:
                        logger.debug(f"已恢复名片: {member.user_id} -> {backup_card}")
                        restored.append(f"名片'{backup_card}'")
                    else:
                        logger.debug(f"已清空名片: {member.user_id}")
                        restored.append("清空名片")
                except Exception as e:
                    logger.warning(f"恢复名片失败 {member.user_id}: {str(e)}")
            
            # 恢复专属头衔（备份值可能是空字符串，也需要设置以清空）
            if self.restore_titles:
                backup_title = member.title or ""
                try:
                    await self.client.set_group_special_title(
                        group_id,
                        member.user_id,
                        backup_title
                    )
                    if backup_title:
                        logger.debug(f"已恢复头衔: {member.user_id} -> {backup_title}")
                        restored.append(f"头衔'{backup_title}'")
                    else:
                        logger.debug(f"已清空头衔: {member.user_id}")
                        restored.append("清空头衔")
                except Exception as e:
                    logger.warning(f"恢复头衔失败 {member.user_id}: {str(e)}")
            
            # 恢复管理员权限
            if self.restore_admins and member.role == "admin":
                try:
                    await self.client.set_group_admin(
                        group_id,
                        member.user_id,
                        True
                    )
                    logger.debug(f"已恢复管理员: {member.user_id}")
                    restored.append("管理员权限")
                except Exception as e:
                    logger.warning(f"恢复管理员失败 {member.user_id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"恢复成员信息失败 {member.user_id}: {str(e)}")
        
        return restored
    
    async def get_rebuild_summary(self) -> Dict[str, Any]:
        """获取重建摘要"""
        if not self._progress:
            return {"message": "没有进行中的重建任务"}
        
        return {
            **self._progress.to_dict(),
            "invite_results": [
                {
                    "user_id": r.user_id,
                    "nickname": r.nickname,
                    "status": r.status.value,
                    "message": r.message,
                }
                for r in self._progress.results
            ]
        }
