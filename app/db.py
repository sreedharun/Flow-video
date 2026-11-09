import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        topic TEXT NOT NULL,
        language TEXT NOT NULL,
        num_scenes INTEGER NOT NULL,
        target_length INTEGER NOT NULL,
        style TEXT NOT NULL,
        tone TEXT NOT NULL,
        aspect_ratio TEXT NOT NULL,
        flow_model TEXT DEFAULT 'omni_1.1_flash',
        character_desc TEXT,
        ref_image_path TEXT,
        title TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        current_scene INTEGER DEFAULT 0,
        error_message TEXT,
        output_dir TEXT,
        zip_path TEXT
    );
    """)

    # Ensure flow_model, flow_project_url, and resolution columns exist
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN flow_model TEXT DEFAULT 'omni_1.1_flash';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN flow_project_url TEXT;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN resolution TEXT DEFAULT '360p';")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        scene_number INTEGER NOT NULL,
        narration_text TEXT NOT NULL,
        video_prompt TEXT NOT NULL,
        target_length INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        clip_filename TEXT,
        clip_path TEXT,
        retries INTEGER DEFAULT 0,
        error_message TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'INFO',
        message TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

def create_job(job_data: Dict[str, Any]) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (
            id, created_at, topic, language, num_scenes, target_length,
            style, tone, aspect_ratio, flow_model, flow_project_url, character_desc, ref_image_path,
            title, status, output_dir
        ) VALUES (
            :id, :created_at, :topic, :language, :num_scenes, :target_length,
            :style, :tone, :aspect_ratio, :flow_model, :flow_project_url, :character_desc, :ref_image_path,
            :title, :status, :output_dir
        )
    """, job_data)
    conn.commit()
    conn.close()
    return job_data["id"]

def update_job_status(job_id: str, status: str, error_message: Optional[str] = None, zip_path: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE jobs
        SET status = ?, error_message = coalesce(?, error_message), zip_path = coalesce(?, zip_path)
        WHERE id = ?
    """, (status, error_message, zip_path, job_id))
    conn.commit()
    conn.close()

def update_job_current_scene(job_id: str, current_scene: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET current_scene = ? WHERE id = ?", (current_scene, job_id))
    conn.commit()
    conn.close()

def save_scenes(job_id: str, scenes: List[Dict[str, Any]]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scenes WHERE job_id = ?", (job_id,))
    for s in scenes:
        cursor.execute("""
            INSERT INTO scenes (
                job_id, scene_number, narration_text, video_prompt,
                target_length, status, clip_filename, clip_path, retries
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            s["scene_number"],
            s["narration_text"],
            s["video_prompt"],
            s.get("target_length", 5),
            s.get("status", "queued"),
            s.get("clip_filename", f"scene_{s['scene_number']:02d}.mp4"),
            s.get("clip_path", None),
            s.get("retries", 0)
        ))
    conn.commit()
    conn.close()

def update_scene_status(job_id: str, scene_number: int, status: str, clip_path: Optional[str] = None, error_message: Optional[str] = None, retries: Optional[int] = None):
    conn = get_connection()
    cursor = conn.cursor()
    updates = ["status = ?"]
    params = [status]
    if clip_path is not None:
        updates.append("clip_path = ?")
        params.append(clip_path)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    if retries is not None:
        updates.append("retries = ?")
        params.append(retries)
    params.extend([job_id, scene_number])

    cursor.execute(f"UPDATE scenes SET {', '.join(updates)} WHERE job_id = ? AND scene_number = ?", tuple(params))
    conn.commit()
    conn.close()

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    job = dict(row)
    cursor.execute("SELECT * FROM scenes WHERE job_id = ? ORDER BY scene_number ASC", (job_id,))
    job["scenes"] = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return job

def get_all_jobs() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    jobs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jobs

def add_log(job_id: str, message: str, level: str = "INFO"):
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO logs (job_id, timestamp, level, message)
        VALUES (?, ?, ?, ?)
    """, (job_id, timestamp, level, message))
    conn.commit()
    conn.close()

def get_logs(job_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs WHERE job_id = ? ORDER BY id ASC LIMIT ?", (job_id, limit))
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs
