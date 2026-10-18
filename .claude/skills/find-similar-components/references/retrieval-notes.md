# Retrieval Notes

Why a search can disappoint, and what to do about it.

## The tool answers two ways

`find_similar_tasks` returns a `retrieval` field:

- `vector` — semantic search over pgvector embeddings. Trustworthy ordering by
  meaning.
- `full_text` — keyword fallback used when no vector matched. Ordering is by text
  rank only, and `distance` is `null`.

Tell the user which one produced the answer when the difference matters.

## Vectors are scoped per model

Every stored embedding records the model that produced it, and a search only
compares against vectors from the model that embedded the query. Mixing models is
never done, so you cannot get a silently wrong result from that.

The trade-off is that a document embedded only with one model is invisible to a
query embedded with another. If results look unexpectedly empty after a provider
change, the workspace may simply need `uv run python reembed.py --apply` to
rebuild vectors for the active model.

## Empty or weak results

1. Rephrase the query in the user's own words rather than keywords alone.
2. Try `list_tasks` to see what is actually saved, in case the description drifted.
3. If the workspace genuinely has nothing, say so and offer to save the new work
   with `save_task`.

## Never

- Never present a low-confidence match as a confident one.
- Never invent matches that the tool did not return.