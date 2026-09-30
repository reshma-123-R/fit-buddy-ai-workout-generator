# 💪 FitBuddy - AI Fitness Plan Generator (Gemini)

FastAPI web app that creates a personalised 7-day workout plan (Gemini Pro), adds a nutrition tip (Gemini Flash),
lets the user send feedback to revise the plan, and stores everything in SQLite.

## Quick start (VS Code)

1. Install **Python 3.10+** (Windows: tick "Add Python to PATH") and VS Code with the **Python** extension.
2. `File > Open Folder...` -> select this `fitbuddy` folder. Open a terminal: `` Ctrl+` ``.
3. Create and activate a virtual environment:

   | OS | Commands |
   |---|---|
   | Windows (PowerShell) | `python -m venv .venv` then `.venv\Scripts\Activate.ps1` |
   | Mac / Linux | `python3 -m venv .venv && source .venv/bin/activate` |

   Windows blocked the script? Run `Set-ExecutionPolicy -Scope Process Bypass`, then activate again.
   When VS Code asks to use the new environment, click **Yes** (or `Ctrl+Shift+P` > *Python: Select Interpreter* > `.venv`).
4. Install dependencies: `pip install -r requirements.txt`
5. Add your Gemini key: get a free one at <https://aistudio.google.com/apikey>, copy `.env.example` to `.env`,
   and replace `your_api_key_here` with the key (no quotes).
6. Run: `uvicorn app.main:app --reload` (or press **F5** and choose *FitBuddy (FastAPI + reload)*).
7. Open <http://127.0.0.1:8000>.

| URL | What it is |
|---|---|
| `/` | Input form |
| `/view-all-users` | Admin table of all users and plans (no login - keep the app local) |
| `/docs` | Interactive API docs (try the JSON endpoints here) |
| `/health` | Health check |

## Try it

**Web:** fill in the form -> *Generate Plan* (10-60 s) -> read the plan and tip -> send feedback (use the same User ID) -> see the updated plan.

**API (curl):**
```bash
curl -X POST http://127.0.0.1:8000/generate-workout/gemini -H "Content-Type: application/json" \
     -d '{"goal":"weight loss","intensity":"Medium"}'

curl "http://127.0.0.1:8000/nutrition-tip?goal=muscle%20gain"

curl -X POST http://127.0.0.1:8000/generate-plan -H "Content-Type: application/json" \
     -d '{"user_id":1,"username":"Asha","age":22,"weight":55,"goal":"muscle gain","intensity":"High"}'

curl -X POST http://127.0.0.1:8000/update-plan/1 -H "Content-Type: application/json" \
     -d '{"feedback":"Add more core exercises and make day 3 easier"}'
```
(On Windows PowerShell use `curl.exe`, or just use `/docs`.)

## Tests
```bash
pytest
```
The 26 tests use a fake Gemini and a temporary database: no API key, no internet, no cost.

## Configuration (`.env`)
| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | - (required) | Your Google AI Studio key |
| `GEMINI_PRO_MODEL` | `gemini-3.1-pro-preview` | 7-day plans and feedback revisions |
| `GEMINI_FLASH_MODEL` | `gemini-3.8-flash` | Nutrition tips, and automatic fallback if the Pro model fails |
| `GEMINI_TIMEOUT_SECONDS` | `90` | Per-request timeout |
| `DATABASE_URL` | `sqlite:///fitbuddy.db` | Database location |

Gemini model names change (1.5 and 2.0 are already retired). If you see *"model ... was not found"*, look up current names at
<https://ai.google.dev/gemini-api/docs/models> and set them in `.env`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "GEMINI_API_KEY is not set" | Create `.env` from `.env.example`, paste the key, restart the server |
| "Gemini rejected the API key" / HTTP 403 | Regenerate the key in AI Studio; check the model is available in your region |
| "model ... not found" | Update `GEMINI_PRO_MODEL` / `GEMINI_FLASH_MODEL` in `.env` |
| "rate limit or quota reached" | Wait a minute, or check quota/billing in AI Studio |
| `ModuleNotFoundError` | The virtual environment isn't active - activate it and rerun `pip install -r requirements.txt` |
| Port 8000 in use | `uvicorn app.main:app --reload --port 8001` |
| Background looks plain | Put any photo at `app/static/images/gym-bg.jpg` (a placeholder is included) |

## Project layout
```
app/main.py                   FastAPI app, static files, startup (creates DB tables)
app/routes.py                 JSON APIs + HTML pages
app/database.py               SQLAlchemy models (users, plans) + data helpers
app/schemas.py                Pydantic validation
app/gemini_client.py          Single Gemini wrapper: errors, timeout, Pro->Flash fallback
app/gemini_generator.py       Gemini Pro: 7-day plan prompt
app/gemini_flash_generator.py Gemini Flash: nutrition tip
app/updated_plan.py           Feedback-based plan revision
app/nutrition.py              Tip + offline fallback tips
app/templates/, app/static/   Jinja2 pages, CSS, background image
tests/                        pytest suite
```

Not medical advice: the generated plans come from an AI model. Check with a doctor before starting a new routine.
