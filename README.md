# Computer-Use Automation System

A focused implementation of the interface.ai take-home assignment:

**The model discovers. The artifact becomes a reusable capability. Deterministic replay is the production path.**

This repo demonstrates a real browser target, an LLM discovery seam, a typed/versioned capability artifact, deterministic replay without an LLM in the decision loop, explicit business outcomes/failures, policy guardrails, evidence capture, and a minimal human-handoff mechanism.

## Architecture

```text
Natural-language goal
        |
        v
Discovery Agent ---> Planner (LLM or local mock)
        |
        v
SurfaceAdapter ---> Playwright ---> LegacyBank demo UI
        |
        v
Capability artifact (.json)
        |
        v
Deterministic Replay Engine
        |
        +--> success + typed outputs
        +--> business outcome
        +--> recoverable/hard failure
        +--> human escalation seam
```

## Repository layout

```text
src/
  agent/            discovery loop + planners
  capabilities/     Pydantic schema + compiler + storage
  replay/           deterministic executor + result contract
  surfaces/         surface abstraction + Playwright implementation
  policy/           allowlist/risk/redaction
  escalation/       control ownership and operator console
  observability/    JSONL evidence and screenshots
  api/              optional capability catalog API

demo_app/            intentionally legacy-looking target UI
artifacts/           example saved capability
evidence/            run logs/screenshots generated locally
tests/               schema/policy/redaction/unit tests
REPORT.md            required seven-heading design write-up
```

## Setup

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
Copy-Item .env.example .env
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS/Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
```

## Run the LegacyBank demo target

Terminal 1:

```bash
python -m demo_app.app
```

Open `http://127.0.0.1:8000`.

Demo members:

| Member ID | Name | Savings |
|---|---|---:|
| 10042 | Avery Stone | 4281.52 |
| 10043 | Jordan Lee | 930.17 |

## Deterministic replay

Terminal 2:

```bash
python -m src.cli replay --artifact artifacts/lookup_member_balance.json --input member_id=10042
```

Expected category: `success`.

Business outcome example:

```bash
python -m src.cli replay --artifact artifacts/lookup_member_balance.json --input member_id=99999
```

Expected category: `business_outcome`, code `MEMBER_NOT_FOUND`.

## Discovery run

For a local run without a paid model:

```bash
python -m src.cli discover --goal "Look up member 10042 and read their current savings balance" --target http://127.0.0.1:8000 --planner mock --artifact artifacts/lookup_member_balance.json
```

For the **final assignment submission**, configure your own API key in `.env` and perform at least one genuine LLM-driven discovery:

```bash
python -m src.cli discover --goal "Look up member 10042 and read their current savings balance" --target http://127.0.0.1:8000 --planner openai --artifact artifacts/lookup_member_balance.json
```

The assignment explicitly requires evidence that a genuine model-driven discovery happened, so do not submit only the mock run.

## Evidence

Runs create JSONL logs and failure screenshots under:

```text
evidence/discovery/
evidence/replay/
evidence/failure/
```

Regenerate these on your machine before submission so they truthfully represent your own runs and environment.

## Human handoff

Start the minimal operator console:

```bash
python -m src.escalation.operator_app
```

Open `http://127.0.0.1:8001`.

The control model is explicit: `AUTOMATION -> PAUSED_FOR_HUMAN -> HUMAN_CONTROL -> RESUMING -> AUTOMATION`.
The operator UI is deliberately minimal; the control-transfer state model is the important seam.

## Optional capability catalog stretch goal

```bash
python -m src.api.app
```

Then use:

```text
GET  /capabilities
POST /capabilities/{name}/run
```

## Tests

```bash
pytest -q
```

## Important before submitting

This is a strong starter repository, but you should not blindly submit a generated take-home. Run it, inspect it, make at least a few decisions/changes yourself, generate real evidence, and be able to defend every architectural choice in `REPORT.md`.
