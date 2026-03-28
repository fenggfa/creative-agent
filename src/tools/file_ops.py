"""文件操作工具 - 提供安全的文件读写能力。"""

from pathlib import Path
from typing import Any


class FileOperationError(Exception):
    """文件操作错误。"""


class FileAccessDeniedError(FileOperationError):
    """文件访问被拒绝。"""


# 允许读取的文件类型白名单
ALLOWED_READ_EXTENSIONS: set[str] = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}

# 允许写入的文件类型白名单
ALLOWED_WRITE_EXTENSIONS: set[str] = {
    ".md",
    ".txt",
}

# 禁止访问的路径模式
FORBIDDEN_PATH_PATTERNS: set[str] = {
    ".env",
    ".git",
    ".venv",
    "__pycache__",
    "secrets",
    "credentials",
    "api_key",
    "password",
}


def _validate_path(file_path: Path, operation: str) -> None:
    """验证文件路径是否允许操作。

    Args:
        file_path: 文件路径
        operation: 操作类型 (read/write)

    Raises:
        FileAccessDeniedError: 路径不允许访问
    """
    path_str = str(file_path).lower()

    # 检查禁止的路径模式
    for pattern in FORBIDDEN_PATH_PATTERNS:
        if pattern in path_str:
            raise FileAccessDeniedError(
                f"Access denied: path contains forbidden pattern '{pattern}'"
            )

    # 检查文件扩展名
    suffix = file_path.suffix.lower()
    if operation == "read" and suffix not in ALLOWED_READ_EXTENSIONS:
        raise FileAccessDeniedError(
            f"Read access denied: file extension '{suffix}' not allowed"
        )
    if operation == "write" and suffix not in ALLOWED_WRITE_EXTENSIONS:
        raise FileAccessDeniedError(
            f"Write access denied: file extension '{suffix}' not allowed"
        )


def safe_read_file(file_path: str, max_size_mb: float = 1.0) -> str:
    """安全读取文件内容。

    Args:
        file_path: 文件路径
        max_size_mb: 最大文件大小（MB）

    Returns:
        文件内容

    Raises:
        FileOperationError: 文件操作错误
        FileAccessDeniedError: 访问被拒绝
    """
    path = Path(file_path).resolve()

    _validate_path(path, "read")

    if not path.exists():
        raise FileOperationError(f"File not found: {file_path}")

    if not path.is_file():
        raise FileOperationError(f"Not a file: {file_path}")

    # 检查文件大小
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise FileOperationError(
            f"File too large: {size_mb:.2f}MB exceeds limit of {max_size_mb}MB"
        )

    return path.read_text(encoding="utf-8")


def safe_write_file(
    file_path: str,
    content: str,
    create_backup: bool = True,
) -> dict[str, Any]:
    """安全写入文件内容。

    Args:
        file_path: 文件路径
        content: 写入内容
        create_backup: 是否创建备份

    Returns:
        操作结果

    Raises:
        FileOperationError: 文件操作错误
        FileAccessDeniedError: 访问被拒绝
    """
    path = Path(file_path).resolve()

    _validate_path(path, "write")

    result: dict[str, Any] = {
        "success": False,
        "path": str(path),
    }

    try:
        # 创建备份
        if create_backup and path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            result["backup_path"] = str(backup_path)

        # 写入内容
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        result["success"] = True
        result["bytes_written"] = len(content.encode("utf-8"))

    except PermissionError as e:
        raise FileAccessDeniedError(f"Permission denied: {e}") from e
    except Exception as e:
        raise FileOperationError(f"Write failed: {e}") from e

    return result


def safe_append_file(file_path: str, content: str) -> dict[str, Any]:
    """安全追加内容到文件。

    Args:
        file_path: 文件路径
        content: 追加内容

    Returns:
        操作结果
    """
    path = Path(file_path).resolve()

    _validate_path(path, "write")

    result: dict[str, Any] = {
        "success": False,
        "path": str(path),
    }

    try:
        # 追加内容
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

        result["success"] = True
        result["bytes_appended"] = len(content.encode("utf-8"))

    except PermissionError as e:
        raise FileAccessDeniedError(f"Permission denied: {e}") from e
    except Exception as e:
        raise FileOperationError(f"Append failed: {e}") from e

    return result


def check_file_exists(file_path: str) -> bool:
    """检查文件是否存在。

    Args:
        file_path: 文件路径

    Returns:
        文件是否存在
    """
    path = Path(file_path)
    return path.exists() and path.is_file()


def get_file_info(file_path: str) -> dict[str, Any]:
    """获取文件信息。

    Args:
        file_path: 文件路径

    Returns:
        文件信息字典
    """
    path = Path(file_path)

    if not path.exists():
        return {"exists": False, "path": str(path)}

    stat = path.stat()

    return {
        "exists": True,
        "path": str(path.resolve()),
        "is_file": path.is_file(),
        "is_directory": path.is_dir(),
        "size_bytes": stat.st_size,
        "size_kb": stat.st_size / 1024,
        "extension": path.suffix,
        "name": path.name,
    }
