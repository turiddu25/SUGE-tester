"""Static product cards for the four confirmed exam products.

Mark Logan flagged these in the revision lecture and said he'd remind students
again before the exam. Each card is a SUGE-framework analysis: CGM type,
network effects, activation, NaP, compounding, common exam angles.
"""

from __future__ import annotations

PRODUCTS: dict[str, dict] = {
    "chatgpt": {
        "id": "chatgpt",
        "name": "ChatGPT",
        "tagline": "AI assistant — generative LLM as core product.",
        "summary": (
            "Conversational AI built on GPT models. Acquired ~100M users in 2 months "
            "(Nov 2022 – Jan 2023), the fastest consumer-product growth ever. The growth "
            "story is a case study in viral organic CGMs colliding with a genuinely novel "
            "core utility."
        ),
        "cgm": (
            "**Direct organic CGM** — early word-of-mouth was overwhelmingly the growth "
            "engine. Each conversation that surprised a user was a referral event. There's "
            "also an **indirect content CGM** today via screenshots circulating on X/Reddit "
            "(company-amplified at first, user-generated now)."
        ),
        "network_effects": (
            "Limited classical network effects (other users don't make the product better "
            "for me). Instead, **data network effects via RLHF** — more usage → more "
            "preference data → better model — are the moat. Mark Logan's framing: this is "
            "a *learning loop*, not a network effect, but it compounds similarly."
        ),
        "activation": (
            "Activation moment: the first response that produces a *useful* answer for the "
            "user's actual job (writing, code, planning). Activation inequality is brutal — "
            "non-activated users churn within a week; activated users hit ~80%+ monthly "
            "retention."
        ),
        "nap": (
            "There is no obvious 'natural' NaP metric. ChatGPT's retention story is closer "
            "to *workflow embedding* — the user incorporates it into a recurring task "
            "(daily writing, weekly planning). Suggested NaP framings: '3 useful "
            "responses per week' (3r7), or sessions per workday."
        ),
        "compounding": (
            "Compounding comes from (a) RLHF data flywheel improving the model, (b) "
            "company-generated content (OpenAI demos, model release announcements), and "
            "(c) user-generated content (screenshots, prompt libraries, custom GPTs)."
        ),
        "exam_angles": [
            "If asked about CGMs, distinguish **direct organic** (word-of-mouth) from the **content indirect CGM** (screenshots).",
            "If asked about retention, lean on **activation inequality** and the workflow-embedding angle, not classical network effects.",
            "If asked about competitive moat, name the **RLHF / data flywheel** explicitly — Logan accepts this as a learning loop with compounding properties.",
            "Watch for two-part questions: 'why did ChatGPT grow so fast' AND 'why has growth slowed' — the second part is the easier one to forget (linear-marketing saturation, alternative products like Claude/Gemini).",
        ],
    },
    "snapchat": {
        "id": "snapchat",
        "name": "Snapchat",
        "tagline": "Social messaging — ephemeral content as core currency.",
        "summary": (
            "Photo / video messaging app whose core innovation was disappearing messages. "
            "Built atomic networks among small friend groups (high-school cohorts) before "
            "expanding outward — a textbook NaP / atomic-network growth pattern."
        ),
        "cgm": (
            "**Direct organic CGM** — to use Snapchat usefully you needed your friends on "
            "it, so users actively recruited their friend group. Also a **direct invitation "
            "CGM** via 'add friends' contact sync. **Streaks** are an in-product retention "
            "mechanic that doubles as viral pull (a friend won't break a streak alone)."
        ),
        "network_effects": (
            "Strong **direct social network effect** within a friend group. Crucially, the "
            "network is *sparse globally but dense locally* — exactly the atomic-network "
            "pattern. Snapchat let small friend groups have value on day one, regardless of "
            "global penetration."
        ),
        "activation": (
            "Activation = sending a snap that gets a snap back. Mark Logan's social-media "
            "rule of thumb: ~60% retention floor for *activated* users; non-activated users "
            "churn within days. Key metric: time-to-first-reciprocal-snap."
        ),
        "nap": (
            "Plausible NaP framings: 'send a snap to 2 friends per day' (2s1) — daily-active "
            "is the right cadence for a messaging product. Streaks formalise this: a 100-day "
            "streak is a 100-day NaP commitment device."
        ),
        "compounding": (
            "Compounding via (a) **organic CGM** (recruit friends), (b) **content indirect "
            "CGM** (Stories produces ambient awareness for non-active users), (c) Discover / "
            "publisher content (company- and partner-generated)."
        ),
        "exam_angles": [
            "If asked why Snapchat succeeded where (e.g.) Threads or Google+ didn't — the answer is **atomic networks**: Snapchat let small groups have value first. Threads/Google+ were sparse-global from day one.",
            "If asked about engagement mechanics, name **streaks** and explain them as a CGM-flavoured retention loop, not just a gimmick.",
            "If a calculation question gives Snapchat numbers, expect to compute either GM = 1/(1-V) for a referral V, or LTV via ad ARPU × retention.",
            "Mark Logan flags Snapchat as a case study in *social-media activation inequality* — be ready to apply that 60% retention floor.",
        ],
    },
    "medium": {
        "id": "medium",
        "name": "Medium",
        "tagline": "Long-form publishing — content marketplace.",
        "summary": (
            "Two-sided content marketplace: writers and readers. Started with curated, "
            "company-generated content, then transitioned to user-generated content as the "
            "writer base grew. Classic example of the CG → UG transition Mark Logan asks "
            "about in past papers."
        ),
        "cgm": (
            "**Indirect content CGM** — articles are the content, and great articles bring "
            "new readers via search and social shares. **Initially company-generated** "
            "(Ev Williams' team commissioned the early articles); **transitioned to "
            "user-generated** as the writer flywheel began producing high-quality work at "
            "scale."
        ),
        "network_effects": (
            "Soft two-sided network effect: more writers → more readers → more writers. "
            "Less explosive than Snapchat-style direct network effects because reader value "
            "doesn't depend on knowing the writers personally."
        ),
        "activation": (
            "Two activation moments. **Reader activation**: reading an article that hits "
            "long enough to come back for another. **Writer activation**: publishing a piece "
            "that gets meaningful engagement (claps / responses). Writer activation is the "
            "harder, more valuable one."
        ),
        "nap": (
            "Reader NaP: '~2 articles per week' (2a7). Writer NaP: '1 published piece per "
            "month' (1p30). Note that the two sides have different cadences — the product "
            "holds both."
        ),
        "compounding": (
            "Compounding via (a) **content indirect CGM** at higher-than-transaction "
            "frequency (company- then user-generated), (b) SEO loop (more articles → more "
            "indexed pages → more search traffic), (c) writer payouts attracting more writers."
        ),
        "exam_angles": [
            "**Two-part question warning** (this is the canonical Logan example): Why might a content CGM operate above transaction frequency? Why later transition CG → UG? Both answers required.",
            "Above transaction frequency = awareness/retention reminder between transactions; you can't make people read more often, but you can keep reminding them you exist.",
            "CG → UG transition = scalability: staff/LLM resources cap CG output, but a large writer base can produce content at unbounded scale.",
            "Watch for asks about the **trust/quality risk** of UG transition — UG content quality is variable, requires moderation/curation (Medium's editor-curated 'staff picks').",
        ],
    },
    "food_delivery": {
        "id": "food_delivery",
        "name": "Food Delivery (Deliveroo / Uber Eats / Meituan)",
        "tagline": "Three-sided marketplace — diners, restaurants, riders.",
        "summary": (
            "Three-sided platform connecting diners, restaurants, and delivery riders. "
            "Geographically constrained network effects — what matters is liquidity in your "
            "city, not globally. A canonical NaP example with explicit transactional cadence."
        ),
        "cgm": (
            "**Direct invitation CGM** (refer-a-friend codes — both classic). **Indirect "
            "linear marketing** is a huge spend (TV, Google, social ads) — the test is "
            "whether organic compounding is meaningfully present at all, or if growth is "
            "almost entirely paid acquisition. Mark Logan flags this as one of the harder "
            "CGM-vs-linear-marketing distinctions."
        ),
        "network_effects": (
            "**Three-sided, geographically local.** More diners → more restaurants want to "
            "list → more selection → more diners. More riders → faster delivery → more "
            "diners. The atomic network is **the city**: London diners don't benefit from "
            "Tokyo restaurant supply."
        ),
        "activation": (
            "Activation = first successful order delivered hot, on time, correctly. "
            "Activation inequality here is fierce because the first failure (cold food, "
            "missing items, late) is unrecoverable for many users. Operations is the "
            "activation function."
        ),
        "nap": (
            "Logan's lecture explicitly cites Deliveroo's NaP: **'4 orders every 28 days' "
            "(4o28)**. This is a rare case where the company has publicly stated its NaP. "
            "Memorise this number for the exam."
        ),
        "compounding": (
            "Compounding via (a) local liquidity flywheel (diners ↔ restaurants ↔ riders), "
            "(b) **invitation CGM** with referral credit, (c) restaurant-side data network "
            "effect (better demand forecasting), (d) habit formation around the NaP cadence."
        ),
        "exam_angles": [
            "**Memorise 4o28** (Deliveroo's stated NaP). If a question asks for an example NaP, this is the safest one.",
            "If asked about whether food delivery has a CGM at all, argue carefully: invitation CGM exists but is weak; the real growth driver is linear marketing + local liquidity. Acknowledge both honestly.",
            "Three-sided market questions: explain the **chicken-and-egg** problem and how Deliveroo solved it — usually by paying riders an hourly minimum during launch (rider supply first), then onboarding restaurants city by city.",
            "Logan's atomic-network point: launching city-by-city is exactly the atomic-network pattern. National advertising before cities are dense is sparse-network growth and burns money.",
            "If a calculation, expect CAC / LTV / payback period for a single market.",
        ],
    },
}


def list_products() -> list[dict]:
    return list(PRODUCTS.values())


def get_product(pid: str) -> dict | None:
    return PRODUCTS.get(pid)
