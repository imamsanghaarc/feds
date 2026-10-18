"""Report live workspace state, used to keep the docs accurate."""

import psycopg

import config

QUERIES = [
    ("documents", "select count(*) from documents"),
    ("conversations", "select count(*) from conversations"),
    ("audit_log rows", "select count(*) from audit_log"),
    ("capability_invocations rows", "select count(*) from capability_invocations"),
    ("embeddings by model", "select model, count(*) from embeddings group by model"),
    (
        "documents without an embedding for the active model",
        "select count(*) from documents d where d.source='frontend-task' and not exists "
        "(select 1 from embeddings e where e.document_id=d.id and e.model=%s)",
        (),
    ),
    ("duplicate frontend-task titles",
     "select lower(title), count(*) from documents where source='frontend-task' "
     "group by lower(title) having count(*)>1"),
    ("run_states by status", "select status, count(*) from run_states group by status"),
    ("approved tasks", "select count(*) from documents where metadata->>'status'='approved'"),
    ("published tasks", "select count(*) from documents where metadata ? 'published'"),
    (
        "token rollup (in/out, est. dollars)",
        "select coalesce(sum((result->>'input_tokens')::bigint),0) || '/' || "
        "coalesce(sum((result->>'output_tokens')::bigint),0) as tokens, "
        "coalesce(sum(cost_cents),0)/100.0 as dollars "
        "from capability_invocations where result ? 'total_tokens'",
    ),
    ("decisions recorded", "select operator, status, count(*) from run_states where operator is not null group by operator, status"),
]


def main() -> None:
    with psycopg.connect(config.NEON_DATABASE_URL) as conn:
        for entry in QUERIES:
            label, sql = entry[0], entry[1]
            params = entry[2] if len(entry) > 2 else ()
            if "%s" in sql:
                sql = sql % ("'gemini-embedding-001'",)
            try:
                rows = conn.execute(sql, params).fetchall()
                print(f"{label:52s} {rows}")
            except Exception as exc:  # noqa: BLE001
                print(f"{label:52s} ERROR {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()