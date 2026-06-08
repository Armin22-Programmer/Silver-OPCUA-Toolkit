# backend/app/core/config.py

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Silver OPC UA Toolkit"
    APP_VERSION: str = "0.1.0"
    ENV: Literal["development", "production"] = "development"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "text"

    # OPC UA
    OPCUA_CONNECT_TIMEOUT: int = 10
    OPCUA_MONITOR_INTERVAL: float = 1.0
    OPCUA_PING_INTERVAL: float = 5.0
    OPCUA_HANDSHAKE_TIMEOUT: float = 10.0

    # Certificates — stored alongside DB in data dir
    # Dev default: backend/certs/   Docker: /app/data/certs/
    CERTS_DIR: str = "certs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton instance
settings = Settings()
