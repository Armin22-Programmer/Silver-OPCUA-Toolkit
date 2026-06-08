# backend/app/main.py

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import init_db, AsyncSessionLocal
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.routes.connections import router as connections_router
from app.api.routes.tags import router as tags_router
from app.api.routes.websocket import router as websocket_router
from app.api.routes.certificates import router as certificates_router
from app.opcua.manager import opcua_manager
from app.models.connection import Connection
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# How often to check if OPC UA connections are still alive
HEALTH_CHECK_INTERVAL = 10.0


async def _connection_health_check() -> None:
    """
    Background task that periodically pings all active OPC UA connections.
    If a connection is found to be dead, marks it as inactive in the DB
    so the frontend reflects the correct state.
    """
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Connection).where(Connection.is_active.is_(True))
                )
                active_connections = result.scalars().all()

                for conn in active_connections:
                    alive = await opcua_manager.ping(conn.id)
                    if not alive:
                        await opcua_manager._force_cleanup(conn.id)
                        conn.is_active = False
                        conn.last_error = "Connection lost — server may have restarted"
                        await db.commit()
                        logger.warning(
                            f"Connection lost [id={conn.id}, endpoint={conn.endpoint}]"
                        )
        except Exception as e:
            logger.error(f"Health check error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENV}]")

    await init_db()

    # Restore active connections from DB on startup
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Connection).where(Connection.is_active.is_(True))
        )
        active_connections = result.scalars().all()

        for conn in active_connections:
            success, _ = await opcua_manager.connect(
                connection_id=conn.id,
                endpoint=conn.endpoint,
                auth_type=conn.auth_type,
                username=conn.username,
                password=conn.password,
                security_mode=conn.security_mode,
                security_policy=conn.security_policy,
                certificate_path=conn.certificate_path,
                private_key_path=conn.private_key_path,
            )
            if not success:
                conn.is_active = False
                await db.commit()
                logger.warning(
                    f"Auto-reconnect failed for connection {conn.id} ({conn.endpoint})"
                )
            else:
                logger.info(f"Auto-reconnected connection {conn.id} ({conn.endpoint})")

    # Start background health check
    health_task = asyncio.create_task(_connection_health_check())

    yield

    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass

    logger.info("Shutting down — closing all OPC UA connections...")
    await opcua_manager.disconnect_all()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="OPC UA Tooling for Industrial Engineers",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connections_router)
app.include_router(tags_router)
app.include_router(websocket_router)
app.include_router(certificates_router)


@app.get("/health")
async def health_check():
    """Simple health check endpoint to verify the server is running."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "env": settings.ENV,
    }
