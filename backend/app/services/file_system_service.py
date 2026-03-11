from __future__ import annotations

import ctypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.config.paths import BASE_DIR


class FileSystemError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileOpResult:
    ok: bool
    message: str
    data: dict


class FileSystemService:
    """
    File system operations with safety restrictions.

    Allowed roots:
    - Documents / Downloads / Desktop
    - Project workspace (repo root)
    """

    def __init__(self, *, allowed_roots: Optional[List[Path]] = None):
        self.allowed_roots = allowed_roots or default_allowed_roots()

    def search_file(self, filename: str, *, max_results: int = 10, timeout_s: float = 4.0) -> FileOpResult:
        name = (filename or "").strip().strip("\"'")
        if not name:
            raise FileSystemError("Missing filename.")

        results: List[str] = []
        deadline = time.monotonic() + max(0.1, float(timeout_s))
        for root in self.allowed_roots:
            for path in self._walk_files(root):
                if time.monotonic() > deadline:
                    return FileOpResult(
                        ok=bool(results),
                        message="Search timed out" if not results else "Partial results (search timed out)",
                        data={"results": results, "timed_out": True},
                    )
                if name.lower() in path.name.lower():
                    results.append(str(path))
                    if len(results) >= max(1, int(max_results)):
                        return FileOpResult(ok=True, message="File(s) found", data={"results": results})
        return FileOpResult(ok=bool(results), message="File(s) found" if results else "No matching files found", data={"results": results})

    def open_file(self, path_or_name: str) -> FileOpResult:
        target = (path_or_name or "").strip().strip("\"'")
        if not target:
            raise FileSystemError("Missing file path or name.")

        path = Path(target)
        if not path.is_absolute():
            found = self.search_file(target, max_results=1).data.get("results", [])
            if not found:
                return FileOpResult(ok=False, message="File not found", data={"name": target})
            path = Path(found[0])

        self._assert_allowed(path)
        if not path.exists() or not path.is_file():
            return FileOpResult(ok=False, message="File not found", data={"path": str(path)})

        try:
            os.startfile(str(path))
        except Exception as e:
            raise FileSystemError(f"Could not open file: {e}") from e
        return FileOpResult(ok=True, message="Opened file", data={"path": str(path)})

    def create_folder(self, name: str, location: str = "documents") -> FileOpResult:
        folder_name = (name or "").strip().strip("\"'")
        if not folder_name:
            raise FileSystemError("Missing folder name.")

        base = self._resolve_location(location)
        target = (base / folder_name).resolve()
        self._assert_allowed(target)
        target.mkdir(parents=True, exist_ok=True)
        return FileOpResult(ok=True, message="Created folder", data={"path": str(target)})

    def delete_file(self, path_or_name: str) -> FileOpResult:
        target = (path_or_name or "").strip().strip("\"'")
        if not target:
            raise FileSystemError("Missing file path or name.")

        path = Path(target)
        if not path.is_absolute():
            found = self.search_file(target, max_results=5).data.get("results", [])
            if not found:
                return FileOpResult(ok=False, message="File not found", data={"name": target})
            if len(found) > 1:
                return FileOpResult(
                    ok=False,
                    message="Multiple matches found. Please provide a more specific name or full path.",
                    data={"name": target, "matches": found[:5]},
                )
            path = Path(found[0])

        self._assert_allowed(path)
        if not path.exists():
            return FileOpResult(ok=False, message="File not found", data={"path": str(path)})

        # Extra safety: refuse deleting directories by default.
        if path.is_dir():
            raise FileSystemError("Refusing to delete a directory. Provide an explicit file path.")

        try:
            if sys.platform.startswith("win"):
                _send_to_recycle_bin(path)
                return FileOpResult(ok=True, message="Moved file to Recycle Bin", data={"path": str(path)})
            path.unlink()
            return FileOpResult(ok=True, message="Deleted file", data={"path": str(path)})
        except FileSystemError:
            raise
        except Exception as e:
            raise FileSystemError(f"Could not delete file: {e}") from e

    def list_directory(self, path: str, *, limit: int = 50) -> FileOpResult:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self._resolve_location(path)
        p = p.resolve()

        self._assert_allowed(p)
        if not p.exists() or not p.is_dir():
            return FileOpResult(ok=False, message="Directory not found", data={"path": str(p)})

        items: List[Dict[str, str]] = []
        for child in list(p.iterdir())[: max(1, int(limit))]:
            items.append({"name": child.name, "type": "dir" if child.is_dir() else "file", "path": str(child)})
        return FileOpResult(ok=True, message="Directory listing", data={"path": str(p), "items": items})

    # -------------------------
    # Internal safety helpers
    # -------------------------

    def _assert_allowed(self, path: Path) -> None:
        p = path.resolve()
        for root in self.allowed_roots:
            r = root.resolve()
            if _is_within(p, r):
                return
        raise FileSystemError(f"Access denied. Path is outside allowed directories: {p}")

    def _resolve_location(self, location: str) -> Path:
        key = (location or "").strip().lower()
        home = Path.home()
        mapping = {
            "documents": home / "Documents",
            "downloads": home / "Downloads",
            "desktop": home / "Desktop",
            "pictures": home / "Pictures",
            "workspace": repo_root(),
        }
        return mapping.get(key, home / "Documents")

    def _walk_files(self, root: Path):
        try:
            root = root.resolve()
        except Exception:
            return

        for dirpath, dirnames, filenames in os.walk(root):
            # Light pruning: skip common huge/irrelevant dirs.
            dirnames[:] = [d for d in dirnames if d.lower() not in {"node_modules", ".git", "__pycache__", "venv", ".venv"}]
            for fname in filenames:
                yield Path(dirpath) / fname


def default_allowed_roots() -> List[Path]:
    home = Path.home()
    return [
        home / "Documents",
        home / "Downloads",
        home / "Desktop",
        repo_root(),
    ]


def repo_root() -> Path:
    # BASE_DIR points to backend/; repo root is one level up.
    return (Path(BASE_DIR).resolve().parent).resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _send_to_recycle_bin(path: Path) -> None:
    """
    Delete a file by sending it to the Windows Recycle Bin (undoable).

    Uses SHFileOperationW with FOF_ALLOWUNDO to avoid permanent deletes.
    """

    # SHFILEOPSTRUCTW definition (minimal)
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    p = Path(path).resolve()
    if not p.exists():
        raise FileSystemError(f"File not found: {p}")
    if p.is_dir():
        raise FileSystemError("Refusing to delete a directory.")

    # Double-null-terminated list of paths.
    from_str = str(p) + "\0\0"
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = from_str
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None

    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0 or op.fAnyOperationsAborted:
        raise FileSystemError("Recycle Bin delete failed or was aborted.")
