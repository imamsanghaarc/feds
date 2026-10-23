"""Data models for FEDS CLI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in the conversation."""
    role: str  # "user" | "assistant" | "system"
    content: str
    ts: str = Field(default_factory=lambda: datetime.now().isoformat())
    thought: Optional[str] = None
    model: Optional[str] = None


class ContextSnapshot(BaseModel):
    """Snapshot of context state at a point in time."""
    skills_loaded: list[str] = Field(default_factory=list)
    files_references: list[str] = Field(default_factory=list)
    last_turn: dict[str, Any] = Field(default_factory=dict)


class SessionMeta(BaseModel):
    """Session metadata."""
    cli_version: str = "0.1.0"
    source: str = "feds-cli"


class Session(BaseModel):
    """A complete FEDS CLI session."""
    id: str
    title: str
    cwd: str
    git_root: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    messages: list[Message] = Field(default_factory=list)
    context: ContextSnapshot = Field(default_factory=ContextSnapshot)
    meta: SessionMeta = Field(default_factory=SessionMeta)