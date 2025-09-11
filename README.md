## Podcast Transcript Puller (AI Daily Brief)

This pulls new episodes from the Apple Podcasts show, retrieves full transcripts (Podcasting 2.0 if provided, else OpenAI Whisper), and generates three LinkedIn post drafts per episode using OpenAI.

### 1) Prerequisites
- Windows 10/11
- Python 3.10+

### 2) Setup
1. Copy `env.example` to `.env` and fill values:
   - `OPENAI_API_KEY` (required for transcription and post generation)
   - `SHOW_ID=1680633614` (AI Daily Brief)
   - Optional: `MAX_EPISODES_PER_RUN` (leave unset or set to `0` for unlimited)
2. Run setup:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

### 3) Run once (manual)
```powershell
.\.venv\Scripts\python.exe -m src.main
```

- Transcripts saved to `data/transcripts`.
- LinkedIn drafts saved to `data/posts`.

### 4) Streamlit dashboard
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run .\ui\app.py
```

Use the sidebar to trigger a pull and browse transcripts/drafts.

### 5) Schedule daily run (Windows Task Scheduler)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\schedule_task.ps1 -Hour 8
```

This registers a task that runs daily at the specified hour using the project’s virtual environment.

### Notes
- Order of transcript sources: `<podcast:transcript>` tag → OpenAI Whisper (if key).
- The state of processed episodes is tracked in `data/state.json` to avoid duplicates.
- To target a different show, update `SHOW_ID` or set `APPLE_EPISODE_URL` (the show id will be parsed from it).
- By default each run processes all new episodes; set `MAX_EPISODES_PER_RUN` to limit if desired.
