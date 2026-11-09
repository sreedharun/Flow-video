import os
import zipfile
from pathlib import Path
from typing import Dict, Any, List
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def generate_script_txt(job: Dict[str, Any], output_path: Path) -> Path:
    """Generate clean, human-readable script.txt"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"PROJECT: {job.get('title', 'Video Project')}")
    lines.append(f"Topic: {job.get('topic', '')}")
    lines.append(f"Language: {job.get('language', 'English')}")
    lines.append(f"Style: {job.get('style', '')} | Tone: {job.get('tone', '')}")
    lines.append(f"Aspect Ratio: {job.get('aspect_ratio', '16:9')} | Scene Length: {job.get('target_length', 5)}s")
    lines.append("=" * 60)
    lines.append("")
    
    if job.get("character_desc"):
        lines.append("CHARACTER DESCRIPTION:")
        lines.append(job.get("character_desc", ""))
        lines.append("-" * 60)
        lines.append("")

    scenes: List[Dict[str, Any]] = job.get("scenes", [])
    for s in scenes:
        num = s.get("scene_number", 1)
        filename = s.get("clip_filename", f"scene_{num:02d}.mp4")
        dur = s.get("target_length", job.get("target_length", 5))
        
        lines.append(f"--- SCENE {num} [{filename}] ({dur}s) ---")
        lines.append(f"NARRATION ({job.get('language', 'Audio')}):")
        lines.append(s.get("narration_text", "").strip())
        lines.append("")
        lines.append("ENGLISH VIDEO PROMPT:")
        lines.append(s.get("video_prompt", "").strip())
        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path

def generate_script_docx(job: Dict[str, Any], output_path: Path) -> Path:
    """Generate beautifully styled script.docx"""
    doc = docx.Document()
    
    # Page Margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Title
    title_p = doc.add_paragraph()
    title_run = title_p.add_run(job.get("title") or "Video Production Script")
    title_run.font.name = "Arial"
    title_run.font.size = Pt(20)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(26, 115, 232) # Google blue

    # Metadata paragraph
    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(14)
    meta_text = (
        f"Topic: {job.get('topic', '')}\n"
        f"Narration Language: {job.get('language', 'English')} | "
        f"Aspect Ratio: {job.get('aspect_ratio', '16:9')} | "
        f"Length/Scene: {job.get('target_length', 5)}s\n"
        f"Style: {job.get('style', '')} | Tone: {job.get('tone', '')}"
    )
    m_run = meta_p.add_run(meta_text)
    m_run.font.name = "Arial"
    m_run.font.size = Pt(10)
    m_run.font.color.rgb = RGBColor(100, 100, 100)

    # Character description section
    if job.get("character_desc"):
        ch_heading = doc.add_heading(level=2)
        ch_heading_run = ch_heading.add_run("Character Profile")
        ch_heading_run.font.name = "Arial"
        ch_heading_run.font.size = Pt(13)
        ch_heading_run.font.bold = True
        
        ch_p = doc.add_paragraph()
        ch_p.paragraph_format.space_after = Pt(14)
        c_run = ch_p.add_run(job.get("character_desc", ""))
        c_run.font.name = "Arial"
        c_run.font.size = Pt(10.5)
        c_run.font.italic = True

    # Scenes Section
    scenes_heading = doc.add_heading(level=2)
    s_head_run = scenes_heading.add_run("Scene Breakdown")
    s_head_run.font.name = "Arial"
    s_head_run.font.size = Pt(14)
    s_head_run.font.bold = True

    scenes: List[Dict[str, Any]] = job.get("scenes", [])
    for s in scenes:
        num = s.get("scene_number", 1)
        filename = s.get("clip_filename", f"scene_{num:02d}.mp4")
        dur = s.get("target_length", job.get("target_length", 5))

        # Scene Box / Table
        table = doc.add_table(rows=3, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        # Set column widths
        table.columns[0].width = Inches(1.8)
        table.columns[1].width = Inches(5.0)

        # Header row
        hdr_cell = table.rows[0].cells
        hdr_cell[0].merge(hdr_cell[1])
        hdr_p = hdr_cell[0].paragraphs[0]
        hdr_run = hdr_p.add_run(f"Scene {num}: {filename} ({dur} seconds)")
        hdr_run.font.name = "Arial"
        hdr_run.font.size = Pt(11)
        hdr_run.font.bold = True
        hdr_run.font.color.rgb = RGBColor(30, 30, 30)

        # Row 1: Narration
        r1 = table.rows[1].cells
        r1_label = r1[0].paragraphs[0].add_run(f"Narration ({job.get('language', 'Audio')}):")
        r1_label.font.name = "Arial"
        r1_label.font.bold = True
        r1_label.font.size = Pt(10)
        
        r1_val = r1[1].paragraphs[0].add_run(s.get("narration_text", ""))
        r1_val.font.name = "Arial"
        r1_val.font.size = Pt(10.5)

        # Row 2: English Video Prompt
        r2 = table.rows[2].cells
        r2_label = r2[0].paragraphs[0].add_run("English Video Prompt:")
        r2_label.font.name = "Arial"
        r2_label.font.bold = True
        r2_label.font.size = Pt(10)

        r2_val = r2[1].paragraphs[0].add_run(s.get("video_prompt", ""))
        r2_val.font.name = "Arial"
        r2_val.font.size = Pt(9.5)
        r2_val.font.color.rgb = RGBColor(60, 60, 60)

        # Spacing after each scene table
        sp = doc.add_paragraph()
        sp.paragraph_format.space_after = Pt(10)

    doc.save(str(output_path))
    return output_path

def create_job_zip(job_dir: Path, zip_output_path: Path) -> Path:
    """Pack all scene clips, script.txt, and script.docx into a single zip bundle."""
    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in job_dir.glob("*"):
            if file_path.is_file() and file_path.suffix != ".zip":
                zipf.write(file_path, arcname=file_path.name)
    return zip_output_path
