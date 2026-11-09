from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Callable

class BaseVideoProvider(ABC):
    """
    Abstract Base Class for Video Generation Providers.
    Allows easy swapping between Google Flow (Playwright), Mock provider,
    or future Veo API / Vertex AI endpoints.
    """

    @abstractmethod
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
        """
        Generate a single video scene given the prompt and target output path.
        Returns the path to the downloaded/generated MP4 file.
        Throws exception if generation fails after retries.
        """
        pass
