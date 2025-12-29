"""
配置管理模块
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class OneBotHttpConfig(BaseModel):
    """OneBot HTTP 配置"""
    host: str = "127.0.0.1"
    port: int = 5700
    timeout: int = 30


class OneBotWebSocketConfig(BaseModel):
    """OneBot WebSocket 配置"""
    host: str = "127.0.0.1"
    port: int = 6700
    reconnect: bool = True
    reconnect_interval: int = 5


class OneBotConfig(BaseModel):
    """OneBot 配置"""
    protocol: str = "http"
    http: OneBotHttpConfig = Field(default_factory=OneBotHttpConfig)
    websocket: OneBotWebSocketConfig = Field(default_factory=OneBotWebSocketConfig)
    access_token: str = ""
    api_timeout: int = 30


class SQLiteConfig(BaseModel):
    """SQLite 配置"""
    path: str = "data/database/valhalla.db"


class PostgreSQLConfig(BaseModel):
    """PostgreSQL 配置"""
    host: str = "localhost"
    port: int = 5432
    database: str = "valhalla"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20


class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: str = "sqlite"
    sqlite: SQLiteConfig = Field(default_factory=SQLiteConfig)
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig)


class BackupConfig(BaseModel):
    """备份配置"""
    auto_backup: bool = True
    interval: int = 3600
    backup_type: str = "incremental"
    max_backups: int = 30
    compression: bool = True
    encryption: bool = False
    encryption_key: str = ""
    backup_dir: str = "data/backups"
    groups: List[int] = Field(default_factory=list)
    exclude_groups: List[int] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    """速率限制配置"""
    invites_per_minute: int = 10
    batch_delay: int = 5
    retry_delay: int = 60
    max_retries: int = 3


class RebuildConfig(BaseModel):
    """重建配置"""
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    restore_admins: bool = True
    restore_cards: bool = True
    restore_titles: bool = False
    send_welcome: bool = True
    welcome_message: str = "欢迎回到群组!"
    continue_on_error: bool = True


class QQNotificationConfig(BaseModel):
    """QQ 通知配置"""
    notify_groups: List[int] = Field(default_factory=list)
    notify_users: List[int] = Field(default_factory=list)
    events: List[str] = Field(default_factory=lambda: [
        "backup_success", "backup_failed",
        "rebuild_start", "rebuild_complete", "rebuild_failed"
    ])


class EmailConfig(BaseModel):
    """邮件配置"""
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: List[str] = Field(default_factory=list)


class WebhookConfig(BaseModel):
    """Webhook 配置"""
    enabled: bool = False
    url: str = ""
    headers: Dict[str, str] = Field(default_factory=lambda: {"Content-Type": "application/json"})
    timeout: int = 10


class NotificationConfig(BaseModel):
    """通知配置"""
    enabled: bool = True
    types: List[str] = Field(default_factory=lambda: ["qq"])
    qq: QQNotificationConfig = Field(default_factory=QQNotificationConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    file: str = "data/logs/valhalla.log"
    max_size: int = 10
    backup_count: int = 5
    console: bool = True
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"


class SecurityConfig(BaseModel):
    """安全配置"""
    admin_users: List[int] = Field(default_factory=list)
    verify_source: bool = True
    allowed_ips: List[str] = Field(default_factory=list)


class CORSConfig(BaseModel):
    """CORS 配置"""
    enabled: bool = True
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])


class WebAPIConfig(BaseModel):
    """Web API 配置"""
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = ""
    docs: bool = True
    cors: CORSConfig = Field(default_factory=CORSConfig)


class CacheConfig(BaseModel):
    """缓存配置"""
    enabled: bool = True
    ttl: int = 300


class PerformanceConfig(BaseModel):
    """性能配置"""
    batch_size: int = 50
    pool_size: int = 10


class AdvancedConfig(BaseModel):
    """高级配置"""
    debug: bool = False
    max_concurrent_tasks: int = 5
    cache: CacheConfig = Field(default_factory=CacheConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)


class Config(BaseModel):
    """主配置"""
    onebot: OneBotConfig = Field(default_factory=OneBotConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    rebuild: RebuildConfig = Field(default_factory=RebuildConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    web_api: WebAPIConfig = Field(default_factory=WebAPIConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._config: Optional[Config] = None
    
    def load(self) -> Config:
        """加载配置"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        self._config = Config(**config_dict)
        return self._config
    
    def save(self, config: Config):
        """保存配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
        
        self._config = config
    
    @property
    def config(self) -> Config:
        """获取配置"""
        if self._config is None:
            self._config = self.load()
        return self._config
    
    def reload(self) -> Config:
        """重新加载配置"""
        self._config = None
        return self.load()


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> Config:
    """获取配置"""
    return config_manager.config
