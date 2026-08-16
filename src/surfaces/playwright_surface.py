from typing import Any
from playwright.async_api import async_playwright
from src.capabilities.schema import LocatorKind, TargetRef
from .base import SurfaceAdapter

class TargetResolutionError(RuntimeError):
    pass

class PlaywrightSurface(SurfaceAdapter):
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._pw = self._browser = self._context = None
        self.page = None

    async def start(self, entry_url: str) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self.page = await self._context.new_page()
        await self.page.goto(entry_url)
        await self.page.wait_for_load_state("domcontentloaded")

    async def close(self) -> None:
        if self._browser: await self._browser.close()
        if self._pw: await self._pw.stop()

    @property
    def current_url(self) -> str:
        return self.page.url if self.page else ""

    async def snapshot(self) -> dict[str, Any]:
        controls = await self.page.locator("input,button,a,select,textarea").evaluate_all("""els => els.map((e,i)=>({index:i,tag:e.tagName.toLowerCase(),text:(e.innerText||e.value||e.getAttribute('aria-label')||'').trim(),name:e.getAttribute('name'),id:e.id||null,type:e.getAttribute('type'),placeholder:e.getAttribute('placeholder'),ariaLabel:e.getAttribute('aria-label')}))""")
        return {"url": self.page.url, "title": await self.page.title(), "controls": controls, "text": (await self.page.locator("body").inner_text())[:5000]}

    async def _resolve(self, target: TargetRef, timeout_ms: int):
        errors = []
        for c in target.candidates:
            try:
                if c.kind == LocatorKind.ROLE:
                    loc = self.page.get_by_role(c.value, name=c.name, exact=c.exact)
                elif c.kind == LocatorKind.LABEL:
                    loc = self.page.get_by_label(c.value, exact=c.exact)
                elif c.kind == LocatorKind.TEXT:
                    loc = self.page.get_by_text(c.value, exact=c.exact)
                else:
                    loc = self.page.locator(c.value)
                await loc.first.wait_for(state="visible", timeout=timeout_ms)
                return loc.first
            except Exception as e:
                errors.append(type(e).__name__)
        raise TargetResolutionError(f"Could not resolve {target.description}: {errors}")

    async def goto(self, url: str) -> None:
        await self.page.goto(url)
        await self.page.wait_for_load_state("domcontentloaded")
    async def click(self, target: TargetRef, timeout_ms: int = 5000) -> None:
        await (await self._resolve(target, timeout_ms)).click()
    async def fill(self, target: TargetRef, value: str, timeout_ms: int = 5000) -> None:
        await (await self._resolve(target, timeout_ms)).fill(value)
    async def extract(self, target: TargetRef, timeout_ms: int = 5000) -> str:
        loc = await self._resolve(target, timeout_ms)
        text = (await loc.inner_text()).strip()
        return text or (await loc.input_value()).strip()
    async def visible_text(self, text: str, timeout_ms: int = 2000) -> bool:
        try:
            await self.page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False
    async def screenshot(self, path: str) -> None:
        await self.page.screenshot(path=path, full_page=True)
