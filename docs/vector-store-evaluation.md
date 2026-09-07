# Should the plugin keep state in a vector database (Chroma, Pinecone)?

Evaluated 2026-09-07, while looking for ways to stop agents re-establishing context. **Decision: no vector
store for run state; yes to a recall index for the one place recall is actually the problem — and that
index is stdlib SQLite FTS5, not embeddings, until a measurement says otherwise.**

## What was actually asked

Two different questions get conflated under "store state in a vector DB":

1. **Run state** — what this run has established: the solution layout, the packages, the endpoints, the
   test project, what each agent did. Small (kilobytes), structured, needs *exact* recall.
2. **Recall over a corpus** — finding the ADR, the consumer note or the changelog entry that decides a
   question, when nobody remembers it exists. Large, unstructured, needs *fuzzy* recall.

They have opposite answers.

## 1. Run state — no

A vector store is the wrong shape for it, on four counts:

- **Similarity is a downgrade from a key.** "Which test project do I write into?" has one right answer.
  A cosine-ranked passage at 0.83 is strictly worse than a line in `context-pack.md` that says it.
- **Latency and cost per query.** Every lookup is an embedding call plus a search; the pack is one `Read`,
  and the hook now answers most orientation questions *without even that* (§3d of the tiered-flow doc).
- **A new silent-failure mode, of the worst class we know.** A stale index that returns plausible, wrong
  context looks exactly like success — the same failure as a mis-bound Roslyn reporting a clean review.
  Our defence against that class is "an empty result is a mis-bind, never clean code"; a vector store
  makes it harder, not easier, to tell.
- **It buys nothing we lack.** The measured bottleneck (§3c) is *token volume from 26 context
  reconstructions*, not slow lookups. Fewer agents fixes that; a database does not.

## 2. Recall over the records — yes, and here is where

`evidence-reconciler` has one job that is genuinely a recall problem: *enumerate every source that states
or enforces this behaviour, before ruling on a contradiction*. Its failure mode is a missed source, and a
missed source produces a confident wrong verdict — the exact damage the agent exists to prevent.

`grep` fails precisely where it matters: the ticket says "active orders", the ADR says "cancelled rows
stay in the ledger", the consumer note says "N counts every order". No shared keyword. This is the one
place in the plugin where fuzzy recall beats exact search.

**Implemented:** `bin/evidence-index.py` — BM25 (SQLite FTS5, stdlib) over the repository's records: `docs/**`,
`**/decisions/**`, `**/consumers/**`, `CHANGELOG*`, CI files, smoke scripts, `appsettings*`, and the XML
docs and comments of `.cs` files (source *bodies* are left to Roslyn, which answers them exactly). It
rebuilds itself when the fingerprint of those files changes, and the reconciler is told to query it twice —
once in the brief's vocabulary, once in the code's — and to treat every hit as a lead it must open and
read.

Measured on the benchmark's T9 overlay: a query in the *brief's* words
(`"report shows only active orders, cancelled ones excluded"`) returns, ranked: `docs/reporting.md`, the
`ReportService` XML doc, **ADR-0003**, the inline comment and the changelog entry — every source that
decides the case, none of which shares the query's decisive keyword.

## 3. Why FTS5 before embeddings

| | SQLite FTS5 (chosen) | Chroma, local | Pinecone / any hosted |
|---|---|---|---|
| Infrastructure | none — stdlib, one file | `pip install chromadb`, a persistent directory | an account, a network dependency |
| Embeddings | none | a local model (~90 MB, CPU) or an API call | an API call |
| Does repository text leave the machine | no | no, with a local model | **yes** |
| Freshness | file fingerprint, rebuilt on drift | must be re-embedded on drift | same, plus network |
| Failure mode | a miss looks like a miss | a stale index looks like an answer | same, plus outages |
| Paraphrase recall | good (BM25 over OR-ed terms) | better | better |

For a proprietary codebase, the hosted option is close to disqualified on its own: the repositories are
proprietary and the overlay contract keeps even configuration secrets out of tracked files — shipping
source, ADRs and consumer contracts to a third-party SaaS is a security decision, not an engineering one,
and not one this plugin should make silently.

## 4. What would change the decision

Escalate to local embeddings (Chroma with a local sentence-transformers model, or pgvector in a
development Postgres) when **measured** recall on the conflict tasks says so — not before:

- add a paraphrase variant of the conflict pair whose decisive record shares **no** term with the brief
  (T8/T9 today share a few: "orders", "report", "cancelled");
- run the reconciler with the FTS5 index and count how often the decisive source is in its top 10;
- if that recall is below ~90 %, an embedding backend behind a flag becomes worth its infrastructure —
  the index's interface (`build` / `query` returning ranked passages) is deliberately backend-shaped so
  the swap touches one file.

Cross-run *decision* memory (past reconciliation verdicts, findings the verifier called noise, convention
rulings) is the second candidate for embeddings, and the same rule applies: it needs a measurement showing
that the file-based records — ADRs, `docs/decisions`, the session memory directory — are actually being
missed, before it earns a database.
