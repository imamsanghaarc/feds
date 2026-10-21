# FEDS KSoR Integration (Rung 1)

This directory contains the KSoR (Knowledge System of Record) integration for FEDS at Rung 1.

## Structure

```
feds-ksor/
├── package.json          # Node.js project with KSoR dependency
├── knowledge/            # Governed knowledge base (OKF format)
│   ├── frontend-development/
│   ├── html/
│   ├── css/
│   ├── javascript/
│   ├── typescript/
│   └── ... (35 skills total)
├── scripts/
│   └── migrate-skills.js # Migration from .claude/skills/
├── llms.txt              # Machine-readable index
└── ksor.config.json      # KSoR configuration
```

## Quick Start

```bash
cd feds-ksor
npm install
npm run migrate    # Migrate skills from .claude/skills/
npm run build      # Validate and build KSoR knowledge base
```

## KSoR Rung 1 Scope

Rung 1 provides:
- **Governed knowledge**: All skills migrated to OKF (Open Knowledge Format) with required frontmatter
- **Build gate**: `ksor build` validates frontmatter; drafts never reach agent surfaces
- **Machine surfaces**: `llms.txt` generated for agent consumption
- **Human site**: KSoR can generate a browsable documentation site

## Boundaries

| Domain | System |
|--------|--------|
| Institutional/method knowledge (skills, patterns, checklists) | **KSoR** |
| Tasks, memories, workspace state, audit | **FEDS (Neon DB)** |

Do not duplicate `find_similar_tasks` over KSoR content. KSoR is for *method knowledge*; FEDS DB is for *workspace state*.

## Governance Frontmatter (OKF)

Every document in `knowledge/` must have:

```yaml
---
title: "Skill Name"
description: "One-line description"
owner: "feds-team"
audience: ["public"]
status: "draft"          # draft | stable | deprecated
sources: []              # reference files
freshness: "2026-10-21"  # ISO date
lifecycle: "active"      # active | archived
tags: ["feds", "skill"]
version: "1.0.0"
---
```

**Status lifecycle:**
- `draft` - New or modified, not yet reviewed
- `stable` - Reviewed, approved for agent consumption
- `deprecated` - Superseded or retired

## CI Integration

The GitHub Actions workflow runs `npm run check` on every push:
- Validates all frontmatter
- Ensures `status: stable` docs have all required fields
- Fails if a draft would be served to agents

## Migration

Run once to migrate existing skills:

```bash
npm run migrate
```

This reads from `.claude/skills/` and writes OKF-formatted markdown to `knowledge/`.

## Next Steps (Rung 2+)

- Streamable HTTP MCP for agent-to-KSoR queries
- Second DSN for KSoR database
- Real-time skill updates via MCP