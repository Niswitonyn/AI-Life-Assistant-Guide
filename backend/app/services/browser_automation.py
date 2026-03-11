from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

import httpx

from app.config.paths import DATA_DIR

logger = logging.getLogger(__name__)


class BrowserAutomationError(RuntimeError):
    pass


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@dataclass
class GoogleSearchResult:
    title: str
    link: str


class BrowserAutomation:
    """
    Playwright-based browser automation with a persistent in-process session.

    Security controls:
    - Only allows http/https navigation
    - Does not execute arbitrary JS from tasks (no evaluate hooks exposed)
    - Downloads restricted to backend data directory
    - Timeouts on navigation/extraction/downloads
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        navigation_timeout_ms: int = 30_000,
        action_timeout_ms: int = 15_000,
        max_concurrent_downloads: int = 5,
    ):
        self.headless = headless
        self.navigation_timeout_ms = navigation_timeout_ms
        self.action_timeout_ms = action_timeout_ms
        self.max_concurrent_downloads = max(1, int(max_concurrent_downloads))

        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def open_browser(self) -> None:
        async with self._lock:
            if self._page is not None:
                return

            try:
                from playwright.async_api import async_playwright
            except Exception as e:
                raise BrowserAutomationError(
                    "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
                ) from e

            self._playwright = await async_playwright().start()

            # Prefer real Chrome channel if available; fall back to bundled chromium.
            launch_kwargs: Dict[str, Any] = {
                "headless": bool(self.headless),
            }

            channel = os.getenv("PLAYWRIGHT_BROWSER_CHANNEL", "").strip().lower()
            if channel:
                launch_kwargs["channel"] = channel
            else:
                # Common on Windows if Chrome is installed.
                launch_kwargs["channel"] = "chrome"

            try:
                self._browser = await self._playwright.chromium.launch(**launch_kwargs)
            except Exception:
                # Fall back to Playwright-managed chromium.
                launch_kwargs.pop("channel", None)
                self._browser = await self._playwright.chromium.launch(**launch_kwargs)

            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
            self._page.set_default_navigation_timeout(self.navigation_timeout_ms)
            self._page.set_default_timeout(self.action_timeout_ms)

    async def close_browser(self) -> None:
        async with self._lock:
            page = self._page
            ctx = self._context
            browser = self._browser
            pw = self._playwright

            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None

            try:
                if page:
                    await page.close()
            finally:
                try:
                    if ctx:
                        await ctx.close()
                finally:
                    try:
                        if browser:
                            await browser.close()
                    finally:
                        if pw:
                            await pw.stop()

    async def visit_url(self, url: str) -> Dict[str, Any]:
        url = (url or "").strip()
        if not _is_http_url(url):
            raise BrowserAutomationError("Only http/https URLs are allowed.")

        await self.open_browser()
        assert self._page is not None

        await self._page.goto(url, wait_until="domcontentloaded")
        return {"url": url, "title": await self._page.title()}

    async def open_url(self, url: str) -> None:
        url = (url or "").strip()
        if not _is_http_url(url):
            raise BrowserAutomationError("Only http/https URLs are allowed.")
        await self.open_browser()
        assert self._page is not None
        await self._page.goto(url, wait_until="domcontentloaded")

    async def search_google(self, query: str, limit: int = 5) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise BrowserAutomationError("Missing query.")
        await self.open_browser()
        assert self._page is not None

        url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en"
        await self._page.goto(url, wait_until="domcontentloaded")

        results = await self._extract_google_search_results(limit=limit)
        return {
            "source": "google",
            "query": query,
            "results": [r.__dict__ for r in results],
        }

    async def extract_page_text(self, *, max_chars: int = 20_000) -> str:
        await self.open_browser()
        assert self._page is not None

        body = self._page.locator("body")
        text = (await body.inner_text()) if body else ""
        text = (text or "").strip()
        if max_chars and len(text) > max_chars:
            return text[:max_chars]
        return text

    async def extract_titles(self, *, limit: int = 50) -> List[str]:
        await self.open_browser()
        assert self._page is not None
        titles = await self._page.locator("h1, h2, h3").all_inner_texts()
        cleaned = [t.strip() for t in titles if t and t.strip()]
        return cleaned[: max(1, int(limit))]

    async def extract_paragraphs(self, *, limit: int = 80) -> List[str]:
        await self.open_browser()
        assert self._page is not None
        paras = await self._page.locator("p").all_inner_texts()
        cleaned = [p.strip() for p in paras if p and p.strip()]
        return cleaned[: max(1, int(limit))]

    async def extract_links(self, *, limit: int = 100) -> List[str]:
        await self.open_browser()
        assert self._page is not None
        loc = self._page.locator("a")
        count = min(await loc.count(), max(1, int(limit)))
        links: List[str] = []
        for i in range(count):
            href = await loc.nth(i).get_attribute("href")
            if href and _is_http_url(href):
                links.append(href)
        return links

    async def take_screenshot(self, *, label: str = "page") -> str:
        await self.open_browser()
        assert self._page is not None

        ts = int(time.time())
        out_dir = DATA_DIR / "downloads" / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{label}_{ts}.png"
        await self._page.screenshot(path=str(path), full_page=True)
        return str(path)

    async def download_images(self, query: str, *, limit: int = 10) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise BrowserAutomationError("Missing query.")

        limit = max(1, int(limit))
        await self.open_browser()
        assert self._page is not None

        url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch&hl=en"
        await self._page.goto(url, wait_until="domcontentloaded")

        image_urls = await self._collect_image_urls(limit=limit * 2)
        image_urls = [u for u in image_urls if _is_http_url(u)]
        image_urls = image_urls[:limit]

        out_dir = DATA_DIR / "downloads" / "images"
        out_dir.mkdir(parents=True, exist_ok=True)

        sem = asyncio.Semaphore(self.max_concurrent_downloads)
        ts = int(time.time())

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:

            async def _fetch_one(idx: int, img_url: str) -> Optional[str]:
                async with sem:
                    try:
                        r = await client.get(img_url)
                        r.raise_for_status()
                        ext = _guess_image_ext(r.headers.get("content-type", ""))
                        filename = f"{_safe_filename(query)}_{ts}_{idx}{ext}"
                        path = out_dir / filename
                        path.write_bytes(r.content)
                        return str(path)
                    except Exception:
                        return None

            tasks = [_fetch_one(i, u) for i, u in enumerate(image_urls, start=1)]
            saved = [p for p in await asyncio.gather(*tasks) if p]

        return {
            "downloaded": len(saved),
            "path": str(out_dir),
            "files": saved,
            "query": query,
            "source": "google",
        }

    # -------------------------
    # Internal helpers
    # -------------------------

    async def _extract_google_search_results(self, *, limit: int = 5) -> List[GoogleSearchResult]:
        assert self._page is not None
        limit = max(1, int(limit))

        # Try a few robust selectors to survive minor layout changes.
        loc = self._page.locator("div#search a:has(h3)")
        count = await loc.count()

        results: List[GoogleSearchResult] = []
        for i in range(min(count, limit * 3)):
            a = loc.nth(i)
            title = (await a.locator("h3").inner_text()) if await a.locator("h3").count() else ""
            href = await a.get_attribute("href")
            title = (title or "").strip()
            href = (href or "").strip()
            if title and href and _is_http_url(href):
                results.append(GoogleSearchResult(title=title, link=href))
            if len(results) >= limit:
                break

        return results

    async def _collect_image_urls(self, *, limit: int) -> List[str]:
        assert self._page is not None

        # Google Images tends to lazy-load thumbnails. Scroll a bit to populate.
        for _ in range(3):
            try:
                await self._page.mouse.wheel(0, 1800)
                await self._page.wait_for_timeout(400)
            except Exception:
                break

        loc = self._page.locator("img")
        count = min(await loc.count(), max(20, int(limit) * 10))
        urls: List[str] = []
        for i in range(count):
            src = await loc.nth(i).get_attribute("src")
            if src and src.startswith("http"):
                urls.append(src)
            if len(urls) >= limit:
                break
        # De-dup preserve order
        seen = set()
        out: List[str] = []
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out


def _safe_filename(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (text or "").strip())
    cleaned = cleaned.strip("_")
    return cleaned[:80] if cleaned else "query"


def _guess_image_ext(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    return ".jpg"


_shared_automation: BrowserAutomation | None = None
_shared_lock = asyncio.Lock()


async def get_browser_automation() -> BrowserAutomation:
    global _shared_automation
    async with _shared_lock:
        if _shared_automation is None:
            _shared_automation = BrowserAutomation(
                headless=os.getenv("BROWSER_HEADLESS", "false").strip().lower() == "true",
            )
        return _shared_automation
