"""CA 证书 SHA-1 指纹计算的最小测试。

用例在 tmp_path 内用 ``cryptography`` 生成一份自签名 PEM 证书，
不访问网络、不读写系统证书库、不触发 MITM。
"""

from __future__ import annotations

import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from awa.cli import ca


def _make_self_signed_pem(path: Path) -> None:
    """在给定路径生成一份自签名证书（PEM 编码）。"""

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "awa-test-ca")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2026, 1, 1))
        .not_valid_after(datetime.datetime(2027, 1, 1))
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def test_read_ca_thumbprint_is_uppercase_sha1(tmp_path: Path) -> None:
    """验证点：自造 PEM 证书算出的 SHA-1 指纹是 40 位大写十六进制，且与直接计算一致。"""

    cert_path = tmp_path / "ca.pem"
    _make_self_signed_pem(cert_path)

    data = cert_path.read_bytes()
    thumbprint = ca._read_ca_thumbprint(data)

    assert len(thumbprint) == 40
    assert thumbprint == thumbprint.upper()
    int(thumbprint, 16)  # 必须是合法十六进制
    parsed = x509.load_pem_x509_certificate(data)
    assert thumbprint == parsed.fingerprint(hashes.SHA1()).hex().upper()
