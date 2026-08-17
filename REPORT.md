# Design Report

## 1. Architecture

The system deliberately separates probabilistic discovery from deterministic production execution.

During discovery, `DiscoveryAgent` observes the current UI through the `SurfaceAdapter`, asks an LLM planner for exactly one structured action, applies policy checks, executes the action against the live UI, records evidence, and repeats until the goal is complete or a stopping condition is reached. The submitted implementation supports Gemini for the required genuine LLM run, plus mock/OpenAI planner seams for local development.

`PlaywrightSurface` is the concrete surface adapter. It exposes observation, navigation, targeting, clicking, filling, extraction, checkpoints, and screenshots while hiding Playwright-specific mechanics from the capability/replay layer. This provides the seam needed to support other UI surfaces later.

A successful discovery is passed through `compile_member_lookup`. Compilation is intentionally separate from the raw model transcript: it turns discovery-time concrete behavior into a reusable contract. For example, the concrete member ID used during discovery is canonicalized into `{{member_id}}`, and an observed balance value is replaced with a stable field locator.

`ReplayEngine` is the production path. It accepts a saved artifact and invocation inputs, applies guardrails, binds parameters, executes stored steps in order, handles known runtime states, verifies the final checkpoint, and returns typed outputs. No LLM is invoked during replay.

The architecture is intentionally local/single-process for the take-home. The important boundaries—planner, surface, artifact, policy, replay, evidence, and control transfer—are explicit without adding queues or distributed infrastructure that do not improve the core demonstration.

## 2. Artifact schema

The capability is a versioned Pydantic model serialized as JSON. It contains:

- schema and capability versions
- capability identity and description
- application identity and entry URL
- allowlisted origins
- typed inputs
- typed outputs
- ordered actions
- locator candidates for targeted controls
- a success checkpoint
- declared business outcomes
- risk/action policy metadata
- provenance metadata

A `CapabilityStep` stores an explicit operation (`goto`, `click`, `fill`, `extract`, or `wait`), a human-readable purpose, its target, any bound value, optional output name, and timeout.

Targets contain ordered locator candidates. Replay tries only the candidates recorded in the artifact and never asks a model to improvise a locator. For the demonstrated flow, the member field prefers its semantic label, the Search control prefers role/name, and CSS is retained only as a fallback. The savings output is located by the field itself rather than the balance value observed during discovery.

The demonstrated capability accepts `member_id: string` and returns `savings_balance: string`. Discovery is performed with member `10042`, while deterministic replay with member `10043` returns `930.17`, demonstrating that the artifact is parameterized rather than tied to the discovery-time record.

The artifact is deliberately decoupled from JSONL model evidence. Evidence remains useful for auditing how the capability was learned, while production replay depends only on the reviewed capability contract.

## 3. Determinism & error handling

Replay never invokes an LLM for decisions. Parameter references are bound from the invocation inputs, action order is fixed, locator priority is fixed, waits are bounded, and the final checkpoint must be satisfied.

The result contract separates:

1. `success` — checkpoint satisfied and declared outputs returned.
2. `business_outcome` — an expected domain result such as `MEMBER_NOT_FOUND`.
3. `recoverable_error` semantics — known runtime conditions are handled by explicit bounded recovery logic and recorded as recovery evidence.
4. `failure` — unrecognized/unsafe conditions stop execution with a structured code, message, step/evidence context when available.

`MEMBER_NOT_FOUND` is explicitly detected and returned as a business outcome instead of an automation crash.

The implementation also includes one concrete recoverable runtime condition. Member `10045` intentionally returns `Temporary Service Delay` once. Replay recognizes that known state, emits `recoverable_condition`, clicks the declared `Retry` control once, emits `recovery_succeeded`, and continues. The recovery attempt is bounded and never invokes the model.

Fill actions are verified by reading the resulting field value before the next step continues. Origin policy is revalidated after actions so navigation cannot silently leave the permitted surface.

## 4. Heterogeneity & multi-tenant

The main heterogeneity seam is `SurfaceAdapter`. The artifact describes stable operations and target candidates; an adapter owns how those semantics are implemented on a concrete UI.

The current adapter uses Playwright and DOM/accessibility-oriented locators. For legacy web applications, the locator model can be extended with frame paths, table-relative anchors, accessibility metadata, OCR text, image anchors, and screenshot coordinates. For native desktop applications, another adapter can map the same action vocabulary onto Windows UI Automation, macOS Accessibility, or screenshot/coordinate control.

For multi-tenant reuse, I would store a vendor/application base capability plus small tenant/version overrides. The shared artifact would retain the common workflow and semantic targets, while an override could provide a tenant-specific entry URL, alternate locator candidate, known interstitial, or renamed field. Compatibility metadata would identify the vendor/version range for which an artifact is approved.

Replay telemetry can detect drift without re-recording every tenant: increasing fallback usage, repeated locator failure, unexpected dialogs, or checkpoint failure would mark a tenant/version combination for review and specialization.

## 5. Escalation & handoff

The implementation includes an explicit control-transfer model with `PAUSED_FOR_HUMAN`, `HUMAN_CONTROL`, `RESUMING`, `COMPLETED`, and `ABORTED` states.

Member `10044` intentionally enters `Manual Review Required`. When replay detects that state, it:

- captures a screenshot,
- creates an intervention with run/capability/step/reason context,
- records `automation_paused`,
- keeps the same Playwright browser/context alive,
- starts the minimal operator UI in the same process,
- waits for a human control transition.

The operator opens `http://127.0.0.1:8001`, clicks **Take Control**, and manually operates the already-open Chromium window. No new browser session is created. After the human clicks **Continue After Review** in that same session, the operator clicks **Resume**. Replay observes the `RESUMING` state, records `automation_resumed`, and continues deterministic execution.

This is deliberately a minimal local handoff rather than a full remote co-browsing system. The important assignment seam—pause, ownership transfer, same-session manual action, evidence, and resume—is real.

## 6. Safety

Safety is independent of LLM reasoning.

During discovery, the target origin is allowlisted before the browser is started, every proposed model action must be in the discovery action allowlist, and the current origin is revalidated after actions. The model therefore proposes actions but does not have authority to bypass the policy layer.

During replay, the artifact entry/current origin is validated, every step action must be permitted by the capability policy, and irreversible capabilities can require explicit confirmation. The demonstrated balance capability is read-only.

Evidence passes through a redaction layer. Secret-bearing keys such as passwords, tokens, authorization values and cookies are replaced, and common sensitive text patterns such as SSNs and bearer tokens are redacted.

No real bank credentials or customer PII are used; the target contains synthetic records only. `.env` is excluded from Git and `.env.example` contains placeholders.

A production deployment would add institution-specific authorization, stronger DLP, retention controls, signed capability approvals, and user/auditor identity on all human interventions.

## 7. Cuts

The project is intentionally a complete vertical slice rather than a broad platform.

Implemented:

- genuine LLM-driven live discovery
- typed/versioned artifact compilation
- parameterized inputs and typed outputs
- deterministic replay with no model in the loop
- semantic locator fallbacks and checkpoints
- business-outcome classification
- one bounded recoverable runtime condition
- same-session human handoff and resume
- discovery/replay guardrails
- redacted structured evidence
- focused automated tests
- minimal agent-facing capability catalog

Deliberate cuts:

- production remote browser streaming/co-browsing
- persistent intervention database
- native desktop adapter implementation
- tenant/version override storage
- artifact signing and formal approval workflow
- multi-run flakiness scoring
- distributed workers/queues
- a polished operator UI

With more time, the next priorities would be remote secure browser streaming for operators, persistent audit identity/control state, artifact approval/signing, and a second tenant variant demonstrating base-capability overrides.
