# FEDS Market Rating and Startup Gaps for SangLabs

Oct 19, 2026 · @Sangchan

## Verdict

FEDS scores about 5.5/10 as a startup bet today: the engineering and safety discipline is strong, but the product is not yet market-ready. It could reach 7–8/10 if SangLabs stops competing on general frontend coding and sells what the big tools handle thinly: governed, audited, outcome-verified frontend work.

This rating comes only from the project's `AGENTS.md`, not from the code, a demo or customer data. Treat the scores as a read of design choices, not a product test.

## Rating by area

| Area | Score | Why |
| --- | --- | --- |
| Engineering discipline and safety | 8.5/10 | Human approval before anything publishes, a least-privilege database role, scoped tools instead of broad SQL, and verified memory promotion. Most agent startups skip this. |
| Honesty of evaluation | 8/10 | Earlier fake eval results were removed, and an incomplete run is never reported as a pass. The evidence is still thin: 11/11 trigger precision is one sample per case, and only one pass is backed by a recorded `load_skill`. |
| Packaging and naming | 7/10 | "FEDS, a named digital specialist" fits the AI-employee trend, where products are sold as a single named hire. |
| Product differentiation | 5/10 | Frontend agents are crowded: Cursor, Claude Code, v0, Lovable, Bolt and Devin. Nothing in the file says FEDS writes better UI than they do. |
| Production readiness | 4/10 | Docker and compose were never run, live testing depends on the Gemini free-tier quota, and production publishing is off by default. |
| Market proof | 2/10 | No paying users, pilots or competitor benchmark are visible. For a startup this matters most. |

## Where the market is weak

Six gaps stand out, and the first five line up with what FEDS already has.

1. **Governance and oversight.** The [OutSystems 2026 report](https://itwire.com/guest-articles/guest-research/agentic-ai-goes-mainstream-in-the-enterprise,-but-94-raise-concern-about-sprawl,-outsystems-research-finds.html) (1,900 IT leaders) says 94% worry that agent sprawl adds complexity and security risk, and only 12% have a central platform to manage it. FEDS already has approval gates, audit records and scoped credentials. This is the strongest selling point.
2. **The "last 30%" and accessibility.** AI app builders are criticised for incomplete output and looping fixes. One [vendor review of Lovable](https://azumo.com/artificial-intelligence/ai-insights/lovable-ai-limitations-benefits) rates it 60–70% production-ready; that firm sells the cleanup work, so weigh it accordingly. It does not discuss accessibility at all. An agent that fixes Core Web Vitals and accessibility problems and proves the improvement before and after is a real niche, and the FEDS prompt already enforces the Core Web Vitals thresholds.
3. **Trust in AI-employee claims.** [Trends.vc](https://trends.vc/ai-employees-named-personas-cautionary-tale-outcome-pricing/) describes 11x, which reportedly claimed $14M ARR with about $3M contracted, and says 70–80% of early customers used break clauses to leave. It names "outcome verification audits" as an opportunity. FEDS's measured-results-only habit fits this well.
4. **Pricing.** The same source expects outcome-based pricing to become dominant, for example about $3 per resolution instead of a $150,000/year flat contract. For FEDS that could mean paying per merged change that stays inside a performance and accessibility budget.
5. **Memory that learns a company's own design system.** The promotion gates and the Verified Lesson Loop design could become lock-in. Nobody wants to retrain a tool on their own components.
6. **Regional and SMB gap (inference, not sourced).** Software agencies in Pakistan and South Asia need Urdu and right-to-left layouts, local payment integrations and low pricing, which the big tools mostly ignore.

## What to do next

Pick one narrow wedge and prove it with real customers before widening.

1. **Choose the wedge.** For example, "frontend performance and accessibility fixes, audited and approved by a human." Do not pitch general frontend coding.
2. **Run 3–5 free pilots** with agencies or startups, and record before and after Core Web Vitals scores for each.
3. **Harden deployment.** Move off the Gemini free tier and actually run the container deployment before showing it to anyone.
4. **Publish a small benchmark** of FEDS against a baseline on real tasks.
5. **Keep the honest-evaluation habit** and make it a selling point.

The main risk is that Claude Code, Codex and similar tools keep absorbing general coding. The defence is depth in governance and verified outcomes, which those tools handle thinly.

## Sources and caveats

Market figures come from the pages below, read on 2026-10-19. Two are vendor or newsletter sources and carry their own bias. The FEDS assessment uses only `AGENTS.md`.

- [AI Employees: Named Personas, Cautionary Tale, Outcome Pricing (Trends.vc)](https://trends.vc/ai-employees-named-personas-cautionary-tale-outcome-pricing/)
- [OutSystems 2026 State of AI Development, via ITWire](https://itwire.com/guest-articles/guest-research/agentic-ai-goes-mainstream-in-the-enterprise,-but-94-raise-concern-about-sprawl,-outsystems-research-finds.html)
- [Lovable AI Review: Key Limitations (Azumo)](https://azumo.com/artificial-intelligence/ai-insights/lovable-ai-limitations-benefits)
- [Best AI for Coding in 2026 (Morph)](https://www.morphllm.com/best-ai-for-coding)
