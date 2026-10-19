"""MITM CA 证书状态检查与安装。

只依赖标准库与 ``cryptography``（随 mitmproxy 安装）；不导入任何界面/服务组件。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

CA_STORE_PATH = "Cert:\\CurrentUser\\Root"
_POWERSHELL_TIMEOUT_SECONDS = 30
_CERTUTIL_TIMEOUT_SECONDS = 30
_SHA1_HEX_RE = re.compile(r"[0-9A-Fa-f]{40}")
_PS_THUMBPRINT_SCRIPT = (
    "Get-ChildItem Cert:\\CurrentUser\\Root | ForEach-Object { $_.Thumbprint }"
)


def _read_ca_thumbprint(data: bytes) -> str:
    """计算 CA 证书的 SHA-1 指纹（大写十六进制，不带空格）。"""

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    try:
        cert = x509.load_pem_x509_certificate(data)
    except ValueError:
        cert = x509.load_der_x509_certificate(data)
    return cert.fingerprint(hashes.SHA1()).hex().upper()


def _parse_powershell_thumbprints(stdout: str) -> list[str]:
    thumbprints: list[str] = []
    for line in stdout.splitlines():
        token = line.strip().replace(" ", "").upper()
        if token and _SHA1_HEX_RE.fullmatch(token):
            thumbprints.append(token)
    return thumbprints


def _parse_certutil_thumbprints(stdout: str) -> list[str]:
    """从 ``certutil -user -store Root`` 文本中解析 ``sha1`` 哈希行。"""

    thumbprints: list[str] = []
    for line in stdout.splitlines():
        if "sha1" not in line.lower():
            continue
        match = _SHA1_HEX_RE.search(line)
        if match:
            thumbprints.append(match.group(0).upper())
    return thumbprints


def _read_root_store_thumbprints() -> tuple[list[str], str | None]:
    """读取 ``Cert:\\CurrentUser\\Root`` 指纹列表；失败时返回原因文本。"""

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _PS_THUMBPRINT_SCRIPT,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_POWERSHELL_TIMEOUT_SECONDS,
        )
        if completed.returncode == 0:
            return _parse_powershell_thumbprints(completed.stdout), None
        power_shell_error = (
            f"PowerShell 返回 {completed.returncode}；{completed.stderr.strip()[:200]}"
        )
    except (OSError, subprocess.SubprocessError) as exc:
        power_shell_error = f"PowerShell 调用失败：{exc}"

    try:
        completed = subprocess.run(
            ["certutil", "-user", "-store", "Root"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CERTUTIL_TIMEOUT_SECONDS,
        )
        thumbprints = _parse_certutil_thumbprints(completed.stdout)
        if completed.returncode == 0 or thumbprints:
            return thumbprints, None
        return [], f"certutil 返回 {completed.returncode}；{power_shell_error}"
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"{power_shell_error}；certutil 调用失败：{exc}"


def ca_status(ca_path: str | Path) -> dict:
    """返回 CA 文件与当前用户证书库的状态快照。"""

    path = Path(ca_path)
    result: dict = {
        "caFileExists": False,
        "caPath": str(path),
        "thumbprint": None,
        "installed": False,
        "storePath": CA_STORE_PATH,
        "storeCertificateCount": 0,
        "status": "missing",
        "message": "",
    }
    if not path.is_file():
        result["message"] = f"CA 证书文件不存在：{path}"
        return result

    result["caFileExists"] = True
    try:
        thumbprint = _read_ca_thumbprint(path.read_bytes())
    except Exception as exc:  # noqa: BLE001 - 任何解析失败都不能抛出
        result["status"] = "file-present"
        result["message"] = f"CA 证书文件存在但无法解析：{exc}"
        return result

    result["thumbprint"] = thumbprint
    thumbprints, store_error = _read_root_store_thumbprints()
    result["storeCertificateCount"] = len(thumbprints)
    if store_error is not None:
        result["status"] = "file-present"
        result["message"] = f"无法读取当前用户证书库，视为未安装：{store_error}"
        return result

    installed = thumbprint in thumbprints
    result["installed"] = installed
    if installed:
        result["status"] = "installed"
        result["message"] = f"CA 证书已安装到当前用户证书库，指纹 {thumbprint}。"
    else:
        result["status"] = "file-present"
        result["message"] = (
            f"CA 证书文件存在但未安装，指纹 {thumbprint}；"
            "可执行 `awa doctor --install-ca` 安装。"
        )
    return result


def install_ca(ca_path: str | Path) -> dict:
    """把 CA 证书安装到当前用户 Root 证书库。"""

    path = Path(ca_path)
    result: dict = {
        "ok": False,
        "returncode": -1,
        "stdout": "",
        "stderr": "",
        "message": "",
    }
    if not path.is_file():
        result["message"] = f"CA 证书文件不存在，无法安装：{path}"
        return result

    try:
        completed = subprocess.run(
            ["certutil", "-user", "-addstore", "Root", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result["message"] = f"执行 certutil 安装 CA 证书失败：{exc}"
        return result

    result["returncode"] = completed.returncode
    result["stdout"] = completed.stdout or ""
    result["stderr"] = completed.stderr or ""
    if completed.returncode == 0:
        result["ok"] = True
        result["message"] = f"CA 证书已安装：{path}"
    else:
        result["message"] = (
            f"certutil 安装失败（返回 {completed.returncode}）："
            f"{(completed.stderr or completed.stdout).strip()[:200]}"
        )
    return result


__all__ = ["ca_status", "install_ca"]
