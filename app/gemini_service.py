import os
import json
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import GEMINI_API_KEY

logger = logging.getLogger("gemini_service")

class SceneItem(BaseModel):
    scene_number: int = Field(description="Scene sequence number starting from 1")
    narration_text: str = Field(description="Narration spoken text in the requested language, sized to clip duration")
    video_prompt: str = Field(description="Detailed English video generation prompt with character description repeated, camera angle, action, lighting, and ambient sound notes (visuals only, no dialogue)")

class ScriptResponse(BaseModel):
    title: str = Field(description="Engaging project title")
    character_desc: str = Field(description="Comprehensive English character description used across all scenes for consistency")
    scenes: List[SceneItem] = Field(description="List of scenes")

def generate_script(
    topic: str,
    language: str,
    num_scenes: int,
    target_length: int,
    style: str,
    tone: str,
    aspect_ratio: str,
    character_desc: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls Google Gemini using the google-genai SDK to generate a multi-scene
    video production script tailored for Google Flow video generation.
    """
    key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key == "your_gemini_api_key_here":
        logger.warning("No GEMINI_API_KEY set. Generating high-quality template script.")
        # Generate demo script matching inputs so user can test immediately
        char_desc_final = character_desc or "A confident protagonist with warm expressive eyes, modern stylish attire, distinctive natural look."
        demo_scenes = []
        for i in range(1, num_scenes + 1):
            demo_scenes.append({
                "scene_number": i,
                "narration_text": f"[{language} Narration Scene {i}]: Natural voiceover covering key message for {topic[:30]} ({target_length}s).",
                "video_prompt": f"{style.capitalize()} style, aspect ratio {aspect_ratio}. Scene {i}: {char_desc_final}. Engaging cinematic action relating to '{topic}'. Camera pans smoothly with cinematic lighting, crisp atmospheric depth. (no dialogue, no talking, cinematic ambient audio, visual storytelling)"
            })
        return {
            "title": f"{topic[:40].strip()} (Preview Script)",
            "character_desc": char_desc_final,
            "scenes": demo_scenes
        }

    client = genai.Client(api_key=key)

    # Word count guidance based on speech pacing
    # 5 sec -> ~10-14 words; 8 sec -> ~18-24 words
    word_count_guidance = (
        "Keep narration short and punchy: around 10 to 14 words per scene (must comfortably fit within 5 seconds)."
        if target_length == 5
        else "Keep narration natural: around 18 to 24 words per scene (must comfortably fit within 8 seconds)."
    )

    system_instruction = f"""
You are an expert AI video director and multilingual scriptwriter specializing in multi-scene video generation for Google Flow / Veo.

CRITICAL DIRECTIVES:
1. NARRATION TEXT:
   - Language: Must be written strictly in {language} (if {language} is Tamil, Hindi, Telugu, Malayalam, Kannada, write in that native script).
   - Style: Natural spoken flow, matching tone '{tone}'.
   - Pacing: {word_count_guidance}
   - No scene headers or speaker tags in narration text. Only the spoken voiceover sentence(s).

2. CHARACTER CONSISTENCY & AVATAR HANDLES:
   - If the user specifies an avatar handle like '@me' or '@[Name]' (e.g. '{character_desc}'):
     You MUST use that exact handle (e.g. '@me') as the subject in EVERY scene's video_prompt (e.g., '@me speaking to the camera in a modern architectural setting...'). This tells Google Flow to directly use the user's created personal avatar.
   - Otherwise, create or refine a distinct character description in English: Age, ethnicity, hairstyle/color, exact clothing, distinctive accessories.
   {f"- Incorporate user's requested character details: '{character_desc}'" if character_desc else "- If none specified, design a compelling character fitting the topic."}
   - You MUST embed this EXACT character/avatar reference into EVERY single scene's video_prompt to maintain visual character consistency across Google Flow generations.

3. VIDEO PROMPTS (Always in English):
   - Format: Style: {style}, Aspect ratio: {aspect_ratio}.
   - Content: Specific camera angle (e.g. cinematic medium shot, low angle, macro close-up, smooth tracking shot), lighting (e.g. warm golden hour, volumetric studio light), setting details, and physical action.
   - AUDIO / SPEECH INSTRUCTION: Include the dialogue and voiceover directly in the video prompt so Google Flow generates the character speech and audio along with the video: Audio & Dialogue: The character speaks in {language} saying: "<narration text>", clear natural voiceover audio with matching ambient sound.
"""

    user_prompt = f"""
Create a {num_scenes}-scene video script and visual prompts for Google Flow.

Topic / Idea: {topic}
Narration Language: {language}
Number of Scenes: {num_scenes}
Target Length per scene: {target_length} seconds
Visual Style: {style}
Tone: {tone}
Aspect Ratio: {aspect_ratio}
{f"Character Info: {character_desc}" if character_desc else ""}

Generate structured output matching the schema with:
- title
- character_desc (in English)
- scenes: list of {num_scenes} scenes, each having scene_number (1 to {num_scenes}), narration_text (in {language}), and video_prompt (in English).
"""

    models_to_try = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
    last_err = None

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ScriptResponse,
                    temperature=0.7,
                )
            )
            data = json.loads(response.text)
            logger.info(f"Successfully generated script using {model_name}.")
            return data
        except Exception as e:
            logger.warning(f"Gemini model '{model_name}' failed: {e}. Trying next available model...")
            last_err = e

    raise RuntimeError(f"Gemini API generation failed across available models: {last_err}")
