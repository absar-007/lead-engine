# Lead Engine

![CI](https://github.com/absar-007/lead-engine/actions/workflows/ci.yml/badge.svg)

A FastAPI service that turns messy inbound lead messages into structured, validated data using Claude, then measures its own accuracy, speed and cost with an automated eval suite.

## What it does

You send it a raw message. It returns who wrote it, how to reach them, what they want, how urgent it is, and a draft reply for a human to review.

| Input | `yo need a quote 4 roof repair, call me after 5. Dave 3105550123` |
|---|---|
| Name | Dave |
| Phone | 3105550123 |
| Email / company | none (not in the message, so left empty rather than guessed) |
| Category | sales_inquiry |
| Priority | 4 / 5 |
| Flags | needs_human (no email, so a person should confirm) |
| Suggested reply | a short, polite draft asking to confirm the call time |

It also handles spam, support requests, partnership offers, and prompt-injection attempts hidden inside a lead.

## Results

Evaluated on 54 hand-reviewed cases (clean, messy, spam, ambiguous, adversarial). 10 are held out and never inspected while tuning. Every prompt change is re-scored against the whole set.

| Prompt | Cases fully correct | What changed |
|---|---|---|
| v1 | 49/54 (91%) | Baseline. Guessed company names from email domains; flagged a message that merely *discussed* prompt injection |
| v2 | 51/54 (94%) | Fixed those two, but a new business description listed industries and made the model call dental and property leads "other" (3 regressions) |
| v3 | 53/54 (98%) | Described the business by what customers ask for instead of by industry; a polite cold pitch drifted to "partnership" |
| v4 | 54/54 (100%) | Added a rule: a company pitching its own services to us is spam; partnership means mutual collaboration |

Holdout set: 9/10 on v1, 10/10 on v2 to v4.

## Model comparison (same 54 cases, prompt v4)

| | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Fully correct | 54/54 | 54/54 |
| Cost per lead | $0.00023 | $0.00478 |
| Cost per 1,000 leads | about $0.23 | about $4.78 |
| Latency p50 / p95 | 1.7 s / 2.9 s | 2.6 s / 4.4 s |

Both models scored the same on this set, so I ship Haiku: about 20x cheaper and faster. The set is too easy to separate the models, so this shows Haiku is *enough* here, not that Sonnet adds nothing.

## Design decisions

- **Structured output, validated twice.** Claude returns JSON in a fixed schema; Pydantic then checks it. If it fails validation, the error is fed back for one retry.
- **Fails safe.** Provider errors retry with exponential backoff. If everything fails, the lead falls back to `needs_human` instead of crashing or guessing.
- **Prompt-injection defense.** The lead text is wrapped as untrusted data, the model is told never to follow instructions inside it, and suspicious messages are flagged with `injection_suspected`.
- **No duplicates.** Each lead gets a SHA-256 fingerprint of its normalized text plus source. A repeat returns the stored result with no new model call and no cost.
- **Cost protection.** A per-visitor rate limit (5 per minute, 40 per day) and a daily spend cap stop a public demo from draining the API budget.
- **Airtable sync that survives outages.** Leads are saved first, then upserted to Airtable in the background by fingerprint, so a retry never creates a second row. If Airtable is down the lead is marked `pending` and a retry endpoint syncs it later.
- **Logs without personal data.** Each request logs ids, labels and numbers only. No message text, names, emails or phone numbers.

## Run it locally

```bash
git clone https://github.com/absar-007/lead-engine.git
cd lead-engine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_key_here
```

Optional settings: `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE`, `ADMIN_KEY`, `DAILY_CAP_USD` (default 0.25), `DATABASE_URL` (default is a local SQLite file), `LEAD_MODEL` (default `claude-haiku-5-5`).

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for the sandbox page, `/docs` for the API, and `/metrics` for live system stats.

Run the tests and the eval suite:

```bash
python -m pytest -q
python -m evals.run_evals
```

The tests use a fake model and cost nothing. The eval run calls the real API (about one cent for all 54 cases).

## How far to trust the numbers

The 54 cases were drafted with AI assistance, reviewed by me, and the prompt was tuned against them, so the scores are optimistic. Real inbound messages will be messier. One expectation (a one-line message containing only an email address) was relaxed after review because the model's answer, escalating to a human, was the right behavior. More cases from real messages are the next improvement.