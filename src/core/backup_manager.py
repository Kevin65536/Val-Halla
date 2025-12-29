"""
备份管理器 - 核心备份逻辑
"""
import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.onebot import OneBotAPI
from src.models import (
    db_manager, Group, Member, MemberHistory,
    Backup, BackupMember, BackupType, BackupStatus
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BackupManager:
    """备份管理器"""
    
    def __init__(
        self,
        client: OneBotAPI,
        backup_dir: str = "data/backups",
        compression: bool = True,
        encryption: bool = False
    ):
        """
        初始化备份管理器
        
        Args:
            client: OneBot API 客户端
            backup_dir: 备份目录
            compression: 是否压缩
            encryption: 是否加密
        """
        self.client = client
        self.backup_dir = Path(backup_dir)
        self.compression = compression
        self.encryption = encryption
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"备份管理器已初始化: {self.backup_dir}")
    
    async def sync_group_info(self, group_id: int) -> Optional[Group]:
        """
        同步群信息到数据库
        
        Args:
            group_id: 群号
            
        Returns:
            群组对象
        """
        try:
            # 从 OneBot 获取群信息
            group_info = await self.client.get_group_info(group_id, no_cache=True)
            
            async with db_manager.get_async_session() as session:
                # 查询现有群组
                result = await session.execute(
                    select(Group).where(Group.group_id == group_id)
                )
                group = result.scalar_one_or_none()
                
                if group:
                    # 更新现有群组
                    group.group_name = group_info.get("group_name", "")
                    group.member_count = group_info.get("member_count", 0)
                    group.max_member_count = group_info.get("max_member_count", 0)
                    group.group_level = group_info.get("group_level", 0)
                    group.updated_at = datetime.utcnow()
                else:
                    # 创建新群组
                    group = Group(
                        group_id=group_id,
                        group_name=group_info.get("group_name", ""),
                        member_count=group_info.get("member_count", 0),
                        max_member_count=group_info.get("max_member_count", 0),
                        group_level=group_info.get("group_level", 0),
                    )
                    session.add(group)
                
                await session.commit()
                await session.refresh(group)
                
                logger.info(f"群信息已同步: {group.group_name}({group_id})")
                return group
                
        except Exception as e:
            logger.error(f"同步群信息失败: {group_id} - {str(e)}")
            raise
    
    async def backup_group(
        self,
        group_id: int,
        backup_type: BackupType = BackupType.FULL,
        notes: str = ""
    ) -> Backup:
        """
        备份群成员
        
        Args:
            group_id: 群号
            backup_type: 备份类型
            notes: 备注
            
        Returns:
            备份记录
        """
        logger.info(f"开始备份群组: {group_id}, 类型: {backup_type.value}")
        
        async with db_manager.get_async_session() as session:
            # 创建备份记录
            backup = Backup(
                group_id=group_id,
                backup_type=backup_type.value,
                status=BackupStatus.RUNNING.value,
                notes=notes,
                started_at=datetime.utcnow(),
                compressed=self.compression,
                encrypted=self.encryption,
            )
            session.add(backup)
            await session.commit()
            await session.refresh(backup)
            
            try:
                # 同步群信息
                await self.sync_group_info(group_id)
                
                # 获取群成员列表
                members_data = await self.client.get_group_member_list(group_id, no_cache=True)
                logger.info(f"获取到 {len(members_data)} 个成员")
                
                # 获取当前数据库中的成员
                old_members = await self._get_current_members(session, group_id)
                old_user_ids = set(old_members.keys())
                new_user_ids = set(m.get("user_id") for m in members_data)
                
                # 计算变化
                joined_ids = new_user_ids - old_user_ids
                left_ids = old_user_ids - new_user_ids
                
                # 记录成员变化历史
                for user_id in joined_ids:
                    member_data = next(m for m in members_data if m.get("user_id") == user_id)
                    history = MemberHistory(
                        group_id=group_id,
                        user_id=user_id,
                        nickname=member_data.get("nickname", ""),
                        action="join",
                        backup_id=backup.id,
                    )
                    session.add(history)
                
                for user_id in left_ids:
                    old_member = old_members[user_id]
                    history = MemberHistory(
                        group_id=group_id,
                        user_id=user_id,
                        nickname=old_member.nickname,
                        action="leave",
                        backup_id=backup.id,
                    )
                    session.add(history)
                
                # 更新成员表
                await self._update_members(session, group_id, members_data)
                
                # 保存备份成员快照
                for member_data in members_data:
                    backup_member = BackupMember(
                        backup_id=backup.id,
                        user_id=member_data.get("user_id"),
                        nickname=member_data.get("nickname", ""),
                        card=member_data.get("card", ""),
                        sex=member_data.get("sex", "unknown"),
                        role=member_data.get("role", "member"),
                        level=member_data.get("level", ""),
                        title=member_data.get("title", ""),
                        join_time=member_data.get("join_time"),
                        last_sent_time=member_data.get("last_sent_time"),
                    )
                    session.add(backup_member)
                
                # 保存备份文件
                file_path, file_size = await self._save_backup_file(
                    backup.id, group_id, members_data
                )
                
                # 更新备份记录
                backup.status = BackupStatus.SUCCESS.value
                backup.member_count = len(members_data)
                backup.new_members = len(joined_ids)
                backup.left_members = len(left_ids)
                backup.file_path = file_path
                backup.file_size = file_size
                backup.completed_at = datetime.utcnow()
                backup.summary = {
                    "total": len(members_data),
                    "joined": list(joined_ids),
                    "left": list(left_ids),
                    "owners": len([m for m in members_data if m.get("role") == "owner"]),
                    "admins": len([m for m in members_data if m.get("role") == "admin"]),
                }
                
                # 更新群组最后备份时间
                result = await session.execute(
                    select(Group).where(Group.group_id == group_id)
                )
                group = result.scalar_one_or_none()
                if group:
                    group.last_backup_at = datetime.utcnow()
                    group.member_count = len(members_data)
                
                await session.commit()
                
                logger.info(
                    f"备份完成: {group_id}, "
                    f"成员: {len(members_data)}, "
                    f"新增: {len(joined_ids)}, "
                    f"退出: {len(left_ids)}"
                )
                
                return backup
                
            except Exception as e:
                # 更新备份状态为失败
                backup.status = BackupStatus.FAILED.value
                backup.error_message = str(e)
                backup.completed_at = datetime.utcnow()
                await session.commit()
                
                logger.error(f"备份失败: {group_id} - {str(e)}")
                raise
    
    async def _get_current_members(
        self,
        session: AsyncSession,
        group_id: int
    ) -> Dict[int, Member]:
        """获取当前数据库中的成员"""
        result = await session.execute(
            select(Member).where(Member.group_id == group_id)
        )
        members = result.scalars().all()
        return {m.user_id: m for m in members}
    
    async def _update_members(
        self,
        session: AsyncSession,
        group_id: int,
        members_data: List[Dict[str, Any]]
    ):
        """更新成员表"""
        # 删除现有成员
        await session.execute(
            delete(Member).where(Member.group_id == group_id)
        )
        
        # 插入新成员
        for data in members_data:
            member = Member.from_onebot_data(group_id, data)
            session.add(member)
    
    async def _save_backup_file(
        self,
        backup_id: int,
        group_id: int,
        members_data: List[Dict[str, Any]]
    ) -> Tuple[str, int]:
        """
        保存备份文件
        
        Returns:
            (文件路径, 文件大小)
        """
        # 构建文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{group_id}_{timestamp}_{backup_id}.json"
        
        if self.compression:
            filename += ".gz"
        
        file_path = self.backup_dir / str(group_id) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 准备数据
        backup_data = {
            "backup_id": backup_id,
            "group_id": group_id,
            "timestamp": timestamp,
            "member_count": len(members_data),
            "members": members_data,
        }
        
        json_data = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        # 保存文件
        if self.compression:
            with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                f.write(json_data)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
        
        file_size = file_path.stat().st_size
        logger.info(f"备份文件已保存: {file_path} ({file_size} bytes)")
        
        return str(file_path), file_size
    
    async def get_backup_history(
        self,
        group_id: int,
        limit: int = 10
    ) -> List[Backup]:
        """
        获取备份历史
        
        Args:
            group_id: 群号
            limit: 返回数量限制
            
        Returns:
            备份记录列表
        """
        async with db_manager.get_async_session() as session:
            result = await session.execute(
                select(Backup)
                .where(Backup.group_id == group_id)
                .order_by(Backup.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_backup_members(self, backup_id: int) -> List[BackupMember]:
        """
        获取备份中的成员列表
        
        Args:
            backup_id: 备份ID
            
        Returns:
            备份成员列表
        """
        async with db_manager.get_async_session() as session:
            result = await session.execute(
                select(BackupMember).where(BackupMember.backup_id == backup_id)
            )
            return list(result.scalars().all())
    
    async def load_backup_file(self, file_path: str) -> Dict[str, Any]:
        """
        加载备份文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            备份数据
        """
        path = Path(file_path)
        
        if path.suffix == '.gz':
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    async def compare_backups(
        self,
        backup_id_1: int,
        backup_id_2: int
    ) -> Dict[str, Any]:
        """
        比较两个备份
        
        Args:
            backup_id_1: 旧备份ID
            backup_id_2: 新备份ID
            
        Returns:
            比较结果
        """
        members_1 = await self.get_backup_members(backup_id_1)
        members_2 = await self.get_backup_members(backup_id_2)
        
        users_1 = {m.user_id: m for m in members_1}
        users_2 = {m.user_id: m for m in members_2}
        
        ids_1 = set(users_1.keys())
        ids_2 = set(users_2.keys())
        
        joined = ids_2 - ids_1
        left = ids_1 - ids_2
        remained = ids_1 & ids_2
        
        # 检查名片变化
        card_changed = []
        for user_id in remained:
            m1, m2 = users_1[user_id], users_2[user_id]
            if m1.card != m2.card:
                card_changed.append({
                    "user_id": user_id,
                    "old_card": m1.card,
                    "new_card": m2.card,
                })
        
        return {
            "joined": [{"user_id": uid, **users_2[uid].to_dict()} for uid in joined],
            "left": [{"user_id": uid, **users_1[uid].to_dict()} for uid in left],
            "remained": len(remained),
            "card_changed": card_changed,
        }
    
    async def cleanup_old_backups(self, group_id: int, keep_count: int = 30):
        """
        清理旧备份
        
        Args:
            group_id: 群号
            keep_count: 保留的备份数量
        """
        async with db_manager.get_async_session() as session:
            # 获取所有备份,按时间排序
            result = await session.execute(
                select(Backup)
                .where(Backup.group_id == group_id)
                .order_by(Backup.created_at.desc())
            )
            backups = list(result.scalars().all())
            
            if len(backups) <= keep_count:
                return
            
            # 删除多余的备份
            for backup in backups[keep_count:]:
                # 删除备份文件
                if backup.file_path:
                    file_path = Path(backup.file_path)
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"已删除备份文件: {file_path}")
                
                # 删除数据库记录
                await session.delete(backup)
            
            await session.commit()
            logger.info(f"清理了 {len(backups) - keep_count} 个旧备份")
