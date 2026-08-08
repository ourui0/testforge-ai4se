# TestForge Claude + Hermes Collaboration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each implementation task uses a fresh Claude session; each review gate uses a fresh, read-only Hermes session.

**Goal:** Safely complete TestForge Tasks 8–19 with Claude responsible for implementation and fixes, Hermes responsible for independent specification/security review, and the human owner retaining every contract and merge decision.

**Architecture:** Work continues on the isolated integration branch. Every task gets its own branch and worktree, a strict RED→GREEN cycle, an immutable review package, a Hermes review, fixes by the original Claude implementer, controller verification, and a non-fast-forward integration merge. Hermes never edits the implementation branch during review.

**Tech Stack:** Python 3.11+, pytest, Pydantic, SQLAlchemy/SQLite, Typer, FastAPI/HTMX, Docker, coverage.py, mutmut, keyring, OpenAI adapter, Git/GitHub.

## Global Constraints

- Canonical repository: `D:\AI4SE`.
- Latest development worktree: `D:\AI4SE\.worktrees\testforge-implementation`.
- Integration branch: `feature/testforge-implementation`.
- Remote: `https://github.com/ourui0/testforge-ai4se.git`.
- `main` currently preserves the cold-start baseline and must not be used as the implementation workspace until the integration PR is merged.
- Tasks 1–7 are complete, reviewed, merged, and verified at integration commit `2828c18`.
- Current integrated verification: `170 passed, 3 skipped`; the skips are approved Windows symlink-permission cases.
- Task 8 is the next implementation task. Its worktree exists, editable installation is rebound, and its baseline is verified as `170 passed, 3 skipped`.
- One fresh Claude implementation session and one fresh Hermes review session are required per task.
- The reviewer is read-only. It must not edit files, commit, format, or silently fix findings.
- Review fixes return to the original Claude implementation session for that task.
- Every feature begins with a genuine failing test before production code.
- Public contracts that are absent or contradictory trigger a human approval gate before product code.
- No real API key, credential, `.env`, raw secret, complete prompt, or unredacted traceback may enter Git, logs, screenshots, fixtures, or review packages.
- Only the integration controller may merge a reviewed task branch into `feature/testforge-implementation`.
- Each merge uses `--no-ff` so task history and review evidence remain visible.
- After each merge, update `PLAN.md`, `AGENT_LOG.md`, `PROJECT_ROADMAP.md`, and the SDD progress ledger.
- Push the integration branch after every completed task or at least at the end of each work session.

---

## 1. Model Responsibility Split

### Claude: implementation owner

Claude owns all production mutations for Tasks 8–19:

- read the bounded task brief and only the referenced contracts;
- stop before coding when a public contract is missing;
- write the first failing test and preserve exact RED evidence;
- implement the minimum code for GREEN;
- add boundary and regression tests;
- run focused, affected, full, Ruff, formatting, and diff checks;
- commit only the current task files;
- write the task implementation report;
- receive Hermes findings and implement every accepted Critical/Important fix;
- rerun verification and commit fixes separately.

Claude must not review and approve its own task as the only reviewer.

### Hermes: independent review owner

Hermes owns the read-only challenge function for Tasks 8–19:

- compare the task brief, implementation report, and immutable diff package;
- check specification compliance before code quality;
- run read-only tests or probes when its host supports them;
- inspect adversarial inputs, security boundaries, state recovery, and cross-platform behavior;
- classify findings as Critical, Important, or Minor with exact file and line references;
- provide a concrete reproduction and expected correction;
- re-review only the original findings and fix diff after Claude responds;
- state `Approved` only when no Critical or Important finding remains.

Hermes must not edit the implementation worktree. If Hermes cannot execute the project interpreter, it performs static review and the controller independently reruns tests.

### Human owner: contract and ownership authority

The human owner decides:

- any new public model, method signature, state, security boundary, or fallback rule;
- any conflict between SPEC and PLAN;
- whether a documented residual risk is acceptable;
- whether a task is allowed to resume after a contract pause;
- when the integration branch is merged into `main`;
- when the project is ready for public deployment and final submission.

---

## 2. Task Assignment Matrix

| Task | Claude implementation assignment | Hermes review assignment | Required result |
|---|---|---|---|
| 8 — Quality Gate and Feedback | Implement deterministic quality decisions, feedback categories, and stagnation logic | Attack metric ordering, zero-mutant fallback, tool-error separation, category precedence, and two-round stagnation | Feedback changes the next attempt without LLM self-evaluation |
| 9 — Structured Project Memory | Implement project-isolated, bounded, expiring structured memory | Check cross-project leakage, source-copy prohibition, deterministic selection, capacity, expiry, and restart persistence | Memory stores summaries/decisions only, never full source |
| 10 — Docker Sandbox | Implement image fingerprinting, trusted build boundary, non-root offline execution, limits, timeout cleanup | Threat-model mounts, networking, Docker socket, credentials, dependency drift, cleanup, and Windows/POSIX behavior | Untrusted generated code runs only in the restricted container |
| 11 — Domain Tool Dispatcher | Implement discriminated tool requests, fixed argument vectors, and explicit handler registry | Probe arbitrary shell injection, unknown tools, path bypass, approval bypass, raw-source audit leakage, and malformed requests | LLM can request only named domain tools |
| 12 — Agent Engine | Implement persisted one-transition advancement, blocking/resume, context building, and mock feedback loop | Check idempotency, crash recovery, duplicate actions, state/event atomicity, stagnation, budget stop, approvals, cancellation, and stale workspace | Deterministic end-to-end mock loop reaches the correct blocking/terminal state |
| 13 — Credential Store | Implement keyring-first set/status/clear and explicit `.env` development fallback | Search for plaintext leaks, environment fallback mistakes, status disclosure, exception leakage, idempotent clear, and log exposure | Credentials never appear in Git, status, logs, or public demo |
| 14 — OpenAI Adapter | Implement provider-neutral adapter using structured responses and normalized errors | Probe authentication/rate-limit/timeout/refusal/schema failures, secret-bearing provider messages, prompt/tool overexposure, and missing parsed output | Real provider remains replaceable; mock mode stays offline |
| 15 — CLI and Application Service | Implement init/run/status/approval/apply/history/credential/service commands | Check actionable errors, unsafe defaults, resume semantics, output redaction, path handling, and command idempotency | CLI exposes the Harness without arbitrary shell access |
| 16 — Local WebUI | Implement local task, timeline, metrics, diff, approval, credential-status, and memory pages | Check authorization assumptions, CSRF/state changes, HTML escaping, secret display, stale approvals, unsafe path input, and accessibility | Local WebUI operates real trusted repositories safely |
| 17 — Public Demo Mode | Implement bundled fixtures, mock-only demo factory, and restricted routes | Prove uploads, repository URLs, API keys, external network, real tools, and arbitrary scenarios are impossible | Public demo shows core mechanisms without executing user code |
| 18 — Distribution | Implement PyPI packaging, Docker images, entry points, secrets documentation, and smoke tests | Check image contents, `.dockerignore`, credential exclusion, reproducibility, host keyring boundary, startup commands, and dependency pinning | CLI and WebUI can be obtained and started from documented artifacts |
| 19 — CI and Final Delivery | Implement CI tests/builds/smoke checks and finish README, evidence, licensing, and reflection | Perform final SPEC/PLAN traceability audit, secret scan, clean-clone test, artifact review, link review, and course checklist review | Last CI run passes and every requirement has verifiable evidence |

---

## 3. Exact Worktree Allocation

Use these branch and worktree names so both models refer to the same locations:

| Task | Branch | Worktree |
|---|---|---|
| 8 | `task-08-feedback` | `D:\AI4SE\.worktrees\task-08-feedback` |
| 9 | `task-09-memory` | `D:\AI4SE\.worktrees\task-09-memory` |
| 10 | `task-10-sandbox` | `D:\AI4SE\.worktrees\task-10-sandbox` |
| 11 | `task-11-dispatcher` | `D:\AI4SE\.worktrees\task-11-dispatcher` |
| 12 | `task-12-engine` | `D:\AI4SE\.worktrees\task-12-engine` |
| 13 | `task-13-credentials` | `D:\AI4SE\.worktrees\task-13-credentials` |
| 14 | `task-14-openai` | `D:\AI4SE\.worktrees\task-14-openai` |
| 15 | `task-15-cli` | `D:\AI4SE\.worktrees\task-15-cli` |
| 16 | `task-16-webui` | `D:\AI4SE\.worktrees\task-16-webui` |
| 17 | `task-17-demo` | `D:\AI4SE\.worktrees\task-17-demo` |
| 18 | `task-18-distribution` | `D:\AI4SE\.worktrees\task-18-distribution` |
| 19 | `task-19-final-delivery` | `D:\AI4SE\.worktrees\task-19-final-delivery` |

Every new task branch starts from the latest reviewed commit on `feature/testforge-implementation`, not from `main` and not from another unmerged task branch.

---

## 4. Per-Task Operating Procedure

### Phase A — controller preparation

- [ ] Confirm the integration worktree is clean.
- [ ] Confirm the previous task is reviewed, merged, documented, tested, and pushed.
- [ ] Extract only the current task section from `PLAN.md` into `.superpowers/sdd/PLAN/task-N-brief.md`.
- [ ] Create the exact branch/worktree listed above from the latest integration commit.
- [ ] Bind the task-local `.venv` to the available project environment.
- [ ] Reinstall the editable package from the current task worktree with `python -m pip install -e . --no-deps`.
- [ ] Run the full baseline suite before dispatching Claude.
- [ ] Record the baseline commit and test count in the task brief.

### Phase B — fresh Claude implementation session

- [ ] Read the bounded task brief completely.
- [ ] Inspect only explicitly referenced source contracts.
- [ ] Report missing public behavior before creating product code.
- [ ] Write the exact first test.
- [ ] Run the exact focused test and capture a genuine feature RED.
- [ ] Implement the minimum production behavior.
- [ ] Run focused GREEN.
- [ ] Add the remaining contract and boundary tests before their implementation.
- [ ] Run focused, affected, and full tests.
- [ ] Run scoped Ruff and format checks.
- [ ] Inspect `git diff --check` and `git status`.
- [ ] Commit only current-task paths.
- [ ] Write `.superpowers/sdd/PLAN/task-N-report.md` with commands, outputs, files, decisions, commit, and concerns.

### Phase C — fresh Hermes read-only review session

- [ ] Read the bounded brief, Claude report, and immutable review diff.
- [ ] Confirm the review base and head commits.
- [ ] Verify every public interface and acceptance rule.
- [ ] Probe the task-specific risks from the assignment matrix.
- [ ] Confirm tests genuinely fail before fixes and assert behavior rather than implementation trivia.
- [ ] Report findings with severity, exact location, reproduction, impact, and correction direction.
- [ ] Do not edit or commit anything.

### Phase D — correction loop

- [ ] Send all accepted Critical/Important findings back to the original Claude task session.
- [ ] Claude adds a regression test and captures RED for every finding.
- [ ] Claude makes the smallest correction and reruns all relevant checks.
- [ ] Claude commits a separate fix commit and updates the report.
- [ ] Hermes re-reviews the original findings and fix-only diff.
- [ ] Repeat until Hermes reports no open Critical/Important finding.

### Phase E — controller integration

- [ ] Independently rerun focused, full, and scoped static checks in the task worktree.
- [ ] Merge the task branch into `feature/testforge-implementation` using `--no-ff`.
- [ ] Run the full suite from the integration worktree.
- [ ] Mark the PLAN checklist complete and record implementer/reviewer identities and commit hashes.
- [ ] Update `AGENT_LOG.md`, `PROJECT_ROADMAP.md`, and the SDD ledger.
- [ ] Commit the evidence update.
- [ ] Push `feature/testforge-implementation` to `origin`.

---

## 5. Task 8 Recovery Procedure

Task 8 preparation was interrupted once, then recovered successfully. Before Claude starts Task 8, confirm the verified state with these lightweight checks:

```powershell
Set-Location 'D:\AI4SE\.worktrees\task-08-feedback'
git status --short --branch
Get-Process python,pip -ErrorAction SilentlyContinue
& '.\.venv\Scripts\python.exe' -c "import testforge; print(testforge.__file__)"
```

Expected repository state:

- branch: `task-08-feedback`;
- starting commit: `2828c18`;
- no product-code changes;
- no Task 8 commit;
- previously verified full baseline: `170 passed, 3 skipped`;
- bounded brief: `D:\AI4SE\.worktrees\testforge-implementation\.superpowers\sdd\PLAN\task-8-brief.md`.

The import path must point into `D:\AI4SE\.worktrees\task-08-feedback\src`. Rerun editable installation and the full baseline only if the path, dependency state, or worktree commit differs.

---

## 6. Claude Session Instruction

Give each fresh Claude implementation session this instruction, followed by the exact task brief path:

> You are the sole implementation owner for one TestForge task. Work only in the assigned task worktree and branch. Read the bounded brief completely and inspect only its named dependencies. Follow strict TDD: capture a genuine RED before product code, implement minimum GREEN, add boundary tests, run focused/affected/full verification, run scoped Ruff/format checks, inspect diff/status, commit only task files, and write the task report. If a public contract is missing or conflicts with SPEC/PLAN, stop before product code and request human approval. Do not review-approve your own work, do not modify integration directly, and never expose credentials or raw sensitive output.

Claude must be told its exact task number, worktree, branch, baseline commit, interpreter, brief path, and report path in the dispatch message.

---

## 7. Hermes Review Instruction

Give each fresh Hermes review session this instruction, followed by the exact brief/report/diff paths:

> You are the independent, read-only reviewer for one TestForge task. Do not edit files, commit, format, or fix findings. Review specification compliance first and code quality second. Compare the bounded brief, implementation report, and immutable diff package. Inspect the implementation worktree and run only read-only tests/probes. Challenge security, determinism, persistence, cross-platform behavior, malformed inputs, error leakage, idempotency, and test quality as applicable. Report Critical, Important, and Minor findings with exact file/line, reproduction, impact, and correction direction. State Approved only when no Critical or Important finding remains.

Hermes must receive the task-specific risk list from the assignment matrix. If it cannot execute Python or Docker, it must say so explicitly; the controller remains responsible for independent execution verification.

---

## 8. Contract Approval Gate

Stop before product code and request the human owner when any of these occurs:

- a promised type has no fields;
- a method is named but has no signature or persistence semantics;
- PLAN example behavior conflicts with SPEC safety requirements;
- error, timeout, unsupported, retry, expiration, or idempotency semantics are absent;
- a reviewer requests a guarantee the selected platform cannot provide;
- a fix would add a public API, dependency, state, tool, network capability, or write authority;
- a task would need to modify files outside its declared scope for reasons other than a focused regression fixture.

The approval record must contain the issue, chosen contract, rejected alternative, affected SPEC/PLAN sections, approving human message, and documentation commit.

---

## 9. Git and GitHub Policy

- Remote name: `origin`.
- Remote URL: `https://github.com/ourui0/testforge-ai4se.git`.
- Push `main` only for approved mainline changes.
- Push `feature/testforge-implementation` after integrated task evidence commits.
- Push an active task branch when remote review or backup is needed.
- Never force-push reviewed history.
- Never use `git reset --hard` or discard unrelated user changes.
- Keep task commits separate from integration evidence commits.
- Open the final integration PR with base `main` and compare `feature/testforge-implementation`.
- Do not merge the integration PR until Tasks 8–19, final review, clean-clone verification, CI, and secret scan pass.

---

## 10. Evidence Required Per Task

Each task record must include:

- task number and title;
- model name and actual model identifier;
- fresh session identity and role (`implementer` or `reviewer`);
- worktree and branch;
- baseline commit;
- exact first RED command and failure;
- focused GREEN result;
- affected and full-suite result;
- Ruff/format/diff/status result;
- implementation commit and every fix commit;
- review package path;
- every finding and final verdict;
- integration merge commit;
- evidence documentation commit;
- remote push status;
- human contract approvals and residual risks.

---

## 11. Final Completion Gate

The project is complete only when all conditions below hold:

- [ ] Tasks 1–19 are marked complete in `PLAN.md`.
- [ ] Every task has a fresh Claude implementer and fresh Hermes reviewer record, or an explicitly documented equivalent model assignment approved by the owner.
- [ ] Every task has genuine RED→GREEN evidence.
- [ ] No Critical or Important review finding remains open.
- [ ] Full tests pass from the integration worktree.
- [ ] Docker-tagged tests pass in an environment with Docker.
- [ ] Mock end-to-end feedback loop deterministically demonstrates failure → feedback → changed action → success.
- [ ] Public demo cannot accept code, repository URLs, credentials, external tools, or network access.
- [ ] Credential and repository secret scans are clean.
- [ ] PyPI and Docker artifacts build and pass smoke tests.
- [ ] Clean-clone installation and documented startup commands succeed.
- [ ] CI's final run is green.
- [ ] README, SPEC, PLAN, SPEC_PROCESS, AGENT_LOG, roadmap, licensing, security boundaries, limitations, and reflection are current.
- [ ] `feature/testforge-implementation` is pushed and ready for the human-approved PR into `main`.

---

## Execution Handoff

Use **Subagent-Driven execution**: one fresh Claude implementation session and one fresh Hermes read-only review session per task. Begin with the Task 8 recovery procedure, then execute Tasks 8–19 sequentially with a review gate between every task.
