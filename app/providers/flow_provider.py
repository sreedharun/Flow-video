import logging
from pathlib import Path
from typing import Optional, Callable
from app.providers.base import BaseVideoProvider
from app.flow_driver import FlowDriver

logger = logging.getLogger("flow_provider")

class FlowVideoProvider(BaseVideoProvider):
    """
    Google Flow Video Provider implementing BaseVideoProvider.
    Automates scene creation via Playwright in FlowDriver.
    """

    def __init__(self, headless: Optional[bool] = None):
        self.driver = FlowDriver(headless=headless)

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
        return await self.driver.generate_scene(
            scene_number=scene_number,
            prompt=prompt,
            output_file=output_file,
            narration_text=narration_text,
            language=language,
            ref_image_path=ref_image_path,
            aspect_ratio=aspect_ratio,
            duration=duration,
            flow_model=flow_model,
            resolution=resolution,
            project_url=project_url,
            log_callback=log_callback
        )

    async def close(self):
        await self.driver.close()
