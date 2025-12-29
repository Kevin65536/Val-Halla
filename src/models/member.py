"""
成员数据模型
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .database import Base

if TYPE_CHECKING:
    from .group import Group


class MemberRole(enum.Enum):
    """成员角色"""
    OWNER = "owner"      # 群主
    ADMIN = "admin"      # 管理员
    MEMBER = "member"    # 普通成员


class MemberGender(enum.Enum):
    """成员性别"""
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class Member(Base):
    """群成员模型"""
    __tablename__ = "members"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        index=True,
        comment="群号"
    )
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="QQ号")
    
    # 基本信息
    nickname: Mapped[str] = mapped_column(String(255), comment="昵称")
    card: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="群名片")
    sex: Mapped[str] = mapped_column(
        String(20), 
        default=MemberGender.UNKNOWN.value,
        comment="性别"
    )
    age: Mapped[int] = mapped_column(Integer, default=0, comment="年龄")
    area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="地区")
    
    # 群内信息
    role: Mapped[str] = mapped_column(
        String(20),
        default=MemberRole.MEMBER.value,
        comment="角色"
    )
    level: Mapped[str] = mapped_column(String(50), default="", comment="等级")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="专属头衔")
    title_expire_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="头衔过期时间戳")
    
    # 时间信息
    join_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="加群时间戳")
    last_sent_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最后发言时间戳")
    shut_up_timestamp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="禁言到期时间戳")
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )
    
    # 关系
    group: Mapped["Group"] = relationship("Group", back_populates="members")
    
    def __repr__(self):
        return f"<Member {self.nickname}({self.user_id}) in {self.group_id}>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "card": self.card,
            "sex": self.sex,
            "age": self.age,
            "area": self.area,
            "role": self.role,
            "level": self.level,
            "title": self.title,
            "title_expire_time": self.title_expire_time,
            "join_time": self.join_time,
            "last_sent_time": self.last_sent_time,
            "shut_up_timestamp": self.shut_up_timestamp,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_onebot_data(cls, group_id: int, data: dict) -> "Member":
        """从 OneBot API 响应创建成员对象"""
        return cls(
            group_id=group_id,
            user_id=data.get("user_id"),
            nickname=data.get("nickname", ""),
            card=data.get("card", ""),
            sex=data.get("sex", "unknown"),
            age=data.get("age", 0),
            area=data.get("area", ""),
            role=data.get("role", "member"),
            level=data.get("level", ""),
            title=data.get("title", ""),
            title_expire_time=data.get("title_expire_time"),
            join_time=data.get("join_time"),
            last_sent_time=data.get("last_sent_time"),
            shut_up_timestamp=data.get("shut_up_timestamp"),
        )


class MemberHistory(Base):
    """成员变更历史"""
    __tablename__ = "member_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="群号")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="QQ号")
    nickname: Mapped[str] = mapped_column(String(255), comment="当时昵称")
    action: Mapped[str] = mapped_column(String(20), comment="操作类型: join/leave")
    backup_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("backups.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联备份ID"
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="变更时间")
    
    def __repr__(self):
        return f"<MemberHistory {self.user_id} {self.action} {self.group_id}>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "action": self.action,
            "backup_id": self.backup_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
