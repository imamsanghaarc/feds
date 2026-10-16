# Escalation Package

Keep it short enough that a reviewer will actually read it.

## 1. Context and Problem
- What was being built, and for whom
- The concrete symptom, not a restatement of the request
- Whether users are affected now

## 2. What Was Attempted
- The real build or review attempt that already happened
- Saved task or component names from the workspace
- What was tried and ruled out

## 3. Why It Remains Unresolved
- The specific blocker
- What is unknown versus what is known
- Anything assumed but unverified

## 4. Risk Signals
- Accessibility or WCAG concerns (always list explicitly, even if none)
- Performance against Core Web Vitals: LCP < 2.5s, FID/INP < 100ms, CLS < 0.1
- User sentiment and whether it is verifiably negative
- Blast radius: who sees the affected surface

## 5. Recommended Review Path
- Who should review, and what they need to decide
- The specific question blocking progress
- Any deadline or user commitment that applies

## 6. Evidence
- Workspace task names and ids
- Recorded review outcomes, quoting the reviewer rather than paraphrasing

## Rules

- Facts and inference must be visibly separated.
- Never claim a test passed without a recorded result.
- If there is no genuine escalation condition, say so and do not send a package.