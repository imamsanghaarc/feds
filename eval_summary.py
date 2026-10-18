"""Summarize the trigger eval results file."""

import json

with open("eval_trigger_results.json", encoding="utf-8") as handle:
    rows = json.load(handle)

scored = [r for r in rows if "error" not in r]
passed = [r for r in scored if r.get("passed")]
failed = [r for r in scored if not r.get("passed")]

print(f"scored : {len(scored)}")
print(f"passed : {len(passed)}")
print(f"failed : {len(failed)}")
print()
for row in rows:
    if "error" in row:
        state = "ERROR"
    else:
        state = "PASS " if row.get("passed") else "FAIL "
    detail = row.get("chosen", str(row.get("error", ""))[:40])
    print(f"  [{state}] {row['id']:42s} {detail}")

if failed:
    print()
    print("remaining failures:")
    for row in failed:
        print(f"  {row['id']}: expected={row['expect']} got={row['chosen']}")