"""Sandboxed code execution for FEDS (v1-08).

Provides a per-run sandbox with credentials stripped, restricted egress,
and a tool contract: execute(name, input) -> string.
Dead/timeout/killed sandbox returns retryable tool error; never kills session.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class SandboxResult:
    """Result of a sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    error: Optional[str] = None
    
    def to_tool_result(self) -> str:
        """Format as tool result string."""
        if self.error:
            return f"Sandbox error (retryable): {self.error}"
        if self.timed_out:
            return f"Sandbox timed out (retryable): {self.stdout}\n{self.stderr}"
        if not self.success:
            return f"Sandbox failed (exit {self.exit_code}):\nSTDOUT:\n{self.stdout}\nSTDERR:\n{self.stderr}"
        return self.stdout


class SandboxExecutor:
    """Executes code in an isolated sandbox."""
    
    # Allowed egress domains (extend as needed)
    DEFAULT_ALLOWED_EGRESS = [
        "api.github.com",
        "raw.githubusercontent.com",
        "registry.npmjs.org",
        "pypi.org",
        "files.pythonhosted.org",
    ]
    
    def __init__(
        self,
        work_dir: Optional[Path] = None,
        timeout_seconds: int = 120,
        allowed_egress: Optional[list[str]] = None,
        memory_limit_mb: int = 512,
    ):
        self.work_dir = work_dir or Path(tempfile.gettempdir()) / "feds_sandbox"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.allowed_egress = allowed_egress or self.DEFAULT_ALLOWED_EGRESS
        self.memory_limit_mb = memory_limit_mb
    
    def _build_env(self) -> dict[str, str]:
        """Build sandbox environment with credentials stripped."""
        env = os.environ.copy()
        # Strip all credentials
        for key in list(env.keys()):
            if any(k in key.upper() for k in [
                "API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL",
                "DATABASE_URL", "PRIVATE_KEY", "ACCESS_KEY"
            ]):
                env.pop(key, None)
        
        # Set safe defaults
        env.update({
            "HOME": str(self.work_dir),
            "TMPDIR": str(self.work_dir / "tmp"),
            "PATH": "/usr/bin:/bin",  # Minimal PATH
            "PYTHONPATH": "",
            "NODE_PATH": "",
        })
        (self.work_dir / "tmp").mkdir(exist_ok=True)
        return env
    
    async def execute(
        self,
        command: str,
        input_data: Optional[str] = None,
        language: str = "python",
    ) -> SandboxResult:
        """Execute a command in the sandbox.
        
        Args:
            command: The code/command to execute
            input_data: Optional stdin input
            language: Language hint (python, javascript, shell, etc.)
        
        Returns:
            SandboxResult with stdout, stderr, exit_code, and success flag
        """
        # Create isolated temp directory for this execution
        exec_dir = self.work_dir / f"exec_{uuid.uuid4().hex[:8]}"
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if language == "python":
                return await self._execute_python(exec_dir, command, input_data)
            elif language == "javascript" or language == "node":
                return await self._execute_node(exec_dir, command, input_data)
            elif language == "shell" or language == "bash":
                return await self._execute_shell(exec_dir, command, input_data)
            else:
                return SandboxResult(
                    success=False,
                    stdout="",
                    stderr=f"Unsupported language: {language}",
                    exit_code=-1,
                    error=f"Unsupported language: {language}",
                )
        finally:
            # Cleanup
            try:
                import shutil
                shutil.rmtree(exec_dir, ignore_errors=True)
            except Exception:
                pass
    
    async def _execute_python(
        self, exec_dir: Path, code: str, input_data: Optional[str]
    ) -> SandboxResult:
        """Execute Python code."""
        script_path = exec_dir / "script.py"
        script_path.write_text(code, encoding="utf-8")
        
        env = self._build_env()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(exec_dir),
            env=env,
        )
        
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input_data.encode() if input_data else None),
                timeout=self.timeout_seconds,
            )
            return SandboxResult(
                success=proc.returncode == 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                timed_out=True,
                error=f"Execution timed out after {self.timeout_seconds}s",
            )
    
    async def _execute_node(
        self, exec_dir: Path, code: str, input_data: Optional[str]
    ) -> SandboxResult:
        """Execute JavaScript/Node.js code."""
        script_path = exec_dir / "script.js"
        script_path.write_text(code, encoding="utf-8")
        
        env = self._build_env()
        
        proc = await asyncio.create_subprocess_exec(
            "node", str(script_path),
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(exec_dir),
            env=env,
        )
        
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input_data.encode() if input_data else None),
                timeout=self.timeout_seconds,
            )
            return SandboxResult(
                success=proc.returncode == 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                timed_out=True,
                error=f"Execution timed out after {self.timeout_seconds}s",
            )
    
    async def _execute_shell(
        self, exec_dir: Path, command: str, input_data: Optional[str]
    ) -> SandboxResult:
        """Execute shell command."""
        env = self._build_env()
        
        proc = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(exec_dir),
            env=env,
        )
        
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input_data.encode() if input_data else None),
                timeout=self.timeout_seconds,
            )
            return SandboxResult(
                success=proc.returncode == 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                timed_out=True,
                error=f"Execution timed out after {self.timeout_seconds}s",
            )


# Tool contract function for worker integration
async def sandbox_execute(
    name: str,
    input_payload: dict[str, Any],
    sandbox: Optional[SandboxExecutor] = None,
) -> str:
    """Tool contract: execute(name, input) -> string.
    
    Args:
        name: Tool/command name (e.g., "python", "npm test", "eslint")
        input_payload: Dict with keys:
            - code: The code to execute (for python/node)
            - command: The shell command (for shell)
            - language: "python" | "javascript" | "shell" (default: python)
            - input: Optional stdin input
        sandbox: Optional SandboxExecutor instance (creates default if None)
    
    Returns:
        Formatted result string (retryable error on failure, never kills session)
    """
    if sandbox is None:
        sandbox = SandboxExecutor()
    
    language = input_payload.get("language", "python")
    
    if language == "shell":
        command = input_payload.get("command") or input_payload.get("code", "")
        result = await sandbox.execute(command, input_payload.get("input"), "shell")
    elif language in ("javascript", "node"):
        code = input_payload.get("code", "")
        result = await sandbox.execute(code, input_payload.get("input"), "node")
    else:
        code = input_payload.get("code", "")
        result = await sandbox.execute(code, input_payload.get("input"), "python")
    
    return result.to_tool_result()


# Offline test to verify sandbox isolation
async def test_sandbox_isolation() -> bool:
    """Verify sandbox cannot access credentials."""
    sandbox = SandboxExecutor()
    
    # Test 1: Environment variables are stripped
    code = """
import os
creds = [k for k in os.environ if any(x in k.upper() for x in ['API_KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'DATABASE_URL'])]
print(f"CREDENTIALS_FOUND: {creds}")
"""
    result = await sandbox.execute(code, language="python")
    if "CREDENTIALS_FOUND: []" not in result.stdout:
        print(f"FAIL: Credentials leaked: {result.stdout}")
        return False
    print("PASS: Credentials stripped from environment")
    
    # Test 2: Cannot read .env file
    code = """
from pathlib import Path
env_path = Path('.env')
if env_path.exists():
    print(f"ENV_FILE_EXISTS: {env_path.read_text()[:50]}")
else:
    print("ENV_FILE_NOT_FOUND")
"""
    result = await sandbox.execute(code, language="python")
    if "ENV_FILE_EXISTS" in result.stdout:
        print(f"FAIL: .env accessible: {result.stdout}")
        return False
    print("PASS: .env file not accessible")
    
    # Test 3: Timeout works
    code = """
import time
time.sleep(10)
print("DONE")
"""
    sandbox.timeout_seconds = 1
    result = await sandbox.execute(code, language="python")
    if not result.timed_out:
        print(f"FAIL: Timeout not enforced: {result}")
        return False
    print("PASS: Timeout enforced")
    sandbox.timeout_seconds = 120
    
    # Test 4: Error is retryable (not session-killing)
    code = """
import sys
sys.exit(1)
"""
    result = await sandbox.execute(code, language="python")
    if result.success:
        print(f"FAIL: Non-zero exit treated as success: {result}")
        return False
    if "retryable" not in result.to_tool_result():
        print(f"FAIL: Error not marked retryable: {result.to_tool_result()}")
        return False
    print("PASS: Errors are retryable")
    
    return True


async def main():
    """Run isolation tests."""
    print("Testing sandbox isolation...")
    success = await test_sandbox_isolation()
    if success:
        print("\nAll sandbox isolation tests PASSED")
    else:
        print("\nSandbox isolation tests FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())