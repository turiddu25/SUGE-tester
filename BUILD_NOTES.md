# SUGE Tutor — Build Notes (Phases 1–3)

Phases 1, 2, and 3 from `SPEC.md` are built and verified. Stopping here for you to test before continuing to Phase 4.

## What I built

### Project structure

```
SUGE-tester/
├── data/
│   ├── questions.json        # 68 questions (moved from project root)
│   └── suge_tutor.db         # SQLite, created on init
├── scripts/
│   └── init_db.py            # creates schema, loads seed
├── suge_tutor/
│   ├── main.py               # FastAPI app, lifespan-style startup
│   ├── config.py             # reads .env
│   ├── db.py                 # SQLite connection + query helpers
│   ├── models.py             # pydantic request models
│   ├── marking.py            # LLM client + verbatim Section 3.2 prompt + JSON parsing
│   ├── exam_selector.py      # 16-question paper assembler (topic-weighted)
│   └── routes/
│       ├── questions.py
│       ├── practice.py
│       └── exam.py
├── templates/
│   ├── base.html             # Tailwind / Alpine / HTMX / marked.js via CDN
│   ├── home.html
│   ├── questions_list.html
│   ├── practice.html
│   ├── exam_setup.html
│   ├── exam_active.html
│   └── exam_results.html
├── static/
│   ├── css/overrides.css
│   └── js/{app,practice,exam}.js
├── pyproject.toml
├── requirements.txt
├── .env.example
└── .gitignore
```

### Phase 1 — skeleton

- `GET /` — home page with question count, LLM provider/model status.
- `GET /questions` — filterable list of all 68 questions (topic, source, difficulty, priority, search). Marks-pill colour-coded by mark count; gold star badge for `priority="highest"` past-paper questions.
- SQLite auto-seeds on first run (lifespan handler).

### Phase 2 — practice mode + AI marking

- `GET /practice/{id}` — markdown-rendered question, elapsed timer, recommended-time hint (`marks × 1.75 min`), exam-technique tip, model-answer reveal, previous-attempts history.
- `POST /api/mark` — calls the LLM with the **verbatim Section 3.2 marking prompt**. Parses JSON robustly (handles fenced/dirty output via `extract_json`). Persists every attempt to `attempts` table. Returns marking inline.
- Result rendered with green checks / red crosses for points awarded vs missed, general feedback, exam-technique notes, would-pass badge.
- Errors are friendly: HTTP 401/403 → "auth" error type with clear message; malformed JSON → raw response shown plus a Retry button. Page never crashes.

### Phase 3 — exam simulation

- `GET /exam-sim` — explains the format (16 questions, 60 marks, 105 minutes) and shows the topic blueprint.
- `POST /exam-sim/start` — runs `select_exam_questions(seed)` and renders the active exam page.
- Selector verified: across 50 random seeds, **all 50 produce exactly 16 questions**, hitting topic weights within ±2 marks per topic (organisation typically 3 vs target 4 because the seed bank only has one organisation question; investment hits exactly 2). Deterministic given a seed; varies across seeds.
- Exam UI: 105-min countdown timer (turns red < 10 min), sticky header, sidebar question map (highlights answered + flagged), flag-for-review checkboxes, `beforeunload` guard so you don't lose answers, confirm-submit modal.
- `POST /api/exam/submit` — marks all 16 answers in parallel using `asyncio.gather` + `Semaphore(LLM_CONCURRENCY=4)`. Persists each attempt linked to the exam session. On finish, redirects to `/exam-sim/results/{session_id}`.
- Results page: total score / 60, percentage, per-question breakdown with sub-50% rows highlighted in rose, points-missed list, feedback.

## LLM config (verified working)

`.env` is now set up for **Moonshot pay-as-you-go with Kimi K2.6**:

```
LLM_PROVIDER=moonshot
LLM_BASE_URL=https://api.moonshot.ai/v1
LLM_API_KEY=<your existing Moonshot key>
LLM_MODEL=kimi-k2.6
LLM_TEMPERATURE=1          # K2.6 only allows 1
LLM_MAX_TOKENS=8000        # K2.6 is a reasoning model — needs headroom for thinking + output
LLM_TIMEOUT_SECONDS=180    # reasoning + marking can take ~30-60s
LLM_CONCURRENCY=4
```

**Why not Kimi Code?** Your Kimi-Code API key is whitelisted only to specific Coding Agents (Claude Code, Roo Code, Kilo Code, Kimi CLI). Hitting `api.kimi.com/coding/v1` from a custom app returns:
> "Kimi For Coding is currently only available for Coding Agents such as Kimi CLI, Claude Code, Roo Code, Kilo Code, etc."

Their docs forbid User-Agent spoofing to bypass this, so the pay-as-you-go Moonshot platform (`api.moonshot.ai/v1`) is the right route for our app.

**K2.6 quirks the marking code now handles:**
- Only accepts `temperature=1` (no low-temperature reproducibility — but we cache attempts in SQLite, so re-runs are stable).
- Returns chain-of-thought in `message.reasoning_content` separately from `message.content`. Our parser reads `content`, then falls back to `reasoning_content` if `content` is empty.
- Reasoning tokens count against `max_tokens` — keep it generous (≥4000).
- A typical marking call takes ~30–60s.

**Calibration test A (perfect answer to `study_q12`) scored 3/3 with full per-point evidence and a "would_pass_in_real_exam: true".** Tests B–E are yours to run via the UI.

## How to run

```
python -m uvicorn suge_tutor.main:app --reload
```

Then open `http://127.0.0.1:8000`. DB and seed already loaded.

## Notes on the dependency tweak

Your installed `fastapi==0.104.1` was incompatible with `starlette==1.0.0` (FastAPI passed `on_startup=` to a Router that no longer accepted it; later, `TemplateResponse(name, {"request": …})` failed with `unhashable type: dict` because Starlette 1.0 requires `TemplateResponse(request, name, ctx)`).

I:
- Upgraded FastAPI to `>=0.110` (now 0.136.1).
- Switched the startup hook from `@app.on_event("startup")` to the modern `lifespan` async-contextmanager API.
- Updated all `templates.TemplateResponse(...)` calls to the new positional `(request, name, ctx)` signature.

`requirements.txt` reflects the new minimum.

## Calibration test reminder

Once you've fixed `LLM_MODEL`, the spec wants you to run the Section 10 calibration tests against `study_q12` (Growth Multiplier, 3 marks):

- **Test A (perfect):** expect 3/3
- **Test B (right method, arithmetic error):** expect 1.5–2/3
- **Test C (concept only, no calculation):** expect 0.5–1/3
- **Test D ("I don't know."):** expect 0/3
- **Test E (verbose but irrelevant):** expect 0/3

If any score wildly wrong, that's the signal to tune the marking prompt — but per spec, don't change Section 3.2 lightly.

## Ready for Phase 4?

Phase 4 = progress dashboard (`/`, charts) + spaced-review queue (`/review` reading from `review_queue`). Phase 5 = product cards, reference page, dark mode, settings, keyboard shortcuts. Tell me when to proceed.