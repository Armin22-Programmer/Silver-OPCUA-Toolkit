# backend/app/api/routes/certificates.py

import datetime
import ipaddress
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/v1/certificates", tags=["certificates"])


class GenerateCertRequest(BaseModel):
    common_name: str = "Silver OPC UA Client"
    app_uri:     str = "urn:silver-opcua:client"
    days_valid:  int = 3650


class GenerateCertResponse(BaseModel):
    certificate_path: str
    private_key_path: str
    message:          str


@router.post("/generate", response_model=GenerateCertResponse)
async def generate_client_certificate(req: GenerateCertRequest):
    """
    Generate a self-signed client certificate and private key
    for use with OPC UA Sign / SignAndEncrypt connections.

    Files are saved to CERTS_DIR (configurable via env var).
    In Docker this is /app/data/certs/ — persisted in the data volume.
    In dev this is backend/certs/.
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="cryptography package not available. Run: uv add cryptography"
        )

    certs_dir = Path(settings.CERTS_DIR)
    certs_dir.mkdir(parents=True, exist_ok=True)

    cert_path = certs_dir / "client_cert.pem"
    key_path  = certs_dir / "client_key.pem"

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # Write private key
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Silver OPC UA Toolkit"),
        x509.NameAttribute(NameOID.COMMON_NAME, req.common_name),
    ])

    san = x509.SubjectAlternativeName([
        x509.UniformResourceIdentifier(req.app_uri),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ])

    # Subject Key Identifier — required by many industrial OPC UA servers
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=req.days_valid)
        )
        .add_extension(san, critical=False)
        # Key Usage — required by Siemens S7 and many industrial servers
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        # Subject Key Identifier — used by some servers for certificate matching
        .add_extension(ski, critical=False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return GenerateCertResponse(
        certificate_path=str(cert_path.resolve()),
        private_key_path=str(key_path.resolve()),
        message=(
            f"Certificate generated successfully. "
            f"Valid for {req.days_valid} days. "
            f"Add {cert_path.name} to your OPC UA server's trusted clients list."
        ),
    )


@router.get("/info", response_model=dict)
async def get_certificate_info():
    """
    Returns info about existing client certificate if present.
    """
    certs_dir = Path(settings.CERTS_DIR)
    cert_path = certs_dir / "client_cert.pem"
    key_path  = certs_dir / "client_key.pem"

    if not cert_path.exists():
        return {
            "exists": False,
            "certificate_path": str(cert_path.resolve()),
            "private_key_path": str(key_path.resolve()),
        }

    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        return {
            "exists": True,
            "certificate_path": str(cert_path.resolve()),
            "private_key_path": str(key_path.resolve()),
            "subject": cert.subject.rfc4514_string(),
            "valid_from": cert.not_valid_before_utc.isoformat(),
            "valid_until": cert.not_valid_after_utc.isoformat(),
        }
    except Exception as e:
        return {
            "exists": True,
            "certificate_path": str(cert_path.resolve()),
            "private_key_path": str(key_path.resolve()),
            "error": str(e),
        }
