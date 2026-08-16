from __future__ import annotations

from typing import Any

from playwright.async_api import (
    Locator,
    Page,
    async_playwright,
)

from src.capabilities.schema import LocatorKind, TargetRef
from .base import SurfaceAdapter


class TargetResolutionError(RuntimeError):
    """Raised when none of the recorded locator candidates can resolve a target."""

    pass


class PlaywrightSurface(SurfaceAdapter):
    def __init__(self, headless: bool = False):
        self.headless = headless

        self._pw = None
        self._browser = None
        self._context = None

        self.page: Page | None = None

    # ------------------------------------------------------------------
    # SESSION LIFECYCLE
    # ------------------------------------------------------------------

    async def start(self, entry_url: str) -> None:
        """
        Start a new Playwright browser session and navigate to the entry URL.
        """

        self._pw = await async_playwright().start()

        self._browser = await self._pw.chromium.launch(
            headless=self.headless
        )

        self._context = await self._browser.new_context()

        self.page = await self._context.new_page()

        await self.page.goto(
            entry_url,
            wait_until="domcontentloaded",
        )

    async def close(self) -> None:
        """
        Close the browser and Playwright runtime.
        """

        if self._browser:
            await self._browser.close()

        if self._pw:
            await self._pw.stop()

        self.page = None
        self._browser = None
        self._context = None
        self._pw = None

    @property
    def current_url(self) -> str:
        if not self.page:
            return ""

        return self.page.url

    # ------------------------------------------------------------------
    # OBSERVATION
    # ------------------------------------------------------------------

    async def snapshot(self) -> dict[str, Any]:
        """
        Return a compact semantic representation of the current UI.

        The discovery planner receives this instead of raw page source.

        In particular, input values are exposed separately so the LLM can
        determine whether a field has actually been filled before submitting
        a form.
        """

        if not self.page:
            raise RuntimeError("Browser surface has not been started.")

        controls = await self.page.locator(
            "input, button, a, select, textarea"
        ).evaluate_all(
            """
            els => els.map((e, i) => ({
                index: i,

                tag: e.tagName.toLowerCase(),

                text: (e.innerText || '').trim(),

                value: ('value' in e)
                    ? e.value
                    : null,

                name: e.getAttribute('name'),

                id: e.id || null,

                role: e.getAttribute('role'),

                type: e.getAttribute('type'),

                placeholder: e.getAttribute('placeholder'),

                ariaLabel: e.getAttribute('aria-label'),

                required: Boolean(e.required),

                disabled: Boolean(e.disabled),

                readonly: Boolean(e.readOnly),

                visible: Boolean(
                    e.offsetWidth ||
                    e.offsetHeight ||
                    e.getClientRects().length
                )
            }))
            """
        )

        body_text = await self.page.locator("body").inner_text()

        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "controls": controls,
            "text": body_text[:5000],
        }

    # ------------------------------------------------------------------
    # TARGET RESOLUTION
    # ------------------------------------------------------------------

    async def _build_locator(
        self,
        target: TargetRef,
        candidate,
    ) -> Locator:
        """
        Convert one locator candidate from the capability schema into a
        Playwright locator.
        """

        if not self.page:
            raise RuntimeError("Browser surface has not been started.")

        if candidate.kind == LocatorKind.ROLE:
            return self.page.get_by_role(
                candidate.value,
                name=candidate.name,
                exact=candidate.exact,
            )

        if candidate.kind == LocatorKind.LABEL:
            return self.page.get_by_label(
                candidate.value,
                exact=candidate.exact,
            )

        if candidate.kind == LocatorKind.TEXT:
            # Gemini may return:
            #
            #   kind = text
            #   value = Search
            #
            # for a button.
            #
            # Prefer an actual button if one exists with this accessible name.
            # This avoids clicking an arbitrary text container.
            button_locator = self.page.get_by_role(
                "button",
                name=candidate.value,
                exact=candidate.exact,
            )

            if await button_locator.count() > 0:
                return button_locator

            return self.page.get_by_text(
                candidate.value,
                exact=candidate.exact,
            )

        if candidate.kind == LocatorKind.CSS:
            return self.page.locator(
                candidate.value
            )

        raise TargetResolutionError(
            f"Unsupported locator kind: {candidate.kind}"
        )

    async def _resolve(
        self,
        target: TargetRef,
        timeout_ms: int,
    ) -> Locator:
        """
        Resolve a target using candidates in deterministic priority order.

        Replay/discovery never invents another locator here. It tries only the
        candidates declared by the planner/artifact.
        """

        errors: list[str] = []

        for candidate in target.candidates:
            try:
                locator = await self._build_locator(
                    target,
                    candidate,
                )

                first = locator.first

                await first.wait_for(
                    state="visible",
                    timeout=timeout_ms,
                )

                if not await first.is_enabled():
                    raise TargetResolutionError(
                        "Resolved control is disabled."
                    )

                return first

            except Exception as exc:
                errors.append(
                    (
                        f"{candidate.kind.value}:"
                        f"{candidate.value} -> "
                        f"{type(exc).__name__}: {exc}"
                    )
                )

        raise TargetResolutionError(
            f"Could not resolve target '{target.description}'. "
            f"Tried: {' | '.join(errors)}"
        )

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    async def goto(self, url: str) -> None:
        if not self.page:
            raise RuntimeError("Browser surface has not been started.")

        await self.page.goto(
            url,
            wait_until="domcontentloaded",
        )

    async def click(
        self,
        target: TargetRef,
        timeout_ms: int = 5000,
    ) -> None:
        """
        Resolve and click a target.

        After the click, briefly wait for the page to settle. This is useful
        for old server-rendered applications where clicking a submit button
        immediately causes navigation.
        """

        if not self.page:
            raise RuntimeError("Browser surface has not been started.")

        locator = await self._resolve(
            target,
            timeout_ms,
        )

        old_url = self.page.url

        await locator.click(
            timeout=timeout_ms
        )

        # The UI may either navigate or update in place.
        # We do not require navigation because not all controls navigate.
        try:
            await self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=2000,
            )
        except Exception:
            pass

        # Give server-rendered forms a very small opportunity to settle.
        await self.page.wait_for_timeout(100)

    async def fill(
        self,
        target: TargetRef,
        value: str,
        timeout_ms: int = 5000,
    ) -> None:
        """
        Fill an input and verify the browser actually contains the requested
        value before returning control to the planner.
        """

        locator = await self._resolve(
            target,
            timeout_ms,
        )

        await locator.fill(
            value,
            timeout=timeout_ms,
        )

        # Explicitly verify the value was written.
        actual_value = await locator.input_value()

        if actual_value != value:
            raise RuntimeError(
                f"Fill verification failed for '{target.description}'. "
                f"Expected {value!r}, observed {actual_value!r}."
            )

        # Trigger normal field-change behavior in legacy applications.
        try:
            await locator.press("Tab")
        except Exception:
            pass

    async def extract(
        self,
        target: TargetRef,
        timeout_ms: int = 5000,
    ) -> str:
        """
        Extract visible text or, for form controls, their value.
        """

        locator = await self._resolve(
            target,
            timeout_ms,
        )

        try:
            text = (
                await locator.inner_text()
            ).strip()

            if text:
                return text

        except Exception:
            pass

        try:
            return (
                await locator.input_value()
            ).strip()

        except Exception as exc:
            raise RuntimeError(
                f"Could not extract value from '{target.description}'."
            ) from exc

    # ------------------------------------------------------------------
    # CHECKPOINT HELPERS
    # ------------------------------------------------------------------

    async def visible_text(
        self,
        text: str,
        timeout_ms: int = 2000,
    ) -> bool:
        if not self.page:
            raise RuntimeError("Browser surface has not been started.")

        try:
            locator = self.page.get_by_text(
                text,
                exact=False,
            ).first

            await locator.wait_for(
                state="visible",
                timeout=timeout_ms,
            )

            return True

        except Exception:
            return False

    # ------------------------------------------------------------------
    # EVIDENCE
    # ------------------------------------------------------------------

    async def screenshot(
        self,
        path: str,
    ) -> None:
        if not self.page:
            raise RuntimeError("Browser surface has not been started.")

        await self.page.screenshot(
            path=path,
            full_page=True,
        )