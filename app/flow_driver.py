import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable
from playwright.async_api import async_playwright, BrowserContext, Page, Download, TimeoutError

from app.config import (
    BROWSER_PROFILE_DIR,
    BROWSER_HEADLESS,
    FLOW_NAV_TIMEOUT_MS,
    DEFAULT_FLOW_PROJECT_URL
)

logger = logging.getLogger("flow_driver")

def cleanup_profile_locks(user_data_dir: Path):
    """Safely cleans up stale Chrome lockfiles in the profile dir if no process owns them."""
    for lock_name in ("lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"):
        target = user_data_dir / lock_name
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass

async def launch_persistent_browser(
    playwright_instance,
    user_data_dir: str,
    headless: bool = False,
    viewport: Optional[dict] = None,
    log_func: Optional[Callable[[str, str], None]] = None
) -> BrowserContext:
    """
    Launches Playwright persistent browser context.
    1. Tries channel='chrome' (the user's installed Google Chrome) with a persistent profile.
    2. Falls back to bundled Chromium if Chrome is not installed or fails to launch.
    3. Handles stale lockfiles gracefully.
    """
    def log(msg: str, lvl: str = "INFO"):
        if log_func:
            log_func(msg, lvl)
        logger.info(msg)

    profile_path = Path(user_data_dir).resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    cleanup_profile_locks(profile_path)

    args = [
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
        "--no-sandbox"
    ]
    kwargs = {
        "user_data_dir": str(profile_path),
        "headless": headless,
        "args": args
    }
    if viewport:
        kwargs["viewport"] = viewport

    # First attempt: System installed Google Chrome
    try:
        log("Attempting to launch with installed Google Chrome (channel='chrome')...")
        context = await playwright_instance.chromium.launch_persistent_context(
            channel="chrome",
            **kwargs
        )
        log("Successfully launched installed Google Chrome.")
        return context
    except Exception as chrome_err:
        log(
            f"Google Chrome launch failed ({chrome_err}). "
            f"Falling back to bundled Chromium...",
            "WARNING"
        )
        cleanup_profile_locks(profile_path)

    # Second attempt: Bundled Chromium
    try:
        log("Launching bundled Chromium...")
        context = await playwright_instance.chromium.launch_persistent_context(
            **kwargs
        )
        log("Successfully launched bundled Chromium.")
        return context
    except Exception as chromium_err:
        log(f"Bundled Chromium launch failed: {chromium_err}", "ERROR")
        raise RuntimeError(
            f"Failed to launch browser (Chrome error: {chrome_err}; Chromium error: {chromium_err})"
        ) from chromium_err


async def try_single_approval_check(page: Page, log: Callable[[str, str], None]) -> bool:
    """One-time check immediately after prompt submit if Flow explicitly requests credit approval."""
    try:
        for phrase in ["Always approve", "Approve"]:
            btn = page.get_by_text(phrase, exact=False)
            if await btn.count() > 0 and await btn.first.is_visible():
                log(f"Found credit authorization prompt: '{phrase}'. Clicking once...")
                await btn.first.click(force=True)
                await asyncio.sleep(1)
                return True
    except Exception:
        pass

    try:
        clicked = await page.evaluate("""() => {
            const elements = Array.from(document.querySelectorAll('*'));
            for (const phrase of ['always approve', 'approve']) {
                for (const el of elements) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if ((text === phrase || text.includes(phrase)) && text.length < 30) {
                        el.scrollIntoView();
                        el.click();
                        return phrase;
                    }
                }
            }
            return null;
        }""")
        if clicked:
            log(f"Authorized credit prompt ('{clicked}').")
            return True
    except Exception:
        pass

    return False


async def download_tile_video(page: Page, output_file: Path, log: Callable[[str, str], None]) -> bool:
    """
    Downloads the completed video directly from Flow's canvas tile grid:
    Hover flow-video-tile -> Click 'More options' -> Click 'Download' -> Click '360p / Original size'.
    """
    try:
        tiles = page.locator("flow-video-tile")
        cnt = await tiles.count()
        if cnt == 0:
            return False

        first_tile = tiles.first
        await first_tile.hover()
        await asyncio.sleep(0.5)

        more_btn = first_tile.locator("button[aria-label='More options']")
        if await more_btn.count() > 0 and await more_btn.first.is_visible():
            await more_btn.first.click()
            await asyncio.sleep(0.5)

            # Look for Download menu item in CDK overlay
            dl_menu = page.locator(".cdk-overlay-pane button:has-text('Download'), [role='menuitem']:has-text('Download')")
            if await dl_menu.count() > 0:
                await dl_menu.first.click()
                await asyncio.sleep(0.5)

                # Look for 360p or Original size in submenu
                submenu_opt = page.locator(
                    ".cdk-overlay-pane button:has-text('360p'), "
                    ".cdk-overlay-pane button:has-text('Original size'), "
                    ".cdk-overlay-pane [role='menuitem']:has-text('360p'), "
                    ".cdk-overlay-pane [role='menuitem']:has-text('Original size')"
                )
                if await submenu_opt.count() > 0:
                    log("Initiating download from Flow tile submenu (360p Original size)...")
                    async with page.expect_download(timeout=25000) as dl_info:
                        await submenu_opt.first.click(force=True)
                    download = await dl_info.value
                    await download.save_as(str(output_file))
                    if output_file.exists() and output_file.stat().st_size > 50000:
                        log(f"Successfully downloaded {output_file.name} ({output_file.stat().st_size} bytes) via Flow tile menu.")
                        return True
    except Exception as e:
        logger.debug(f"Tile download attempt: {e}")

    return False


async def check_and_save_video(
    page: Page,
    output_file: Path,
    existing_video_srcs: list,
    video_stream_urls: list,
    initial_stream_count: int,
    log: Callable[[str, str], None]
) -> bool:
    """
    Checks if a newly generated video is ready in Google Flow.
    Downloads it directly to output_file using multiple strategies:
    1. Direct canvas tile menu: More options -> Download -> 360p Original size
    2. Stream fetch from new googlevideo.com URL captured by network
    3. Direct download button or download link
    """
    # Strategy 1: Flow Canvas Tile Menu Download (Primary proven path)
    if await download_tile_video(page, output_file, log):
        return True

    # Strategy 2: Stream URL fetch if new stream detected
    if len(video_stream_urls) > initial_stream_count:
        new_url = video_stream_urls[-1]
        try:
            log("Fetching video stream directly from Google media stream...")
            resp = await page.request.get(new_url)
            if resp.status in (200, 206):
                body = await resp.body()
                if len(body) > 50000:
                    with open(output_file, "wb") as f:
                        f.write(body)
                    if output_file.exists() and output_file.stat().st_size > 50000:
                        log(f"Saved video stream ({len(body)} bytes) to {output_file.name}.")
                        return True
        except Exception as se:
            logger.debug(f"Stream fetch attempt: {se}")

    # Strategy 3: Check visible Download button in chat or page
    dl_locators = [
        page.locator("button[aria-label*='Download' i]"),
        page.locator("[role='button'][aria-label*='Download' i]"),
        page.locator("a[download]")
    ]
    for dl in dl_locators:
        try:
            if await dl.count() > 0 and await dl.first.is_visible():
                log("Visible Download button detected! Initiating download...")
                async with page.expect_download(timeout=20000) as dl_info:
                    await dl.first.click()
                download = await dl_info.value
                await download.save_as(str(output_file))
                if output_file.exists() and output_file.stat().st_size > 50000:
                    log(f"Download complete: {output_file.stat().st_size} bytes saved.")
                    return True
        except Exception:
            pass

    return False


class FlowDriver:
    """
    Playwright driver for Google Flow (labs.google/fx/tools/flow).
    Follows design rules:
    - All Flow UI steps and selectors isolated in this file.
    - Persistent user profile (saved Google session, no passwords stored).
    - Failure screenshot captured on any error.
    - Clean interface: generate_scene(...) -> file path.
    """

    FLOW_URL = "https://labs.google/fx/tools/flow"

    def __init__(self, headless: Optional[bool] = None, timeout_ms: int = FLOW_NAV_TIMEOUT_MS):
        self.headless = BROWSER_HEADLESS if headless is None else headless
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._project_created = False

    async def start(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """Starts persistent browser context with automatic crash recovery."""
        def log(msg: str, lvl: str = "INFO"):
            if log_callback:
                log_callback(msg, lvl)
            logger.info(msg)

        # Check if existing context and page are truly alive and open
        if self._context and self._page:
            try:
                if not self._page.is_closed():
                    return
            except Exception:
                pass

        # If context exists but page or browser is closed/crashed, clean up state first
        await self.close()

        log("Launching browser with persistent profile...")
        self._playwright = await async_playwright().start()

        self._context = await launch_persistent_browser(
            self._playwright,
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=self.headless,
            viewport={"width": 1366, "height": 900},
            log_func=log_callback
        )

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)

        log("Navigating to Google Flow...")
        await self._page.goto(self.FLOW_URL, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        content = await self._page.content()
        if "accounts.google.com" in self._page.url or ("Sign in" in content and "Sign in with Google" in content):
            log("NOTICE: Google login required. Please log in using the 'Google Login / Settings' tab first.", "WARNING")

    async def ensure_project(self, project_url: Optional[str] = None, log_callback: Optional[Callable[[str, str], None]] = None):
        """Navigates to the designated project (user's existing project URL) and keeps all scenes in it."""
        def log(msg: str, lvl: str = "INFO"):
            if log_callback:
                log_callback(msg, lvl)

        if self._project_created:
            return

        target_url = (project_url or "").strip() or DEFAULT_FLOW_PROJECT_URL
        if target_url and target_url.startswith("http"):
            if target_url.rstrip("/") in self._page.url.rstrip("/"):
                log(f"Already inside target Flow project: {target_url}")
                self._project_created = True
                return
            log(f"Opening your Flow project: {target_url}...")
            await self._page.goto(target_url, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            self._project_created = True
            return

        if "/project/" in self._page.url:
            log(f"Already in active project: {self._page.url}. Keeping same project for all scenes.")
            self._project_created = True
            return

        try:
            new_btn = self._page.get_by_role("button", name=re.compile(r"New project|Create project|\+ New|Start project", re.I))
            if await new_btn.count() > 0 and await new_btn.first.is_visible():
                log("Clicking 'New Project' button...")
                await new_btn.first.click()
                await asyncio.sleep(3)
            self._project_created = True
        except Exception as e:
            log(f"Project check: {e} (proceeding to canvas)")
            self._project_created = True

    async def generate_scene(
        self,
        scene_number: int,
        prompt: str,
        output_file: Path,
        narration_text: str = "",
        language: str = "Tamil",
        ref_image_path: Optional[str] = None,
        aspect_ratio: str = "9:16",
        duration: int = 5,
        flow_model: str = "omni_1.1_flash",
        resolution: str = "360p",
        project_url: Optional[str] = None,
        log_callback: Optional[Callable[[str, str], None]] = None
    ) -> Path:
        """
        Generates a single scene in Google Flow and downloads the MP4.
        """
        def log(msg: str, lvl: str = "INFO"):
            if log_callback:
                log_callback(msg, lvl)
            logger.info(f"[Scene {scene_number}] {msg}")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            page_alive = False
            if self._context and self._page:
                try:
                    page_alive = not self._page.is_closed()
                except Exception:
                    page_alive = False

            if not page_alive:
                await self.start(log_callback)

            await self.ensure_project(project_url=project_url, log_callback=log_callback)

            log("Finding prompt input field in Flow...")

            prompt_input = None
            candidate_locators = [
                self._page.get_by_role("textbox", name=re.compile(r"prompt|describe|video|create", re.I)),
                self._page.get_by_placeholder(re.compile(r"what do you want to create|describe|prompt|imagine|create|type", re.I)),
                self._page.locator("textarea[placeholder*='create' i], textarea[placeholder*='prompt' i], textarea[placeholder*='describe' i]"),
                self._page.locator("flow-creative-agent-prompt-box textarea"),
                self._page.locator("[contenteditable='true']"),
                self._page.locator("textarea")
            ]

            # Wait up to 25 seconds for prompt input to be ready/visible (Flow briefly re-renders its agent box after submitting)
            for wait_attempt in range(25):
                for loc in candidate_locators:
                    try:
                        if await loc.count() > 0 and await loc.first.is_visible():
                            prompt_input = loc.first
                            break
                    except Exception:
                        pass
                if prompt_input:
                    break
                await asyncio.sleep(1)

            if not prompt_input:
                raise RuntimeError("Could not find Flow prompt input textarea. Please check if you are logged in to Google Flow.")

            # Explicit prompt instructions: 360p, Omni 1.1 Flash, and 9:16 Reels format
            model_tag = "using model Omni 1.1 Flash" if "1.1" in flow_model.lower() else "using model Omni 1.2 Flash"
            res_tag = f"at {resolution} resolution" if resolution else "at 360p resolution"
            if "9:16" in aspect_ratio or "reels" in str(aspect_ratio).lower():
                aspect_tag = "in 9:16 vertical portrait format (Shorts/Reels)"
            else:
                aspect_tag = "in 16:9 widescreen landscape format"
            
            flow_prompt = prompt.strip()
            # Remove any legacy negative dialogue directives
            flow_prompt = re.sub(r"\(no dialogue[^\)]*\)", "", flow_prompt, flags=re.I).strip()
            
            # Embed audio/speech instruction directly with the prompt if narration exists
            if narration_text and "Audio & Speech:" not in flow_prompt:
                audio_instruction = f"Audio & Speech: The character speaks in {language} saying: \"{narration_text.strip()}\", clear natural voiceover audio."
                flow_prompt = f"{flow_prompt}. {audio_instruction}"

            if not flow_prompt.lower().startswith("create a video") and not flow_prompt.lower().startswith("generate a video"):
                flow_prompt = f"Create a video {res_tag} {model_tag} {aspect_tag}: {flow_prompt}"
            else:
                flow_prompt = f"{flow_prompt} ({res_tag}, {model_tag}, {aspect_tag})"

            log(f"Entering video prompt: {flow_prompt[:70]}...")
            await prompt_input.fill("")
            await prompt_input.fill(flow_prompt)
            await asyncio.sleep(1)

            if ref_image_path and Path(ref_image_path).exists():
                log("Attaching character reference image...")
                file_input = self._page.locator("input[type='file']")
                if await file_input.count() > 0:
                    await file_input.first.set_input_files(ref_image_path)
                    await asyncio.sleep(2)

            log("Submitting prompt for video generation...")
            send_btn = None
            btn_locators = [
                self._page.locator("button[aria-label*='send' i]"),
                self._page.locator("button[aria-label*='submit' i]"),
                self._page.locator("button[aria-label*='generate' i]"),
                self._page.get_by_role("button", name=re.compile(r"^generate$|^create$|^run$|^make video$", re.I)),
                self._page.locator("button:has(svg)")
            ]
            for btn in btn_locators:
                if await btn.count() > 0 and await btn.first.is_visible():
                    send_btn = btn.first
                    break

            if send_btn:
                await send_btn.click()
            else:
                await prompt_input.press("Enter")

            log(f"Scene {scene_number} prompt submitted to Google Flow! Generation triggered.")
            
            # Allow Flow 20 seconds to comfortably register the video tile on the board
            wait_seconds = 20
            log(f"Giving Flow {wait_seconds}s to spawn video tile before next scene...")
            await asyncio.sleep(wait_seconds)

            # Ensure prompt textarea is re-enabled and ready before moving to next scene
            for _ in range(5):
                try:
                    if self._page and not self._page.is_closed():
                        p_box = self._page.locator("textarea, [contenteditable='true']")
                        if await p_box.count() > 0 and await p_box.first.is_visible():
                            break
                except Exception:
                    pass
                await asyncio.sleep(2)

            log(f"Scene {scene_number} active on board! Ready for next scene.")
            return output_file

        except Exception as e:
            screenshot_path = output_file.parent / f"error_scene_{scene_number}_{int(asyncio.get_event_loop().time())}.png"
            log(f"Failure occurred: {e}. Saving diagnostic screenshot to {screenshot_path.name}", "ERROR")
            try:
                if self._page and not self._page.is_closed():
                    await self._page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception as ss_err:
                log(f"Could not capture screenshot: {ss_err}", "WARNING")
            raise

    async def close(self):
        """Closes browser session and cleanly resets state."""
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._context = None
            self._page = None
            self._playwright = None
            self._project_created = False
