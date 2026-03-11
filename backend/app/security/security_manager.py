from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.paths import BASE_DIR
from app.security.security_logs import log_security_event


class PermissionLevel:
    SAFE = "SAFE"
    SENSITIVE = "SENSITIVE"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    level: str
    reason: str | None = None
    requires_confirmation: bool = False
    prompt: str | None = None


class SecurityManager:
    """
    Central command/task validator.
    """

    def __init__(self):
        self._blocked_counts: Dict[str, list[float]] = {}
        self._blocked_until: Dict[str, float] = {}

    def validate_command(self, command: str, *, user_id: str = "default") -> SecurityDecision:
        # Minimal string validation: block obvious injection markers.
        t = (command or "").strip()
        if any(x in t for x in ["&&", "||", "|", ";", "`", "$("]):
            self._note_block(user_id, "shell_injection")
            return SecurityDecision(allowed=False, level=PermissionLevel.CRITICAL, reason="Blocked potential command injection.")
        return SecurityDecision(allowed=True, level=PermissionLevel.SAFE)

    def validate_task(
        self,
        task: Dict[str, Any],
        *,
        user_id: str,
        is_authenticated: bool,
        confirmed: bool = False,
    ) -> SecurityDecision:
        uid = (user_id or "").strip() or "default"
        now = time.time()
        if self._blocked_until.get(uid, 0) > now:
            return SecurityDecision(
                allowed=False,
                level=PermissionLevel.CRITICAL,
                reason="Temporarily blocked due to repeated unsafe requests. Please try again later.",
            )

        action = (task.get("action") or "").strip()
        params = task.get("params") or {}
        text = (task.get("text") or "").strip()

        # Basic injection guard on the natural-language command text as well.
        cmd_decision = self.validate_command(text, user_id=uid)
        if not cmd_decision.allowed:
            return cmd_decision

        level = self._level_for_action(action)

        # Auth gate for high-impact actions.
        if level in {PermissionLevel.SENSITIVE, PermissionLevel.CRITICAL} and not is_authenticated:
            self._note_block(uid, "auth_required")
            return SecurityDecision(
                allowed=False,
                level=level,
                reason="Authentication required for this operation.",
            )

        # Confirmation gate.
        if level in {PermissionLevel.SENSITIVE, PermissionLevel.CRITICAL} and not confirmed:
            prompt = self._prompt_for_task(action, params, text)
            return SecurityDecision(
                allowed=False,
                level=level,
                requires_confirmation=True,
                prompt=prompt,
                reason="Confirmation required.",
            )

        # File/path safety (defense in depth; services also enforce).
        if action in {"delete_file", "open_file", "list_files", "create_folder", "open_folder"}:
            path_value = params.get("path") or params.get("name") or params.get("location") or params.get("base") or ""
            if isinstance(path_value, str) and path_value.strip():
                if not self._is_path_allowed(Path(path_value)):
                    self._note_block(uid, "path_blocked")
                    return SecurityDecision(
                        allowed=False,
                        level=level,
                        reason="That path is restricted for security reasons.",
                    )

        # Block legacy arbitrary system execution.
        if action in {"system_execute"}:
            self._note_block(uid, "arbitrary_system_execute")
            return SecurityDecision(allowed=False, level=PermissionLevel.CRITICAL, reason="Arbitrary system execution is blocked.")

        return SecurityDecision(allowed=True, level=level)

    # -------------------------
    # Internals
    # -------------------------

    def _level_for_action(self, action: str) -> str:
        a = (action or "").strip()
        if a in {"shutdown", "restart"}:
            return PermissionLevel.CRITICAL
        if a in {"delete_file", "send_email", "draft_email", "create_folder"}:
            return PermissionLevel.SENSITIVE
        return PermissionLevel.SAFE

    def _prompt_for_task(self, action: str, params: Dict[str, Any], text: str) -> str:
        if action == "shutdown":
            return "Do you want me to shut down the computer? Reply 'yes' to confirm."
        if action == "restart":
            return "Do you want me to restart the computer? Reply 'yes' to confirm."
        if action == "delete_file":
            name = params.get("name") or params.get("path") or ""
            return f"Do you want me to delete '{name}'? Reply 'yes' to confirm."
        if action == "send_email":
            return "Do you want me to send the email? Reply 'yes' to confirm."
        if action == "create_folder":
            name = params.get("name") or ""
            return f"Do you want me to create the folder '{name}'? Reply 'yes' to confirm."
        if action == "open_file":
            name = params.get("name") or params.get("path") or ""
            return f"Do you want me to open '{name}'? Reply 'yes' to confirm."
        return f"Do you want me to run: {text or action}? Reply 'yes' to confirm."

    def _is_path_allowed(self, path: Path) -> bool:
        try:
            p = path.expanduser()
            if not p.is_absolute():
                # Non-absolute names are resolved by services within allowed roots.
                return True
            resolved = p.resolve()
        except Exception:
            return False

        home = Path.home().resolve()
        allowed_roots = [
            (home / "Documents").resolve(),
            (home / "Downloads").resolve(),
            (home / "Desktop").resolve(),
            (BASE_DIR.parent).resolve(),
        ]

        blocked_roots = [
            Path(os.environ.get("WINDIR", r"C:\Windows")).resolve(),
            Path(r"C:\Program Files").resolve(),
            Path(r"C:\Program Files (x86)").resolve(),
        ]

        for br in blocked_roots:
            try:
                resolved.relative_to(br)
                return False
            except Exception:
                pass

        for ar in allowed_roots:
            try:
                resolved.relative_to(ar)
                return True
            except Exception:
                continue
        return False

    def _note_block(self, user_id: str, reason: str) -> None:
        uid = (user_id or "").strip() or "default"
        now = time.time()
        window_s = 120.0
        threshold = int(os.getenv("SECURITY_BLOCK_THRESHOLD", "6"))
        block_s = float(os.getenv("SECURITY_TEMP_BLOCK_S", "300"))

        hits = [t for t in self._blocked_counts.get(uid, []) if now - t < window_s]
        hits.append(now)
        self._blocked_counts[uid] = hits

        log_security_event("security.blocked", {"user_id": uid, "reason": reason, "count": len(hits)})

        if len(hits) >= threshold:
            self._blocked_until[uid] = now + block_s
            log_security_event("security.temp_block", {"user_id": uid, "seconds": block_s})


security_manager = SecurityManager()
