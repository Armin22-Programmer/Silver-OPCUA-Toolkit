# backend/app/opcua/manager.py

import asyncio
from asyncua import Client
from asyncua.crypto.security_policies import (
    SecurityPolicyBasic256Sha256,
    SecurityPolicyAes128Sha256RsaOaep,
    SecurityPolicyAes256Sha256RsaPss,
)
from asyncua.ua import MessageSecurityMode
from typing import Dict, Optional
import logging
import os

logger = logging.getLogger(__name__)

# Map policy name → asyncua policy class
POLICY_MAP = {
    "Basic256Sha256":       SecurityPolicyBasic256Sha256,
    "Aes128Sha256RsaOaep":  SecurityPolicyAes128Sha256RsaOaep,
    "Aes256Sha256RsaPss":   SecurityPolicyAes256Sha256RsaPss,
}

# Map security mode string → asyncua enum
MODE_MAP = {
    "None":           MessageSecurityMode.None_,
    "Sign":           MessageSecurityMode.Sign,
    "SignAndEncrypt":  MessageSecurityMode.SignAndEncrypt,
}


def _human_readable_error(e: Exception, endpoint: str, security_mode: str) -> str:
    """
    Convert asyncua/SSL exceptions into human-readable messages
    that industrial engineers can act on.
    """
    msg = str(e).lower()

    if "certificate" in msg and "not found" in msg:
        return "Certificate file not found. Check the certificate path in connection settings."
    if "private key" in msg or "key file" in msg:
        return "Private key file not found or invalid. Check the private key path."
    if "certificate" in msg and ("invalid" in msg or "verify" in msg or "expired" in msg):
        return "Server rejected the client certificate. The certificate may be expired or untrusted by the server."
    if "bad certificate" in msg or "badsecuritychecksfailed" in msg:
        return "Security check failed. The server did not accept the certificate. Add the client certificate to the server's trusted certificates."
    if "unsupported" in msg and "policy" in msg:
        return "The selected security policy is not supported by this OPC UA server."
    if "auth" in msg or "username" in msg or "password" in msg or "badidentitytoken" in msg:
        return "Authentication failed. Check username and password."
    if "badconnectionrejected" in msg or "connection refused" in msg:
        return f"Connection refused by server at {endpoint}. The server may be offline or the endpoint is incorrect."
    if "timeout" in msg or "timed out" in msg:
        return f"Connection timed out connecting to {endpoint}. The server may be unreachable."
    if "securitymode" in msg or "security mode" in msg:
        return f"Security mode '{security_mode}' is not supported by this server."
    if "ssl" in msg or "handshake" in msg:
        return "SSL/TLS handshake failed. Check that the certificate and private key are valid and match."

    return f"Failed to connect to {endpoint}: {e}"


def _extract_app_uri_from_cert(cert_path: str) -> str | None:
    """
    Extract the Application URI from a PEM certificate's Subject Alternative Name.
    This must match what asyncua sends during the OPC UA handshake.
    """
    try:
        from cryptography import x509 as _x509
        from cryptography.hazmat.backends import default_backend as _backend
        with open(cert_path, "rb") as f:
            cert = _x509.load_pem_x509_certificate(f.read(), _backend())
        san = cert.extensions.get_extension_for_class(_x509.SubjectAlternativeName)
        for name in san.value:
            if isinstance(name, _x509.UniformResourceIdentifier):
                return name.value
    except Exception:
        pass
    return None


class OPCUAManager:
    def __init__(self):
        self._clients: Dict[int, Client] = {}

    async def connect(
        self,
        connection_id: int,
        endpoint: str,
        # Authentication
        auth_type: str = "anonymous",
        username: str | None = None,
        password: str | None = None,
        # Security
        security_mode: str = "None",
        security_policy: str = "None",
        certificate_path: str | None = None,
        private_key_path: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Connect to an OPC UA server with optional security.
        Returns (success, error_message).
        error_message is None on success, human-readable string on failure.
        """
        # Clean up any existing connection for this ID
        if connection_id in self._clients:
            logger.warning(
                f"Connection {connection_id} already exists — cleaning up before reconnect"
            )
            await self._force_cleanup(connection_id)

        client = Client(url=endpoint, timeout=10)

        try:
            # ── Apply security mode and policy ────────────────────────────
            if security_mode != "None" and security_policy != "None":
                policy_class = POLICY_MAP.get(security_policy)
                mode_enum    = MODE_MAP.get(security_mode)

                if policy_class is None:
                    return False, f"Unsupported security policy: '{security_policy}'."
                if mode_enum is None:
                    return False, f"Unsupported security mode: '{security_mode}'."

                # Validate certificate files exist before attempting connection
                if not certificate_path or not os.path.isfile(certificate_path):
                    return False, (
                        f"Client certificate not found at: '{certificate_path}'. "
                        "Provide a valid certificate path in connection settings."
                    )
                if not private_key_path or not os.path.isfile(private_key_path):
                    return False, (
                        f"Private key not found at: '{private_key_path}'. "
                        "Provide a valid private key path in connection settings."
                    )

                # Extract application URI from certificate to ensure it matches
                # what asyncua sends during handshake — Siemens checks this strictly
                app_uri = _extract_app_uri_from_cert(certificate_path)

                await client.set_security(
                    policy_class,
                    certificate=certificate_path,
                    private_key=private_key_path,
                    mode=mode_enum,
                )

                # Set application URI to match certificate — critical for Siemens S7
                if app_uri:
                    client.application_uri = app_uri
                logger.info(
                    f"Security configured: mode={security_mode}, "
                    f"policy={security_policy} [id={connection_id}]"
                )

            # ── Apply authentication BEFORE connect ──────────────────────
            if auth_type == "username":
                if not username:
                    return False, "Username is required for username/password authentication."
                client.set_user(username)
                client.set_password(password or "")
                logger.info(
                    f"Credentials set for user '{username}' [id={connection_id}]"
                )

            # ── Connect ───────────────────────────────────────────────────
            await client.connect()

            self._clients[connection_id] = client
            logger.info(
                f"Connected to {endpoint} "
                f"[id={connection_id}, auth={auth_type}, security={security_mode}]"
            )
            return True, None

        except Exception as e:
            error_msg = _human_readable_error(e, endpoint, security_mode)
            logger.error(
                f"Failed to connect to {endpoint} [id={connection_id}]: {e}"
            )
            # Best-effort cleanup — don't leave dangling client
            try:
                await client.disconnect()
            except Exception:
                pass
            return False, error_msg

    async def disconnect(self, connection_id: int) -> bool:
        if connection_id not in self._clients:
            logger.warning(
                f"Disconnect called for unknown connection {connection_id}"
            )
            return False

        success = await self._force_cleanup(connection_id)
        if success:
            logger.info(f"Disconnected connection {connection_id}")
        return success

    async def _force_cleanup(self, connection_id: int) -> bool:
        """
        Always removes connection_id from the registry first,
        then attempts disconnect. Guarantees no memory leak
        even if disconnect() raises.
        """
        client = self._clients.pop(connection_id, None)
        if client is None:
            return False

        try:
            await client.disconnect()
            return True
        except Exception as e:
            logger.warning(
                f"Exception during disconnect of connection {connection_id} "
                f"(client already removed from registry): {e}"
            )
            return True

    def is_connected(self, connection_id: int) -> bool:
        """
        Checks both registry membership and actual connection state.
        """
        client = self._clients.get(connection_id)
        if client is None:
            return False
        try:
            return client.uaclient.protocol is not None
        except Exception:
            return False

    async def ping(self, connection_id: int) -> bool:
        """
        Tests the connection by reading the server state node.
        More reliable than is_connected() for detecting dropped connections.
        """
        client = self._clients.get(connection_id)
        if client is None:
            return False
        try:
            # Read server state node — lightweight, supported by all OPC UA servers
            server_node = client.get_node("ns=0;i=2259")
            await server_node.read_value()
            return True
        except Exception:
            return False

    def get_client(self, connection_id: int) -> Optional[Client]:
        return self._clients.get(connection_id)

    async def disconnect_all(self) -> None:
        """
        Cleanly closes all active connections.
        Must be called on application shutdown.
        """
        if not self._clients:
            return

        connection_ids = list(self._clients.keys())
        logger.info(f"Shutting down {len(connection_ids)} OPC UA connection(s)...")

        results = await asyncio.gather(
            *[self._force_cleanup(cid) for cid in connection_ids],
            return_exceptions=True
        )

        failed = sum(1 for r in results if isinstance(r, Exception))
        if failed:
            logger.warning(
                f"disconnect_all: {failed}/{len(connection_ids)} cleanups had exceptions"
            )
        else:
            logger.info("disconnect_all: all connections closed cleanly")


# Singleton instance
opcua_manager = OPCUAManager()
