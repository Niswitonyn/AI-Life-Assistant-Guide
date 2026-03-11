from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PlannedTask:
    id: int
    text: str


class TaskPlanner:
    """
    Lightweight rule-based task splitter.

    Purpose: turn compound user commands into an ordered list of task clauses.
    Example:
      "open chrome and search cats and download images"
        -> ["open chrome", "search cats", "download images"]
    """

    _MARKERS = [
        "open gmail",
        "read my emails",
        "read emails",
        "search emails from",
        "write email to",
        "improve this email",
        "track emails from",
        "notify when new mail arrives",
        "get latest email",
        "send email to",
        "read my inbox",
        "check my inbox",
        "summarize inbox",
        "upcoming events",
        "calendar",
        "schedule",
        "open chrome and download images of",
        "open chrome and search images of",
        "open chrome and search",
        "download images of",
        "search images of",
        "collect information about",
        "open website",
        "open site",
        "open my documents",
        "open my downloads",
        "open my desktop",
        "open my pictures",
        "open documents",
        "open downloads",
        "open file",
        "delete file",
        "create folder",
        "shutdown computer",
        "restart computer",
        "lock screen",
        "increase volume",
        "decrease volume",
        "set volume",
        "mute volume",
        "find file",
        "search file",
        "create folder called",
        "shutdown",
        "restart",
        "lock",
        "volume up",
        "volume down",
        "increase volume",
        "decrease volume",
        "mute",
        "unmute",
        "remind me to",
        "add task",
        "create task",
        "list documents",
        "summarize document",
        "summarize my",
        "ask about document",
        "what does the document say about",
        "open ",
        "search ",
        "download ",
    ]

    _CONNECTOR_RE = re.compile(r"\s*(?:,|;|\band then\b|\bthen\b|\band\b|\bafter\b|\bnext\b)\s+", flags=re.IGNORECASE)
    _LEADING_CONNECTOR_RE = re.compile(r"^(?:and|then)\s+", flags=re.IGNORECASE)
    _TRAILING_CONNECTOR_RE = re.compile(r"\s+(?:and|then)\s*$", flags=re.IGNORECASE)

    def split(self, text: str) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []

        # Prefer marker-based chunking when we can detect multiple known command starts.
        marker_chunks = self._split_by_markers(text)
        if len(marker_chunks) > 1:
            return marker_chunks

        # Otherwise fall back to connector splitting with some cleanup.
        parts = [p.strip(" ,;.") for p in self._CONNECTOR_RE.split(text) if p and p.strip(" ,;.")]
        cleaned: List[str] = []
        for part in parts:
            part = self._LEADING_CONNECTOR_RE.sub("", part).strip()
            if part:
                cleaned.append(part)
        return cleaned or [text]

    def plan(self, text: str) -> List[PlannedTask]:
        parts = self.split(text)
        return [PlannedTask(id=i + 1, text=part) for i, part in enumerate(parts)]

    def plan_tasks(self, user_input: str) -> List[dict]:
        """
        Compatibility helper for the task-planning spec.

        Returns a list of structured task clauses which are later parsed by SmartRouter.
        """
        return [{"id": t.id, "text": t.text} for t in self.plan(user_input)]

    def _split_by_markers(self, text: str) -> List[str]:
        lower = text.lower()
        positions: List[int] = []
        for marker in self._MARKERS:
            start = 0
            while True:
                idx = lower.find(marker, start)
                if idx < 0:
                    break
                positions.append(idx)
                start = idx + 1

        if not positions:
            return [text]

        positions = sorted(set(positions))
        if len(positions) == 1:
            return [text]

        chunks: List[str] = []
        for i, pos in enumerate(positions):
            next_pos = positions[i + 1] if i + 1 < len(positions) else len(text)
            piece = text[pos:next_pos].strip(" ,;.")
            piece = self._LEADING_CONNECTOR_RE.sub("", piece).strip()
            piece = self._TRAILING_CONNECTOR_RE.sub("", piece).strip(" ,;.")
            if piece:
                chunks.append(piece)

        return chunks or [text]
