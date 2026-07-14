from __future__ import annotations

import stat
import zipfile
from pathlib import Path


MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_FILES = 2000
MAX_SINGLE_FILE_BYTES = 1 * 1024 * 1024

SENSITIVE_NAMES = {
    ".env",
    ".git",
    ".ssh",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
}

SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".crt",
    ".p12",
    ".pfx",
}


class ZipSafetyError(ValueError):
    """上传 ZIP 不满足安全约束时抛出。"""


def is_sensitive_path(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & SENSITIVE_NAMES:
        return True
    return path.suffix.lower() in SENSITIVE_SUFFIXES


def safe_extract_zip(zip_path: Path, target_dir: Path) -> list[Path]:
    """安全解压 ZIP，禁止路径穿越、软链接和敏感文件。"""

    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise ZipSafetyError("ZIP 文件超过 20 MB 限制")

    extracted: list[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()

    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_EXTRACTED_FILES:
                raise ZipSafetyError("ZIP 内文件数量超过限制")

            for member in members:
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ZipSafetyError(f"发现非法路径: {member.filename}")

                # ZIP 外部属性中包含 Unix 文件类型，软链接必须跳过。
                file_type = (member.external_attr >> 16) & 0o170000
                if file_type == stat.S_IFLNK:
                    continue

                if member.file_size > MAX_SINGLE_FILE_BYTES:
                    continue

                if is_sensitive_path(member_path):
                    continue

                destination = (target_dir / member_path).resolve()
                if not str(destination).startswith(str(resolved_target)):
                    raise ZipSafetyError(f"发现路径穿越: {member.filename}")

                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as output:
                    output.write(source.read())
                extracted.append(destination)
    except zipfile.BadZipFile as exc:
        raise ZipSafetyError("上传文件不是合法 ZIP") from exc

    return extracted

