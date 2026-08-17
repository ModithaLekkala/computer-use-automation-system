# Computer-Use Automation System

Implementation of the interface.ai take-home assignment: an LLM discovers how to complete a task in a real UI, the successful run is compiled into a typed reusable capability, and later invocations replay that capability deterministically with no model in the decision loop.

The included target is a local legacy-style banking application used only with synthetic data.

## What is implemented

- Real LLM-driven discovery using Gemini (with mock/OpenAI planner seams also available)
- Observe → decide → act browser loop
- Typed/versioned Pydantic capability artifact
- Discovery-time value canonicalization (`10042` → `{{member_id}}`)
- Deterministic Playwright replay with no LLM
- Stable ordered locator candidates and fill verification
- Typed outputs and final checkpoint
- `MEMBER_NOT_FOUND` as a business outcome rather than a crash
- One bounded recoverable runtime condition (`Temporary Service Delay` → `Retry`)
- Same-session human handoff: automation pauses, a human operates the already-open Chromium session, then signals resume
- Origin/action guardrails during both discovery and replay
- Redacted structured JSONL evidence and failure screenshots
- Minimal capability catalog API
- Automated tests

## Repository layout

```text
src/
  agent/            LLM discovery loop and planners
  capabilities/     schema, compiler and artifact storage
  replay/           deterministic execution/result contract
  surfaces/         surface abstraction + Playwright implementation
  policy/           allowlists, risk checks and redaction
  escalation/       intervention state model + embedded operator console
  observability/    JSONL logs and screenshots
  api/              optional agent-facing capability catalog

demo_app/            local LegacyBank proxy target
artifacts/           saved reusable capability
evidence/            discovery/replay/failure/recovery/handoff evidence
tests/               focused unit tests
REPORT.md            design write-up
```

## Setup

Python 3.11+ is recommended.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
playwright install chromium
Copy-Item .env.example .env
```

Put a Gemini API key in your local `.env`:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
```

Do not commit `.env`.

## Start the target app

Terminal 1:

```powershell
python -m demo_app.app
```

Open `http://127.0.0.1:8000`.

Synthetic demo members:

| Member ID | Behavior |
|---|---|
| `10042` | Normal discovery record; savings `4281.52` |
| `10043` | Normal replay record; savings `930.17` |
| `99999` | `MEMBER_NOT_FOUND` business outcome |
| `10044` | Manual-review / human-handoff demo |
| `10045` | One transient load, then bounded retry succeeds |

## Genuine LLM discovery

Terminal 2:

```powershell
python -m src.cli discover --goal "Look up member 10042 and read their current savings balance" --target http://127.0.0.1:8000 --planner gemini --artifact artifacts/lookup_member_balance.json
```

The model operates the live browser. A successful run is compiled into a capability whose input is parameterized as `{{member_id}}` and whose output is `savings_balance`.

## Deterministic replay

Replay the Gemini-discovered artifact with a different input:

```powershell
python -m src.cli replay --artifact artifacts/lookup_member_balance.json --input member_id=10043
```

Expected output includes:

```json
{
  "status": "success",
  "outputs": {
    "savings_balance": "930.17"
  }
}
```

Business outcome:

```powershell
python -m src.cli replay --artifact artifacts/lookup_member_balance.json --input member_id=99999
```

Expected:

```json
{
  "status": "business_outcome",
  "code": "MEMBER_NOT_FOUND"
}
```

## Recoverable runtime condition

Reset the demo server if needed, then run:

```powershell
python -m src.cli recovery-demo --artifact artifacts/lookup_member_balance.json
```

Member `10045` returns `Temporary Service Delay` once. Replay detects the known condition, logs `recoverable_condition`, clicks `Retry` exactly once, and continues without an LLM.

Evidence is written to:

```text
evidence/recovery/
```

## Same-session human handoff

Run:

```powershell
python -m src.cli handoff-demo --artifact artifacts/lookup_member_balance.json
```

The browser reaches `Manual Review Required` and **remains open**.

Then:

1. Open `http://127.0.0.1:8001`.
2. Click **Take Control** for the active run.
3. In the same already-open Chromium window, click **Continue After Review**.
4. Return to the operator page and click **Resume**.
5. Replay continues and extracts the balance.

Evidence is written to:

```text
evidence/handoff/
```

This deliberately uses a minimal local operator surface rather than building a full remote co-browsing product.

## Tests

```powershell
pytest -q
```

## Safety

- Entry/current origins are validated against an explicit allowlist.
- Discovery actions are constrained before execution.
- Replay actions are validated against the capability policy.
- Risk classes distinguish read-only, reversible and irreversible capabilities.
- Logs redact secret-bearing keys and common sensitive patterns.
- `.env` and credentials are excluded from the repository.
- The demo contains synthetic data only.

## Evidence

The repository includes the evidence structure and existing genuine discovery/replay evidence. Before final submission, run the current build once for each important path so the latest evidence reflects the final code:

```text
evidence/discovery/
evidence/replay/
evidence/recovery/
evidence/handoff/
```

## Design

See [`REPORT.md`](REPORT.md) for architecture, schema, determinism/error handling, heterogeneity/multi-tenant design, escalation, safety and deliberate cuts.
