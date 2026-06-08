# backend/app/models/schemas.py

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Literal


# Valid values for security configuration
AUTH_TYPES      = Literal["anonymous", "username"]
SECURITY_MODES  = Literal["None", "Sign", "SignAndEncrypt"]
SECURITY_POLICIES = Literal[
    "None",
    "Basic256Sha256",
    "Aes128Sha256RsaOaep",
    "Aes256Sha256RsaPss",
]


class ConnectionCreate(BaseModel):
    name: str
    endpoint: str

    # Security — all optional with safe defaults
    auth_type:        AUTH_TYPES       = "anonymous"
    username:         str | None       = None
    password:         str | None       = None
    security_mode:    SECURITY_MODES   = "None"
    security_policy:  SECURITY_POLICIES = "None"
    certificate_path: str | None       = None
    private_key_path: str | None       = None

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        if not v.startswith("opc.tcp://"):
            raise ValueError("Endpoint must start with opc.tcp://")
        return v

    @field_validator("security_policy")
    @classmethod
    def validate_policy_mode_combo(cls, v: str, info) -> str:
        """Security policy must match security mode."""
        mode = info.data.get("security_mode", "None")
        if mode == "None" and v != "None":
            raise ValueError(
                "Security policy must be 'None' when security mode is 'None'"
            )
        if mode != "None" and v == "None":
            raise ValueError(
                f"Security policy cannot be 'None' when security mode is '{mode}'. "
                "Choose a policy such as 'Basic256Sha256'."
            )
        return v

    @field_validator("username")
    @classmethod
    def validate_username_required(cls, v: str | None, info) -> str | None:
        """Username is required when auth_type is 'username'."""
        if info.data.get("auth_type") == "username" and not v:
            raise ValueError("Username is required for username/password authentication")
        return v


class ConnectionResponse(BaseModel):
    id: int
    name: str
    endpoint: str
    is_active: bool
    created_at: datetime

    # State machine fields
    last_connected_at: datetime | None = None
    last_error: str | None = None
    retry_count: int = 0

    # Security fields — password intentionally excluded from response
    auth_type:        str = "anonymous"
    security_mode:    str = "None"
    security_policy:  str = "None"
    certificate_path: str | None = None
    private_key_path: str | None = None

    model_config = {"from_attributes": True}
