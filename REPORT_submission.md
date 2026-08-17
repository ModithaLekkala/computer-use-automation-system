# Design Report

## 1. Architecture

The system separates one-time LLM-guided discovery from deterministic production replay. During discovery, a `DiscoveryAgent` observes the current UI through a `SurfaceAdapter`, asks a planner for one structured action, executes that action against the live application, records evidence, and repeats until the planner declares the goal complete or the step budget is exhausted. The repository supports a local mock planner, OpenAI, and Gemini; the submitted evidence includes a genuine Gemini-driven browser run.

The concrete surface implementation is `PlaywrightSurface`. It exposes a narrow interface for navigation, observation, clicking, filling, extracting values, checking visible text, and collecting screenshots. The discovery and replay layers depend on this interface rather than directly on Playwright page objects.

A successful discovery run is compiled into a versioned `CapabilityArtifact`. The compiler removes discovery-time concrete values from the reusable capability. For the demonstrated `lookup_member_balance` capability, the discovered member ID is converted to `{{member_id}}`, and the observed savings value is replaced with stable field targeting. This compilation step is important because the model is allowed to reason probabilistically during discovery, while the saved production capability must be reviewable and reusable.

The `ReplayEngine` is the production execution path. It loads a saved artifact, binds typed invocation inputs, executes the recorded steps in order, checks policy, verifies the final checkpoint, extracts declared outputs, and returns a structured result. No model is called during replay.

The implementation is intentionally single-process and local. Distributed queues, durable orchestration, and production multi-tenant infrastructure are outside the scope of this take-home because they do not improve the core discovery-to-capability-to-replay demonstration.

## 2. Artifact schema

`CapabilityArtifact` is a typed Pydantic model and is serialized as JSON. It contains:

- `schema_version` and `capability_version`
- capability name, description, application identity, and entry URL
- allowlisted origins
- typed input definitions
- typed output definitions
- ordered capability steps
- target locator candidates for each UI control
- a final checkpoint
- declared business outcomes
- capability risk and permitted action types
- metadata describing how the artifact was produced

Each step has an explicit action type (`goto`, `click`, `fill`, `extract`, or `wait`), a description, an optional target, an optional parameterized value, and a timeout.

Targets contain prioritized locator candidates. The demonstrated artifact prefers semantic locators where possible: the member ID field uses its label before CSS fallbacks, and the Search control uses role/name before text. The savings output uses a stable field-level selector rather than the concrete balance observed during discovery.

Inputs and outputs are part of the capability contract. The demonstrated artifact accepts `member_id: string` and returns `savings_balance: string`. A discovery performed with member `10042` successfully produced an artifact that replayed with member `10043`, demonstrating that the saved artifact is not tied to the discovery-time input.

The artifact is intentionally decoupled from the raw model transcript. The JSONL discovery evidence remains useful for debugging and review, but replay consumes only the compiled capability.

## 3. Determinism & error handling

Replay does not invoke an LLM. Parameter references such as `{{member_id}}` are bound from the invocation input, then the fixed artifact steps are executed in order.

Locator resolution is deterministic. Candidates are attempted in their stored order; the replay engine does not invent a new selector when a locator fails. Field filling is verified by reading the value back before execution continues. The final artifact checkpoint verifies that the expected `Member Profile` state was actually reached.

The result contract distinguishes successful execution, expected business outcomes, recoverable errors, and failures. The implemented demonstration explicitly handles `MEMBER_NOT_FOUND` as a business outcome rather than treating it as a crash. A replay using member `99999` returns `business_outcome` with code `MEMBER_NOT_FOUND` and captures a screenshot as evidence. Unexpected exceptions are returned as structured failures with an error code, message, and screenshot when the browser session is available.

The current implementation relies primarily on Playwright's bounded waits and target fallbacks for transient UI timing. A production version would make recoverable-condition handling more explicit by adding named retry policies for known interstitials, session-expiry flows, and transient application errors rather than treating all unrecognized exceptions as hard failures.

## 4. Heterogeneity & multi-tenant

The main extension seam is `SurfaceAdapter`. The recorded artifact describes semantic operations, while an adapter is responsible for perceiving and acting on a concrete UI. The current implementation uses a browser DOM/accessibility-oriented Playwright adapter, but the capability model does not store Playwright page objects or model-specific transcripts.

For a legacy browser surface, a future adapter could add frame paths, table-relative targeting, accessibility-tree metadata, OCR/screenshot coordinates, or visual anchors as additional locator kinds. A desktop adapter could map the same higher-level operations onto Windows UI Automation, macOS Accessibility, or a screenshot/coordinate automation layer. The artifact schema can therefore remain the agent-facing contract while surface-specific targeting evolves underneath it.

For multi-tenant reuse, I would separate a vendor/application-level base capability from tenant/version overrides. The base artifact would contain the common workflow and semantic targets. A tenant override would be limited to details such as entry URL, an alternate locator candidate, a known version-specific dialog, or a renamed field. Each artifact would carry an application/vendor identity, compatibility metadata, and an approval version.

Replay telemetry would be used to detect drift. Increasing fallback usage, locator failures, or checkpoint failures for one tenant/version would mark that specialization for review without forcing every institution using the same vendor product to re-record the workflow.

## 5. Escalation & handoff

The repository includes an explicit handoff state model with `AUTOMATION`, `PAUSED_FOR_HUMAN`, `HUMAN_CONTROL`, and `RESUMING` states, plus a minimal operator console with endpoints to claim control and signal resume.

In the current implementation, this operator state model is a real executable component, but it is not yet connected to the discovery/replay runner in a way that transfers the existing Playwright browser session to the operator. The current console therefore demonstrates the control-ownership seam rather than a complete same-session takeover.

The production design is to keep the browser/session lifetime owned by the run coordinator. When discovery or replay reaches a blocked state, the coordinator would create an intervention containing the run ID, capability/goal, current step, reason, and screenshot; transition to `PAUSED_FOR_HUMAN`; expose the same browser session to the operator; record the operator's actions; and resume from that same session when control is returned.

A full remote co-browsing product is intentionally outside this project. The remaining implementation gap is the transport between the existing live Playwright session and the operator control surface.

## 6. Safety

Safety checks are separated from model reasoning. The replay engine validates the capability entry origin against an explicit allowlist and validates every recorded action type against the capability policy before dispatch.

Capabilities declare one of three risk levels: `read_only`, `reversible`, or `irreversible`. The demonstrated member-balance capability is read-only. The policy layer blocks mutation-style steps for an irreversible capability when explicit confirmation is required.

Logs pass through a redaction layer before persistence. Known secret-bearing keys such as password, token, secret, authorization, cookie, and SSN are replaced, and SSN/bearer-token patterns are redacted from text. The saved capability uses parameter references rather than embedding the discovery-time member identifier.

The demo application contains only synthetic records and no real credentials or customer PII. `.env` is excluded from Git and `.env.example` contains placeholders only.

The current safety limitation is that discovery itself does not yet apply the same explicit origin-policy checks as replay, and the origin check is performed at replay entry rather than after every possible navigation. A production implementation would enforce the same policy gate before every discovery and replay action and revalidate origin after navigation.

## 7. Cuts

I deliberately kept the implementation focused on the end-to-end vertical slice rather than building production infrastructure.

Implemented:
- real LLM-driven discovery against a live browser UI
- structured, versioned capability compilation
- parameterized replay inputs and typed outputs
- deterministic replay with no model in the loop
- locator fallbacks and checkpoint verification
- explicit `MEMBER_NOT_FOUND` business outcome
- structured evidence logs and failure screenshots
- origin/action guardrails and log redaction
- a minimal operator state model and console
- a small capability catalog API
- automated schema, policy, redaction, and parameter-binding tests

Deliberate or remaining cuts:
- complete same-live-session operator takeover and action capture
- named recoverable-condition/retry policies beyond bounded waits
- discovery-time policy enforcement equivalent to replay
- native desktop automation
- tenant/version override persistence
- artifact approval/signing workflow
- multi-run stability scoring
- distributed execution infrastructure
- polished operator UI

With more time, the first priorities would be wiring the operator state model into the live run coordinator, applying policy checks uniformly during discovery and replay, and adding explicit recoverable-condition handlers with evidence and tests. Those changes would strengthen the production-readiness of the same abstractions without changing the basic architecture.
