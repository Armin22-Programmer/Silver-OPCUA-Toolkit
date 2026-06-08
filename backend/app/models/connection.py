# backend/app/models/connection.py

from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.core.database import Base


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # State machine fields
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Security fields (v0.4.0-alpha) ────────────────────────────────────

    # Authentication type: "anonymous" or "username"
    auth_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="anonymous"
    )
    # Username for username/password auth (stored in plaintext for alpha)
    username: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    # Password for username/password auth (stored in plaintext for alpha)
    # Note: production deployments should encrypt this field
    password: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    # OPC UA Security Mode: "None", "Sign", "SignAndEncrypt"
    security_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="None"
    )
    # OPC UA Security Policy URI short name:
    # "None", "Basic256Sha256", "Aes128Sha256RsaOaep", "Aes256Sha256RsaPss"
    security_policy: Mapped[str] = mapped_column(
        String(50), nullable=False, default="None"
    )

    # Filesystem paths for certificates (file-based, no PKI UI)
    certificate_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None
    )
    private_key_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None
    )
