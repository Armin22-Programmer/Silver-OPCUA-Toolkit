# backend/app/api/routes/connections.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.core.database import get_db
from app.models.connection import Connection
from app.models.schemas import ConnectionCreate, ConnectionResponse
from app.opcua.manager import opcua_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


@router.get("/", response_model=list[ConnectionResponse])
async def list_connections(db: AsyncSession = Depends(get_db)):
    """Return all saved OPC UA connections from the database."""
    result = await db.execute(select(Connection))
    return result.scalars().all()


@router.post("/", response_model=ConnectionResponse)
async def create_connection(
    data: ConnectionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Save a new OPC UA connection to the database."""
    connection = Connection(
        name=data.name,
        endpoint=data.endpoint,
        auth_type=data.auth_type,
        username=data.username,
        password=data.password,
        security_mode=data.security_mode,
        security_policy=data.security_policy,
        certificate_path=data.certificate_path,
        private_key_path=data.private_key_path,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    logger.info(
        f"Connection created [id={connection.id}, name={connection.name}, "
        f"auth={connection.auth_type}, security={connection.security_mode}]"
    )
    return connection


@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a connection from the database and close it if active."""
    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if opcua_manager.is_connected(connection_id):
        await opcua_manager.disconnect(connection_id)
        logger.info(f"Closed active connection before delete [id={connection_id}]")

    await db.delete(connection)
    await db.commit()
    logger.info(f"Connection deleted [id={connection_id}]")
    return {"message": "Connection deleted"}


@router.post("/{connection_id}/connect", response_model=ConnectionResponse)
async def connect_to_server(
    connection_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Connect to the OPC UA server with stored security configuration."""
    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    success, error_msg = await opcua_manager.connect(
        connection_id=connection_id,
        endpoint=connection.endpoint,
        auth_type=connection.auth_type,
        username=connection.username,
        password=connection.password,
        security_mode=connection.security_mode,
        security_policy=connection.security_policy,
        certificate_path=connection.certificate_path,
        private_key_path=connection.private_key_path,
    )

    if not success:
        connection.is_active = False
        connection.retry_count += 1
        connection.last_error = error_msg
        await db.commit()
        await db.refresh(connection)
        logger.warning(
            f"Connection failed [id={connection_id}, "
            f"endpoint={connection.endpoint}, "
            f"retry_count={connection.retry_count}]: {error_msg}"
        )
        raise HTTPException(status_code=400, detail=error_msg)

    connection.is_active = True
    connection.last_connected_at = datetime.now(timezone.utc)
    connection.last_error = None
    connection.retry_count = 0
    await db.commit()
    await db.refresh(connection)
    logger.info(
        f"Connection established [id={connection_id}, "
        f"endpoint={connection.endpoint}, "
        f"auth={connection.auth_type}, security={connection.security_mode}]"
    )
    return connection


@router.post("/{connection_id}/disconnect", response_model=ConnectionResponse)
async def disconnect_from_server(
    connection_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Close the OPC UA connection and mark as inactive in DB."""
    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    await opcua_manager.disconnect(connection_id)

    connection.is_active = False
    await db.commit()
    await db.refresh(connection)
    logger.info(f"Connection closed [id={connection_id}]")
    return connection
