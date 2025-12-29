"""
日志工具模块
"""
from pathlib import Path
from typing import Optional
from loguru import logger
import sys


class LoggerManager:
    """日志管理器"""
    
    def __init__(self):
        self._initialized = False
    
    def setup(
        self,
        level: str = "INFO",
        log_file: Optional[str] = None,
        max_size: int = 10,
        backup_count: int = 5,
        console: bool = True,
        format_string: Optional[str] = None
    ):
        """
        设置日志
        
        Args:
            level: 日志级别
            log_file: 日志文件路径
            max_size: 日志文件最大大小 (MB)
            backup_count: 保留的日志文件数量
            console: 是否输出到控制台
            format_string: 日志格式
        """
        if self._initialized:
            logger.warning("日志已经初始化，跳过重复初始化")
            return
        
        # 移除默认处理器
        logger.remove()
        
        # 默认格式
        if format_string is None:
            format_string = (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            )
        
        # 添加控制台处理器
        if console:
            logger.add(
                sys.stdout,
                format=format_string,
                level=level,
                colorize=True,
                backtrace=True,
                diagnose=True
            )
        
        # 添加文件处理器
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_file,
                format=format_string,
                level=level,
                rotation=f"{max_size} MB",
                retention=backup_count,
                compression="zip",
                encoding="utf-8",
                backtrace=True,
                diagnose=True
            )
        
        self._initialized = True
        logger.info(f"日志系统已初始化 - Level: {level}, File: {log_file}")
    
    def get_logger(self, name: str = None):
        """获取日志器"""
        if not self._initialized:
            self.setup()
        
        if name:
            return logger.bind(name=name)
        return logger


# 全局日志管理器实例
logger_manager = LoggerManager()


def get_logger(name: str = None):
    """获取日志器"""
    return logger_manager.get_logger(name)


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_size: int = 10,
    backup_count: int = 5,
    console: bool = True,
    format_string: Optional[str] = None
):
    """设置日志（便捷函数）"""
    logger_manager.setup(
        level=level,
        log_file=log_file,
        max_size=max_size,
        backup_count=backup_count,
        console=console,
        format_string=format_string
    )
