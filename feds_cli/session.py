"""Session management for FEDS CLI.

Sessions are stored as JSON in platform-specific config directory
or repo-local .feds/sessions/ for development.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import platformdirs

from feds_cli.models import Session


def get_sessions_dir() -> Path:
    """Get the sessions directory, preferring platform config dir."""
    # Check if we're in a development environment (repo has .git)
    cwd = Path.cwd()
    repo_sessions = cwd / ".feds" / "sessions"
    if (cwd / ".git").exists() and repo_sessions.exists():
        return repo_sessions
    if (cwd / ".git").exists():
        repo_sessions.mkdir(parents=True, exist_ok=True)
        return repo_sessions

    # Otherwise use platform config dir
    config_dir = Path(platformdirs.user_data_dir("feds", "feds-cli"))
    sessions_dir = config_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def new_session_id() -> str:
    """Generate a new session ID."""
    return f"sess_{uuid.uuid4().hex[:12]}"


def generate_title(first_user_message: str) -> str:
    """Generate a session title from first user message."""
    # Truncate to 50 chars, strip newlines
    title = first_user_message.strip().replace("\n", " ")
    if len(title) > 50:
        title = title[:47] + "..."
    return title or "New Session"


def save_session(session: Session) -> Path:
    """Save session to JSON file."""
    sessions_dir = get_sessions_dir()
    session.updated_at = datetime.now().isoformat()
    file_path = sessions_dir / f"{session.id}.json"
    
    # Convert to dict for JSON serialization
    data = session.model_dump(mode="json")
    file_path.write_text(json.dumps(data, indent=2))
    return file_path


def load_session(session_id: str) -> Optional[Session]:
    """Load session from JSON file."""
    sessions_dir = get_sessions_dir()
    file_path = sessions_dir / f"{session_id}.json"
    if not file_path.exists():
        return None
    data = json.loads(file_path.read_text())
    return Session.model_validate(data)


def list_sessions() -> list[dict[str, Any]]:
    """List all sessions with basic metadata."""
    sessions_dir = get_sessions_dir()
    sessions = []
    for file_path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(file_path.read_text())
            sessions.append({
                "id": data.get("id"),
                "title": data.get("title"),
                "cwd": data.get("cwd"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sessions


def delete_session(session_id: str) -> bool:
    """Delete a session file."""
    sessions_dir = get_sessions_dir()
    file_path = sessions_dir / f"{session_id}.json"
    if file_path.exists():
        file_path.unlink()
        return True
    return False