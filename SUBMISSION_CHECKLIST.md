# Submission Checklist

- [ ] Create local `.env` from `.env.example`; never commit `.env`.
- [ ] `pip install -e ".[dev]"`.
- [ ] `playwright install chromium`.
- [ ] Start `python -m demo_app.app`.
- [ ] Run genuine Gemini discovery with member `10042`.
- [ ] Replay artifact with `10043`; confirm `savings_balance = 930.17`.
- [ ] Replay artifact with `99999`; confirm `MEMBER_NOT_FOUND`.
- [ ] Run `python -m src.cli recovery-demo`; confirm recovery evidence.
- [ ] Run `python -m src.cli handoff-demo`; take control of the SAME Chromium window and resume.
- [ ] Run `pytest -q`; all tests must pass.
- [ ] Confirm `evidence/discovery`, `evidence/replay`, `evidence/recovery`, and `evidence/handoff` contain current final-run evidence.
- [ ] Confirm `.env` is absent from `git status` and GitHub.
- [ ] Review `REPORT.md` against the final implementation.
- [ ] Push development branch.
- [ ] Merge development into main only after all checks pass.
- [ ] Verify public repo from an incognito/logged-out browser.
- [ ] Email the public repository URL on its own line to `assignments@interface.ai`.
