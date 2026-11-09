import os
import uuid
import asyncio
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import set_key

from app.config import (
    BASE_DIR, OUTPUT_DIR, UPLOADS_DIR, BROWSER_PROFILE_DIR,
    APP_HOST, APP_PORT, GEMINI_API_KEY, DEFAULT_VIDEO_PROVIDER,
    DEFAULT_FLOW_PROJECT_URL, BROWSER_HEADLESS, SUPPORTED_LANGUAGES, SUPPORTED_STYLES, SUPPORTED_TONES,
    FLOW_MODELS, SUPPORTED_RESOLUTIONS, DEFAULT_RESOLUTION
)
from app.db import (
    init_db, create_job, get_job, get_all_jobs, save_scenes,
    get_logs, update_job_status
)
from app.gemini_service import generate_script
from app.worker import worker
from app.health_check import perform_health_check

app = FastAPI(title="Google Flow Multi-Scene Video Studio")

# Static files & templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

@app.on_event("startup")
async def startup_event():
    init_db()

# --- Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "active_page": "create",
            "languages": SUPPORTED_LANGUAGES,
            "styles": SUPPORTED_STYLES,
            "tones": SUPPORTED_TONES,
            "flow_models": FLOW_MODELS,
            "resolutions": SUPPORTED_RESOLUTIONS,
            "default_resolution": DEFAULT_RESOLUTION,
            "default_project_url": os.getenv("FLOW_PROJECT_URL", DEFAULT_FLOW_PROJECT_URL)
        }
    )

@app.get("/progress/{job_id}", response_class=HTMLResponse)
async def progress_page(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = get_logs(job_id)
    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "active_page": "create",
            "job": job,
            "logs": logs
        }
    )

@app.get("/results/{job_id}", response_class=HTMLResponse)
async def results_page(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "active_page": "history",
            "job": job
        }
    )

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    jobs = get_all_jobs()
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "active_page": "history",
            "jobs": jobs
        }
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    # Mask API key for security
    masked_key = ""
    current_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if current_key:
        masked_key = current_key[:4] + "..." + current_key[-4:] if len(current_key) > 8 else "***"

    health = perform_health_check()

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "active_page": "settings",
            "current_provider": os.getenv("VIDEO_PROVIDER", DEFAULT_VIDEO_PROVIDER),
            "headless": os.getenv("BROWSER_HEADLESS", str(BROWSER_HEADLESS)).lower() in ("true", "1", "yes"),
            "masked_gemini_key": masked_key,
            "health": health
        }
    )

@app.get("/api/health")
async def api_health():
    return perform_health_check()

# --- API Endpoints ---

@app.post("/api/script/generate")
async def api_generate_script(
    topic: str = Form(...),
    language: str = Form(...),
    num_scenes: int = Form(4),
    target_length: int = Form(5),
    style: str = Form("cinematic"),
    tone: str = Form("informative"),
    aspect_ratio: str = Form("9:16"),
    flow_model: str = Form("omni_1.1_flash"),
    resolution: str = Form("360p"),
    flow_project_url: Optional[str] = Form(None),
    character_desc: Optional[str] = Form(None),
    ref_image: Optional[UploadFile] = File(None)
):
    try:
        ref_image_path = None
        if ref_image and ref_image.filename:
            file_ext = Path(ref_image.filename).suffix
            saved_name = f"ref_{uuid.uuid4().hex[:8]}{file_ext}"
            save_path = UPLOADS_DIR / saved_name
            with open(save_path, "wb") as f:
                f.write(await ref_image.read())
            ref_image_path = str(save_path)

        # Call Gemini script generator
        script_data = generate_script(
            topic=topic,
            language=language,
            num_scenes=num_scenes,
            target_length=target_length,
            style=style,
            tone=tone,
            aspect_ratio=aspect_ratio,
            character_desc=character_desc
        )

        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        job_record = {
            "id": job_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic,
            "language": language,
            "num_scenes": num_scenes,
            "target_length": target_length,
            "style": style,
            "tone": tone,
            "aspect_ratio": aspect_ratio,
            "flow_model": flow_model,
            "resolution": resolution,
            "flow_project_url": (flow_project_url or "").strip() or DEFAULT_FLOW_PROJECT_URL,
            "character_desc": script_data.get("character_desc", character_desc or ""),
            "ref_image_path": ref_image_path,
            "title": script_data.get("title", topic[:40]),
            "status": "draft",
            "output_dir": str(job_dir)
        }
        create_job(job_record)

        # Save initial scenes to DB
        scenes = []
        for s in script_data.get("scenes", []):
            scenes.append({
                "scene_number": s["scene_number"],
                "narration_text": s["narration_text"],
                "video_prompt": s["video_prompt"],
                "target_length": target_length,
                "status": "queued"
            })
        save_scenes(job_id, scenes)

        return {"status": "ok", "job_id": job_id, "script": script_data}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

class SceneUpdate(BaseModel):
    scene_number: int
    narration_text: str
    video_prompt: str

class StartJobRequest(BaseModel):
    job_id: str
    single_scene_only: bool = False
    title: Optional[str] = None
    character_desc: Optional[str] = None
    scenes: List[SceneUpdate]

@app.post("/api/job/start")
async def api_start_job(req: StartJobRequest):
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update scenes in SQLite with user edits
    scenes_data = []
    for s in req.scenes:
        scenes_data.append({
            "scene_number": s.scene_number,
            "narration_text": s.narration_text,
            "video_prompt": s.video_prompt,
            "target_length": job["target_length"],
            "status": "queued"
        })
    save_scenes(req.job_id, scenes_data)

    # Launch background generation
    active_provider = os.getenv("VIDEO_PROVIDER", DEFAULT_VIDEO_PROVIDER)
    worker.start_job(req.job_id, single_scene_only=req.single_scene_only, provider_type=active_provider)

    return {"status": "ok", "job_id": req.job_id}

@app.post("/api/job/{job_id}/cancel")
async def api_cancel_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    worker.cancel_job(job_id)
    return {"status": "ok", "message": "Job cancelled."}

@app.post("/api/job/{job_id}/retry-failed")
async def api_retry_failed_scenes(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    active_provider = os.getenv("VIDEO_PROVIDER", DEFAULT_VIDEO_PROVIDER)
    worker.start_job(job_id, retry_failed_only=True, provider_type=active_provider)
    return {"status": "ok", "message": "Retrying failed scenes."}

@app.get("/api/config/active-provider")
async def api_get_active_provider():
    active_provider = os.getenv("VIDEO_PROVIDER", DEFAULT_VIDEO_PROVIDER)
    return {"provider": active_provider}

@app.get("/api/job/{job_id}/status")
async def api_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = get_logs(job_id, limit=50)
    job["logs"] = logs
    return job

@app.get("/api/job/{job_id}/events")
async def api_job_events(job_id: str):
    queue = worker.subscribe(job_id)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            worker.unsubscribe(job_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Google One-Time Login Helper ---
@app.post("/api/browser/open-login")
async def api_open_browser_login():
    """
    Opens Chromium / Chrome visibly using the persistent user profile folder so
    the user can log into their Google account on Google Labs Flow.
    Prefers installed Google Chrome (channel='chrome') with fallback to bundled Chromium.
    Catches exact exception and reports back.
    """
    from playwright.async_api import async_playwright
    from app.flow_driver import launch_persistent_browser, cleanup_profile_locks

    cleanup_profile_locks(BROWSER_PROFILE_DIR)

    async def run_login_browser():
        try:
            async with async_playwright() as p:
                context = await launch_persistent_browser(
                    playwright_instance=p,
                    user_data_dir=str(BROWSER_PROFILE_DIR),
                    headless=False,
                    viewport=None
                )
                page = context.pages[0] if context.pages else await context.new_page()
                try:
                    await page.goto("https://flow.google.com", timeout=60000)
                except Exception:
                    await page.goto("https://labs.google/fx/tools/flow", timeout=60000)

                # Keep browser open until the user manually closes all tabs / the window
                while len(context.pages) > 0:
                    await asyncio.sleep(1)
                await context.close()
        except Exception as e:
            logger.error(f"Error in background login browser: {e}", exc_info=True)

    try:
        # Launch background task
        asyncio.create_task(run_login_browser())
        return {
            "status": "ok",
            "message": "Browser window opening! Sign in to Google, then close the browser window when finished."
        }
    except Exception as e:
        logger.error(f"Failed to initiate login browser: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

class SettingsUpdate(BaseModel):
    provider: str
    headless: bool
    gemini_key: Optional[str] = None

@app.post("/api/settings")
async def api_update_settings(settings: SettingsUpdate):
    env_file = BASE_DIR / ".env"
    set_key(str(env_file), "VIDEO_PROVIDER", settings.provider)
    set_key(str(env_file), "BROWSER_HEADLESS", str(settings.headless).lower())
    
    if settings.gemini_key and not settings.gemini_key.startswith("***") and "..." not in settings.gemini_key:
        set_key(str(env_file), "GEMINI_API_KEY", settings.gemini_key.strip())
        os.environ["GEMINI_API_KEY"] = settings.gemini_key.strip()

    os.environ["VIDEO_PROVIDER"] = settings.provider
    os.environ["BROWSER_HEADLESS"] = str(settings.headless).lower()

    return {"status": "ok"}
