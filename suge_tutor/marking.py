from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from . import db
from .config import config
from . import users

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

9. EQUIVALENT PATHS ARE EQUIVALENT. If the student's calculation path is mathematically
   equivalent to the model's — for example, scaling a salary down to a 6-month window
   first vs. annualising the customer count and then dividing — both yield the same
   per-customer cost. Do NOT penalise the alternative path. Only the final number and
   the conclusion need to match. If you suspect the student's setup is wrong, before
   marking it down, do the algebra to check whether their path simplifies to the model's.

10. ARITHMETIC SLIPS AT THE END LOSE ONE MARK, NOT THE WHOLE CHAIN. If the student's
    setup, formula, intermediate steps, and reasoning are correct but they make a single
    arithmetic / decimal-point error at the FINAL step (e.g. computing 10000/1500 ≈ 65
    instead of 6.67), award full method marks for the chain and only deduct the final-
    answer mark — plus, at most, one additional mark for any conclusion that flips
    because of the wrong number. Do NOT cascade the deduction into earlier method marks.
    Mark Logan: "if you've gone wrong right at the start, but you did the rest correctly,
    I'll still give you marks" — this principle applies symmetrically to errors at the
    END of an otherwise-correct chain.

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


class LLMQuotaError(LLMError):
    pass


def _llm_runtime(user_id: str | None) -> dict[str, Any]:
    runtime = {
        "provider": config.LLM_PROVIDER,
        "base_url": config.LLM_BASE_URL,
        "api_key": config.LLM_API_KEY,
        "model": config.LLM_MODEL,
        "using_own_key": False,
    }
    if not user_id:
        return runtime
    settings = db.ensure_user_settings(user_id)
    own_key = users.decrypt_secret(settings.get("encrypted_llm_api_key"))
    if settings.get("use_own_key") and own_key:
        runtime.update(
            {
                "provider": settings.get("llm_provider") or runtime["provider"],
                "base_url": settings.get("llm_base_url") or runtime["base_url"],
                "api_key": own_key,
                "model": settings.get("llm_model") or runtime["model"],
                "using_own_key": True,
            }
        )
        return runtime
    used = db.app_key_call_count(user_id)
    if used >= config.APP_KEY_FREE_CALL_LIMIT:
        raise LLMQuotaError(
            f"You have used {config.APP_KEY_FREE_CALL_LIMIT} AI marking attempts on the shared app key. Add your own API key in Settings to continue."
        )
    return runtime


async def call_llm(prompt: str, *, user_id: str | None = None) -> str:
    runtime = _llm_runtime(user_id)
    api_key = runtime["api_key"]
    model = runtime["model"]
    if not api_key:
        raise LLMAuthError("No LLM_API_KEY configured. Set it in .env or via /settings.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": model,
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
    if "k2.6" in model.lower():
        body["thinking"] = {"type": "disabled"}
        body["temperature"] = 0.6
    url = runtime["base_url"].rstrip("/") + "/chat/completions"
    timeout = httpx.Timeout(config.LLM_TIMEOUT_SECONDS, connect=15.0)
    t_start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LLMError(f"Network error calling LLM: {exc}") from exc
    latency_ms = int((time.monotonic() - t_start) * 1000)

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

    # Log token usage for cost tracking. Best-effort — never block marking on a
    # logging failure (e.g. transient DB lock).
    try:
        usage = data.get("usage") or {}
        cached_tokens = int(
            (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        )
        db.log_llm_call(
            user_id=user_id,
            attempt_id=None,
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            cached_tokens=cached_tokens,
            used_own_key=bool(runtime["using_own_key"]),
            latency_ms=latency_ms,
            called_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        pass

    return content


async def mark_answer(question: dict, student_answer: str, *, user_id: str | None = None) -> dict[str, Any]:
    """Returns a dict with marking fields plus 'raw_response' and optional 'error'."""
    prompt = build_prompt(question, student_answer)
    try:
        raw = await call_llm(prompt, user_id=user_id)
    except LLMAuthError as exc:
        return {"error": "auth", "message": str(exc), "raw_response": ""}
    except LLMQuotaError as exc:
        return {"error": "quota", "message": str(exc), "raw_response": ""}
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


# Module-level TTL cache so we don't hit Moonshot's billing endpoint on every
# page render. Refresh every 60 seconds — balance changes slowly and we already
# have an exact local figure for spend.
_balance_cache: dict[str, Any] = {"value": None, "fetched_at": 0.0}
_BALANCE_TTL_SECONDS = 60.0


async def fetch_balance() -> dict[str, Any]:
    """Fetch the remaining USD balance from Moonshot's official endpoint:
        GET /v1/users/me/balance
    Returns {available_balance, voucher_balance, cash_balance} in USD, or
    {error, message} if the call failed. Cached 60s to avoid spamming the API."""
    now = time.monotonic()
    if (
        _balance_cache["value"] is not None
        and (now - _balance_cache["fetched_at"]) < _BALANCE_TTL_SECONDS
    ):
        return _balance_cache["value"]
    if not config.LLM_API_KEY:
        return {"error": "no_api_key"}
    url = config.LLM_BASE_URL.rstrip("/") + "/users/me/balance"
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            return {"error": "http", "status": resp.status_code, "message": resp.text[:200]}
        body = resp.json()
        data = (body.get("data") or {}) if body.get("status") else {}
        result = {
            "available_balance": float(data.get("available_balance") or 0),
            "voucher_balance": float(data.get("voucher_balance") or 0),
            "cash_balance": float(data.get("cash_balance") or 0),
            "available_gbp": float(data.get("available_balance") or 0) * config.USD_TO_GBP,
        }
        _balance_cache["value"] = result
        _balance_cache["fetched_at"] = now
        return result
    except httpx.HTTPError as exc:
        return {"error": "network", "message": str(exc)}
