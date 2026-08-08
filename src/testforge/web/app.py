"""FastAPI application factory and routes for local TestForge WebUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from testforge.domain.errors import InputError

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(application: object, demo_mode: bool = False) -> FastAPI:
    app = FastAPI(title="TestForge")

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "mode": "demo" if demo_mode else "local"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        if demo_mode:
            return _demo_index()
        return _page("TestForge", "<h1>TestForge</h1><p>Local WebUI running.</p>")

    @app.get("/tasks/{task_id}", response_class=HTMLResponse)
    def task_detail(task_id: str) -> HTMLResponse:
        try:
            view = application.get_task_view(UUID(task_id))
        except (InputError, ValueError):
            return HTMLResponse(
                content=_page("Error", "<h1>Task not found</h1>"),
                status_code=404,
            )
        if demo_mode:
            return HTMLResponse(_demo_task_detail(view))
        return HTMLResponse(
            _page(
                f"Task {task_id[:8]}",
                f"<h1>Task {task_id[:8]}</h1>"
                f"<p>State: {view.state}</p>"
                f"<p>Mutation score: {view.mutation_score}</p>"
                f"<p>{view.status_text}</p>",
            )
        )

    @app.get("/approvals", response_class=HTMLResponse)
    def approvals_list() -> str:
        try:
            items = application.get_pending_approvals()
        except (InputError, ValueError, LookupError):
            items = []
        if demo_mode and items:
            return HTMLResponse(_demo_approvals(items))
        rows = "".join(
            f"<li>{a.id} — {a.kind} "
            f'<form method="post" action="/approvals/{a.id}/approve">'
            f'<button>Approve</button></form>'
            f'<form method="post" action="/approvals/{a.id}/reject">'
            f'<button>Reject</button></form></li>'
            for a in items
        )
        return _page("Approvals", f"<h1>Pending Approvals</h1><ul>{rows}</ul>")

    @app.post("/approvals/{approval_id}/{decision}")
    def decide(approval_id: str, decision: str) -> RedirectResponse:
        application.decide_approval(
            UUID(approval_id),
            approved=decision == "approve",
            actor="local-owner",
        )
        return RedirectResponse(url="/approvals", status_code=303)

    @app.post("/demo/tasks")
    async def demo_create_task(request: Request) -> JSONResponse:
        if not demo_mode:
            return JSONResponse({"error": "demo mode only"}, status_code=403)
        body = await request.json()
        if any(k in body for k in ("repository_url", "api_key")):
            return JSONResponse(
                {"detail": "repository_url and api_key are forbidden in demo mode"},
                status_code=422,
            )
        scenario = body.get("scenario", "weak-then-strong")
        task = application.create_demo_task(scenario)
        task_state = getattr(task, "state", "created")
        return JSONResponse({"task_id": str(task.id), "state": str(task_state)})

    @app.post("/demo/tasks/{task_id}/advance")
    def demo_advance(task_id: str) -> JSONResponse:
        if not demo_mode:
            return JSONResponse({"error": "demo mode only"}, status_code=403)
        result = application.advance_demo_task(UUID(task_id))
        return JSONResponse({
            "state": result.state,
            "blocked": result.blocked,
            "reason": result.reason,
            "attempts": result.attempts,
            "metrics": result.metrics,
        })

    @app.get("/settings")
    def settings_page() -> str:
        if demo_mode:
            return _page(
                "Settings",
                "<h1>Settings</h1>"
                "<p>Demo mode — no credentials required.</p>"
                "<p>Credential status: <strong>disabled (public demo)</strong></p>",
            )
        return _page("Settings", "<h1>Settings</h1><p>Credential status: OK</p>")

    return app


# ── demo mode support ──────────────────────────────────────────────────

# Pre-scripted state sequences for each demo scenario.
# Each step is (state, mutation_score_delta, reason, blocked_flag).

_WEAK_THEN_STRONG_SEQUENCE = [
    ("validating_input", 0.0, "Input validated — target module found", False),
    ("preparing_sandbox", 0.0, "Sandbox image built, container ready", False),
    ("baselining", 0.0, "Baseline established — 45% branch coverage, 0 mutants killed", False),
    ("generating", 0.0, "LLM generated first test proposal (weak assertion strategy)", False),
    ("testing", 0.0, "Tests executed — 1 passed, 0 failed", False),
    ("measuring_coverage", 45.0, "Coverage measured — 48% branch coverage (+3%)", False),
    ("mutation_testing", 48.0, "Mutation testing — 2/20 mutants killed (10%)", False),
    ("evaluating", 10.0, "Quality gate: MISSED — mutation score too low, need stronger tests", False),
    ("generating", 10.0, "LLM generated second test proposal (kill arithmetic mutant strategy)", False),
    ("testing", 10.0, "Tests executed — 3 passed, 0 failed", False),
    ("measuring_coverage", 78.0, "Coverage measured — 78% branch coverage (+33%)", False),
    ("mutation_testing", 78.0, "Mutation testing — 15/20 mutants killed (75%)", False),
    ("evaluating", 75.0, "Quality gate: PASSED — mutation score improved by 65 points", False),
    ("awaiting_apply_approval", 75.0, "Waiting for human approval to apply patch", True),
    ("applying_patch", 75.0, "Approval received — applying generated tests", False),
    ("completed", 75.0, "Task complete — 3 tests generated, 75% mutation score", False),
]

_REFACTOR_BLOCKED_SEQUENCE = [
    ("validating_input", 0.0, "Input validated — target module found", False),
    ("preparing_sandbox", 0.0, "Sandbox ready", False),
    ("baselining", 0.0, "Baseline established — 60% branch coverage", False),
    ("generating", 0.0, "LLM proposed a refactor (improve performance, low risk)", False),
    ("awaiting_refactor_approval", 0.0, "Refactor proposal requires human approval", True),
    ("baselining", 0.0, "Refactor rejected — re-baselining with original code", False),
    ("generating", 0.0, "LLM generated test proposal (boundary test strategy)", False),
    ("testing", 0.0, "Tests executed — 2 passed, 0 failed", False),
    ("measuring_coverage", 82.0, "Coverage measured — 82% branch coverage (+22%)", False),
    ("mutation_testing", 82.0, "Mutation testing — 18/20 mutants killed (90%)", False),
    ("evaluating", 90.0, "Quality gate: PASSED — mutation score improved by 90 points", False),
    ("awaiting_apply_approval", 90.0, "Waiting for human approval to apply patch", True),
    ("applying_patch", 90.0, "Approval received — applying generated tests", False),
    ("completed", 90.0, "Task complete — 2 tests generated, 90% mutation score", False),
]

_SCENARIO_SEQUENCES: dict[str, list[tuple[str, float, str, bool]]] = {
    "weak-then-strong": _WEAK_THEN_STRONG_SEQUENCE,
    "refactor-blocked": _REFACTOR_BLOCKED_SEQUENCE,
}


@dataclass
class _DemoTask:
    """In-memory state for a single demo task."""

    id: UUID = field(default_factory=uuid4)
    scenario: str = ""
    step_index: int = 0
    sequence: list[tuple[str, float, str, bool]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: str = "created"
    mutation_score: float = 0.0
    status_text: str = "Task created — click Advance to begin"
    blocked: bool = False

    @property
    def percent(self) -> int:
        total = max(len(self.sequence), 1)
        return min(100, int(100 * self.step_index / total))


class DemoApplication:
    """In-memory demo application backed by pre-scripted state sequences.

    Each scenario has a deterministic sequence of state transitions
    with associated metrics and status text. Every call to
    advance_demo_task() moves one step forward in the sequence.
    """

    def __init__(self) -> None:
        self._tasks: dict[UUID, _DemoTask] = {}
        self._approval_counter = 0

    def create_demo_task(self, scenario: str) -> _DemoTask:
        if scenario not in _SCENARIO_SEQUENCES:
            raise ValueError(f"unknown demo scenario: {scenario}")
        task = _DemoTask()
        task.scenario = scenario
        task.sequence = _SCENARIO_SEQUENCES[scenario]
        self._tasks[task.id] = task
        return task

    def advance_demo_task(self, task_id: UUID) -> _AdvanceResult:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        if task.step_index >= len(task.sequence):
            return _AdvanceResult(
                state=task.state,
                blocked=True,
                reason="no more steps — task finished",
                attempts=task.step_index,
                metrics={"mutation_score": task.mutation_score},
            )
        state, score, reason, blocked = task.sequence[task.step_index]
        task.state = state
        task.mutation_score = score
        task.status_text = reason
        task.blocked = blocked
        task.step_index += 1
        return _AdvanceResult(
            state=state,
            blocked=blocked,
            reason=reason,
            attempts=task.step_index,
            metrics={"mutation_score": score},
        )

    def get_task_view(self, task_id: UUID) -> _DemoTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError("task not found")
        return task

    def get_pending_approvals(self) -> list[_DemoApproval]:
        results: list[_DemoApproval] = []
        for task in self._tasks.values():
            if task.blocked and "approval" in task.state.lower():
                self._approval_counter += 1
                results.append(
                    _DemoApproval(
                        id=uuid4(),
                        kind="apply_tests",
                        task_id=str(task.id),
                    )
                )
        return results

    def decide_approval(
        self, approval_id: UUID, *, approved: bool, actor: str
    ) -> None:
        pass  # demo: no persistent side-effect needed


@dataclass
class _AdvanceResult:
    state: str
    blocked: bool
    reason: str
    attempts: int
    metrics: dict[str, float]


@dataclass
class _DemoApproval:
    id: UUID
    kind: str
    task_id: str


def create_demo_app() -> FastAPI:
    """Create a FastAPI app in public demo mode.

    No credentials, no external code execution, no network access.
    All state is in-memory and driven by pre-scripted sequences.
    """
    application = DemoApplication()
    return create_app(application, demo_mode=True)


# ── HTML rendering ─────────────────────────────────────────────────────

_STYLE = """<style>
:root {
  --bg: #f8f9fa; --card-bg: #fff; --text: #212529; --muted: #6c757d;
  --border: #dee2e6; --accent: #0d6efd; --accent-hover: #0b5ed7;
  --green: #198754; --red: #dc3545; --orange: #fd7e14;
  --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,.1);
}
*,*::before,*::after{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:0;
  background:var(--bg);color:var(--text);line-height:1.6}
nav{background:var(--card-bg);border-bottom:1px solid var(--border);
  padding:.75rem 1.5rem;display:flex;gap:1.5rem;align-items:center}
nav a{color:var(--accent);text-decoration:none;font-weight:500}
nav a:hover{text-decoration:underline}
main{padding:2rem 1.5rem;max-width:900px;margin:0 auto}
h1{font-size:1.75rem;margin:0 0 .5rem}
h2{font-size:1.25rem;margin:1.5rem 0 .5rem}
.card{background:var(--card-bg);border:1px solid var(--border);
  border-radius:var(--radius);padding:1.25rem;margin:1rem 0;
  box-shadow:var(--shadow)}
.card h2{margin-top:0}
.metrics{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.metric{flex:1;min-width:140px;text-align:center;padding:1rem;
  background:var(--bg);border-radius:var(--radius)}
.metric .value{font-size:2rem;font-weight:700;line-height:1.2}
.metric .label{font-size:.85rem;color:var(--muted);margin-top:.25rem}
.metric .value.green{color:var(--green)}.metric .value.red{color:var(--red)}
.metric .value.orange{color:var(--orange)}
.progress-bar{background:var(--border);border-radius:99px;height:8px;
  margin:1rem 0;overflow:hidden}
.progress-bar .fill{background:var(--accent);height:100%;
  border-radius:99px;transition:width .3s}
.state-badge{display:inline-block;padding:.25em .75em;border-radius:99px;
  font-size:.85rem;font-weight:600;background:var(--accent);color:#fff}
.state-badge.blocking{background:var(--orange)}
.state-badge.terminal{background:var(--green)}
button, .btn{display:inline-block;padding:.5rem 1.25rem;border:none;
  border-radius:var(--radius);font-size:.95rem;font-weight:600;cursor:pointer;
  color:#fff;background:var(--accent);text-decoration:none;
  transition:background .15s}
button:hover,.btn:hover{background:var(--accent-hover)}
button:disabled{opacity:.5;cursor:not-allowed}
.actions{display:flex;gap:.75rem;flex-wrap:wrap;margin:1rem 0}
.choices{display:flex;gap:.75rem;flex-wrap:wrap}
.choice-card{flex:1;min-width:250px}
.timeline{margin:1rem 0}
.timeline-item{display:flex;gap:.75rem;padding:.5rem 0;
  border-left:2px solid var(--border);padding-left:1rem;margin-left:.5rem}
.timeline-item .step{font-weight:600;color:var(--muted);min-width:2rem}
footer{margin-top:3rem;padding:1rem 0;border-top:1px solid var(--border);
  color:var(--muted);font-size:.85rem;text-align:center}
[aria-live]{border-left:3px solid var(--accent);padding-left:1em}
.disclaimer{background:#fff3cd;border:1px solid #ffc107;padding:.75rem 1rem;
  border-radius:var(--radius);margin-bottom:1.5rem;font-size:.9rem}
</style>"""


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title} — TestForge</title>{_STYLE}</head>
<body>
<nav><a href="/">Home</a> | <a href="/approvals">Approvals</a> | <a href="/settings">Settings</a></nav>
<main aria-live="polite">{body}</main>
<script src="/static/htmx.min.js"></script>
</body></html>"""


def _demo_index() -> str:
    scenarios = [
        {
            "id": "weak-then-strong",
            "name": "Weak → Strong",
            "desc": (
                "First attempt generates a weak assertion test; "
                "the quality gate rejects it. The feedback loop drives "
                "a second, stronger attempt that kills 15/20 mutants "
                "and achieves 75% mutation score."
            ),
            "steps": len(_WEAK_THEN_STRONG_SEQUENCE),
        },
        {
            "id": "refactor-blocked",
            "name": "Refactor Blocked",
            "desc": (
                "The LLM proposes a refactor; the governance gate pauses "
                "for human approval. After rejection, the agent proceeds "
                "with test generation and reaches 90% mutation score."
            ),
            "steps": len(_REFACTOR_BLOCKED_SEQUENCE),
        },
    ]
    cards = "".join(
        f"""<div class="card choice-card">
  <h2>{s['name']}</h2>
  <p>{s['desc']}</p>
  <p style="color:var(--muted)">{s['steps']} steps</p>
  <button onclick="startScenario('{s['id']}')">Start Demo</button>
</div>"""
        for s in scenarios
    )
    return _page(
        "TestForge Demo",
        f"""<div class="disclaimer">
  <strong>Public Demo Mode</strong> — No credentials, no external code
  execution, no Docker. All behavior is driven by deterministic,
  pre-recorded scenarios.
</div>
<h1>TestForge Demo</h1>
<p>
  TestForge is an AI-powered pytest unit test generation harness with
  Docker sandboxing and deterministic coverage-mutation feedback.
  Select a scenario below to see the core feedback loop in action.
</p>
<div class="choices">{cards}</div>
<div id="task-container"></div>
<script>
async function startScenario(scenario) {{
  const resp = await fetch('/demo/tasks', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{scenario}})
  }});
  const data = await resp.json();
  if (data.task_id) {{
    window.location.href = '/tasks/' + data.task_id;
  }}
}}
</script>""",
    )


def _demo_task_detail(view: object) -> str:
    """Render a rich demo task detail page with auto-advance and timeline."""
    # Normalise the view — it may be a _DemoTask or a MagicMock from tests
    state = getattr(view, "state", "unknown")
    mutation_score = getattr(view, "mutation_score", 0.0)
    status_text = getattr(view, "status_text", "")
    blocked = getattr(view, "blocked", False)
    step_index = getattr(view, "step_index", 0)
    task_id = str(getattr(view, "id", "unknown"))[:8]
    percent = getattr(view, "percent", 0)
    scenario = getattr(view, "scenario", "")
    is_demo_task = hasattr(view, "sequence") and hasattr(view, "step_index")

    total_steps = len(getattr(view, "sequence", [])) if is_demo_task else 0
    completed = (
        is_demo_task and step_index >= total_steps and state == "completed"
    )

    # determine badge class
    badge_class = ""
    if completed or state in ("completed", "no_action_needed"):
        badge_class = "terminal"
    elif blocked:
        badge_class = "blocking"

    badge_html = f'<span class="state-badge {badge_class}">{state}</span>'

    # progress
    progress_html = ""
    if is_demo_task and total_steps > 0:
        progress_html = (
            f'<div class="progress-bar">'
            f'<div class="fill" style="width:{percent}%"></div></div>'
            f'<p style="color:var(--muted)">Step {step_index} of {total_steps}</p>'
        )

    score_class = "green" if mutation_score >= 75 else (
        "orange" if mutation_score >= 40 else "red"
    )

    actions_html = ""
    if is_demo_task and not completed:
        actions_html = f"""
<div class="actions">
  <button id="advance-btn" onclick="advanceTask('{task_id}')">
    {('Resume (approval granted)' if blocked else 'Advance')}
  </button>
  <button onclick="autoAdvance('{task_id}')" style="background:var(--muted)">
    Auto-Run All
  </button>
</div>"""

    timeline_items = ""
    if is_demo_task:
        seq = view.sequence
        for i, (s, score, reason, b) in enumerate(seq):
            marker = "✓" if i < step_index else ("▸" if i == step_index else "○")
            tl_state_class = ""
            if s in ("completed", "no_action_needed"):
                tl_state_class = "terminal"
            elif b:
                tl_state_class = "blocking"
            timeline_items += (
                f'<div class="timeline-item">'
                f'<span class="step">{marker}</span>'
                f'<span class="state-badge {tl_state_class}"'
                f'  style="font-size:.75rem">{s}</span>'
                f'<span style="color:var(--muted)">{reason}</span>'
                f'</div>'
            )

    return _page(
        f"Task {task_id}",
        f"""<h1>Task {task_id}</h1>
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <h2 style="margin:0">Status {badge_html}</h2>
    <span style="color:var(--muted)">Scenario: {scenario}</span>
  </div>
  {progress_html}
  <div class="metrics">
    <div class="metric">
      <div class="value {score_class}">{mutation_score:.0f}%</div>
      <div class="label">Mutation Score</div>
    </div>
    <div class="metric">
      <div class="value">{percent}%</div>
      <div class="label">Progress</div>
    </div>
    <div class="metric">
      <div class="value">{step_index}</div>
      <div class="label">Steps Taken</div>
    </div>
  </div>
  <p style="color:var(--muted)">{status_text}</p>
  {actions_html}
</div>
<h2>State Timeline</h2>
<div class="card timeline">{timeline_items}</div>
<div id="advance-status" aria-live="polite"></div>
<script>
async function advanceTask(id) {{
  const btn = document.getElementById('advance-btn');
  if (btn) btn.disabled = true;
  const resp = await fetch('/demo/tasks/' + id + '/advance', {{method:'POST'}});
  const data = await resp.json();
  if (data.blocked && data.reason.includes('approval')) {{
    document.getElementById('advance-status').innerHTML =
      '<div class="disclaimer">This step requires human approval. '
      + 'Click <strong>Resume</strong> to simulate approval and continue.</div>';
  }} else {{
    document.getElementById('advance-status').innerHTML = '';
  }}
  window.location.reload();
}}
async function autoAdvance(id) {{
  const btn = document.querySelector('[onclick^="autoAdvance"]');
  if (btn) btn.disabled = true;
  for (let i = 0; i < 30; i++) {{
    const resp = await fetch('/demo/tasks/' + id + '/advance', {{method:'POST'}});
    const data = await resp.json();
    if (data.state === 'completed' || !data.blocked === false) break;
    if (data.blocked) {{
      document.getElementById('advance-status').innerHTML =
        '<div class="disclaimer">Paused — approval required. '
        + 'Click <strong>Resume</strong> to continue.</div>';
      break;
    }}
  }}
  window.location.reload();
}}
</script>""",
    )


def _demo_approvals(items: list[object]) -> str:
    rows = "".join(
        f"""<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div><strong>{a.id}</strong> — {a.kind} (task: {a.task_id[:8]})</div>
    <div class="actions" style="margin:0">
      <form method="post" action="/approvals/{a.id}/approve" style="margin:0">
        <button>Approve</button>
      </form>
      <form method="post" action="/approvals/{a.id}/reject" style="margin:0">
        <button style="background:var(--red)">Reject</button>
      </form>
    </div>
  </div>
</div>"""
        for a in items
    )
    return _page("Approvals", f"<h1>Pending Approvals</h1>{rows}")
