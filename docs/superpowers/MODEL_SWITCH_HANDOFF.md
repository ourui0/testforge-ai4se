# TestForge Model-Switch Handoff

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for implementation and a fresh read-only reviewer for every task.

**Goal:** Continue TestForge from Task 8 without repeating Tasks 1–7, losing review evidence, or accidentally developing from the stale `main` worktree.

**Architecture:** Claude owns task implementation and accepted review fixes. Hermes owns independent read-only review. The human owner approves missing public contracts and final merges. Development occurs on isolated task worktrees and merges into `feature/testforge-implementation` only after review.

**Tech Stack:** Python 3.11+, pytest, Pydantic, SQLAlchemy/SQLite, Docker, Typer, FastAPI/HTMX, keyring, OpenAI adapter, Git/GitHub.

## 1. Exact Handoff State

- Date: 2026-08-05, Asia/Shanghai.
- Repository: `D:\AI4SE`.
- Remote: `https://github.com/ourui0/testforge-ai4se.git`.
- Do not implement from `D:\AI4SE`; it is the older `main` worktree at `f22ce97`.
- Latest development worktree: `D:\AI4SE\.worktrees\testforge-implementation`.
- Integration branch: `feature/testforge-implementation`.
- Integration HEAD: `2828c182a2ea616438a5096797b0197784fc5f83`.
- Integration upstream: `origin/feature/testforge-implementation`.
- Tasks 1–7: implemented, independently reviewed, fixed where required, merged, documented, tested, and pushed.
- Latest integrated test evidence: `170 passed, 3 skipped`.
- The three skips are approved Windows symlink-creation permission cases.
- Next task: Task 8 — Quality Gate and Feedback Classification.
- Task 8 worktree: `D:\AI4SE\.worktrees\task-08-feedback`.
- Task 8 branch: `task-08-feedback` at `2828c18`.
- Task 8 worktree is clean and contains no product changes or commits.
- Task 8 `.venv` is a junction to `D:\AI4SE\.worktrees\task-07-parsers\.venv`.
- Editable installation has been rebound successfully to `D:\AI4SE\.worktrees\task-08-feedback`.
- The recovered Task 8 baseline is verified as `170 passed, 3 skipped`.
- No Python or pip process remained after recovery.
- Task 8 bounded brief: `D:\AI4SE\.worktrees\testforge-implementation\.superpowers\sdd\PLAN\task-8-brief.md`.
- Root collaboration guide: `D:\AI4SE\MODEL_COLLABORATION_GUIDE.md`.
- This handoff file and the collaboration guide are currently uncommitted files in the old `main` worktree.

## 2. Remaining-Quota Execution Budget

The previous Codex session was told approximately 11% of the weekly allowance remained. The session cannot inspect the provider's exact quota, so the safe allocation is outcome-based:

1. **35% of remaining allowance — handoff safety:** create and verify this file plus the Claude/Hermes collaboration guide before further coding.
2. **20% — Task 8 environment recovery:** verify no background process, rebind editable installation, run the 170-test baseline, and record exact output.
3. **25% — Task 8 contract audit:** resolve public types and quality/stagnation/category precedence before implementation. Stop for human approval when needed.
4. **10% — remote and evidence hygiene:** push any approved integration documentation change and record branch/commit state.
5. **10% — final conversational handoff:** report completed work, open decisions, exact next command, and model prompts before ending the session.

Do not spend the final handoff reserve on speculative implementation or repeated full-suite runs.

## 3. Verified Recovery Commands

Run from PowerShell:

```powershell
Set-Location 'D:\AI4SE\.worktrees\task-08-feedback'
git status --short --branch
Get-Process python,pip -ErrorAction SilentlyContinue
& '.\.venv\Scripts\python.exe' -m pip install -e . --no-deps
& '.\.venv\Scripts\python.exe' -m pytest -q
```

Observed results on 2026-08-05:

- branch line `## task-08-feedback`;
- no modified/untracked task files;
- no stale Python or pip process before setup;
- editable install points at `D:\AI4SE\.worktrees\task-08-feedback`;
- baseline result `170 passed, 3 skipped`.

The recovery is complete. A new model should run `git status --short --branch` before writing tests, but should not repeat installation or the full baseline unless the environment or dependency state changed.

## 4. Task 8 Known Contract Gaps

The existing PLAN section is not yet sufficient for safe implementation. A fresh Claude session must stop before product code and ask the human owner to approve exact answers for these points:

1. `QualityDecision` has no defined fields, frozen behavior, or allowed `reason` values.
2. PLAN references `MetricSnapshot.mutation_supported`, but the current model exposes only `mutation_status` and computed `mutation_score`.
3. Coverage fallback is unclear when mutation is technically supported but produces zero valid mutants.
4. Candidate mutation `timeout`/`error` handling is unclear when the baseline was supported or unsupported.
5. Test-regression ordering does not specify whether fewer passing tests is a regression in addition to failures and extra skips.
6. Mutation comparison across different mutant totals needs an explicit rule.
7. `FeedbackEngine` promises syntax/import/assertion/fixture/mock/timeout/flaky categories but its draft signature receives only metric snapshots, attempt summaries, and surviving-mutant strings.
8. A structured analyzer-failure input model or exact alternative is required before those categories can be deterministic.
9. Category precedence is undefined when multiple signals exist, such as test failure plus timeout or surviving mutants.
10. “Two consecutive attempts unchanged” should explicitly state whether it compares the current candidate with the most recent prior attempt. The existing example instead compares two prior attempts, which delays stagnation by one round.

Recommended contract direction:

- frozen `QualityDecision(passed: bool, reason: Literal[...])`;
- mutation status is supported only when `mutation_status == "supported"`;
- valid mutation gating requires at least one valid mutant; explicit unsupported or zero valid mutants uses coverage fallback;
- timeout/error always yields `mutation_tool_error` and never coverage fallback;
- all test regressions and metric regressions are evaluated before improvement gates;
- introduce one frozen structured `FailureSignal` model carrying category and sanitized summary, rather than parsing prose in `FeedbackEngine`;
- define precedence as tool/test failure, flaky/timeout, surviving mutant, coverage-not-improved, then generic threshold-missed;
- stagnation compares the current candidate metrics with the latest prior attempt, so two consecutive equal rounds stop immediately.

These are recommendations, not approved behavior. Record the human ruling in SPEC, PLAN, AGENT_LOG, and a documentation commit before implementation.

## 5. Claude Task 8 Dispatch

After environment recovery and human contract approval, start a fresh Claude implementation session with this instruction:

> Implement only TestForge Task 8 in `D:\AI4SE\.worktrees\task-08-feedback` on branch `task-08-feedback`. Read the complete bounded brief at `D:\AI4SE\.worktrees\testforge-implementation\.superpowers\sdd\PLAN\task-8-brief.md` and the approved Task 8 contract revision. Baseline is `2828c18` with `170 passed, 3 skipped`. Follow strict TDD: write the exact mutation-success and timeout-fallback tests first, capture genuine missing-feedback RED before product code, implement minimum GREEN, then add ordered regression/gate/category/stagnation tests. Stop before product code if any public behavior remains undefined. Run focused, affected, full, Ruff, format, diff, and status checks. Commit Task 8 only and write `D:\AI4SE\.worktrees\testforge-implementation\.superpowers\sdd\PLAN\task-8-report.md` with exact RED/GREEN evidence and final commit.

Claude is the sole product-code editor for this task.

## 6. Hermes Task 8 Review Dispatch

After Claude commits and writes the report, generate an immutable review package and start a fresh Hermes session with this instruction:

> Review TestForge Task 8 read-only. Do not edit, commit, or format. Compare the bounded Task 8 brief, implementation report, approved contract revision, and immutable diff. Check ordered quality decisions, all regression cases, supported/unsupported/zero-mutant/timeout/error distinctions, changing mutant totals, exact reason values, deterministic failure-category precedence, sanitized diagnostics, and current-versus-prior stagnation. Run read-only adversarial probes if possible. Report Critical, Important, and Minor findings with exact file/line and reproduction. Approve only when no Critical or Important finding remains.

Return accepted findings to the original Claude Task 8 session. Hermes remains read-only.

## 7. Task 8 Integration Gate

Do not merge Task 8 until all items pass:

- [ ] Human-approved Task 8 contract is committed on the integration branch.
- [ ] Genuine first RED predates feedback production code.
- [ ] Focused feedback suite passes.
- [ ] Full suite passes with only approved skips.
- [ ] Scoped Ruff and format checks pass.
- [ ] Claude implementation report is complete.
- [ ] Hermes reports no open Critical/Important finding.
- [ ] Controller independently reruns focused and full tests.
- [ ] Task branch merges with `--no-ff` into `feature/testforge-implementation`.
- [ ] PLAN, AGENT_LOG, roadmap, and SDD ledger are updated.
- [ ] Integration tests pass after merge.
- [ ] Evidence commit and integration branch are pushed to `origin`.

## 8. Work After Task 8

Continue Tasks 9–19 using `D:\AI4SE\MODEL_COLLABORATION_GUIDE.md`. Claude implements; Hermes reviews. Start every task from the latest reviewed integration commit. Never branch from the stale root `main` worktree or an unmerged sibling task.

## 9. Safe Stop Message

If the current model must stop before Task 8 is complete, its final response must include:

- latest integration and task commit hashes;
- exact test counts last observed;
- dirty/clean status of root, integration, and Task 8 worktrees;
- whether editable installation and baseline recovery completed;
- whether the Task 8 contract was approved and committed;
- exact files created or modified but not committed;
- active background processes, if any;
- the next single command to run;
- which model/session owns implementation and which owns review.
