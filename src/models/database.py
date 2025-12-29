"""
数据库连接和会话管理
"""
from pathlib import Path
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None
        self._initialized = False
    
    def init_sqlite(self, db_path: str):
        """
        初始化 SQLite 数据库
        
        Args:
            db_path: 数据库文件路径
        """
        # 确保目录存在
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 同步引擎
        sync_url = f"sqlite:///{db_path}"
        self._engine = create_engine(sync_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        
        # 异步引擎
        async_url = f"sqlite+aiosqlite:///{db_path}"
        self._async_engine = create_async_engine(async_url, echo=False)
        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self._initialized = True
        logger.info(f"SQLite 数据库已初始化: {db_path}")
    
    def init_postgresql(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        pool_size: int = 10,
        max_overflow: int = 20
    ):
        """
        初始化 PostgreSQL 数据库
        
        Args:
            host: 数据库主机
            port: 数据库端口
            database: 数据库名
            user: 用户名
            password: 密码
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
        """
        # 同步引擎
        sync_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self._engine = create_engine(
            sync_url,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow
        )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        
        # 异步引擎
        async_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        self._async_engine = create_async_engine(
            async_url,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow
        )
        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self._initialized = True
        logger.info(f"PostgreSQL 数据库已初始化: {host}:{port}/{database}")
    
    def create_tables(self):
        """创建所有表"""
        if not self._initialized:
            raise RuntimeError("数据库未初始化")
        
        Base.metadata.create_all(self._engine)
        logger.info("数据库表已创建")
    
    async def create_tables_async(self):
        """异步创建所有表"""
        if not self._initialized:
            raise RuntimeError("数据库未初始化")
        
        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已创建 (async)")
    
    def get_session(self) -> Session:
        """获取同步会话"""
        if not self._initialized:
            raise RuntimeError("数据库未初始化")
        return self._session_factory()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取异步会话"""
        if not self._initialized:
            raise RuntimeError("数据库未初始化")
        
        session = self._async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def close(self):
        """关闭数据库连接"""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._engine:
            self._engine.dispose()
        logger.info("数据库连接已关闭")


# 全局数据库管理器实例
db_manager = DatabaseManager()


def init_database(config):
    """
    根据配置初始化数据库
    
    Args:
        config: 数据库配置对象
    """
    if config.type == "sqlite":
        db_manager.init_sqlite(config.sqlite.path)
    elif config.type == "postgresql":
        pg = config.postgresql
        db_manager.init_postgresql(
            host=pg.host,
            port=pg.port,
            database=pg.database,
            user=pg.user,
            password=pg.password,
            pool_size=pg.pool_size,
            max_overflow=pg.max_overflow
        )
    else:
        raise ValueError(f"不支持的数据库类型: {config.type}")
    
    # 创建表
    db_manager.create_tables()


def get_db() -> DatabaseManager:
    """获取数据库管理器"""
    return db_manager
