#!/usr/bin/env python3
"""
import_embeddings.py — Bulk import pre-computed embeddings into Qdrant.

Imports text + pre-computed vectors from a JSONL or JSON file into a
Qdrant collection (corpus_{dataset_id} or learning_{project_id}).
Stores a CorpusManifest in MongoDB and optionally writes full documents
to corpus_docs for later hydration.

Supported input formats:
  JSONL  (.jsonl / .ndjson)  — one JSON object per line  ← recommended
  JSON   (.json)             — JSON array, streamed via ijson

Required per-record fields (names configurable via CLI flags):
  text      — the document text
  embedding — pre-computed vector (list of floats)

Optional per-record fields:
  id        — stable ID (auto-generated UUID if missing)
  metadata  — dict of extra metadata to store

Usage examples:
  python scripts/import_embeddings.py data.jsonl \\
      --dataset-id arxiv_cs_2020 \\
      --embedding-model bge-large

  python scripts/import_embeddings.py data.jsonl \\
      --project-id proj_abc123

  python scripts/import_embeddings.py data.jsonl \\
      --dataset-id pubmed_2024 \\
      --embedding-model ada \\
      --text-field abstract \\
      --batch-size 500

  python scripts/import_embeddings.py data.jsonl \\
      --dataset-id test --dry-run
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Iterator

from qdrant_client import QdrantClient, models

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 6333
DEFAULT_BATCH = 200


# ── file readers ──────────────────────────────────────────────────────────────

def iter_jsonl(path: Path) -> Iterator[dict]:
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
    try:
        import ijson
    except ImportError:
        print(
            "❌  JSON array files require the ijson package:\n"
            "       pip install ijson",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(path, "rb") as fh:
        yield from ijson.items(fh, "item")


def _is_json_array(path: Path) -> bool:
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
            print("ℹ   Detected JSONL format inside .json file.")
            yield from iter_jsonl(path)
    else:
        yield from iter_jsonl(path)


# ── helpers ───────────────────────────────────────────────────────────────────

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
        description="Bulk import pre-computed embeddings into Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("file", type=Path, help="Input file (.jsonl or .json)")

    # Target
    tgt = parser.add_mutually_exclusive_group(required=True)
    tgt.add_argument(
        "--dataset-id",
        help="Corpus dataset ID — imports into corpus_{dataset_id}",
    )
    tgt.add_argument(
        "--project-id",
        help="IDS project ID — imports into learning_{project_id}",
    )
    tgt.add_argument(
        "--collection",
        help="Raw Qdrant collection name",
    )

    # Embedding model
    parser.add_argument(
        "--embedding-model", default="ada",
        help="Embedding registry key (default: ada)",
    )

    # Connection
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    # MongoDB (for manifest + corpus_docs)
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--mongo-db", default="ids")

    # Field mapping
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--embedding-field", default="embedding")
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--metadata-field", default="metadata")

    # Behaviour
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--skip-errors", action="store_true")
    parser.add_argument("--drop-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--on-disk", action="store_true", help="Use on-disk HNSW (for large corpora)")

    args = parser.parse_args()

    if not args.file.exists():
        print(f"❌  File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    file_gb = args.file.stat().st_size / 1024 ** 3

    # Determine collection name
    if args.dataset_id:
        collection_name = f"corpus_{args.dataset_id}"
    elif args.project_id:
        collection_name = f"learning_{args.project_id}"
    else:
        collection_name = args.collection

    emb_model = args.embedding_model

    print(f"📂  Input:      {args.file}  ({file_gb:.2f} GB)")
    print(f"🗄   Collection: {collection_name}")
    print(f"🌐  Qdrant:     {args.host}:{args.port}")
    print(f"📦  Batch size: {args.batch_size}")
    print(f"🧠  Embedding:  {emb_model}")
    if args.dry_run:
        print("🔍  DRY RUN — nothing will be written")
    print()

    client = None
    if not args.dry_run:
        try:
            client = QdrantClient(host=args.host, port=args.port)
        except Exception as exc:
            print(f"❌  Cannot connect to Qdrant: {exc}", file=sys.stderr)
            sys.exit(1)

    # ── streaming import ───────────────────────────────────────────────────
    points: list[models.PointStruct] = []
    inserted = 0
    skipped = 0
    first_dim: int | None = None
    t0 = time.time()

    def flush() -> None:
        nonlocal inserted
        if not points or args.dry_run:
            if points:
                inserted += len(points)
                _progress(inserted, skipped, t0)
                points.clear()
            return
        client.upsert(collection_name=collection_name, points=points)
        inserted += len(points)
        _progress(inserted, skipped, t0)
        points.clear()

    try:
        for record in iter_records(args.file):
            vec = record.get(args.embedding_field)
            if not vec or not isinstance(vec, list):
                skipped += 1
                if not args.skip_errors:
                    print(f"\n❌  Missing '{args.embedding_field}' field.", file=sys.stderr)
                    sys.exit(1)
                continue

            if first_dim is None:
                first_dim = len(vec)
                print(f"📐  Embedding dimension: {first_dim}")
                # Create collection if needed
                if client and not args.dry_run:
                    if args.drop_existing:
                        try:
                            client.delete_collection(collection_name)
                            print(f"🗑   Deleted existing: {collection_name}")
                        except Exception:
                            pass
                    try:
                        client.get_collection(collection_name)
                        print(f"ℹ   Collection exists — upserting.")
                    except Exception:
                        client.create_collection(
                            collection_name=collection_name,
                            vectors_config={
                                emb_model: models.VectorParams(
                                    size=first_dim,
                                    distance=models.Distance.COSINE,
                                    on_disk=args.on_disk,
                                ),
                            },
                        )
                        print(f"✅  Created collection: {collection_name}")

            elif len(vec) != first_dim:
                skipped += 1
                if not args.skip_errors:
                    print(f"\n❌  Dim mismatch: {first_dim} vs {len(vec)}", file=sys.stderr)
                    sys.exit(1)
                continue

            text = record.get(args.text_field, "")
            if not isinstance(text, str):
                text = str(text)

            rec_id = record.get(args.id_field)
            rec_id = str(rec_id) if rec_id else str(uuid.uuid4())
            # Ensure valid UUID for Qdrant
            try:
                uuid.UUID(rec_id)
            except ValueError:
                rec_id = str(uuid.uuid5(uuid.NAMESPACE_URL, rec_id))

            meta = record.get(args.metadata_field) or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["text"] = text
            meta["embedding_model"] = emb_model

            points.append(models.PointStruct(
                id=rec_id,
                vector={emb_model: vec},
                payload=meta,
            ))

            if len(points) >= args.batch_size:
                flush()

    except KeyboardInterrupt:
        print("\n\n⚠   Interrupted — flushing …")
        flush()
        print(f"Partial: {inserted:,} inserted, {skipped:,} skipped.")
        sys.exit(130)

    flush()

    elapsed = time.time() - t0
    print(f"\n\n✅  Done in {elapsed:.1f}s")
    print(f"   Inserted: {inserted:,}")
    if skipped:
        print(f"   Skipped:  {skipped:,}")

    # ── write corpus manifest to MongoDB ──────────────────────────────────
    if args.dataset_id and not args.dry_run:
        try:
            from pymongo import MongoClient
            mongo = MongoClient(args.mongo_uri)
            db = mongo[args.mongo_db]
            db["corpus_manifests"].replace_one(
                {"dataset_id": args.dataset_id},
                {
                    "dataset_id": args.dataset_id,
                    "embedding_model": emb_model,
                    "vector_dim": first_dim or 0,
                    "doc_count": inserted,
                    "chunk_count": inserted,
                    "schema_version": 1,
                    "source_file": str(args.file),
                    "field_map": {
                        "text": args.text_field,
                        "id": args.id_field,
                        "embedding": args.embedding_field,
                    },
                },
                upsert=True,
            )
            print(f"\n📋  Manifest written to MongoDB: corpus_manifests/{args.dataset_id}")
        except Exception as e:
            print(f"\n⚠   Failed to write manifest: {e}", file=sys.stderr)

    if not args.dry_run:
        print()
        print("Next steps:")
        if args.dataset_id:
            print(f"  1. Bind corpus to project: add DataSource with namespace='corpus_{args.dataset_id}'")
        else:
            print(f"  1. In Telegram: /project <name>")
        print(f"  2. Query: /sourcer claude <your question>")


if __name__ == "__main__":
    main()
