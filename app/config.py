import os
from pathlib import Path
from dotenv import load_dotenv

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

OUTPUT_DIR = BASE_DIR / "output"
UPLOADS_DIR = BASE_DIR / "uploads"
BROWSER_PROFILE_DIR = BASE_DIR / "flow_user_data"
DB_PATH = BASE_DIR / "jobs.db"

# Ensure essential directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# App Configuration
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Video Generation Provider ('flow' or 'mock')
DEFAULT_VIDEO_PROVIDER = os.getenv("VIDEO_PROVIDER", "flow").strip()
DEFAULT_FLOW_PROJECT_URL = os.getenv("FLOW_PROJECT_URL", "https://flow.google.com/project/5bbffd82-f0b0-4148-ab6d-389035675fcb").strip()

# Browser settings
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
FLOW_NAV_TIMEOUT_MS = int(os.getenv("FLOW_NAV_TIMEOUT_MS", "60000"))

# Choices
SUPPORTED_LANGUAGES = [
    "English",
    "Tamil",
    "Hindi",
    "Telugu",
    "Malayalam",
    "Kannada"
]

SUPPORTED_STYLES = [
    "cinematic",
    "cartoon",
    "realistic",
    "ad/commercial",
    "custom"
]

SUPPORTED_TONES = [
    "informative",
    "emotional",
    "funny",
    "advertisement"
]

ASPECT_RATIOS = ["9:16", "16:9"]
TARGET_LENGTHS = [5, 8]
DEFAULT_RESOLUTION = os.getenv("FLOW_RESOLUTION", "360p").strip()
SUPPORTED_RESOLUTIONS = [
    {"id": "360p", "name": "360p (Ultra Low Cost: ~6 credits - Recommended)", "credits": 6},
    {"id": "720p", "name": "720p (Standard HD: ~12 credits)", "credits": 12},
    {"id": "1080p", "name": "1080p (Full HD: ~30 credits)", "credits": 30}
]
FLOW_MODELS = [
    {"id": "omni_1.1_flash", "name": "Omni 1.1 Flash (Low Cost: ~6 credits, fast)", "prompt_tag": "using Omni 1.1 Flash"},
    {"id": "omni_1.2_flash", "name": "Omni 1.2 Flash (Default: ~30 credits)", "prompt_tag": "using Omni 1.2 Flash"}
]
