"""Seed the semantic reference library with varied, resolved frontend cases.

Decision 5 in plan.md: semantic search only proves it ranks by meaning when the
library contains cases that look alike on the surface but differ in substance,
plus genuinely distinct cases. The corpus below is hand-authored rather than
LLM-generated on purpose:

- It is deterministic and reviewable - each case can be read, argued with, and
  diffed in a commit.
- Regenerating it costs zero quota, so it is never wed to a provider.
- It contains deliberate confusable pairs (same main noun, different problem)
  so a ranker that keys on keywords is exposed.

Everything is written with source="frontend-task" and metadata "status":
"resolved" like a real completed task, so retrieval and re-embedding treat the
rows exactly like production data. Idempotent: already-stored titles are
skipped, so re-running adds nothing and re-embeds nothing.

Usage:
    uv run python seed_corpus.py            # dry-run: what would be added
    uv run python seed_corpus.py --apply    # insert the missing cases and embed them
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import asyncpg

from frontend_workspace_mcp.server import (
    NEON_DATABASE_URL,
    _chunk_text,
    _embed_texts,
    _EMBEDDING_MODELS,
    _embedding_order,
    _vector_literal,
)

SEED_CASES: list[dict[str, str]] = [
    {
        "title": "Navbar A: sticky header collapsed the hero section (resolved)",
        "body": (
            "Request: make the marketing site header stick while scrolling. Symptom: "
            "after switching from position: fixed to position: sticky, the hero banner "
            "was overlapped by the header and its height collapsed by 96px, pushing the "
            "first paint down and recycling layout on fast loads. Diagnosis: the header "
            "was still inside the normal flow, but an old spacer div sized for a fixed "
            "header kept reserving height. Fix: removed the spacer, placed the header in "
            "a grid row reserved with 1fr, and moved the banner into the remaining track. "
            "Outcome: no overlap, CLS back to 0.02 at p75, verified in RUM."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "navbar", "vitals": "cls"},
    },
    {
        "title": "Navbar B: megamenu keyboard traversal froze pointer input (resolved)",
        "body": (
            "Request: keyboard-accessible megamenu navigation. Symptom: tab order walked "
            "into hidden panels and the first arrow-key press made the menu swallow "
            "clicks for ~400ms; INP on the navigation group registered 610ms. Diagnosis: "
            "each panel re-rendered on hover and focus simultaneously because the open "
            "state lived in two states. Fix: single source of truth for open state, "
            "aria-expanded on one trigger, panels rendered once and toggled with the "
            "hidden attribute so no re-mount happens. Outcome: INP 130ms at p75 and full "
            "keyboard traversal verified."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "navbar", "vitals": "inp"},
    },
    {
        "title": "Button C: icon targets under 24px failed WCAG 2.2 AA (resolved)",
        "body": (
            "Request: pass the new WCAG 2.2 target-size rule on the article actions row. "
            "Symptom: three icon-only buttons measured 22x22px because the inline SVG "
            "shrank the hit box, and the page failed AA. Diagnosis: generous padding "
            "existed visually but the hit area followed the glyph box. Fix: enforced a "
            "24px CSS minimum with min-width/min-height and a negative-offset ::before "
            "hit area, without changing visual size. Outcome: AA re-audit passed and the "
            "row kept its density."
        ),
        "metadata": {
            "status": "resolved",
            "seed": True,
            "component": "button",
            "wcag_notes": "WCAG 2.2 target size minimum 24px; icon-only buttons need an enlarged hit area.",
        },
    },
    {
        "title": "Button D: CTA entrance transition ignored reduced motion (resolved)",
        "body": (
            "Request: stop the signup CTA from animating for vestibular users. Symptom: a "
            "900ms tab transition with a full-page translation played for everyone, and "
            "prefers-reduced-motion had no effect for this one element. Diagnosis: the "
            "keyframe animation lived in a scoped style block that excluded the shared "
            "reduced-motion rule. Fix: animation gate on @media (prefers-reduced-motion: "
            "no-preference) so the default is no motion, plus a cross-fade fallback. "
            "Outcome: motion audit clean and the CTA retained its affordance."
        ),
        "metadata": {
            "status": "resolved",
            "seed": True,
            "component": "button",
            "wcag_notes": "prefers-reduced-motion must disable non-essential movement.",
        },
    },
    {
        "title": "Form E: inline validation error text caused layout shift (resolved)",
        "body": (
            "Request: validate the address form inline. Symptom: error messages appeared "
            "below fields on submit and pushed the footer down, CLS hit 0.14 and mobile "
            "keyboarding made it worse. Diagnosis: messages were appended into the flow "
            "only when the error existed. Fix: pre-reserved message rows with a fixed "
            "min-height inside the field stack and aria-live polite on the container. "
            "Outcome: CLS 0.01 at p75, screen reader announcement verified."
        ),
        "metadata": {
            "status": "resolved",
            "seed": True,
            "component": "form",
            "wcag_notes": "aria-live polite announces validation; reserved space prevents shift.",
        },
    },
    {
        "title": "Form F: duplicate submit clicks created two orders (resolved)",
        "body": (
            "Request: investigate double order events from the checkout form. Symptom: "
            "about 3% of orders duplicated on slow connections; the network tab showed "
            "two POSTs fired 900ms apart. Diagnosis: the submit button stayed enabled "
            "while the request was in flight, and the handler was not idempotent. Fix: "
            "moved the disabled state into the request lifecycle instead of relying on "
            "the response, and deduplicated by a client request id. Outcome: zero "
            "duplicates in the following week."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "form", "vitals": "inp"},
    },
    {
        "title": "Gallery G: LCP image above the fold was lazy-loaded (resolved)",
        "body": (
            "Request: the homepage cover image loads late on 4G. Symptom: LCP measured "
            "4.1s; the cover image is the largest element and was being decoded after "
            "hydration. Diagnosis: the global lazy-loading data attribute applied to "
            "everything, including above-the-fold media. Fix: eager loading and a "
            "preload with fetchpriority high for the cover, with a responsive srcset at "
            "the actual viewport width. Outcome: LCP 1.9s at p75."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "image-gallery", "vitals": "lcp"},
    },
    {
        "title": "Gallery H: lazy scroll jitter from unreserved image slots (resolved)",
        "body": (
            "Request: the gallery page wobbles while scrolling on phones. Symptom: rows "
            "jumped as images arrived because every card was sized by its intrinsic "
            "image. Diagnosis: no width or height attributes, so the grid re-measured "
            "each cell on decode. Fix: enforced an aspect-ratio per card from the CMS "
            "metadata and reserved each slot before the source is loaded. Outcome: "
            "scroll smoothness confirmed, CLS 0.03 at p75."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "image-gallery", "vitals": "cls"},
    },
    {
        "title": "Table I: 5,000-row report froze the main thread (resolved)",
        "body": (
            "Request: display the full operations report, up to 5,000 rows, in the "
            "browser. Symptom: an initial paint of all rows took 6s on the mid-range QA "
            "laptop and blocked input, INP unmeasurable. Diagnosis: every row built one "
            "DOM node with live listeners. Fix: windowed virtualization of 40 rows, "
            "keyboard-accessible scrolling kept inside the grid, and sort applied on the "
            "model instead of the DOM. Outcome: INP 140ms at p75 and the report stays "
            "usable on the same laptop."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "data-table", "vitals": "inp"},
    },
    {
        "title": "Table J: sortable headers were divs, not buttons (resolved)",
        "body": (
            "Request: make the report table sortable by any column. Symptom: worked for "
            "the mouse but keyboard users could not reach the headers, and the audit "
            "flagged interactive divs. Diagnosis: header markup used a styled div with a "
            "click handler. Fix: button inside the th with aria-sort updated on the "
            "column, focus ring restored, and Enter and Space behavior verified. Outcome: "
            "axe report clean and column sorting reachable by keyboard alone."
        ),
        "metadata": {
            "status": "resolved",
            "seed": True,
            "component": "data-table",
            "wcag_notes": "Interactive controls must be real buttons; aria-sort communicates column state.",
        },
    },
    {
        "title": "Modal K: focus walked into background content (resolved)",
        "body": (
            "Request: confirm dialog for destructive bulk actions. Symptom: after the "
            "dialog opened, tabbing reached links behind the overlay, and closing the "
            "dialog left focus nowhere. Diagnosis: a div overlay was rendered without "
            "restrain on the base layer. Fix: native dialog element, focus placed on the "
            "confirm control on open, returned to the invoking button on close, and acts "
            "as an inert backdrop. Outcome: keyboard-only walkthrough passes and the "
            "escape key closes it."
        ),
        "metadata": {
            "status": "resolved",
            "seed": True,
            "component": "modal",
            "wcag_notes": "Dialog focus is trapped and restored; background is inert.",
        },
    },
    {
        "title": "Theme L: dark mode switch flickered white on every load (resolved)",
        "body": (
            "Request: add a dark theme with a user toggle. Symptom: a white flash on "
            "every visit between the HTML paint and the first hydration tick. Diagnosis: "
            "the theme class was applied from a hydration callback after first paint. "
            "Fix: an inline script in the head resolved the saved preference before any "
            "render, the CSS variable set is present in the root scope, and the toggle "
            "around the three options is reachable without the pointer. Outcome: no "
            "flash in repeat visits and the toggle is keyboard operable."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "theme-toggle", "vitals": "lcp"},
    },
    {
        "title": "Dashboard M: skeleton placeholders pushed charts down (resolved)",
        "body": (
            "Request: loading skeletons for the analytics dashboard. Symptom: when real "
            "charts replaced the skeletons the whole grid re-flowed, CLS 0.18. Diagnosis: "
            "skeleton blocks had no intrinsic size, so their heights differed from the "
            "real components. Fix: fixed aspect ratio boxes matching each widget and "
            "skeletons that use the same grid tracks. Outcome: CLS 0.02 at p75 and the "
            "skeleton-to-chart swap is visually stable."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "dashboard", "vitals": "cls"},
    },
    {
        "title": "Chart N: hover tooltip chased the cursor and jittered (resolved)",
        "body": (
            "Request: tooltips on the revenue chart. Symptom: the tooltip repainted on "
            "every pointermove with a position jump around the plot edges, and pointer "
            "input felt laggy on the laptop trackpad. Diagnosis: the tooltip was "
            "absolutely positioned inside the same stetted layer that recomputed on each "
            "event, also triggering a chart-cache rebuild. Fix: positions determined by "
            "a transform on a dedicated overlay layer, move events coalesced to one "
            "frame, and edge clamping replaced the reflow. Outcome: tooltip tracking is "
            "smooth and pointer latency on the chart is unchanged."
        ),
        "metadata": {"status": "resolved", "seed": True, "component": "chart", "vitals": "inp"},
    },
]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="insert missing cases and embed them (default: dry-run)"
    )
    args = parser.parse_args()
    apply = args.apply

    order = _embedding_order()
    model = _EMBEDDING_MODELS[order[0]]

    pool = await asyncpg.create_pool(
        NEON_DATABASE_URL,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
        ssl="require",
    )
    try:
        rows = await pool.fetch(
            "SELECT lower(title) AS title FROM documents WHERE source = 'frontend-task'"
        )
        existing = {row["title"] for row in rows}

        fresh = [case for case in SEED_CASES if case["title"].lower() not in existing]
        print(f"seed corpus size : {len(SEED_CASES)} cases")
        print(f"already stored   : {len(SEED_CASES) - len(fresh)}")
        print(f"to insert        : {len(fresh)}")
        print(f"embedding model  : {model}")
        for case in fresh:
            print(f"  - {case['title']}")
        if not apply:
            print("\nDRY RUN. Re-run with --apply to insert and embed.")
            return 0
        if not fresh:
            print("\nnothing to do: every seed case is already stored.")
            return 0

        inserted = 0
        for case in fresh:
            wcag = case["metadata"].get("wcag_notes", "")
            # Same convention as reembed.py: the stored chunk stays the raw
            # body text, while the embedding input carries the title and the
            # accessibility context so retrieval keys on meaning.
            chunks = _chunk_text(case["body"]) or [case["body"]]
            inputs = [f"{case['title']}. {chunk}. {wcag}".strip() for chunk in chunks]
            vectors, used_model = await _embed_texts(inputs)

            async with pool.acquire() as conn:
                async with conn.transaction():
                    document_id = await conn.fetchval(
                        """
                        INSERT INTO documents (source, title, body, metadata)
                        VALUES ($1, $2, $3, $4::jsonb)
                        RETURNING id
                        """,
                        "frontend-task",
                        case["title"],
                        case["body"],
                        json.dumps(case["metadata"]),
                    )
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                        await conn.execute(
                            """
                            INSERT INTO embeddings
                                (document_id, chunk_text, chunk_index, embedding, model)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            document_id,
                            chunk[:6000],
                            index,
                            _vector_literal(vector),
                            used_model,
                        )
            inserted += 1
            print(f"  seeded {case['title']!r} ({len(inputs)} chunks, {used_model})")

        print(f"\ndone: {inserted} seed cases inserted and embedded.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
