"""Shared configuration and dependency construction for CLI and WebUI."""

from src.api.onebot import OneBotAPI
from src.models import init_database
from src.utils.config import config_manager, project_path
from src.utils.logger import setup_logger


def load_config():
    config = config_manager.load().model_copy(deep=True)
    config.database.sqlite.path = str(project_path(config.database.sqlite.path))
    config.backup.backup_dir = str(project_path(config.backup.backup_dir))
    config.logging.file = str(project_path(config.logging.file))
    return config


def initialize(config=None):
    config = config or load_config()
    setup_logger(
        level=config.logging.level,
        log_file=config.logging.file,
        max_size=config.logging.max_size,
        backup_count=config.logging.backup_count,
        console=config.logging.console,
    )
    init_database(config.database)
    return config


def create_client(config):
    protocol, host, port = config.onebot.endpoint
    return OneBotAPI(
        host=host,
        port=port,
        protocol=protocol,
        access_token=config.onebot.access_token,
        timeout=config.onebot.api_timeout,
    )
