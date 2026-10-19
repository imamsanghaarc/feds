# Day 1 — Digital FTE Kickoff

**Digital FTE Role:** Frontend Developer  
**Primary Domain:** Website Development (Frontend Only)  
**Operating Tools:** All (Claude Code, OpenCode, Gemini CLI, Copilot, etc.)  
**Agency Division:** Engineering  
**Day 1 Priority:** Basic setup first

---

## 1. Purpose

This Digital FTE will function as a **Frontend Developer** agent specialized in website development (frontend only). It will assist with building, reviewing, and optimizing web interfaces and user experiences.

## 2. What Was Decided Today

- **Role:** Frontend Developer — focused on website development, UI implementation, and frontend performance
- **Key Tasks:** Frontend website development (component building, UI/UX implementation, responsive design, performance optimization)
- **Tooling:** Will operate across all supported tools (Claude Code, OpenCode, Gemini CLI, Copilot)
- **Division Mapping:** Engineering division (consistent with frontend development agents)
- **Priority:** Basic setup first before building specific capabilities

## 3. Day 1 Setup Checklist

Since basic setup is the priority, Day 1 focuses on establishing the foundation:

- [ ] **Repository structure** — confirmed `agency/` source layout, `integrations/` as generated output
- [ ] **Conversion pipeline** — `./scripts/convert.sh` runs without errors for the target tool(s)
- [ ] **Installation** — `./scripts/install.sh --tool <tool>` works for at least one tool
- [ ] **Division alignment** — agent files under `engineering/` division match the frontend developer role
- [ ] **Agent format** — YAML frontmatter with `name`, `description`, `color` fields verified
- [ ] **Color resolution** — named colors convert to hex via `resolve_opencode_color()` (e.g., cyan → #00FFFF)
- [ ] **Slug derivation** — `slugify(name)` produces the install slug from `name: Frontend Developer`

## 4. Known Signals from The Agency Repo

- 73 of 279 agents use `<slug>.md` as their filename already (all of `game-development/`, most of `specialized/`); for these the install slug matches the source file name exactly
- The converter strips `README.md` from integrations output — never delete it from `integrations/`
- `check-divisions.sh` (CI) will fail if `divisions.json` disagrees with on-disk division dirs
- Files must start with `---` (YAML frontmatter) to be considered agents — skip `QUICKSTART.md`, `README.md`, etc.
- OpenCode registers ~119 agents silently; use `--division` to stay under the limit (upstream #27988)

## 5. Next Steps (After Day 1 Basic Setup)

Once the foundation is verified:

- Build the first `SKILL.md` skill for frontend capabilities
- Wire MCP connection to the system of record (Neon Postgres + pgvector)
- Implement progressive disclosure (Stage 1: discovery via `name`+`description` only)
- Test skill firing within the Worker runtime

---

*Captured: Day 1 of Digital FTE creation — frontend developer role, basic setup first, engineering division, all-tool operation.*