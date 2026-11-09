import logging
import subprocess
from pathlib import Path
from typing import Optional
from gtts import gTTS
import imageio_ffmpeg

logger = logging.getLogger("audio_service")

# Map supported language names to gTTS language codes
LANG_CODES = {
    "tamil": "ta",
    "english": "en",
    "hindi": "hi",
    "telugu": "te",
    "malayalam": "ml",
    "kannada": "kn"
}

def get_lang_code(language_name: str) -> str:
    cleaned = (language_name or "english").strip().lower()
    for key, code in LANG_CODES.items():
        if key in cleaned:
            return code
    return "en"

def generate_voiceover(text: str, language: str, output_path: Path) -> Optional[Path]:
    """Generates natural TTS voiceover audio file using gTTS in the requested language."""
    try:
        clean_text = text.strip()
        if not clean_text:
            return None
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lang_code = get_lang_code(language)
        
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        tts.save(str(output_path))
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info(f"Generated voiceover audio ({lang_code}): {output_path.name}")
            return output_path
        return None
    except Exception as e:
        logger.warning(f"Voiceover TTS generation failed: {e}")
        return None

def merge_video_and_voiceover(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """
    Merges the generated video visuals with the spoken narration voiceover.
    Uses bundled FFmpeg with stream looping so the video smoothly plays
    for the exact duration of the spoken voiceover explanation.
    """
    if not audio_path or not audio_path.exists():
        return video_path

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_out = output_path.parent / f"temp_{output_path.name}"

        # Combine video stream with audio stream
        cmd = [
            ffmpeg_exe,
            "-y",
            "-stream_loop", "-1",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(temp_out)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 5000:
            temp_out.replace(output_path)
            logger.info(f"Successfully merged voiceover audio into {output_path.name}")
            return output_path
        else:
            logger.warning(f"FFmpeg merge warning ({result.returncode}): {result.stderr[:200]}")
            if temp_out.exists():
                temp_out.unlink()
            return video_path
    except Exception as e:
        logger.warning(f"Failed to merge voiceover into video: {e}")
        return video_path
