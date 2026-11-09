import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.config import OUTPUT_DIR, DEFAULT_VIDEO_PROVIDER
from app.db import (
    update_job_status,
    update_job_current_scene,
    update_scene_status,
    add_log,
    get_job
)
from app.doc_generator import generate_script_txt, generate_script_docx, create_job_zip
from app.audio_service import generate_voiceover, merge_video_and_voiceover
from app.providers.base import BaseVideoProvider
from app.providers.mock_provider import MockVideoProvider

logger = logging.getLogger("worker")

class JobWorker:
    def __init__(self):
        self._provider: Optional[BaseVideoProvider] = None
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._listeners: Dict[str, List[asyncio.Queue]] = {}

    def get_provider(self, provider_type: Optional[str] = None) -> BaseVideoProvider:
        p_type = provider_type or DEFAULT_VIDEO_PROVIDER
        if p_type == "flow":
            # Lazy import to avoid importing Playwright before needed
            from app.providers.flow_provider import FlowVideoProvider
            return FlowVideoProvider()
        return MockVideoProvider()

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if job_id not in self._listeners:
            self._listeners[job_id] = []
        self._listeners[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue):
        if job_id in self._listeners:
            if q in self._listeners[job_id]:
                self._listeners[job_id].remove(q)
            if not self._listeners[job_id]:
                del self._listeners[job_id]

    async def broadcast(self, job_id: str, event: Dict[str, Any]):
        if job_id in self._listeners:
            for q in list(self._listeners[job_id]):
                try:
                    await q.put(event)
                except Exception:
                    pass

    def log(self, job_id: str, message: str, level: str = "INFO"):
        logger.info(f"[{job_id}] [{level}] {message}")
        add_log(job_id, message, level)
        asyncio.create_task(self.broadcast(job_id, {
            "type": "log",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }))

    def cancel_job(self, job_id: str) -> bool:
        """Cancels a currently executing generation job."""
        task = self._active_tasks.get(job_id)
        cancelled = False
        if task and not task.done():
            task.cancel()
            cancelled = True

        self.log(job_id, "Job cancelled by user.", "WARNING")
        update_job_status(job_id, "cancelled", error_message="Job cancelled by user.")

        # Update remaining scenes to cancelled
        job = get_job(job_id)
        if job:
            for s in job.get("scenes", []):
                if s["status"] in ("queued", "generating"):
                    update_scene_status(job_id, s["scene_number"], "cancelled", error_message="Cancelled by user.")

        asyncio.create_task(self.broadcast(job_id, {
            "type": "job_status",
            "status": "cancelled"
        }))
        return cancelled

    def start_job(
        self,
        job_id: str,
        single_scene_only: bool = False,
        retry_failed_only: bool = False,
        provider_type: Optional[str] = None
    ):
        """Launches background generation task for a job."""
        if job_id in self._active_tasks and not self._active_tasks[job_id].done():
            logger.warning(f"Job {job_id} already has a running task.")
            return

        task = asyncio.create_task(self._process_job(job_id, single_scene_only, retry_failed_only, provider_type))
        self._active_tasks[job_id] = task

    async def _process_job(
        self,
        job_id: str,
        single_scene_only: bool,
        retry_failed_only: bool,
        provider_type: Optional[str]
    ):
        job = get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in database.")
            return

        provider = self.get_provider(provider_type)
        provider_name = provider.__class__.__name__

        mode_desc = "Retry failed scenes only" if retry_failed_only else ("Single scene test" if single_scene_only else "All scenes")
        self.log(job_id, f"Job started ({mode_desc}) with provider: {provider_name}.")
        update_job_status(job_id, "processing")
        await self.broadcast(job_id, {"type": "job_status", "status": "processing"})

        job_dir = Path(job["output_dir"])
        job_dir.mkdir(parents=True, exist_ok=True)

        all_scenes = job["scenes"]
        if retry_failed_only:
            scenes_to_process = [s for s in all_scenes if s["status"] == "failed"]
            if not scenes_to_process:
                self.log(job_id, "No failed scenes found to retry.")
                update_job_status(job_id, "completed")
                await self.broadcast(job_id, {"type": "job_status", "status": "completed"})
                return
        elif single_scene_only and all_scenes:
            scenes_to_process = [all_scenes[0]]
        else:
            scenes_to_process = all_scenes

        overall_success = True

        try:
            for scene in scenes_to_process:
                scene_num = scene["scene_number"]
                target_dur = scene["target_length"] or job["target_length"]
                video_prompt = scene["video_prompt"]
                aspect_ratio = job["aspect_ratio"]
                ref_image = job["ref_image_path"]
                clip_name = f"scene_{scene_num:02d}.mp4"
                output_file = job_dir / clip_name

                update_job_current_scene(job_id, scene_num)
                update_scene_status(job_id, scene_num, "generating")
                await self.broadcast(job_id, {
                    "type": "scene_status",
                    "scene_number": scene_num,
                    "status": "generating"
                })
                self.log(job_id, f"Starting Scene {scene_num}/{len(all_scenes)} generation: {clip_name}")

                # Retry loop: max 2 retries (3 total attempts)
                max_retries = 2
                attempts = 0
                scene_done = False
                last_error = ""

                while attempts <= max_retries and not scene_done:
                    try:
                        if attempts > 0:
                            self.log(job_id, f"Retry attempt {attempts}/{max_retries} for Scene {scene_num}...", "WARNING")
                        
                        def cb(msg: str, lvl: str = "INFO"):
                            self.log(job_id, f"[Scene {scene_num}] {msg}", lvl)

                        # 1. Generate natural spoken Tamil voiceover audio FIRST
                        voice_file = job_dir / f"scene_{scene_num:02d}_voice.mp3"
                        self.log(job_id, f"Generating natural spoken voiceover in {job['language']}...")
                        try:
                            generate_voiceover(scene["narration_text"], job["language"], voice_file)
                            if voice_file.exists():
                                self.log(job_id, f"Spoken voiceover ready ({voice_file.name}, {voice_file.stat().st_size} bytes).")
                        except Exception as vo_err:
                            self.log(job_id, f"Voiceover generation note: {vo_err}", "WARNING")

                        # 2. Generate video in Google Flow (with embedded speech/dialogue in prompt)
                        await provider.generate_scene(
                            scene_number=scene_num,
                            prompt=video_prompt,
                            output_file=output_file,
                            narration_text=scene["narration_text"],
                            language=job["language"],
                            ref_image_path=ref_image,
                            aspect_ratio=aspect_ratio,
                            duration=target_dur,
                            flow_model=job.get("flow_model", "omni_1.1_flash"),
                            resolution=job.get("resolution", "360p"),
                            project_url=job.get("flow_project_url"),
                            log_callback=cb
                        )

                        # 3. If local video was downloaded, merge voiceover into video
                        if output_file.exists() and output_file.stat().st_size > 50000 and voice_file.exists():
                            self.log(job_id, f"Merging spoken voiceover with {output_file.name}...")
                            try:
                                merge_video_and_voiceover(output_file, voice_file, output_file)
                            except Exception as m_err:
                                self.log(job_id, f"Merge note: {m_err}", "WARNING")

                        clip_path_val = str(output_file) if (output_file.exists() and output_file.stat().st_size > 50000) else None
                        update_scene_status(job_id, scene_num, "done", clip_path=clip_path_val, retries=attempts)
                        await self.broadcast(job_id, {
                            "type": "scene_status",
                            "scene_number": scene_num,
                            "status": "done",
                            "clip_path": f"/output/{job_id}/{clip_name}" if clip_path_val else None,
                            "voice_path": f"/output/{job_id}/{voice_file.name}" if voice_file.exists() else None
                        })
                        self.log(job_id, f"Scene {scene_num} successfully completed.")
                        scene_done = True

                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        attempts += 1
                        last_error = str(e)
                        self.log(job_id, f"Error generating Scene {scene_num} (attempt {attempts}): {last_error}", "ERROR")
                        if attempts <= max_retries:
                            await asyncio.sleep(3)

                if not scene_done:
                    overall_success = False
                    update_scene_status(
                        job_id,
                        scene_num,
                        "failed",
                        error_message=last_error,
                        retries=max_retries
                    )
                    await self.broadcast(job_id, {
                        "type": "scene_status",
                        "scene_number": scene_num,
                        "status": "failed",
                        "error": last_error
                    })
                    self.log(job_id, f"Scene {scene_num} failed after {max_retries} retries.", "ERROR")

            # Check if all scenes in the job are now done
            latest_job = get_job(job_id)
            all_done = all(s["status"] == "done" for s in latest_job["scenes"])
            if not all_done and not overall_success:
                overall_success = False

            # Now generate script.txt, script.docx, and ZIP package
            self.log(job_id, "Generating script.txt and script.docx documentation...")
            refreshed_job = get_job(job_id)
            
            txt_path = job_dir / "script.txt"
            docx_path = job_dir / "script.docx"
            zip_path = job_dir / f"{job_id}_all_files.zip"

            try:
                generate_script_txt(refreshed_job, txt_path)
                generate_script_docx(refreshed_job, docx_path)
                create_job_zip(job_dir, zip_path)
                self.log(job_id, f"Updated script.txt, script.docx, and bundle {zip_path.name}")
            except Exception as e:
                self.log(job_id, f"Error generating document/zip exports: {e}", "WARNING")

            final_status = "completed" if overall_success else "failed"
            update_job_status(job_id, final_status, zip_path=str(zip_path))
            await self.broadcast(job_id, {
                "type": "job_status",
                "status": final_status,
                "zip_url": f"/output/{job_id}/{zip_path.name}"
            })
            self.log(job_id, f"Job finished with status: {final_status}")

        except asyncio.CancelledError:
            self.log(job_id, "Job execution was cancelled.", "WARNING")
            update_job_status(job_id, "cancelled", error_message="Cancelled by user.")
            await self.broadcast(job_id, {"type": "job_status", "status": "cancelled"})
        finally:
            # Cleanup provider resources if needed (e.g. browser context)
            if hasattr(provider, "close"):
                try:
                    await provider.close()
                except Exception as close_err:
                    logger.warning(f"Error closing provider: {close_err}")

# Singleton worker instance
worker = JobWorker()
