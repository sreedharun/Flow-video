import os
import sys
import time
import socket
import webbrowser
import threading
from pathlib import Path
from dotenv import load_dotenv

# Ensure base directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def find_available_port(host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 20) -> int:
    """Finds the first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port + max_attempts}")

def wait_and_open_browser(url: str, host: str, port: int, timeout: float = 15.0):
    """Polls until the server socket is accepting connections, then opens the browser."""
    start_time = time.time()
    opened = False
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                time.sleep(0.5)  # small buffer for FastAPI startup event
                print(f"\n[READY] Server is live at {url}")
                print(f"[READY] Opening your default browser to {url} ...\n")
                webbrowser.open(url)
                opened = True
                break
        time.sleep(0.3)
    if not opened:
        print(f"\n[WARNING] Server startup took longer than expected. Please open {url} manually in your browser.\n")

def main():
    print("=" * 60)
    print("      FLOW VIDEO STUDIO - STARTUP DIAGNOSTICS")
    print("=" * 60)

    # 1. Check Python version
    major, minor = sys.version_info.major, sys.version_info.minor
    print(f"[*] Python Version: {sys.version.split()[0]} ({sys.executable})")
    if major < 3 or (major == 3 and minor < 11):
        print(f"[ERROR] Python 3.11 or newer is required. Found {major}.{minor}.")
        sys.exit(1)

    # 2. Check and load .env
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        example_path = BASE_DIR / ".env.example"
        if example_path.exists():
            print("[*] .env file missing. Automatically creating .env from .env.example ...")
            import shutil
            shutil.copy(example_path, env_path)
        else:
            print("[!] Warning: .env file not found.")

    load_dotenv(env_path)

    # Check Gemini API Key
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        print("[!] NOTICE: GEMINI_API_KEY is not set in .env.")
        print("    (Script generation will run in offline preview template mode until an API key is added in Settings)")
    else:
        print("[*] GEMINI_API_KEY: Configured (ends with ..." + gemini_key[-4:] + ")")

    # Check Video Provider
    provider = os.getenv("VIDEO_PROVIDER", "mock").strip()
    print(f"[*] VIDEO_PROVIDER: '{provider}'")

    # 3. Port allocation
    host = os.getenv("APP_HOST", "127.0.0.1")
    requested_port = int(os.getenv("APP_PORT", "8000"))
    
    try:
        port = find_available_port(host, requested_port)
    except Exception as e:
        print(f"[ERROR] Port check failed: {e}")
        sys.exit(1)

    if port != requested_port:
        print(f"[!] Port {requested_port} was busy. Automatically switched to free port {port}.")
    else:
        print(f"[*] Port {port} is free and ready.")

    server_url = f"http://{host}:{port}"
    print(f"[*] Web App URL: {server_url}")

    # 4. Launch browser wait thread
    threading.Thread(target=wait_and_open_browser, args=(server_url, host, port), daemon=True).start()

    # 5. Start uvicorn
    import uvicorn
    print("\nStarting Flow Video Studio server... Press Ctrl+C in this terminal to stop.")
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
