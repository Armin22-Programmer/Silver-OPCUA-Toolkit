# backend/simulator/server.py

import asyncio
import math
import random
import os
import logging
import datetime
from pathlib import Path

from asyncua import Server
from asyncua.server.user_managers import PermissiveUserManager
from asyncua.ua import SecurityPolicyType
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import ipaddress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Certificate paths ──────────────────────────────────────────────────────

CERT_DIR    = Path(os.environ.get("SIMULATOR_CERT_DIR", "/tmp/simulator_certs"))
SERVER_CERT = CERT_DIR / "server_cert.pem"
SERVER_KEY  = CERT_DIR / "server_key.pem"
TRUSTED_DIR = CERT_DIR / "trusted"


def generate_self_signed_cert() -> None:
    """
    Generate a self-signed certificate and private key.
    For development and testing only.
    """
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    TRUSTED_DIR.mkdir(parents=True, exist_ok=True)

    if SERVER_CERT.exists() and SERVER_KEY.exists():
        logger.info(f"Using existing server certificates from {CERT_DIR}")
        return

    logger.info("Generating self-signed server certificate for simulator...")

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # Write private key
    with open(SERVER_KEY, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Silver OPC UA Toolkit"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Silver Simulator"),
    ])

    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.DNSName("simulator"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.UniformResourceIdentifier("urn:silver-opcua:simulator"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
        )
        .add_extension(san, critical=False)
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.CLIENT_AUTH,
                ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256(), default_backend())
    )

    # Write certificate
    with open(SERVER_CERT, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Server certificate generated: {SERVER_CERT}")
    logger.info(f"Server private key generated: {SERVER_KEY}")
    logger.info(
        f"To connect with Sign/SignAndEncrypt, add {SERVER_CERT} "
        "to your OPC UA client's trusted certificates."
    )


# ── Signal generators ──────────────────────────────────────────────────────

def sine_wave(tick: int, base: float, amplitude: float, period: float, noise: float) -> float:
    return base + amplitude * math.sin(2 * math.pi * tick / period) + random.gauss(0, noise)


def step_change(tick: int, base: float, step_size: float, step_every: int) -> float:
    step = (tick // step_every) % 4
    offsets = [0, step_size, step_size * 0.6, step_size * 1.2]
    return base + offsets[step] + random.gauss(0, 0.3)


def noisy_analog(tick: int, base: float, drift_speed: float, noise: float) -> float:
    drift = drift_speed * math.sin(tick * 0.003)
    return base + drift + random.gauss(0, noise)


def spike(value: float, probability: float, spike_magnitude: float) -> float:
    if random.random() < probability:
        return value + random.choice([-1, 1]) * spike_magnitude * random.uniform(0.5, 1.0)
    return value


# ── Simulator state machine ────────────────────────────────────────────────

class SimulatorState:
    MODES = ['normal', 'alarm', 'step', 'frozen', 'recovering']

    def __init__(self):
        self.mode = 'normal'
        self.mode_tick = 0
        self.frozen_value = None
        self.is_running = True

    def update(self, tick: int) -> None:
        self.mode_tick += 1

        if self.mode == 'normal':
            if self.mode_tick > 60 and random.random() < 0.005:
                self.mode = 'alarm'
                self.mode_tick = 0
                logger.info("Simulator entering ALARM mode")
            elif self.mode_tick > 30 and random.random() < 0.008:
                self.mode = 'step'
                self.mode_tick = 0
                logger.info("Simulator entering STEP CHANGE mode")
            elif self.mode_tick > 20 and random.random() < 0.004:
                self.mode = 'frozen'
                self.mode_tick = 0
                logger.info("Simulator entering FROZEN mode")

        elif self.mode == 'alarm':
            if self.mode_tick > 20:
                self.mode = 'recovering'
                self.mode_tick = 0
                self.is_running = False
                logger.info("Simulator entering RECOVERING mode")

        elif self.mode == 'step':
            if self.mode_tick > 15:
                self.mode = 'normal'
                self.mode_tick = 0
                logger.info("Simulator returning to NORMAL mode")

        elif self.mode == 'frozen':
            if self.mode_tick > 10:
                self.mode = 'normal'
                self.mode_tick = 0
                self.frozen_value = None
                logger.info("Simulator returning to NORMAL mode (unfrozen)")

        elif self.mode == 'recovering':
            if self.mode_tick > 15:
                self.mode = 'normal'
                self.mode_tick = 0
                self.is_running = True
                logger.info("Simulator RECOVERED — back to NORMAL mode")


# ── Main simulator ─────────────────────────────────────────────────────────

async def run_simulator():
    host = os.environ.get("SIMULATOR_HOST", "0.0.0.0")
    port = int(os.environ.get("SIMULATOR_PORT", "4840"))
    endpoint = f"opc.tcp://{host}:{port}"

    # Security level: "none"=no security, "sign", "signencrypt", "all"=all modes
    security_level = os.environ.get("SIMULATOR_SECURITY", "all").lower()

    # Generate certificates
    generate_self_signed_cert()

    # ── User manager for username/password auth ──
    class SimpleUserManager(PermissiveUserManager):
        """
        Extends PermissiveUserManager to add username/password validation.
        Anonymous access is handled by PermissiveUserManager (returns User role).
        """
        USERS = {"admin": "admin123", "operator": "op456"}

        def get_user(self, iserver, username=None, password=None, certificate=None):
            # Username/password: validate credentials
            if username is not None:
                pw = password.decode("utf-8") if isinstance(password, bytes) else (password or "")
                expected = self.USERS.get(username)
                if expected is not None and expected == pw:
                    return super().get_user(iserver, username=username,
                                            password=password, certificate=certificate)
                return None  # Wrong credentials — deny
            # Anonymous or certificate: delegate to PermissiveUserManager
            return super().get_user(iserver, username=username,
                                    password=password, certificate=certificate)

    server = Server(user_manager=SimpleUserManager())
    await server.init()

    server.set_endpoint(endpoint)
    server.set_server_name("Silver OPC UA Toolkit - Simulator")

    # Load server certificate and private key
    await server.load_certificate(str(SERVER_CERT))
    await server.load_private_key(str(SERVER_KEY))

    # ── Build security policies ──
    # set_security_policy is synchronous and takes a list of SecurityPolicyType integers
    security_policies = []
    if security_level in ("all", "none"):
        security_policies.append(SecurityPolicyType.NoSecurity)
    if security_level in ("all", "sign"):
        security_policies.append(SecurityPolicyType.Basic256Sha256_Sign)
    if security_level in ("all", "signencrypt"):
        security_policies.append(SecurityPolicyType.Basic256Sha256_SignAndEncrypt)

    server.set_security_policy(security_policies)
    server.set_security_IDs(["Anonymous", "Username", "Basic256Sha256"])

    uri = "http://silver-opcua-toolkit.local"
    namespace = await server.register_namespace(uri)

    objects = server.get_objects_node()
    device  = await objects.add_object(namespace, "SimulatedDevice")

    temperature = await device.add_variable(namespace, "Temperature", 25.0)
    pressure    = await device.add_variable(namespace, "Pressure", 101.3)
    flow_rate   = await device.add_variable(namespace, "FlowRate", 50.0)
    is_running  = await device.add_variable(namespace, "IsRunning", True)

    await temperature.set_writable()
    await pressure.set_writable()
    await flow_rate.set_writable()

    logger.info(f"OPC UA Simulator starting on {endpoint}")
    logger.info(f"Security level: {security_level.upper()}")
    logger.info(f"Server certificate: {SERVER_CERT}")
    logger.info("Default users: admin/admin123, operator/op456")
    logger.info("Tags: Temperature, Pressure, FlowRate, IsRunning")
    logger.info("Modes: normal → alarm → recovering → step → frozen → normal")

    state = SimulatorState()

    async with server:
        tick = 0
        while True:
            tick += 1
            state.update(tick)

            if state.mode == 'normal':
                temp = sine_wave(tick, 25.0, 10.0, 120, 0.3)
                pres = sine_wave(tick, 101.3, 5.0, 200, 0.15)
                flow = sine_wave(tick, 50.0, 20.0, 90, 0.5)
                temp = spike(temp, 0.02, 3.0)
                flow = spike(flow, 0.02, 5.0)

            elif state.mode == 'alarm':
                temp = 25.0 + 18.0 + random.gauss(0, 1.5)
                pres = 101.3 - 12.0 + random.gauss(0, 0.8)
                flow = 50.0 + 30.0 + random.gauss(0, 2.0)

            elif state.mode == 'step':
                temp = step_change(tick, 25.0, 8.0, 5) + random.gauss(0, 0.3)
                pres = step_change(tick, 101.3, 4.0, 5) + random.gauss(0, 0.2)
                flow = step_change(tick, 50.0, 15.0, 5) + random.gauss(0, 0.5)

            elif state.mode == 'frozen':
                if state.frozen_value is None:
                    state.frozen_value = (
                        round(sine_wave(tick, 25.0, 10.0, 120, 0), 2),
                        round(sine_wave(tick, 101.3, 5.0, 200, 0), 2),
                        round(sine_wave(tick, 50.0, 20.0, 90, 0), 2),
                    )
                temp, pres, flow = state.frozen_value

            elif state.mode == 'recovering':
                temp = noisy_analog(tick, 25.0, 5.0, 1.2)
                pres = noisy_analog(tick, 101.3, 3.0, 0.6)
                flow = noisy_analog(tick, 50.0, 8.0, 1.5)

            else:
                temp, pres, flow = 25.0, 101.3, 50.0

            await temperature.write_value(round(float(temp), 2))
            await pressure.write_value(round(float(pres), 2))
            await flow_rate.write_value(round(float(flow), 2))
            await is_running.write_value(state.is_running)

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_simulator())
