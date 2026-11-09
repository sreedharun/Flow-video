import asyncio
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import cv2
from app.providers.base import BaseVideoProvider

class MockVideoProvider(BaseVideoProvider):
    """
    Fast mock provider for local development, UI testing, and previewing
    without spending Google Flow credits or running browser automation.
    Creates a real MP4 clip with visual text and motion.
    """

    async def generate_scene(
        self,
        scene_number: int,
        prompt: str,
        output_file: Path,
        narration_text: str = "",
        language: str = "Tamil",
        ref_image_path: Optional[str] = None,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        flow_model: str = "omni_1.1_flash",
        resolution: str = "360p",
        project_url: Optional[str] = None,
        log_callback: Optional[Callable[[str, str], None]] = None
    ) -> Path:
        def log(msg: str, lvl: str = "INFO"):
            if log_callback:
                log_callback(msg, lvl)

        log(f"[MockProvider] Starting generation for Scene {scene_number} ({duration}s, {aspect_ratio})...")
        await asyncio.sleep(1.0)
        log(f"[MockProvider] Prompt: {prompt[:70]}...")
        await asyncio.sleep(1.5)

        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Generate simple MP4 clip
        width = 1280 if aspect_ratio == "16:9" else 720
        height = 720 if aspect_ratio == "16:9" else 1280
        fps = 24
        total_frames = fps * duration

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_file), fourcc, fps, (width, height))

        # Color palette depending on scene number
        colors = [
            (30, 40, 80),    # Dark navy
            (60, 30, 80),    # Purple
            (20, 60, 60),    # Dark teal
            (80, 50, 20),    # Deep bronze
            (40, 70, 30),    # Forest
            (70, 30, 40),    # Burgundy
            (30, 50, 70),    # Slate
            (60, 60, 40),    # Olive
        ]
        base_color = colors[(scene_number - 1) % len(colors)]

        for i in range(total_frames):
            frame = np.full((height, width, 3), base_color, dtype=np.uint8)
            
            # Subtle gradient/animation
            offset = int((i / total_frames) * (width // 3))
            cv2.circle(frame, (width // 4 + offset, height // 2), 120, (100, 150, 220), -1)

            # Text overlay
            text1 = f"SCENE {scene_number} (MOCK CLIP)"
            text2 = f"Duration: {duration}s | Aspect: {aspect_ratio}"
            text3 = f"Frame: {i+1}/{total_frames}"

            cv2.putText(frame, text1, (width // 10, height // 2 - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(frame, text2, (width // 10, height // 2 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 230, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, text3, (width // 10, height // 2 + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1, cv2.LINE_AA)

            writer.write(frame)

        writer.release()
        log(f"[MockProvider] Scene {scene_number} generated successfully -> {output_file.name}")
        return output_file
