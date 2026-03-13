#!/usr/bin/env python3
"""
import_embeddings.py — Bulk import pre-computed embeddings into ChromaDB.

Imports text + pre-computed vectors from a JSONL or JSON file into a
ChromaDB collection (learning_{project_id}) using OpenAI's
text-embedding-ada-002 embedding function.

Because the vectors are pre-computed, no OpenAI API calls are made during
import. The OpenAI EF is only attached to the collection so that /sourcer
queries can embed the search query with the same model at query time.

Supported input formats:
  JSONL  (.jsonl / .ndjson)  — one JSON object per line  ← recommended for large files
  JSON   (.json)             — JSON array, streamed via ijson

Required per-record fields (names configurable via CLI flags):
  text      — the document text
  embedding — pre-computed vector (list of floats)

Optional per-record fields:
  id        — stable ID (auto-generated UUID if missing)
  metadata  — dict of extra metadata to store

Usage examples:
  python scripts/import_embeddings.py data.jsonl \\
      --project-id proj_abc123 \\
      --openai-key sk-...

  python scripts/import_embeddings.py data.json \\
      --project-id proj_abc123 \\
      --openai-key sk-... \\
      --text-field content \\
      --embedding-field vector \\
      --batch-size 500

  # Dry-run to validate file structure without writing anything
  python scripts/import_embeddings.py data.jsonl \\
      --project-id proj_abc123 \\
      --openai-key sk-... \\
      --dry-run
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Iterator

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000
DEFAULT_BATCH = 200
OPENAI_MODEL = "text-embedding-ada-002"
EXPECTED_DIM = 1536


# ── file readers ──────────────────────────────────────────────────────────────

def iter_jsonl(path: Path) -> Iterator[dict]:
    """Stream records from a JSONL / NDJSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  ⚠  line {lineno}: {exc}", file=sys.stderr)


def iter_json_array(path: Path) -> Iterator[dict]:
    """Stream records from a large JSON array using ijson."""
    try:
        import ijson
    except ImportError:
        print(
            "❌  JSON array files require the ijson package:\n"
            "       pip install ijson\n\n"
            "   Or convert to JSONL first (much faster for 14 GB):\n"
            "       python -c \""
            "import json,sys; [print(json.dumps(r)) "
            "for r in json.load(open(sys.argv[1]))\" data.json > data.jsonl",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(path, "rb") as fh:
        yield from ijson.items(fh, "item")


def _is_json_array(path: Path) -> bool:
    """Peek at first non-whitespace byte to distinguish array ([) from JSONL ({)."""
    with open(path, "rb") as fh:
        while True:
            byte = fh.read(1)
            if not byte:
                return False
            if byte.strip():
                return byte == b"["


def iter_records(path: Path) -> Iterator[dict]:
    suffix = path.suffix.lower()
    if suffix in (".jsonl", ".ndjson"):
        yield from iter_jsonl(path)
    elif suffix == ".json":
        if _is_json_array(path):
            yield from iter_json_array(path)
        else:
            # .json file containing JSONL (one object per line)
            print("ℹ   Detected JSONL format inside .json file — streaming line by line.")
            yield from iter_jsonl(path)
    else:
        # Unknown extension — try JSONL first (works for most export formats)
        yield from iter_jsonl(path)


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_meta(meta: dict) -> dict:
    """ChromaDB metadata values must be str / int / float / bool."""
    return {
        k: v for k, v in meta.items()
        if isinstance(v, (str, int, float, bool))
    }


def _progress(inserted: int, skipped: int, t0: float) -> None:
    elapsed = time.time() - t0
    rate = inserted / elapsed if elapsed > 0 else 0
    print(
        f"\r  ✓  {inserted:>10,} inserted  |  {skipped:>6,} skipped  |  "
        f"{rate:>7.0f} rec/s",
        end="",
        flush=True,
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk import pre-computed ada-002 embeddings into ChromaDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("file", type=Path, help="Input file (.jsonl or .json)")

    # Target
    tgt = parser.add_mutually_exclusive_group(required=True)
    tgt.add_argument(
        "--project-id",
        help="IDS project ID — imports into learning_{project_id}",
    )
    tgt.add_argument(
        "--collection",
        help="Raw ChromaDB collection name",
    )

    # Connection
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"ChromaDB host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"ChromaDB port (default: {DEFAULT_PORT})")

    # Auth
    parser.add_argument(
        "--openai-key",
        default=None,
        help="OpenAI API key (can also be set via OPENAI_API_KEY env var)",
    )

    # Field mapping
    parser.add_argument("--text-field",      default="text",      help="Field containing document text (default: text)")
    parser.add_argument("--embedding-field", default="embedding", help="Field containing vector (default: embedding)")
    parser.add_argument("--id-field",        default="id",        help="Field for record ID (default: id)")
    parser.add_argument("--metadata-field",  default="metadata",  help="Field for metadata dict (default: metadata)")

    # Behaviour
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH, help=f"Records per upsert batch (default: {DEFAULT_BATCH})")
    parser.add_argument("--skip-errors", action="store_true", help="Skip bad records instead of aborting")
    parser.add_argument("--drop-existing", action="store_true", help="Delete the collection before importing")
    parser.add_argument("--dry-run", action="store_true", help="Parse + validate without writing to ChromaDB")

    args = parser.parse_args()

    # ── validate file ──────────────────────────────────────────────────────────
    if not args.file.exists():
        print(f"❌  File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    file_gb = args.file.stat().st_size / 1024 ** 3
    collection_name = f"learning_{args.project_id}" if args.project_id else args.collection

    # ── resolve OpenAI key ─────────────────────────────────────────────────────
    import os
    openai_key = args.openai_key or os.getenv("OPENAI_API_KEY")
    if not openai_key and not args.dry_run:
        print(
            "❌  OpenAI API key is required.\n"
            "   Pass --openai-key sk-... or set OPENAI_API_KEY in the environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── connect to ChromaDB ────────────────────────────────────────────────────
    print(f"📂  Input:      {args.file}  ({file_gb:.2f} GB)")
    print(f"🗄   Collection: {collection_name}")
    print(f"🌐  ChromaDB:   {args.host}:{args.port}")
    print(f"📦  Batch size: {args.batch_size}")
    if args.dry_run:
        print("🔍  DRY RUN — nothing will be written")
    print()

    if not args.dry_run:
        import chromadb
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        try:
            client = chromadb.HttpClient(host=args.host, port=args.port)
            client.heartbeat()
        except Exception as exc:
            print(f"❌  Cannot connect to ChromaDB at {args.host}:{args.port}: {exc}", file=sys.stderr)
            sys.exit(1)

        ef = OpenAIEmbeddingFunction(api_key=openai_key, model_name=OPENAI_MODEL)

        if args.drop_existing:
            try:
                client.delete_collection(collection_name)
                print(f"🗑   Deleted existing collection: {collection_name}")
            except Exception:
                pass  # didn't exist yet

        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

        existing = collection.count()
        if existing > 0:
            print(f"ℹ   Collection already has {existing:,} records — new records will be upserted.")
        print()

    # ── streaming import ───────────────────────────────────────────────────────
    b_ids:   list[str]        = []
    b_docs:  list[str]        = []
    b_vecs:  list[list[float]] = []
    b_metas: list[dict]       = []

    inserted = 0
    skipped  = 0
    batch_n  = 0
    first_dim: int | None = None
    t0 = time.time()

    def flush() -> None:
        nonlocal inserted, skipped, batch_n
        if not b_ids:
            return
        # Deduplicate within batch — keep last occurrence (source file may have dupes)
        seen: dict[str, int] = {}
        for i, rec_id in enumerate(b_ids):
            seen[rec_id] = i
        if len(seen) < len(b_ids):
            dupes = len(b_ids) - len(seen)
            skipped += dupes
            idxs = sorted(seen.values())
            u_ids   = [b_ids[i]   for i in idxs]
            u_docs  = [b_docs[i]  for i in idxs]
            u_vecs  = [b_vecs[i]  for i in idxs]
            u_metas = [b_metas[i] for i in idxs]
        else:
            u_ids, u_docs, u_vecs, u_metas = b_ids, b_docs, b_vecs, b_metas
        if not args.dry_run:
            collection.upsert(
                ids=u_ids,
                documents=u_docs,
                embeddings=u_vecs,
                metadatas=u_metas,
            )
        inserted += len(u_ids)
        batch_n  += 1
        _progress(inserted, skipped, t0)
        b_ids.clear(); b_docs.clear(); b_vecs.clear(); b_metas.clear()

    try:
        for record in iter_records(args.file):

            # ── embedding ──────────────────────────────────────────────────────
            vec = record.get(args.embedding_field)
            if not vec or not isinstance(vec, list):
                skipped += 1
                if not args.skip_errors:
                    print(
                        f"\n❌  Record missing '{args.embedding_field}' field.\n"
                        "   Use --skip-errors to skip bad records.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                continue

            # Dimension check (first record sets the reference)
            if first_dim is None:
                first_dim = len(vec)
                print(f"📐  Embedding dimension: {first_dim}")
                if first_dim != EXPECTED_DIM:
                    print(
                        f"⚠   Expected {EXPECTED_DIM} dims for ada-002 but got {first_dim}. "
                        "Continuing anyway.",
                        file=sys.stderr,
                    )
            elif len(vec) != first_dim:
                skipped += 1
                if not args.skip_errors:
                    print(
                        f"\n❌  Dimension mismatch: expected {first_dim}, got {len(vec)}.\n"
                        "   Use --skip-errors to skip.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                continue

            # ── text ───────────────────────────────────────────────────────────
            text = record.get(args.text_field, "")
            if not isinstance(text, str):
                text = str(text)

            # ── id ─────────────────────────────────────────────────────────────
            rec_id = record.get(args.id_field)
            rec_id = str(rec_id) if rec_id else str(uuid.uuid4())

            # ── metadata ───────────────────────────────────────────────────────
            meta = record.get(args.metadata_field) or {}
            meta = _safe_meta(meta) if isinstance(meta, dict) else {}
            meta["embedding_model"] = OPENAI_MODEL

            b_ids.append(rec_id)
            b_docs.append(text)
            b_vecs.append(vec)
            b_metas.append(meta)

            if len(b_ids) >= args.batch_size:
                flush()

    except KeyboardInterrupt:
        print("\n\n⚠   Interrupted — flushing current batch …")
        flush()
        print(f"Partial import: {inserted:,} inserted, {skipped:,} skipped.")
        sys.exit(130)

    flush()  # final batch

    # ── summary ────────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n\n✅  Done in {elapsed:.1f}s")
    print(f"   Inserted: {inserted:,}")
    if skipped:
        print(f"   Skipped:  {skipped:,}")
    if not args.dry_run:
        print(f"   Collection total: {collection.count():,}")
        print()
        print("Next steps:")
        print(f"  1. In Telegram: /project <name>")
        print(f"  2. Set embedding model: /set_model embedding ada-002")
        print(f"  3. Query: /sourcer claude <your question>")


if __name__ == "__main__":
    main()
