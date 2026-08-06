"""FastAPI application factory and routes for local TestForge WebUI."""

from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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
        return _page("TestForge", "<h1>TestForge</h1><p>Local WebUI running.</p>")

    @app.get("/tasks/{task_id}", response_class=HTMLResponse)
    def task_detail(task_id: str) -> HTMLResponse:
        try:
            view = application.get_task_view(UUID(task_id))
        except Exception:
            return HTMLResponse(
                content=_page("Error", "<h1>Task not found</h1>"),
                status_code=404,
            )
        return _page(
            f"Task {task_id[:8]}",
            f"<h1>Task {task_id[:8]}</h1>"
            f"<p>State: {view.state}</p>"
            f"<p>Mutation score: {view.mutation_score}</p>"
            f"<p>{view.status_text}</p>",
        )

    @app.get("/approvals", response_class=HTMLResponse)
    def approvals_list() -> str:
        try:
            items = application.get_pending_approvals()
        except Exception:
            items = []
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
        return JSONResponse({"task_id": str(task.id)})

    @app.post("/demo/tasks/{task_id}/advance")
    def demo_advance(task_id: str) -> JSONResponse:
        if not demo_mode:
            return JSONResponse({"error": "demo mode only"}, status_code=403)
        task = application.advance_demo_task(UUID(task_id))
        return JSONResponse({
            "state": task.state.value if hasattr(task.state, 'value') else str(task.state),
            "attempts": [],
            "feedback": [],
        })

    @app.get("/settings")
    def settings_page() -> str:
        return _page("Settings", "<h1>Settings</h1><p>Credential status: OK</p>")

    return app


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title} — TestForge</title>
<style>body{{font-family:system-ui,sans-serif;max-width:800px;margin:2em auto}}
[aria-live]{{border-left:3px solid #0366d6;padding-left:1em}}</style></head>
<body>
<nav><a href="/">Home</a> | <a href="/approvals">Approvals</a> | <a href="/settings">Settings</a></nav>
<main aria-live="polite">{body}</main>
<script src="/static/htmx.min.js"></script>
</body></html>"""
