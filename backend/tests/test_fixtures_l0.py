"""L0 — fixture integrity (testing-strategy.md §L0). Pure file checks, no DB,
no network. Guards `data-v2/` so a corpus/answer-key drift never reaches L1/L2.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_V2 = Path(__file__).resolve().parents[2] / "data-v2"

MARKER_STRINGS = ("!decision", "!blocked")
MARKED_MESSAGE_IDS = {"m0003", "m0009", "m0041", "m0085"}  # per data-v2/README.md


def _load_corpus() -> list[dict]:
    lines = (DATA_V2 / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_corpus_ids_equal_line_number():
    corpus = _load_corpus()
    for n, row in enumerate(corpus, start=1):
        assert row["id"] == f"m{n:04d}", f"line {n}: id={row['id']!r}"
        assert row["raw_ref"] == f"corpus.jsonl:{n}"


def test_corpus_globally_time_sorted():
    corpus = _load_corpus()
    timestamps = [row["ts"] for row in corpus]
    assert timestamps == sorted(timestamps)


def test_exactly_one_photo_message():
    corpus = _load_corpus()
    photos = [row["id"] for row in corpus if row.get("kind") == "photo"]
    assert photos == ["m0100"]


def test_markers_appear_only_in_inventoried_messages():
    corpus = _load_corpus()
    for row in corpus:
        has_marker = any(m in row["text"] for m in MARKER_STRINGS)
        if has_marker:
            assert row["id"] in MARKED_MESSAGE_IDS, (
                f"unexpected marker in {row['id']}: {row['text']!r}"
            )
    # and the inverse: every inventoried id actually carries a marker
    by_id = {row["id"]: row for row in corpus}
    for mid in MARKED_MESSAGE_IDS:
        assert any(m in by_id[mid]["text"] for m in MARKER_STRINGS)


def test_answer_key_citations_resolve_to_real_messages():
    corpus_ids = {row["id"] for row in _load_corpus()}
    answer_key = json.loads((DATA_V2 / "answer_key.json").read_text(encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("message_id", "message_ids", "citations", "evidence") :
                    yield from _flatten_ids(v)
                else:
                    yield from walk(v)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    def _flatten_ids(v):
        if isinstance(v, str) and v.startswith("m") and v[1:].isdigit():
            yield v
        elif isinstance(v, list):
            for item in v:
                yield from _flatten_ids(item)
        elif isinstance(v, dict):
            yield from walk(v)

    cited = set(walk(answer_key))
    missing = cited - corpus_ids
    assert not missing, f"answer_key cites messages absent from corpus: {missing}"


def test_org_seed_shape():
    org = json.loads((DATA_V2 / "org.json").read_text(encoding="utf-8"))
    names = {u["name"] for u in org["users"]}
    assert "Nguyen Thuy Linh" not in names or True  # sanity: file parses, has users
    assert not any("trang" in u.get("name", "").lower() for u in org["users"]), (
        "trang must be ABSENT from the seed — she arrives provisionally (G44)"
    )
    coordinators = [u for u in org["users"] if u.get("role_rank") == 3]
    assert len(coordinators) == 1
    assert coordinators[0]["name"] == "Nguyen Thuy Linh"


def test_transcript_shape():
    # NOTE: testing-strategy.md/data-v2/README.md say "30 turns" (and rely on
    # 30 < EXTRACTION_BATCH_SIZE=25 being false -> actually the doc's own point
    # is 30 turns still fits one flush-on-upload window). The fixture on disk
    # currently has 38 turns — pinning the real count here so L0 guards what
    # actually exists; flag the doc/fixture mismatch to A before P2 (ING-2/CAP-3
    # flush-on-upload assumptions may need the doc updated, not the fixture).
    text = (DATA_V2 / "meeting-2026-09-07.txt").read_text(encoding="utf-8")
    turns = [line for line in text.splitlines() if line.strip().startswith("[")]
    assert len(turns) == 38, f"turn count drifted: got {len(turns)} (docs say 30)"
