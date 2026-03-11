from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.config.paths import BASE_DIR


class SystemControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class SystemResult:
    ok: bool
    message: str
    data: dict


class SystemControl:
    """
    Windows-only system control service.
    Provides a narrow, safe command surface for agents.
    """

    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF

    def __init__(self, app_map: Optional[Dict[str, str]] = None):
        self.app_map = app_map or default_app_map()

    def open_application(self, app_name: str) -> SystemResult:
        name = (app_name or "").strip().lower()
        if not name:
            raise SystemControlError("Missing application name.")

        target = self.app_map.get(name)
        if not target:
            supported = ", ".join(sorted(self.app_map.keys()))
            raise SystemControlError(f"Unsupported application '{app_name}'. Supported: {supported}")
        target = os.path.expandvars(target)

        try:
            if _looks_like_path(target):
                path = Path(target)
                if not path.exists():
                    raise SystemControlError(f"Application not found: {target}")
                subprocess.Popen([str(path)], close_fds=True)
            else:
                # Built-in executables like notepad/calc.
                subprocess.Popen([target], close_fds=True)
        except SystemControlError:
            raise
        except Exception as e:
            raise SystemControlError(f"Could not open application '{app_name}': {e}") from e

        return SystemResult(ok=True, message=f"Opening {name}", data={"application": name})

    def shutdown_pc(self) -> SystemResult:
        try:
            subprocess.run(["shutdown", "/s", "/t", "1"], check=True, capture_output=True, text=True)
        except Exception as e:
            raise SystemControlError(f"Shutdown failed: {e}") from e
        return SystemResult(ok=True, message="Shutting down computer", data={})

    def restart_pc(self) -> SystemResult:
        try:
            subprocess.run(["shutdown", "/r", "/t", "1"], check=True, capture_output=True, text=True)
        except Exception as e:
            raise SystemControlError(f"Restart failed: {e}") from e
        return SystemResult(ok=True, message="Restarting computer", data={})

    def lock_screen(self) -> SystemResult:
        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            # Fallback for environments where ctypes call is blocked.
            try:
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True, capture_output=True, text=True)
            except Exception as e:
                raise SystemControlError(f"Lock screen failed: {e}") from e
        return SystemResult(ok=True, message="Locking screen", data={})

    def set_volume(self, level: int) -> SystemResult:
        """
        Best-effort absolute volume set using media keys.

        Note: Windows does not expose a stable built-in CLI for absolute volume.
        This approximates by:
          1) sending "volume down" many times (near 0)
          2) sending "volume up" proportional to requested level
        """
        level = int(level)
        if level < 0 or level > 100:
            raise SystemControlError("Volume level must be between 0 and 100.")

        # Windows typically uses 50 steps from 0..100.
        # Drive down hard first to normalize, then raise to target.
        self._tap_key(self.VK_VOLUME_DOWN, times=60)
        up_steps = max(0, min(50, round(level / 2)))
        if up_steps:
            self._tap_key(self.VK_VOLUME_UP, times=up_steps)

        return SystemResult(
            ok=True,
            message="Volume set (approximate)",
            data={"requested_level": level, "approximate": True, "steps_up": up_steps},
        )

    def increase_volume(self, steps: int = 6) -> SystemResult:
        self._tap_key(self.VK_VOLUME_UP, times=max(1, int(steps)))
        return SystemResult(ok=True, message="Volume increased", data={"steps": int(steps)})

    def decrease_volume(self, steps: int = 6) -> SystemResult:
        self._tap_key(self.VK_VOLUME_DOWN, times=max(1, int(steps)))
        return SystemResult(ok=True, message="Volume decreased", data={"steps": int(steps)})

    def mute_volume(self) -> SystemResult:
        self._tap_key(self.VK_VOLUME_MUTE, times=1)
        return SystemResult(ok=True, message="Volume muted", data={})

    def unmute_volume(self) -> SystemResult:
        self._tap_key(self.VK_VOLUME_MUTE, times=1)
        return SystemResult(ok=True, message="Volume toggled (unmute)", data={})

    def open_folder(self, path: str) -> SystemResult:
        p = Path(path).expanduser()
        if not p.exists():
            raise SystemControlError(f"Folder not found: {p}")
        if not p.is_dir():
            raise SystemControlError(f"Not a folder: {p}")

        p_resolved = p.resolve()
        allowed_roots = _default_allowed_folder_roots()
        if not _is_within_any_root(p_resolved, allowed_roots):
            allowed_display = ", ".join(str(r) for r in allowed_roots)
            raise SystemControlError(f"Opening this folder is not allowed: {p_resolved}. Allowed: {allowed_display}")
        try:
            os.startfile(str(p))
        except Exception as e:
            raise SystemControlError(f"Could not open folder: {e}") from e
        return SystemResult(ok=True, message=f"Opening folder: {p}", data={"path": str(p)})

    def _tap_key(self, virtual_key: int, times: int = 1) -> None:
        for _ in range(max(1, times)):
            ctypes.windll.user32.keybd_event(virtual_key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(virtual_key, 0, 2, 0)


def default_app_map() -> Dict[str, str]:
    home = str(Path.home())
    vscode_path = rf"{home}\AppData\Local\Programs\Microsoft VS Code\Code.exe"
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    return {
        "chrome": chrome_path,
        "google chrome": chrome_path,
        "vscode": vscode_path,
        "vs code": vscode_path,
        "visual studio code": vscode_path,
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
    }


def _looks_like_path(value: str) -> bool:
    v = (value or "").strip()
    return (":" in v) or ("\\" in v) or ("/" in v)


def _default_allowed_folder_roots() -> list[Path]:
    home = Path.home()
    return [
        (home / "Documents").resolve(),
        (home / "Downloads").resolve(),
        (home / "Desktop").resolve(),
        (home / "Pictures").resolve(),
        (BASE_DIR.parent).resolve(),
    ]


def _is_within_any_root(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except Exception:
            continue
    return False
