# Design Report

## 1. Architecture

The system separates discovery from execution. During discovery, a planner observes the current surface through a `SurfaceAdapter`, selects one constrained action, executes it, and repeats until the goal is complete or a stopping condition is reached. A successful run is compiled into a capability artifact.

The production path is the `ReplayEngine`. It accepts a saved artifact plus typed inputs and executes the recorded steps without asking a model to make decisions. The split is deliberate: probabilistic reasoning is useful for learning a workflow; repeat execution should be cheap, reviewable, debuggable, and predictable.

`SurfaceAdapter` is the boundary between capability semantics and a concrete UI technology. The current implementation uses Playwright, but replay logic does not directly depend on Playwright page objects. That keeps a seam for accessibility-tree or desktop adapters.

The implementation stays single-process because distributed infrastructure is not the interesting part of this take-home. The important boundaries—discovery, replay, policy, evidence, and handoff—remain explicit.

## 2. Artifact schema

A capability is a typed, versioned contract rather than a raw model transcript. It contains capability identity, typed inputs and outputs, ordered steps, prioritized locator candidates, a checkpoint, declared business outcomes, and policy metadata.

Each target stores multiple locator candidates in preference order. Semantic locators such as label or role/name are preferred. Text/context comes next. Structural CSS is the final fallback. The replay engine only uses declared candidates; it does not improvise with an LLM.

Per-run values such as a member ID are represented as parameters (`{{member_id}}`) so artifacts remain reusable and do not persist concrete customer data.

## 3. Determinism & error handling

Replay never invokes an LLM to choose the next step. Each artifact action has a fixed type, locator priority, timeout, and expected final checkpoint.

Results are separated into four categories: `success`, `business_outcome`, `recoverable_error`, and `failure`. A nonexistent member is a legitimate business result rather than an automation crash. Hard failures record a code, failing step when known, and evidence path.

When a locator cannot be resolved, the executor tries only the artifact’s predefined fallback locators. It does not silently choose a different control. This keeps failures reproducible and reviewable.

## 4. Heterogeneity & multi-tenant

The artifact stores semantic actions (`click`, `fill`, `extract`, `checkpoint`); `SurfaceAdapter` owns how those semantics map to a particular surface.

A legacy web adapter could add frame paths, accessibility information, OCR/screenshot coordinates, or table-aware targeting. A desktop adapter could map the same actions to Windows UI Automation, macOS Accessibility, or computer-vision targets.

For multi-tenant reuse, capabilities should have a vendor/application identity and compatibility range. Tenant-specific differences should be small override patches—entry URL, alternate locator candidate, renamed field, or a known interstitial—rather than a copied artifact per institution. Replay telemetry can reveal rising fallback usage or checkpoint failures and mark a tenant/version combination for review.

## 5. Escalation & handoff

A run has an explicit control owner: `AUTOMATION` or `HUMAN`. When the agent is stuck, replay hits an unsafe/unrecognized state, or policy requires a human decision, the run can transition to `PAUSED_FOR_HUMAN` with the current run ID, step, reason, and screenshot.

The operator registry models claiming control and resuming. The current console is intentionally simple; a production implementation would pair this state machine with a remote browser stream/control channel so the human operates the same live session. The important design seam is that session lifetime and control ownership are separate from planning logic.

## 6. Safety

Safety is enforced outside the planner. Allowed origins and action types are checked by the policy layer. Capabilities declare a risk level. Irreversible actions can require explicit confirmation. Evidence passes through redaction before persistence, and artifacts contain parameter references instead of credentials or raw PII.

The demo workflow is read-only. A production implementation would additionally integrate institution-specific authorization, stronger DLP, audit identity, retention policies, and signed artifact approvals.

## 7. Cuts

I deliberately did not build production multi-tenant infrastructure, distributed workers, a polished co-browsing console, native desktop automation, automatic cross-version migration, or open-ended LLM fallback during replay.

With more time I would add an approval lifecycle (`draft -> reviewed -> approved`), multi-run stability scoring, a second tenant variant with locator overrides, richer accessibility/screenshot targeting, artifact signatures and provenance, and remote shared-session operator control.
