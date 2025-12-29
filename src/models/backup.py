"""
备份记录数据模型
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .database import Base

if TYPE_CHECKING:
    from .group import Group


class BackupType(enum.Enum):
    """备份类型"""
    FULL = "full"              # 全量备份
    INCREMENTAL = "incremental"  # 增量备份
    MANUAL = "manual"          # 手动备份


class BackupStatus(enum.Enum):
    """备份状态"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 进行中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    PARTIAL = "partial"      # 部分成功


class Backup(Base):
    """备份记录模型"""
    __tablename__ = "backups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        index=True,
        comment="群号"
    )
    
    # 备份信息
    backup_type: Mapped[str] = mapped_column(
        String(20),
        default=BackupType.FULL.value,
        comment="备份类型"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=BackupStatus.PENDING.value,
        comment="备份状态"
    )
    
    # 统计信息
    member_count: Mapped[int] = mapped_column(Integer, default=0, comment="备份成员数")
    new_members: Mapped[int] = mapped_column(Integer, default=0, comment="新增成员数")
    left_members: Mapped[int] = mapped_column(Integer, default=0, comment="退群成员数")
    
    # 文件信息
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备份文件路径")
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="文件大小(字节)")
    compressed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否压缩")
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否加密")
    
    # 备份数据摘要 (JSON格式)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="备份摘要")
    
    # 备注和错误
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    
    # 时间信息
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="开始时间")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    
    # 关系
    group: Mapped["Group"] = relationship("Group", back_populates="backups")
    
    def __repr__(self):
        return f"<Backup {self.id} for {self.group_id} ({self.status})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "backup_type": self.backup_type,
            "status": self.status,
            "member_count": self.member_count,
            "new_members": self.new_members,
            "left_members": self.left_members,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "compressed": self.compressed,
            "encrypted": self.encrypted,
            "summary": self.summary,
            "notes": self.notes,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @property
    def duration(self) -> Optional[float]:
        """获取备份耗时(秒)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class BackupMember(Base):
    """备份中的成员快照"""
    __tablename__ = "backup_members"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backup_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("backups.id", ondelete="CASCADE"),
        index=True,
        comment="备份ID"
    )
    
    # 成员信息快照
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="QQ号")
    nickname: Mapped[str] = mapped_column(String(255), comment="昵称")
    card: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="群名片")
    sex: Mapped[str] = mapped_column(String(20), default="unknown", comment="性别")
    role: Mapped[str] = mapped_column(String(20), default="member", comment="角色")
    level: Mapped[str] = mapped_column(String(50), default="", comment="等级")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="专属头衔")
    join_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="加群时间戳")
    last_sent_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最后发言时间戳")
    
    def __repr__(self):
        return f"<BackupMember {self.user_id} in backup {self.backup_id}>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "backup_id": self.backup_id,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "card": self.card,
            "sex": self.sex,
            "role": self.role,
            "level": self.level,
            "title": self.title,
            "join_time": self.join_time,
            "last_sent_time": self.last_sent_time,
        }
