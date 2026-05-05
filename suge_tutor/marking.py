from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import config

SYSTEM_PROMPT_TEMPLATE = """You are an experienced examiner for the COMPSCI4087 Startup Growth Engineering course at
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

{{
  "marks_awarded": <number, decimals allowed>,
  "marks_total": {marks},
  "percentage": <0-100>,
  "points_awarded": [
    {{
      "point": "<the mark-worthy point from the scheme>",
      "marks": <number>,
      "evidence": "<short quote or paraphrase of where the student demonstrated this>"
    }}
  ],
  "points_missed": [
    {{
      "point": "<mark-worthy point not covered>",
      "marks_lost": <number>,
      "why": "<short explanation of what was missing or wrong>"
    }}
  ],
  "general_feedback": "<2-4 sentences. What was strong, what to improve, what to remember next time. Conversational and constructive.>",
  "exam_technique_notes": "<optional — only include if relevant. E.g. 'You wrote 200 words for a 1-mark question — practise concision' or 'You answered the first sub-question well but missed the second part entirely.' Empty string if no notes.>",
  "would_pass_in_real_exam": <true | false>
}}

Begin marking now. Return JSON only."""


def build_prompt(question: dict, student_answer: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        marks=question.get("marks", 0),
        question_text=question.get("question_text", ""),
        model_answer=question.get("model_answer") or "(no model answer provided)",
        marking_scheme_notes=question.get("marking_scheme_notes") or "(no extra notes)",
        student_answer=student_answer.strip() or "(empty answer)",
    )


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    candidates: list[str] = []
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


async def call_llm(prompt: str) -> str:
    if not config.LLM_API_KEY:
        raise LLMAuthError("No LLM_API_KEY configured. Set it in .env or via /settings.")

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": config.LLM_MODEL,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict but fair examiner. Return only the requested JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    # Kimi K2.6 enables chain-of-thought by default. We don't need the reasoning,
    # we want the JSON answer fast — switch it off when supported.
    # K2.6 also enforces temperature=0.6 when thinking is disabled (and 1.0 when enabled).
    if "k2.6" in config.LLM_MODEL.lower():
        body["thinking"] = {"type": "disabled"}
        body["temperature"] = 0.6
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    timeout = httpx.Timeout(config.LLM_TIMEOUT_SECONDS, connect=15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LLMError(f"Network error calling LLM: {exc}") from exc

    if resp.status_code in (401, 403):
        raise LLMAuthError(
            f"LLM auth failed ({resp.status_code}). Check LLM_API_KEY / LLM_BASE_URL."
        )
    if resp.status_code >= 400:
        raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {data}") from exc
    content = msg.get("content") or ""
    # Reasoning models (e.g. kimi-k2.6) emit thinking in `reasoning_content`.
    # If the visible `content` is empty, fall back to it so JSON extraction has something to chew on.
    if not content.strip():
        content = msg.get("reasoning_content") or ""
    return content


async def mark_answer(question: dict, student_answer: str) -> dict[str, Any]:
    """Returns a dict with marking fields plus 'raw_response' and optional 'error'."""
    prompt = build_prompt(question, student_answer)
    try:
        raw = await call_llm(prompt)
    except LLMAuthError as exc:
        return {"error": "auth", "message": str(exc), "raw_response": ""}
    except LLMError as exc:
        return {"error": "llm", "message": str(exc), "raw_response": ""}

    parsed = extract_json(raw)
    if parsed is None:
        return {
            "error": "malformed_json",
            "message": "LLM did not return parseable JSON.",
            "raw_response": raw,
        }

    parsed.setdefault("marks_total", question.get("marks"))
    awarded = parsed.get("marks_awarded")
    total = parsed.get("marks_total") or question.get("marks") or 0
    if awarded is not None and total:
        try:
            parsed.setdefault("percentage", round(100.0 * float(awarded) / float(total), 1))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    parsed["raw_response"] = raw
    return parsed


async def test_connection() -> dict[str, Any]:
    try:
        raw = await call_llm('Reply with the JSON: {"ok": true}.')
    except LLMAuthError as exc:
        return {"ok": False, "error": "auth", "message": str(exc)}
    except LLMError as exc:
        return {"ok": False, "error": "llm", "message": str(exc)}
    return {"ok": True, "sample": raw[:200]}
