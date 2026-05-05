# SUGE Tutor — Specification Sheet

**Project:** Self-paced revision web app for COMPSCI4087 Startup Growth Engineering (H), University of Glasgow.
**Goal:** A locally hosted web app where the user practises exam-style questions and receives partial-credit AI marking calibrated to the actual exam's marking style.
**Target user:** One person — the developer themself, sitting the exam in May 2026. Single-user, local, no auth, no deployment.

---

## 1. Why this app exists (read this first)

The user has lectures, study notes, sample questions, further sample questions, past paper worked examples, and a revision-lecture transcript. The exam (60 marks, 16 questions, 105 minutes, mostly written answers) marks **fuzzily** — model answers say things like *"1 mark for any of these"* and *"or similar answer scores too"*. **You cannot mark this with regex.** Hence: AI marking via the user's chosen LLM (default Kimi/Moonshot, but design must be provider-agnostic).

Mark Logan (the lecturer) repeatedly says in the revision lecture:
- "Past paper questions and sample questions make all the difference between not doing very well and doing very well."
- "Activate your knowledge — don't just read. Question yourself."
- "Re-do questions a few days later — small, regular, repeated revision."
- "Pay attention to marks per question. Don't write 12 lines for a 2-mark question."
- "Two-part questions: students often answer only one part."

The app must operationalise these insights — not just "show question, take answer".

---

## 2. Tech stack (recommended)

These choices optimise for: **zero-friction local hosting, no build step, single-process, easy for one developer to maintain.**

- **Backend:** Python 3.11+ with **FastAPI** + **uvicorn**. SQLite for persistence (single file, zero setup).
- **Frontend:** Single-page-ish app with **HTML + Tailwind (via CDN) + Alpine.js (via CDN) + HTMX (via CDN)**. No build step. No npm. Just static files served by FastAPI.
  - Rationale: AlpineJS handles small reactive bits (timer, form state). HTMX handles partial page swaps for question navigation. Tailwind gives a clean look without writing CSS. The user can change a single HTML file without restarting anything.
- **LLM client:** `httpx` (async) calling an OpenAI-compatible chat completions endpoint. Provider-agnostic — Kimi/Moonshot is the default but the user can swap to OpenAI, Anthropic (via OpenAI-compatible endpoints), or local Ollama by changing config.
- **Markdown rendering in browser:** `marked.js` via CDN (model answers contain formatting and equations).
- **Charts (for progress page):** `Chart.js` via CDN.

**Reject these alternatives** unless the user requests them: React/Next.js (build step overhead), Django (overkill), Streamlit/Gradio (poor UX for timed exam mode), Electron (no desktop wrapper needed).

---

## 3. The KIMI / LLM marking mechanism (the hardest part — get this right)

### 3.1 API config

The Moonshot/Kimi API is OpenAI-compatible:
- Base URL: `https://api.moonshot.ai/v1`
- Auth: `Authorization: Bearer $MOONSHOT_API_KEY`
- Model: `kimi-k2-0905-preview` or whichever is current at build time. Make this a config variable.

**IMPORTANT:** The user said they have a "Kimi subscription". This is ambiguous between (a) consumer chat subscription (no API access) and (b) Moonshot platform credits (has API access). **The app must not assume.** On first run, if the API call fails with a credentials error, surface a clear setup screen explaining the user needs an API key from `platform.moonshot.ai` (or a different provider).

Provide a `.env.example` file with:
```
LLM_PROVIDER=moonshot           # moonshot | openai | anthropic | ollama | custom
LLM_BASE_URL=https://api.moonshot.ai/v1
LLM_API_KEY=sk-...
LLM_MODEL=kimi-k2-0905-preview
LLM_TEMPERATURE=0.2             # low — we want consistent marking
LLM_MAX_TOKENS=2000
```

### 3.2 The marking prompt (use this verbatim — calibrated to the marking style)

```text
You are an experienced examiner for the COMPSCI4087 Startup Growth Engineering course at
the University of Glasgow, taught by Professor Mark Logan. You are marking a student's
exam-style answer. The marking style is FAIR and PARTIAL-CREDIT — Mark Logan repeatedly
says "I'm trying to give you marks if I possibly can". You should mirror this.

QUESTION (worth {marks} marks):
{question_text}

MODEL ANSWER / MARKING SCHEME:
{model_answer}

ADDITIONAL MARKING NOTES:
{marking_scheme_notes}

STUDENT'S ANSWER:
{student_answer}

MARKING PRINCIPLES (apply all of these):

1. PARTIAL CREDIT IS THE DEFAULT. Identify each mark-worthy point in the model answer.
   For each point, check whether the student covered it — verbatim, paraphrased, or via
   genuinely equivalent content. Award marks per point, accumulating to the total.

2. "OR SIMILAR" IS GENEROUS. The marking scheme often allows alternative correct answers.
   If the student's reasoning is sound and reaches a valid conclusion, award the mark
   even if their wording differs from the model.

3. CALCULATIONS GET METHOD MARKS. For numerical questions, marks are awarded for:
   (a) correct setup / extracting the right numbers,
   (b) correct intermediate calculations (CAC, LTV, etc.),
   (c) correct final answer,
   (d) correct conclusion/commentary.
   If the student makes an arithmetic error early but then continues correctly with
   their wrong number, award method marks downstream — Mark Logan: "if you've gone wrong
   right at the start, but you did the rest correctly, I'll still give you marks".

4. TWO-PART QUESTIONS. If the question has two distinct parts, mark each independently.
   Note explicitly if the student answered only one part — this is the most common error
   Mark Logan flags in the revision lecture.

5. DO NOT REWARD WAFFLE. Do not give marks for vague generalities, irrelevant content,
   or restating the question. Marks are for substantive points that match the scheme.

6. DO NOT PUNISH BREVITY. A 2-mark question with two correct sentences is full marks.
   The student does not need to write more than the marks justify.

7. KEYWORDS CAN BE PARAPHRASED. Concepts like "Conway's Law", "Activation Inequality",
   "atomic network", "decision intensity" etc. should ideally be named — but if the
   student describes the concept correctly without naming it, award most of the mark
   (e.g. 0.5 of 1) and note the missing terminology.

8. HALF MARKS ARE ALLOWED. If a point is partially made or partially correct, 0.5 is fine.

OUTPUT FORMAT (return ONLY a JSON object — no other text, no markdown fences):

{
  "marks_awarded": <number, decimals allowed>,
  "marks_total": {marks},
  "percentage": <0-100>,
  "points_awarded": [
    {
      "point": "<the mark-worthy point from the scheme>",
      "marks": <number>,
      "evidence": "<short quote or paraphrase of where the student demonstrated this>"
    }
  ],
  "points_missed": [
    {
      "point": "<mark-worthy point not covered>",
      "marks_lost": <number>,
      "why": "<short explanation of what was missing or wrong>"
    }
  ],
  "general_feedback": "<2-4 sentences. What was strong, what to improve, what to remember next time. Conversational and constructive.>",
  "exam_technique_notes": "<optional — only include if relevant. E.g. 'You wrote 200 words for a 1-mark question — practise concision' or 'You answered the first sub-question well but missed the second part entirely.' Empty string if no notes.>",
  "would_pass_in_real_exam": <true | false>
}

Begin marking now. Return JSON only.
```

### 3.3 Marking call implementation notes

- Use a **system message** containing the prompt template above, then a **user message** containing the filled-in payload. This usually works better than a single huge user message.
- Set temperature low (0.2) for reproducibility. Cache identical (question_id, student_answer_hash) requests for 1 hour to avoid double-charging on accidental re-submissions.
- If the LLM returns malformed JSON (it sometimes will), fall back gracefully: show the raw response, the score the LLM mentions, and a "regenerate marking" button. Do not crash the page.
- Show a streaming spinner while waiting (Kimi can take 5-15s for marking).
- Log every marking response to the SQLite DB (`attempts` table) — never lose marking history.

---

## 4. Data model

### 4.1 Question bank

Provided as **`questions.json`** (alongside this spec — 68 starter questions, fully tagged). The schema:

```json
{
  "id": "string (unique)",
  "source": "past_paper_examples | further_sample_questions | sample_questions | study_notes_practice",
  "source_label": "human-readable source",
  "priority": "highest | high | medium | low",
  "topic": "activation_retention | compounding_growth | acquisition | organisation | investment",
  "subtopic": "string",
  "difficulty": "easy | medium | hard",
  "marks": "integer",
  "question_text": "string (markdown allowed)",
  "question_type": "explanation | calculation_with_commentary | scenario_application | chart_analysis | growth_model_inventory | comparison | concept_identification | etc.",
  "model_answer": "string (markdown allowed)",
  "marking_scheme_notes": "string — extra guidance for the marker",
  "products_mentioned": ["array of product names"],
  "related_concepts": ["array of concept tags"],
  "is_calculation": "boolean",
  "exam_technique_notes": "string (optional)"
}
```

**Treat `questions.json` as seed data** — load it into SQLite on first run. Allow the user to add new questions later via either a JSON file drop or a simple `/admin/add-question` page (markdown textarea; not exposed in main nav).

### 4.2 SQLite schema

```sql
CREATE TABLE questions (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_label TEXT,
  priority TEXT,
  topic TEXT NOT NULL,
  subtopic TEXT,
  difficulty TEXT,
  marks INTEGER NOT NULL,
  question_text TEXT NOT NULL,
  question_type TEXT,
  model_answer TEXT,
  marking_scheme_notes TEXT,
  products_mentioned TEXT,        -- JSON array as text
  related_concepts TEXT,          -- JSON array as text
  is_calculation INTEGER,
  exam_technique_notes TEXT
);

CREATE TABLE attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL,
  student_answer TEXT NOT NULL,
  marks_awarded REAL,
  marks_total INTEGER,
  marking_response_json TEXT,     -- full LLM response
  attempted_at TEXT NOT NULL,     -- ISO datetime
  duration_seconds INTEGER,
  exam_session_id INTEGER,        -- nullable, links to exam_sessions
  flagged_for_review INTEGER DEFAULT 0,
  FOREIGN KEY (question_id) REFERENCES questions(id)
);

CREATE TABLE exam_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,             -- 'exam_simulation' | 'topic_drill' | 'free_practice' | 'spaced_review'
  started_at TEXT NOT NULL,
  finished_at TEXT,
  total_marks_awarded REAL,
  total_marks_possible INTEGER,
  config_json TEXT                -- e.g. {"topic": "compounding_growth", "n_questions": 8}
);

CREATE TABLE review_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL,
  next_review_at TEXT NOT NULL,   -- ISO datetime
  ease_level INTEGER DEFAULT 0,   -- spaced repetition difficulty
  FOREIGN KEY (question_id) REFERENCES questions(id),
  UNIQUE(question_id)
);

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
```

---

## 5. Features (MVP must-have, then nice-to-have)

### 5.1 MVP (build these first)

**M1. Question Bank Browser** — `/questions`
- Filterable by topic, source, difficulty, priority, marks.
- Search by free text.
- Each row: id, marks, topic, source label, "Practise" button.
- Show small badge for `priority="highest"` (past paper examples) — these are the gold standard.

**M2. Practice Mode** — `/practice/{question_id}`
- Display question text (rendered markdown), marks badge, source.
- Large textarea for student answer.
- Optional collapsed sections: "Show model answer" (hidden until submission), "Show marking scheme" (hidden), "Show exam technique notes" (visible by default — these are useful before answering).
- Timer that starts on page load (purely informational — no enforced limit). Display elapsed time; recommended time = `marks * 1.75` minutes (105 / 60 ≈ 1.75 min/mark).
- "Submit for marking" button → calls LLM → shows marking result inline.
- After marking: show points awarded, points missed, general feedback, exam technique notes (if any). User can click "Try again" or "Next question".
- Three buttons after marking: "Got it — easy" / "Needs review" / "Hard — review soon". These feed into the spaced-repetition queue.

**M3. Exam Simulation Mode** — `/exam-sim`
- Start screen: explain the exam format (16 questions, 60 marks, 105 minutes), confirm to start.
- Selects 16 questions weighted to match real exam distribution:
  - 22 marks of activation_retention questions
  - 17 marks of compounding_growth
  - 15 marks of acquisition
  - 4 marks of organisation
  - 2 marks of investment
  - Prefer `priority="highest"` and `priority="high"` questions where possible. Fall back to medium.
  - Include a mix of calculation and explanation questions.
  - The selector should be deterministic given a seed, so the user can either redo the same paper or generate a new one.
- 105-minute count-down timer (visible at top of screen).
- All 16 questions on a scrollable single page (Moodle-style). Each has a textarea, a flag-for-review checkbox, and a marks badge.
- "Submit exam" button at the bottom. Confirmation modal: "Submit and mark all? This will use ~16 LLM calls."
- After submission: marking happens for all 16 in parallel (asyncio.gather). Show progress ("Marking 7 of 16…").
- Results page: total score / 60, percentage, per-question breakdown, highlight any below 50% for review, button to add weak questions to review queue.

**M4. AI Marking** — `/api/mark` POST endpoint
- Body: `{ question_id, student_answer, exam_session_id? }`
- Returns the LLM's JSON response.
- Records an `attempts` row.
- Handles LLM errors gracefully (timeout, malformed JSON, auth error).

**M5. Settings** — `/settings`
- LLM provider, base URL, API key, model name. Test connection button.
- Marking strictness (passes a flag to the prompt — e.g. "be slightly stricter than usual").
- Reset/export DB.

### 5.2 Nice-to-have (build if MVP is solid)

**N1. Topic Drill** — `/drill/{topic}` — Guided practice on one topic. Picks ~6 questions weighted by difficulty progression (easy → medium → hard).

**N2. Spaced Review** — `/review` — Reads from `review_queue`. Implements simple spaced repetition: questions you flagged "Needs review" reappear after 2 days; "Hard" after 1 day; "Got it" after 7 days. Each successful review extends the interval (×2). Mark Logan explicitly recommends this in the revision lecture.

**N3. Progress Dashboard** — `/` (home page)
- Today's stats, total questions answered, average score by topic, weakest topic.
- Chart (Chart.js): rolling average score over time per topic.
- "Recommended next" — picks 3 questions from review queue + 1 new question from weakest topic.

**N4. Product Cards** — `/products`
- One page each for ChatGPT, Snapchat, Medium, Food Delivery (the four confirmed exam products).
- Pre-filled with the relevant network effects, CGMs, retention metrics, exam angles (data source: Chapter 13 of the study notes — already extracted; embed as static markdown).

**N5. Reference / Cheat Sheet** — `/reference`
- Searchable view of the comprehensive study notes (the "PDF" — actually a JSON-of-pages with text extracted).
- Key formulas card always visible: CAC, LTV, Growth Multiplier `GM = 1/(1-V)`, NaP structure.
- Hot-keyed: Press `?` from anywhere to open a quick reference modal.

**N6. Mark Calibration** — When the user clicks "I disagree with this marking", let them edit the marks_awarded and add a note. This is logged. After 10+ disagreements, a `/calibration` page can show patterns (e.g. "the LLM seems too lenient on calculation questions").

### 5.3 Explicitly OUT of scope

- Multi-user / auth / accounts.
- Cloud deployment.
- Mobile-first design (single-user desktop is fine).
- Generating new questions with AI (the existing 68 are calibrated; LLM-generated ones would not match the actual exam style).
- OCR of handwritten answers.
- Voice input.

---

## 6. UI/UX guidance

### 6.1 Visual design

- Clean, academic, high-contrast. Default to a light theme. Add a dark theme toggle.
- Tailwind palette: neutral greys + a single accent (suggest `indigo-600`).
- Generous whitespace. Question text in a serif (`font-serif`); UI in `font-sans`.
- Marks badges: prominent, e.g. `[3 marks]` in a coloured pill at top-right of question cards. Colour-code by marks: 1-2 = green, 3-4 = blue, 5+ = orange.
- Source-priority badges next to questions: `★ Past Paper` (gold), `Further Sample` (purple), `Sample` (grey), `Study Notes` (light grey).

### 6.2 Practice Mode layout

```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to Questions   |   Question 14 of 68   |  Settings   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [3 marks] [★ Past Paper] [Compounding Growth · CGM]        │
│                                                              │
│  Explain why a company might operate a content-based        │
│  indirect CGM using company-generated content at a higher   │
│  frequency than the product's transaction frequency. Why    │
│  might the company later decide to attempt to transition    │
│  the CGM to user-generated content?                         │
│                                                              │
│  💡 Exam technique tip: Two-part question. Common student   │
│  error: answering only one part.                            │
│                                                              │
│  ⏱ Recommended time: ~5 min   |   Elapsed: 0:42             │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Type your answer here...                            │   │
│  │                                                      │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  [ Submit for marking ]   [ Skip — see model answer ]       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

After submission, the result expands BELOW the answer — do not navigate away. Show:
- Big score: `2.5 / 3` with percentage.
- Green checkmarks for points awarded; red crosses for points missed; each with a one-line explanation.
- General feedback paragraph.
- "Review later" / "Got it" / "Hard" buttons.
- "Show model answer" reveal — let the user compare their answer to the canonical.

### 6.3 Exam mode layout

Mimic the Moodle exam UI loosely (a grid of 16 questions in a sidebar, click to scroll to that question; flag checkbox per question; big timer at top). The familiarity helps under exam stress.

---

## 7. File structure

```
suge-tutor/
├── README.md
├── SPEC.md                        ← this file
├── .env.example
├── .gitignore
├── pyproject.toml                 ← uv / pip-installable
├── data/
│   ├── questions.json             ← seed question bank (68 questions; provided)
│   └── study_notes_pages.json     ← parsed study notes for /reference (build script)
├── scripts/
│   ├── init_db.py                 ← creates SQLite, loads questions
│   └── extract_study_notes.py     ← (optional) extracts pages from the source PDF/zip
├── suge_tutor/
│   ├── __init__.py
│   ├── main.py                    ← FastAPI app entry
│   ├── config.py                  ← reads .env
│   ├── db.py                      ← SQLite connection + query helpers
│   ├── models.py                  ← pydantic models for questions, attempts, etc.
│   ├── marking.py                 ← LLM client + prompt template + JSON parsing
│   ├── exam_selector.py           ← logic to assemble a 16-question exam paper
│   ├── spaced_repetition.py       ← review queue logic
│   └── routes/
│       ├── questions.py
│       ├── practice.py
│       ├── exam.py
│       ├── progress.py
│       └── settings.py
├── static/
│   ├── css/
│   │   └── overrides.css          ← small Tailwind overrides
│   ├── js/
│   │   ├── app.js                 ← shared utilities
│   │   ├── practice.js            ← Alpine component for practice mode
│   │   └── exam.js                ← Alpine component for exam mode
│   └── img/
└── templates/
    ├── base.html                  ← layout, nav, Tailwind/Alpine/HTMX CDNs
    ├── home.html
    ├── questions_list.html
    ├── practice.html
    ├── exam_setup.html
    ├── exam_active.html
    ├── exam_results.html
    ├── progress.html
    ├── reference.html
    ├── products/
    │   ├── chatgpt.html
    │   ├── snapchat.html
    │   ├── medium.html
    │   └── food_delivery.html
    └── settings.html
```

---

## 8. Implementation phases

### Phase 1 — Skeleton (target: ~30 min for an experienced dev)
- FastAPI app starts, serves a "Hello SUGE" page.
- SQLite created on first run.
- `questions.json` loaded into DB on init.
- `/questions` page lists all 68 questions with topic/marks badges.

### Phase 2 — Practice Mode (~1 hour)
- `/practice/{id}` page renders question, accepts answer.
- `/api/mark` calls LLM, returns marking JSON.
- Marking result rendered nicely on the page.
- Attempts persisted.

### Phase 3 — Exam Simulation (~1 hour)
- Exam selector logic that hits the topic-marks budget.
- Exam UI with timer, flagging, sidebar nav.
- Parallel marking on submit; results page.

### Phase 4 — Progress & Spaced Review (~1 hour)
- Progress dashboard with charts.
- Review queue page with spaced-repetition logic.

### Phase 5 — Polish (~1 hour)
- Product pages (ChatGPT, Snapchat, Medium, Food Delivery).
- Reference page (study notes search).
- Dark mode.
- Keyboard shortcuts.
- Settings page with API key input + connection test.

**Total: ~5 hours of focused dev time** for a complete app. Phase 1+2 alone delivers core value.

---

## 9. Acceptance criteria (the "done" checklist)

The app is "done" when:

1. **Local-first.** `python -m uvicorn suge_tutor.main:app --reload` starts the app. No Docker, no cloud, no other dependencies beyond Python and a working LLM API key.
2. **Question bank loaded.** `/questions` shows all 68 questions, filterable.
3. **Practice mode works.** User can pick any question, type an answer, get a sensible AI-marked response with partial credit and specific feedback.
4. **AI marking is calibrated.** When the user gives the model answer verbatim, they should score full marks. When they give an empty answer, they should score 0. When they give a half-correct answer, they should score roughly half.
5. **Exam mode works.** User can run a full 16-question exam under a 105-minute timer, submit, and see total score with per-question breakdown.
6. **Spaced review works.** Questions flagged "Hard" return after 1 day; "Needs review" after 2 days; "Got it" after 7 days.
7. **Provider-agnostic.** Swapping `LLM_BASE_URL` and `LLM_API_KEY` to point at OpenAI or Anthropic (via OpenAI-compatible endpoints) or local Ollama works without code changes.
8. **Errors are friendly.** Bad API key → settings page redirect with clear message. LLM returns malformed JSON → "Marking failed; here's the raw response — click to retry."
9. **Persistence survives restarts.** Attempts, settings, review queue all in SQLite — quitting and restarting loses nothing.
10. **No build step.** No `npm install`, no webpack, no bundler. Just `pip install` and run.

---

## 10. Calibration test cases (use these to verify marking quality)

Before declaring done, run these manually against `study_q12` (Growth Multiplier calculation, 3 marks):

**Test A — Perfect answer:**
> "GM = 1/(1-V). With V=0.52, GM = 1/0.48 = 2.08. With V=0.58, GM = 1/0.42 = 2.38. The improvement of 0.06 in V produces a 0.30 increase in GM, demonstrating compounding amplification."
> **Expect:** 3/3.

**Test B — Right method, arithmetic error:**
> "GM = 1/(1-V). V=0.52 gives 1/0.48 = 2.5 (wrong, should be 2.08). V=0.58 gives 1/0.42 = 2.5. Big improvement."
> **Expect:** 1.5-2/3 — method marks awarded, arithmetic penalised once.

**Test C — Conceptual but no calculation:**
> "Higher V means a much bigger growth multiplier because of compounding. Small changes in V produce big changes in GM."
> **Expect:** 0.5-1/3 — concept partly there but no numerical answer.

**Test D — Empty / nonsense:**
> "I don't know."
> **Expect:** 0/3.

**Test E — Verbose but irrelevant:**
> "Growth is very important for startups. They should focus on retention and CGMs to build a strong product."
> **Expect:** 0/3 — no engagement with the question.

If any of these scores wildly wrong, tune the prompt (Section 3.2) — usually adding more examples in the prompt fixes it.

---

## 11. Crucial details lifted from the source material (DO NOT lose these)

**The exam itself (verified from the revision-lecture transcript):**
- Date: ~mid-May 2026 (confirmed in revision lecture for May 15 prep crib sheet — exact date TBC).
- 90 + 15 minutes (the +15 is buffer for technical issues). Use 105 in the timer.
- 16 questions, 60 marks. Marks range 1–8 per question.
- Mostly written. Exactly ONE multiple choice. No negative marking.
- No calculator. Simple arithmetic only.
- Pen and paper allowed for working (last year's policy; not yet confirmed for this year).

**Confirmed exam products:**
- ChatGPT
- Snapchat
- Medium
- Food Delivery (Deliveroo / Uber Eats / Meituan — pick the one you know best)

(Mark Logan said he will repeat these a few days before the exam. The app's `/products` pages should link to a "study these in detail" prompt.)

**Topic weighting (from the comprehensive study notes — this is the exam blueprint):**
| Topic | Marks | % | Priority |
| --- | --- | --- | --- |
| Activation & Retention | 22 | 37% | HIGHEST |
| Compounding Growth | 17 | 28% | HIGH |
| Acquisition | 15 | 25% | MEDIUM |
| Organisation | 4 | 7% | LOW |
| Investment | 2 | 3% | LOW |

The exam selector must hit these weights ±2 marks per topic.

**Score range last 2 years (per the revision lecture):**
- 2025: high 83%, low 14%.
- 2024: high 91%, low 7%.
> Mark Logan: "the difference is past papers and just making sure you're comfortable with those things."

**Question-style quirks Mark Logan flagged in the revision lecture:**
1. **"Explain" requires reasoning.** "Describe" just describe. Two different question verbs.
2. **Two-part questions are sneaky.** Students answer only one part. The marking prompt explicitly checks both.
3. **Marks count = points expected.** 3 marks ≈ 3 points. Don't over-write 1-mark questions.
4. **Words in questions are clues.** If it says "social media product", the expected behaviour is social-media-specific (e.g. ~60% activated retention floor).
5. **"Pay attention to how many marks every question's worth"** — surface this prominently in the UI.
6. **Show working on calculations** — even if wrong, partial credit comes from the chain of logic.
7. **Find an easy question first** in exam mode to settle nerves — the exam UI should let students jump around freely.

---

## 12. Concrete answers to obvious follow-up questions

> **Q: What if the user doesn't have a Moonshot/Kimi API key?**
> A: The settings page accepts any OpenAI-compatible endpoint. They can use Anthropic Claude (via the official Claude API — needs a small adapter), OpenAI directly, Together AI, Groq, or local Ollama. Ship with `LLM_PROVIDER=moonshot` as default but document fallbacks in README.

> **Q: Should the app support importing custom questions?**
> A: Yes — drop a JSON file matching the schema into `data/` and re-init the DB. Don't build a fancy admin UI for MVP.

> **Q: What about questions with charts/images (e.g. cohort retention charts)?**
> A: For MVP, keep these as text descriptions of the chart (as in `past_revision_q6` and `further_q7` in the seed data). Later, optionally embed inline SVG charts. The marking prompt is text-only; charts are never sent to the LLM.

> **Q: Should the app store the user's API key?**
> A: In the SQLite settings table, in plain text. This is a single-user local app — encryption is theatre. Add it to `.gitignore` along with `.env` and `*.db`.

> **Q: Should the marking call use streaming?**
> A: Optional. Streaming improves perceived speed but complicates JSON parsing. For MVP, do non-streaming with a 30s timeout and a spinner. If marking feels slow, switch to streaming and parse JSON at end-of-stream.

> **Q: How should the app handle the user revising the same question multiple times?**
> A: Each attempt is a new row in `attempts`. The Question detail page should show a small history sparkline ("you've answered this 3 times: 1.5/3, 2.5/3, 3/3"). The "Last attempt" score is what feeds the progress dashboard.

> **Q: What if Kimi/Moonshot is slow or rate-limited during exam mode (16 calls in parallel)?**
> A: Implement a small client-side rate limiter — concurrent=4, with retries on 429. If a single call fails, mark that question with score=null and let the user manually retry. Don't fail the whole exam.

> **Q: Where do calculation questions get their math checked?**
> A: The LLM does it (Kimi K2 is strong at arithmetic for these simple values). Do not try to write a custom calculator parser. The marking prompt explicitly tells the LLM to award method marks even if the final number is wrong.

---

## 13. README essentials (for the final shipped app)

The generated README must include:
1. One-paragraph description.
2. Quick start: `cp .env.example .env`, edit, `pip install -r requirements.txt`, `python scripts/init_db.py`, `uvicorn suge_tutor.main:app --reload`, open `localhost:8000`.
3. Where to get a Moonshot API key (`platform.moonshot.ai`) and how to swap providers.
4. How to add custom questions.
5. The exam blueprint (topic weights table) so the user remembers what to focus on.
6. Mark Logan's revision tips, summarised: do past papers more than once, revise actively, small-and-regular beats big-and-rare.

---

## 14. Final note to the implementer (Claude Code)

Build the MVP first (Phase 1 + Phase 2 + Phase 3). That delivers ~80% of the user's value: practising questions with AI marking, plus full exam simulation. Phases 4 and 5 are upside.

When in doubt about UI choices: **academic, restrained, fast**. This is a tool for someone trying to study under deadline pressure. Every animation longer than 200ms, every confirmation modal that doesn't need to be there, every form field that requires extra clicks — these all get in the way of revision. The user has weeks until the exam, not days; they will use this app daily; small UX wins compound.

The marking prompt (Section 3.2) is the single most important part of the app. If you change anything in this spec, do **not** change that prompt without running the calibration tests in Section 10. Mark Logan's marking style — generous on equivalent answers, strict on missing keywords, partial credit on calculations — is fully encoded there.

Good luck — and tell the user to do the past papers.
