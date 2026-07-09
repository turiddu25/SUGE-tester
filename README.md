# SUGE Tutor — Spec Sheet Bundle

This bundle contains everything you need to feed into Claude Code to build your local
revision app for COMPSCI4087 Startup Growth Engineering.

## What's in this bundle

| File | What it is | What to do with it |
|---|---|---|
| `SPEC.md` | The full specification — architecture, prompts, schema, features, file layout, acceptance criteria | Drop this into your Claude Code project and say *"build the app described in SPEC.md, using questions.json as the seed data"* |
| `questions.json` | 68 fully-tagged starter questions across all four sources (8 past paper examples, 10 further sample, 24 sample, 26 study notes practice). Each question includes model answer, marking-scheme notes, topic, marks, difficulty, and exam-technique hints. | Place in `data/questions.json` of the new project. The init script will load it into SQLite. |
| `README.md` | This file | Read first. |

## How to use it

1. Open Claude Code in an empty directory.
2. Drop `SPEC.md` and `questions.json` into the directory.
3. Tell Claude Code:
   > Build the app described in SPEC.md. Use questions.json as the seed data for the question bank. Start with Phase 1 (skeleton) and Phase 2 (practice mode) — that gets me a working app I can use today. Then do Phase 3 (exam mode). Phases 4 and 5 are optional polish.

4. Once you have Phase 1+2+3 working, get a Moonshot API key from `platform.moonshot.ai`, drop it in `.env`, and start practising.

## Why this design (the short version)

- **AI marking is the whole point.** The exam marks fuzzily ("1 mark for any of these"). A regex script can't do that. The carefully calibrated marking prompt in §3.2 of `SPEC.md` is the heart of the app — Claude Code must use it verbatim.
- **The question bank is pre-built.** I already extracted, tagged, and weighted 68 questions covering every source you have. You don't have to do that yourself, and Claude Code doesn't have to either.
- **Past paper questions get priority.** The 8 questions Mark Logan worked through in the revision lecture are tagged `priority: highest` — these are your actual exam-style questions and should appear most in exam mode.
- **Topic weighting matches the real exam.** Activation/Retention 37%, Compounding Growth 28%, Acquisition 25%, Organisation 7%, Investment 3% — the exam-mode selector hits this distribution.
- **Provider-agnostic LLM.** Kimi/Moonshot is the default but the same code works with OpenAI, Anthropic, or local Ollama by changing one config variable. If your "Kimi subscription" turns out to be the consumer chat product (no API), you can swap providers without rewriting code.
- **No build step.** Python + SQLite + HTML/Tailwind/AlpineJS via CDN. `pip install` and run.

## Vercel deployment notes

This repo includes a minimal Vercel entrypoint in `api/index.py` and routes all
requests to the FastAPI app via `vercel.json`.

On Vercel, environment variables must be configured in the Vercel dashboard; the
app intentionally does not load the local `.env` file when `VERCEL` is set.

The current SQLite database is only a bootstrapping fallback on Vercel. It is
created under the platform temp directory, so user attempts, exam sessions, and
review state should be treated as ephemeral until the app is moved to hosted
Postgres/Supabase.

## The "must-not-lose" details

- Exam: **105 minutes (90 + 15 buffer), 60 marks, 16 questions, 1–8 marks each, mostly written, ONE multiple choice, no negative marking, no calculator**.
- Confirmed exam products: **ChatGPT, Snapchat, Medium, Food Delivery (Deliveroo / Uber Eats / Meituan)**.
- Mark Logan's verbatim advice for the highest payoff: *"do the past paper questions more than once"*. The app's spaced-review feature operationalises this.

Good luck.
