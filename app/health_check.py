import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any

from app.config import (
    BASE_DIR, OUTPUT_DIR, UPLOADS_DIR, BROWSER_PROFILE_DIR,
    GEMINI_API_KEY, DEFAULT_VIDEO_PROVIDER
)

def perform_health_check() -> Dict[str, Any]:
    """
    Performs comprehensive diagnostic checks:
    - Python environment & version
    - Required packages installed
    - Gemini API key configured
    - Google Chrome executable found
    - Playwright Chromium installed
    - Output directory writable
    - Video provider setting
    """
    results = {}

    # 1. Python Environment
    v = sys.version_info
    py_ok = v >= (3, 11)
    results["python"] = {
        "ok": py_ok,
        "label": f"Python {v.major}.{v.minor}.{v.micro}",
        "detail": sys.executable if py_ok else f"Python 3.11+ required (found {v.major}.{v.minor})"
    }

    # 2. Required Packages
    pkgs = ["fastapi", "uvicorn", "google.genai", "playwright", "docx", "dotenv", "pydantic"]
    missing_pkgs = []
    for pkg in pkgs:
        try:
            __import__(pkg)
        except ImportError:
            missing_pkgs.append(pkg)
    results["packages"] = {
        "ok": len(missing_pkgs) == 0,
        "label": "All core packages installed" if not missing_pkgs else f"Missing: {', '.join(missing_pkgs)}",
        "detail": "fastapi, uvicorn, google-genai, playwright, python-docx, python-dotenv, pydantic"
    }

    # 3. Gemini API Key
    key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    has_key = bool(key and key != "your_gemini_api_key_here")
    results["gemini_key"] = {
        "ok": has_key,
        "label": f"Configured (...{key[-4:]})" if has_key else "Missing / Not set",
        "detail": "Set in .env or Settings page" if not has_key else "Ready for script generation"
    }

    # 4. Google Chrome Detection
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome") or "",
        shutil.which("google-chrome") or ""
    ]
    detected_chrome = next((p for p in chrome_paths if p and os.path.isfile(p)), None)
    results["chrome"] = {
        "ok": detected_chrome is not None,
        "label": "Installed Google Chrome found" if detected_chrome else "Chrome not detected (will use bundled Chromium)",
        "detail": detected_chrome or "Bundled Chromium available via Playwright"
    }

    # 5. Playwright Browsers
    playwright_dir = Path(os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"))
    has_chromium = False
    if playwright_dir.exists():
        has_chromium = any(playwright_dir.glob("chromium*"))
    results["playwright"] = {
        "ok": has_chromium,
        "label": "Chromium browser installed" if has_chromium else "Chromium missing (run: python -m playwright install chromium)",
        "detail": str(playwright_dir) if has_chromium else "Run: playwright install chromium"
    }

    # 6. FFmpeg status (Playwright bundles its own or uses internal writers)
    ffmpeg_on_path = shutil.which("ffmpeg") is not None
    results["ffmpeg"] = {
        "ok": True,
        "label": "Playwright self-contained (FFmpeg optional)",
        "detail": "System FFmpeg found on PATH" if ffmpeg_on_path else "Not strictly required for web app"
    }

    # 7. Output directory writable
    output_ok = False
    test_file = OUTPUT_DIR / ".write_test"
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        test_file.write_text("ok")
        test_file.unlink()
        output_ok = True
    except Exception:
        output_ok = False
    results["output_dir"] = {
        "ok": output_ok,
        "label": "Output folder writable",
        "detail": str(OUTPUT_DIR)
    }

    # 8. Active Video Provider
    active_prov = os.getenv("VIDEO_PROVIDER", DEFAULT_VIDEO_PROVIDER).strip()
    results["provider"] = {
        "ok": True,
        "label": f"Active: '{active_prov}'",
        "detail": "Mock Provider (offline & free testing)" if active_prov == "mock" else "Google Flow (Playwright automation)"
    }

    return results
