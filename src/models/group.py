"""
群组数据模型
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, BigInteger, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Group(Base):
    """群组模型"""
    __tablename__ = "groups"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, comment="QQ群号")
    group_name: Mapped[str] = mapped_column(String(255), comment="群名称")
    owner_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="群主QQ")
    member_count: Mapped[int] = mapped_column(Integer, default=0, comment="成员数")
    max_member_count: Mapped[int] = mapped_column(Integer, default=0, comment="最大成员数")
    group_level: Mapped[int] = mapped_column(Integer, default=0, comment="群等级")
    group_memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="群公告/简介")
    
    # 元数据
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否活跃")
    last_backup_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最后备份时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        comment="更新时间"
    )
    
    # 关系
    members: Mapped[List["Member"]] = relationship(
        "Member",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    backups: Mapped[List["Backup"]] = relationship(
        "Backup",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Group {self.group_name}({self.group_id})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "owner_id": self.owner_id,
            "member_count": self.member_count,
            "max_member_count": self.max_member_count,
            "group_level": self.group_level,
            "group_memo": self.group_memo,
            "is_active": self.is_active,
            "last_backup_at": self.last_backup_at.isoformat() if self.last_backup_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
