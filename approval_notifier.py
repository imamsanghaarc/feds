"""Approval pause notifications for FEDS (v1-14).

Slack webhook or email notifications when a run enters parked state.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NotificationConfig:
    """Notification configuration."""
    slack_webhook_url: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_from: Optional[str] = None
    enabled: bool = True


class ApprovalNotifier:
    """Sends notifications when approval is required."""
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig(
            slack_webhook_url=os.getenv("FEDS_SLACK_WEBHOOK_URL"),
            email_smtp_host=os.getenv("FEDS_EMAIL_SMTP_HOST"),
            email_smtp_port=int(os.getenv("FEDS_EMAIL_SMTP_PORT", "587")),
            email_username=os.getenv("FEDS_EMAIL_USERNAME"),
            email_password=os.getenv("FEDS_EMAIL_PASSWORD"),
            email_from=os.getenv("FEDS_EMAIL_FROM"),
        )
    
    async def notify_approval_required(
        self,
        run_id: str,
        conversation_id: str,
        tool_name: str,
        task_description: str = "",
        console_url: Optional[str] = None,
    ) -> None:
        """Send notification that approval is required."""
        if not self.config.enabled:
            return
        
        message = self._format_message(
            run_id=run_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            task_description=task_description,
            console_url=console_url,
        )
        
        # Send to all configured channels
        await asyncio.gather(
            self._send_slack(message),
            self._send_email(message),
            return_exceptions=True,
        )
    
    async def notify_approval_resolved(
        self,
        run_id: str,
        conversation_id: str,
        tool_name: str,
        decision: str,
        operator: str,
    ) -> None:
        """Send notification that approval was resolved (optional)."""
        if not self.config.enabled:
            return
        
        message = self._format_resolution_message(
            run_id=run_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            decision=decision,
            operator=operator,
        )
        
        await asyncio.gather(
            self._send_slack(message),
            self._send_email(message),
            return_exceptions=True,
        )
    
    def _format_message(
        self,
        run_id: str,
        conversation_id: str,
        tool_name: str,
        task_description: str,
        console_url: Optional[str],
    ) -> dict:
        """Format notification message."""
        lines = [
            "🔔 **FEDS Approval Required**",
            f"**Run ID:** `{run_id}`",
            f"**Conversation:** `{conversation_id}`",
            f"**Tool:** `{tool_name}`",
        ]
        
        if task_description:
            lines.append(f"**Task:** {task_description[:200]}")
        
        lines.append("")
        lines.append("**Action Required:** Approve or reject this run.")
        
        if console_url:
            lines.append(f"**Console:** {console_url}/approvals/{run_id}")
        else:
            lines.append(f"**CLI:** `uv run python worker.py --decide {run_id} approve [operator]`")
        
        lines.append("")
        lines.append(f"_Timestamp: {datetime.now(timezone.utc).isoformat()}_")
        
        return {
            "text": "\n".join(lines),
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "🔔 FEDS Approval Required"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Run ID:*\n`{run_id}`"},
                    {"type": "mrkdwn", "text": f"*Tool:*\n`{tool_name}`"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
                {"type": "actions", "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "value": f"approve:{run_id}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "value": f"reject:{run_id}",
                    },
                ]} if console_url else {"type": "section", "text": {"type": "mrkdwn", "text": "Use the CLI to decide."}},
            ]
        }
    
    def _format_resolution_message(
        self,
        run_id: str,
        conversation_id: str,
        tool_name: str,
        decision: str,
        operator: str,
    ) -> dict:
        """Format resolution notification."""
        emoji = "✅" if decision == "approve" else "❌"
        text = (
            f"{emoji} **FEDS Approval {decision.capitalize()}d**\n"
            f"**Run ID:** `{run_id}`\n"
            f"**Conversation:** `{conversation_id}`\n"
            f"**Tool:** `{tool_name}`\n"
            f"**Decided by:** {operator}\n"
            f"_Timestamp: {datetime.now(timezone.utc).isoformat()}_"
        )
        return {"text": text}
    
    async def _send_slack(self, message: dict) -> None:
        """Send to Slack webhook."""
        if not self.config.slack_webhook_url:
            return
        
        # Use blocks if available, fallback to text
        payload = {
            "text": message.get("text", ""),
            "blocks": message.get("blocks", []),
        }
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.config.slack_webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        except Exception as e:
            print(f"Slack notification failed: {e}")
    
    async def _send_email(self, message: dict) -> None:
        """Send email notification (placeholder)."""
        # This is a placeholder - integrate with your email provider
        # (SendGrid, Mailgun, SES, etc.)
        pass


# Integration with worker: call from decide_run or when run parks
async def notify_on_park(
    run_id: str,
    conversation_id: str,
    tool_name: str,
    task_description: str = "",
) -> None:
    """Call this when a run parks for approval."""
    notifier = ApprovalNotifier()
    console_url = os.getenv("FEDS_CONSOLE_URL")
    await notifier.notify_approval_required(
        run_id=run_id,
        conversation_id=conversation_id,
        tool_name=tool_name,
        task_description=task_description,
        console_url=console_url,
    )


# Test function
async def test_notification():
    """Test notification sending."""
    notifier = ApprovalNotifier(NotificationConfig(
        slack_webhook_url=os.getenv("FEDS_SLACK_WEBHOOK_URL", ""),
        enabled=bool(os.getenv("FEDS_SLACK_WEBHOOK_URL")),
    ))
    
    await notifier.notify_approval_required(
        run_id="test-run-123",
        conversation_id="conv-456",
        tool_name="publish_task",
        task_description="Create responsive navbar component",
        console_url="https://console.example.com",
    )
    print("Test notification sent")


if __name__ == "__main__":
    asyncio.run(test_notification())