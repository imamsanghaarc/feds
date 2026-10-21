"""Budget and cost alert system for FEDS (v1-12).

Monthly budget per workspace/user, computed from capability_invocations rollups.
Warning threshold and hard cap; hard cap blocks new turns via guardrail path.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import asyncpg

from config import DATABASE_URL


@dataclass
class BudgetConfig:
    """Budget configuration for a workspace."""
    workspace_id: str
    monthly_budget_cents: int
    warning_threshold_pct: float = 0.8  # 80%
    hard_cap_enabled: bool = True
    alert_recipients: list[str] = None  # email/slack webhook URLs
    
    def __post_init__(self):
        if self.alert_recipients is None:
            self.alert_recipients = []


@dataclass
class BudgetStatus:
    """Current budget status."""
    workspace_id: str
    period_start: datetime
    period_end: datetime
    spent_cents: int
    budget_cents: int
    remaining_cents: int
    pct_used: float
    status: str  # ok | warning | exceeded
    
    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "spent_cents": self.spent_cents,
            "budget_cents": self.budget_cents,
            "remaining_cents": self.remaining_cents,
            "pct_used": round(self.pct_used, 2),
            "status": self.status,
        }


class BudgetManager:
    """Manages budgets and cost alerts."""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
    
    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=3,
                statement_cache_size=0,
                ssl="require",
            )
        return self._pool
    
    async def close(self):
        if self._pool:
            await self._pool.close()
    
    async def get_current_period_spending(self, workspace_id: str) -> int:
        """Get total cost_cents for current month (NULL costs excluded)."""
        pool = await self._get_pool()
        now = datetime.now(timezone.utc)
        period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        
        async with pool.acquire() as conn:
            # Sum cost_cents from capability_invocations, excluding NULL
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(cost_cents), 0) as total
                FROM capability_invocations ci
                JOIN conversations c ON ci.conversation_id = c.session_id
                WHERE c.metadata->>'workspace_id' = $1
                  AND ci.cost_cents IS NOT NULL
                  AND ci.created_at >= $2
                  AND ci.created_at < $3
            """, workspace_id, period_start, period_end)
            return row["total"] or 0
    
    async def get_budget_status(self, workspace_id: str) -> BudgetStatus:
        """Get current budget status for workspace."""
        pool = await self._get_pool()
        now = datetime.now(timezone.utc)
        period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        
        # Get budget config
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT monthly_budget_cents, warning_threshold_pct, hard_cap_enabled
                FROM workspace_budgets
                WHERE workspace_id = $1
            """, workspace_id)
        
        if not row:
            # No budget set - return ok status
            return BudgetStatus(
                workspace_id=workspace_id,
                period_start=period_start,
                period_end=period_end,
                spent_cents=0,
                budget_cents=0,
                remaining_cents=0,
                pct_used=0.0,
                status="ok",
            )
        
        spent = await self.get_current_period_spending(workspace_id)
        budget = row["monthly_budget_cents"]
        remaining = budget - spent
        pct_used = (spent / budget * 100) if budget > 0 else 0
        
        if spent >= budget and row["hard_cap_enabled"]:
            status = "exceeded"
        elif pct_used >= row["warning_threshold_pct"] * 100:
            status = "warning"
        else:
            status = "ok"
        
        return BudgetStatus(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            spent_cents=spent,
            budget_cents=budget,
            remaining_cents=max(0, remaining),
            pct_used=pct_used,
            status=status,
        )
    
    async def set_budget(
        self,
        workspace_id: str,
        monthly_budget_cents: int,
        warning_threshold_pct: float = 0.8,
        hard_cap_enabled: bool = True,
        alert_recipients: list[str] = None,
    ) -> None:
        """Set or update budget for workspace."""
        if alert_recipients is None:
            alert_recipients = []
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO workspace_budgets (workspace_id, monthly_budget_cents, warning_threshold_pct, hard_cap_enabled, alert_recipients, updated_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
                ON CONFLICT (workspace_id) DO UPDATE SET
                    monthly_budget_cents = EXCLUDED.monthly_budget_cents,
                    warning_threshold_pct = EXCLUDED.warning_threshold_pct,
                    hard_cap_enabled = EXCLUDED.hard_cap_enabled,
                    alert_recipients = EXCLUDED.alert_recipients,
                    updated_at = NOW()
            """, workspace_id, monthly_budget_cents, warning_threshold_pct, hard_cap_enabled, json.dumps(alert_recipients))
    
    async def check_hard_cap(self, workspace_id: str) -> tuple[bool, str]:
        """Check if hard cap is exceeded. Returns (allowed, reason)."""
        status = await self.get_budget_status(workspace_id)
        if status.status == "exceeded":
            return False, f"Hard cap exceeded: spent {status.spent_cents} cents of {status.budget_cents} cents budget"
        return True, ""
    
    async def send_alert(self, workspace_id: str, status: BudgetStatus) -> None:
        """Send budget alert to recipients."""
        # Get budget config for recipients
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT alert_recipients FROM workspace_budgets WHERE workspace_id = $1
            """, workspace_id)
        
        if not row or not row["alert_recipients"]:
            return
        
        recipients = row["alert_recipients"]
        message = self._format_alert_message(status)
        
        for recipient in recipients:
            try:
                if recipient.startswith("http"):
                    # Slack/webhook
                    await self._send_webhook(recipient, message)
                elif "@" in recipient:
                    # Email (placeholder)
                    await self._send_email(recipient, f"FEDS Budget Alert: {status.workspace_id}", message)
            except Exception as e:
                # Log but don't fail
                print(f"Failed to send budget alert to {recipient}: {e}")
    
    def _format_alert_message(self, status: BudgetStatus) -> str:
        emoji = "🔴" if status.status == "exceeded" else "🟡"
        return (
            f"{emoji} FEDS Budget Alert for {status.workspace_id}\n"
            f"Status: {status.status.upper()}\n"
            f"Spent: {status.spent_cents/100:.2f} / {status.budget_cents/100:.2f} USD\n"
            f"Usage: {status.pct_used:.1f}%\n"
            f"Remaining: {status.remaining_cents/100:.2f} USD\n"
            f"Period: {status.period_start.date()} to {status.period_end.date()}"
        )
    
    async def _send_webhook(self, url: str, message: str) -> None:
        import urllib.request
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    
    async def _send_email(self, to: str, subject: str, body: str) -> None:
        # Placeholder - integrate with your email provider
        pass
    
    async def run_periodic_check(self) -> None:
        """Run periodic budget check for all workspaces with budgets."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT workspace_id FROM workspace_budgets")
        
        for row in rows:
            status = await self.get_budget_status(row["workspace_id"])
            if status.status in ("warning", "exceeded"):
                await self.send_alert(row["workspace_id"], status)


# Guardrail function to enforce hard cap
async def budget_hard_cap_guardrail(ctx, agent, user_input) -> bool:
    """Guardrail that blocks turns when hard cap exceeded.
    
    Returns True if allowed, False if blocked.
    """
    # Extract workspace_id from conversation context
    # This would need integration with your conversation/workspace mapping
    workspace_id = os.getenv("FEDS_WORKSPACE_ID", "default")
    
    manager = BudgetManager()
    try:
        allowed, reason = await manager.check_hard_cap(workspace_id)
        if not allowed:
            # Log to audit
            pool = await manager._get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO audit_log (conversation_id, actor, action, target, payload, result)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                """, workspace_id, "worker:guardrail", "budget_hard_cap", "turn", 
                    json.dumps({"reason": reason}), json.dumps({"status": "blocked"}))
            return False
        return True
    finally:
        await manager.close()


# CLI for budget management
async def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="FEDS Budget Management")
    subparsers = parser.add_subparsers(dest="command")
    
    set_parser = subparsers.add_parser("set", help="Set budget")
    set_parser.add_argument("workspace_id")
    set_parser.add_argument("budget_usd", type=float)
    set_parser.add_argument("--warning", type=float, default=80, help="Warning threshold %")
    set_parser.add_argument("--hard-cap", action="store_true", default=True)
    set_parser.add_argument("--recipients", nargs="*", default=[])
    
    status_parser = subparsers.add_parser("status", help="Show budget status")
    status_parser.add_argument("workspace_id")
    
    check_parser = subparsers.add_parser("check", help="Run periodic check")
    
    args = parser.parse_args()
    
    manager = BudgetManager()
    try:
        if args.command == "set":
            await manager.set_budget(
                args.workspace_id,
                int(args.budget_usd * 100),
                args.warning / 100,
                args.hard_cap,
                args.recipients,
            )
            print(f"Budget set for {args.workspace_id}: ${args.budget_usd:.2f}/month")
        elif args.command == "status":
            status = await manager.get_budget_status(args.workspace_id)
            print(json.dumps(status.to_dict(), indent=2))
        elif args.command == "check":
            await manager.run_periodic_check()
            print("Periodic check complete")
        else:
            parser.print_help()
    finally:
        await manager.close()


if __name__ == "__main__":
    import json
    asyncio.run(main())