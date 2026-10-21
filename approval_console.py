"""Approval Console - Web UI for FEDS approval workflow (v1-10).

Simple FastAPI server that:
- Lists parked runs from run_states
- Shows conversation trail from audit_log
- Approve/reject with operator attribution
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import asyncpg
from config import DATABASE_URL, operator_authorized

app = FastAPI(title="FEDS Approval Console", version="1.0.0")
templates = Jinja2Templates(directory="templates")

# --- Database pool ---
_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            statement_cache_size=0,
            ssl="require",
        )
    return _pool

@app.on_event("shutdown")
async def shutdown():
    global _pool
    if _pool:
        await _pool.close()

# --- Models ---
class DecisionRequest(BaseModel):
    run_id: str
    decision: str  # "approve" or "reject"
    operator: str

# --- Helpers ---
async def get_parked_runs() -> List[dict]:
    """Get all parked approval runs with context."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                rs.run_id,
                rs.conversation_id,
                rs.tool_name,
                rs.state_text,
                rs.status,
                rs.created_at,
                rs.updated_at,
                c.metadata->>'workspace_id' as workspace_id,
                c.summary
            FROM run_states rs
            LEFT JOIN conversations c ON rs.conversation_id = c.session_id
            WHERE rs.status = 'awaiting'
            ORDER BY rs.created_at DESC
        """)
        return [dict(row) for row in rows]

async def get_conversation_trail(conversation_id: str) -> List[dict]:
    """Get audit trail for a conversation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT actor, action, target, payload, result, created_at
            FROM audit_log
            WHERE conversation_id = $1
            ORDER BY created_at ASC
        """, conversation_id)
        return [dict(row) for row in rows]

async def get_task_context(conversation_id: str) -> Optional[dict]:
    """Get task details from conversation metadata."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT metadata, summary FROM conversations WHERE session_id = $1
        """, conversation_id)
        return dict(row) if row else None

async def decide_run_db(run_id: str, decision: str, operator: str) -> bool:
    """Apply decision using existing worker logic (import and call decide_run)."""
    from worker import decide_run
    return await decide_run(run_id, decision, operator)

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard showing parked runs."""
    runs = await get_parked_runs()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "runs": runs,
        "title": "FEDS Approval Console",
    })

@app.get("/run/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """Detail view for a parked run with conversation trail."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow("""
            SELECT * FROM run_states WHERE run_id = $1
        """, run_id)
    
    if not run:
        raise HTTPException(404, "Run not found")
    
    run = dict(run)
    trail = await get_conversation_trail(run["conversation_id"])
    task_context = await get_task_context(run["conversation_id"])
    
    return templates.TemplateResponse("run_detail.html", {
        "request": request,
        "run": run,
        "trail": trail,
        "task_context": task_context,
        "title": f"Run {run_id[:8]}",
    })

@app.post("/run/{run_id}/decide")
async def decide_run_endpoint(
    run_id: str,
    decision: str = Form(...),
    operator: str = Form(...),
):
    """Apply approve/reject decision."""
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "Decision must be 'approve' or 'reject'")
    
    if not operator.strip():
        raise HTTPException(400, "Operator name required")
    
    # Check operator authorization
    if not operator_authorized(operator):
        raise HTTPException(403, f"Operator '{operator}' not authorized. Set FEDS_ALLOWED_OPERATORS.")
    
    # Apply decision via worker's decide_run
    success = await decide_run_db(run_id, decision, operator)
    
    if not success:
        raise HTTPException(500, "Decision failed - check logs")
    
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/runs")
async def api_runs():
    """JSON API for parked runs."""
    runs = await get_parked_runs()
    return {"runs": runs}

@app.get("/api/run/{run_id}/trail")
async def api_trail(run_id: str):
    """JSON API for conversation trail."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow("SELECT conversation_id FROM run_states WHERE run_id = $1", run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        trail = await get_conversation_trail(run["conversation_id"])
    return {"trail": trail}

# --- Health check ---
@app.get("/health")
async def health():
    return {"status": "ok", "service": "FEDS Approval Console"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)