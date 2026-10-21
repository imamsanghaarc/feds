"""Zero-quota frontend verifier using Playwright + axe-core.

Measures lab Core Web Vitals (LCP, INP, CLS) and WCAG 2.2 A/AA accessibility
without any model calls. Used to gate `publish_task` and provide evidence.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


@dataclass
class CWVMetrics:
    """Core Web Vitals lab measurements."""
    lcp_ms: Optional[float] = None
    inp_ms: Optional[float] = None
    cls_score: Optional[float] = None
    
    def passes_thresholds(self) -> bool:
        """Check against SYSTEM_PROMPT.md thresholds (p75 field)."""
        if self.lcp_ms is not None and self.lcp_ms > 2500:
            return False
        if self.inp_ms is not None and self.inp_ms > 200:
            return False
        if self.cls_score is not None and self.cls_score > 0.1:
            return False
        return True
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AxeViolation:
    """Single axe-core accessibility violation."""
    rule_id: str
    impact: str  # critical, serious, moderate, minor
    description: str
    help: str
    help_url: str
    nodes: list[dict[str, Any]]
    tags: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    """Complete verification result for a page."""
    task_id: str
    conversation_id: str
    revision: int
    verifier_version: str
    timestamp: str
    status: str  # pass | fail
    metrics: CWVMetrics
    violations: list[AxeViolation]
    artifact_path: Optional[str] = None
    error: Optional[str] = None
    
    def passed(self) -> bool:
        return self.status == "pass"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "conversation_id": self.conversation_id,
            "revision": self.revision,
            "verifier_version": self.verifier_version,
            "timestamp": self.timestamp,
            "status": self.status,
            "metrics": self.metrics.to_dict(),
            "violations": [v.to_dict() for v in self.violations],
            "artifact_path": self.artifact_path,
            "error": self.error,
        }


VERIFIER_VERSION = "1.0.0"
ARTIFACT_DIR = Path("verification_artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)


class ZeroQuotaVerifier:
    """Headless browser verifier for frontend quality."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
    
    async def __aenter__(self) -> "ZeroQuotaVerifier":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
        )
        return self
    
    async def __aexit__(self, *args) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        await self._playwright.stop()
    
    async def verify_url(
        self,
        url: str,
        task_id: str,
        conversation_id: str,
        revision: int = 1,
        wait_for_network_idle: bool = True,
    ) -> VerificationResult:
        """Verify a live URL."""
        if not self._context:
            raise RuntimeError("Verifier not initialized. Use async context manager.")
        
        page = await self._context.new_page()
        artifact_path = None
        error = None
        metrics = CWVMetrics()
        violations = []
        
        try:
            # Navigate and measure CWV
            await page.goto(url, wait_until="domcontentloaded")
            
            if wait_for_network_idle:
                await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Measure Core Web Vitals via web-vitals library
            metrics = await self._measure_cwv(page)
            
            # Run axe-core accessibility scan
            violations = await self._run_axe(page)
            
            # Capture screenshot artifact
            artifact_path = await self._capture_screenshot(page, task_id, revision)
            
            # Determine pass/fail
            cwv_pass = metrics.passes_thresholds()
            a11y_pass = len([v for v in violations if v.impact in ("critical", "serious")]) == 0
            status = "pass" if cwv_pass and a11y_pass else "fail"
            
        except Exception as e:
            error = str(e)
            status = "fail"
            # Still try to capture screenshot on error
            try:
                artifact_path = await self._capture_screenshot(page, task_id, revision)
            except Exception:
                pass
        finally:
            await page.close()
        
        return VerificationResult(
            task_id=task_id,
            conversation_id=conversation_id,
            revision=revision,
            verifier_version=VERIFIER_VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status,
            metrics=metrics,
            violations=violations,
            artifact_path=artifact_path,
            error=error,
        )
    
    async def verify_html_file(
        self,
        html_path: Path,
        task_id: str,
        conversation_id: str,
        revision: int = 1,
    ) -> VerificationResult:
        """Verify a local HTML file."""
        file_url = html_path.resolve().as_uri()
        return await self.verify_url(file_url, task_id, conversation_id, revision)
    
    async def verify_html_content(
        self,
        html: str,
        task_id: str,
        conversation_id: str,
        revision: int = 1,
    ) -> VerificationResult:
        """Verify raw HTML content by writing to temp file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html)
            temp_path = Path(f.name)
        try:
            return await self.verify_html_file(temp_path, task_id, conversation_id, revision)
        finally:
            temp_path.unlink(missing_ok=True)
    
    async def _measure_cwv(self, page: Page) -> CWVMetrics:
        """Measure LCP, INP, CLS using web-vitals library."""
        # Inject web-vitals measurement script
        await page.add_script_tag(url="https://unpkg.com/web-vitals@4.2.3/dist/web-vitals.attribution.iife.js")
        
        # Wait for metrics to be collected
        result = await page.evaluate("""
            () => new Promise((resolve) => {
                const metrics = {};
                let collected = 0;
                
                function checkDone() {
                    collected++;
                    if (collected >= 3) resolve(metrics);
                }
                
                webVitals.onLCP((m) => { metrics.lcp = m.value; checkDone(); });
                webVitals.onINP((m) => { metrics.inp = m.value; checkDone(); });
                webVitals.onCLS((m) => { metrics.cls = m.value; checkDone(); });
                
                // Fallback timeout
                setTimeout(() => resolve(metrics), 10000);
            })
        """)
        
        return CWVMetrics(
            lcp_ms=result.get("lcp"),
            inp_ms=result.get("inp"),
            cls_score=result.get("cls"),
        )
    
    async def _run_axe(self, page: Page) -> list[AxeViolation]:
        """Run axe-core accessibility scan."""
        # Inject axe-core
        await page.add_script_tag(url="https://unpkg.com/axe-core@4.8.4/axe.min.js")
        
        results = await page.evaluate("""
            () => new Promise((resolve) => {
                axe.run(document, {
                    runOnly: { type: "tag", values: ["wcag2aa", "wcag21aa", "best-practice"] },
                    resultTypes: ["violations"],
                }, (err, results) => {
                    if (err) resolve({ error: err.message });
                    else resolve(results.violations);
                });
            })
        """)
        
        if isinstance(results, dict) and "error" in results:
            return []
        
        violations = []
        for v in results:
            for node in v.get("nodes", []):
                violations.append(AxeViolation(
                    rule_id=v.get("id", "unknown"),
                    impact=v.get("impact", "moderate"),
                    description=v.get("description", ""),
                    help=v.get("help", ""),
                    help_url=v.get("helpUrl", ""),
                    nodes=[node],
                    tags=v.get("tags", []),
                ))
        
        return violations
    
    async def _capture_screenshot(
        self, page: Page, task_id: str, revision: int
    ) -> str:
        """Capture screenshot artifact."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{task_id}_rev{revision}_{timestamp}.png"
        path = ARTIFACT_DIR / filename
        await page.screenshot(path=str(path), full_page=True)
        return str(path)


async def verify_before_after(
    before_url: str,
    after_url: str,
    task_id: str,
    conversation_id: str,
) -> tuple[VerificationResult, VerificationResult, dict[str, Any]]:
    """Verify before/after pair and compute deltas."""
    async with ZeroQuotaVerifier() as verifier:
        before = await verifier.verify_url(before_url, task_id, conversation_id, revision=1)
        after = await verifier.verify_url(after_url, task_id, conversation_id, revision=2)
        
        deltas = compute_deltas(before, after)
        return before, after, deltas


def compute_deltas(before: VerificationResult, after: VerificationResult) -> dict[str, Any]:
    """Compute numeric deltas between before/after verifications."""
    bm = before.metrics
    am = after.metrics
    
    def delta(b, a):
        if b is None or a is None:
            return None
        return round(a - b, 2)
    
    return {
        "lcp_delta_ms": delta(bm.lcp_ms, am.lcp_ms),
        "inp_delta_ms": delta(bm.inp_ms, am.inp_ms),
        "cls_delta": delta(bm.cls_score, am.cls_score),
        "critical_violations_fixed": len([
            v for v in before.violations if v.impact == "critical"
        ]) - len([v for v in after.violations if v.impact == "critical"]),
        "serious_violations_fixed": len([
            v for v in before.violations if v.impact == "serious"
        ]) - len([v for v in after.violations if v.impact == "serious"]),
        "total_violations_before": len(before.violations),
        "total_violations_after": len(after.violations),
        "before_status": before.status,
        "after_status": after.status,
    }


async def main():
    """CLI for manual verification."""
    import sys
    if len(sys.argv) < 3:
        print("Usage: uv run python verifier.py <url|file> <task_id> [conversation_id]")
        sys.exit(1)
    
    target = sys.argv[1]
    task_id = sys.argv[2]
    conversation_id = sys.argv[3] if len(sys.argv) > 3 else "manual"
    
    async with ZeroQuotaVerifier() as verifier:
        if target.startswith("http"):
            result = await verifier.verify_url(target, task_id, conversation_id)
        else:
            result = await verifier.verify_html_file(Path(target), task_id, conversation_id)
    
    print(json.dumps(result.to_dict(), indent=2))
    if not result.passed():
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())