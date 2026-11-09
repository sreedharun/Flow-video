# 🎬 Flow Video Studio

A local, non-technical friendly web application that automates making multi-scene AI video clips with **Google Flow** and **Gemini**.

Instead of manually writing prompts in ChatGPT, pasting them into Google Flow, creating characters, generating scenes, and tracking files by hand, this app automates the entire prompt writing and Flow video generation process.

---

## 🚀 Quick Start (One Command)

Double-click `run.bat` or run in terminal:

```bash
run.bat
```

This starts the local web server and automatically opens your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## 🛠️ First-Time Setup Guide

### 1. Requirements
* **Windows PC**
* **Python 3.11+** installed ([python.org](https://www.python.org/downloads/)) with "Add Python to PATH" checked.

### 2. Install Dependencies & Playwright Browser
Open PowerShell or Command Prompt in this folder (`d:\Automation ADD`):

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Create your `.env` File
Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Open `.env` in Notepad and add your **Gemini API Key**:
```env
GEMINI_API_KEY=AIzaSy...your_gemini_key_here
```
*(You can get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)).*

---

## 🔐 One-Time Google Login

Google Flow requires a Google login. To keep things secure:
* **The app never asks for or stores your Google password.**
* Your login session is saved inside the local `browser_profile/` folder on your machine.

1. Open the app at `http://localhost:8000`.
2. Click **⚙️ Google Login / Settings** in the top navigation.
3. Click the big blue button: **"Open Browser to Sign In to Google"**.
4. A real Chrome window will open to `labs.google/fx/tools/flow`.
5. Sign in to your Google Account.
6. Once signed in, you can close that Chrome window. You will remain logged in for future automated runs!

---

## 🌟 How to Use

1. **Enter Your Video Idea**:
   - Fill in your topic / story.
   - Select your narration language (e.g. **Tamil, Hindi, Telugu, Malayalam, Kannada, English, or custom**).
   - Choose scene count (1 to 8), scene length (5s or 8s), style, and aspect ratio (16:9 or 9:16).
   - *(Optional)* Add a character description or reference photo.
2. **Generate Script**:
   - Click **⚡ Generate Script with Gemini**.
   - Gemini creates a title, a character profile, and each scene's narration in your chosen language plus an English visual prompt.
3. **Review & Edit**:
   - Every narration line and English video prompt is displayed in **editable text boxes**. Fix any wording before spending credits.
4. **Test or Generate**:
   - Click **🧪 Test with 1 Scene Only** to verify the character and visual style without burning credits.
   - When satisfied, click **🚀 Start All Video Generation**.
5. **View Results & Matching**:
   - In the Results page, each video clip (`scene_01.mp4`, `scene_02.mp4`...) is displayed side-by-side with its narration script.
   - Click **📦 Download All as ZIP** to download all clips + formatted `script.docx` and `script.txt` for your video editor.

---

## 📁 Output Folder Structure

Every job produces a dedicated directory under `/output/<job_id>/`:
```text
output/<job_id>/
├── scene_01.mp4
├── scene_02.mp4
├── ...
├── script.txt               # Plain text script breakdown
├── script.docx              # Styled Word document with scene table & character profile
└── <job_id>_all_files.zip   # ZIP archive containing everything
```

---

## 🧩 Architecture & Customization

* **Swappable Providers (`app/providers/`)**:
  - `MockVideoProvider`: Instant offline testing and UI development without spending credits.
  - `FlowVideoProvider`: Automates Google Flow using Playwright.
  - Ready for future official Veo / Vertex AI APIs by adding a new provider class inheriting from `BaseVideoProvider`.
* **Flow Driver (`app/flow_driver.py`)**:
  - Contains all UI selectors and interactions for Google Flow.
  - Uses resilient role-based and text-based locators.
  - Automatically captures full-page diagnostic screenshots in `/output/<job_id>/` if an error occurs.
