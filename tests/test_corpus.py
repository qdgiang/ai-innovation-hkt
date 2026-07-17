"""Integrity checks for the synthetic corpus + answer key + golden set.

These are the fixtures every later phase (extraction, eval, demo) stands on, so
their internal consistency is tested like code. Skipped until the data files
exist (they are authored in Phase 0).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

from ingestion.replay import iter_corpus
from ingestion.transcript import parse_transcript

DATA = Path(__file__).resolve().parent.parent / "data"
CORPUS = DATA / "corpus.jsonl"
ANSWER_KEY = DATA / "answer_key.json"
GOLDEN_SET = DATA / "golden_set.json"
TRANSCRIPT = DATA / "meeting-2026-06-28.txt"

MARKER_RE = re.compile(r"!(decision|blocked|status)\b")
VALID_CHANNELS = {"aiv-education": "education", "aiv-events": "events", "aiv-comms": "comms"}

pytestmark = pytest.mark.skipif(
    not (CORPUS.exists() and ANSWER_KEY.exists() and GOLDEN_SET.exists()),
    reason="corpus fixtures not yet authored",
)


@pytest.fixture(scope="module")
def messages():
    return list(iter_corpus(CORPUS))


@pytest.fixture(scope="module")
def answer_key():
    return json.loads(ANSWER_KEY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def golden_set():
    return json.loads(GOLDEN_SET.read_text(encoding="utf-8"))


class TestCorpusFile:
    def test_ids_sequential_and_match_line_numbers(self, messages):
        for i, msg in enumerate(messages, start=1):
            assert msg.id == f"m{i:04d}"
            assert msg.raw_ref == f"corpus.jsonl:{i}"

    def test_timestamps_nondecreasing(self, messages):
        for prev, cur in zip(messages, messages[1:], strict=False):
            assert cur.ts >= prev.ts, f"{cur.id} is earlier than {prev.id}"

    def test_channels_and_teams_consistent(self, messages):
        for msg in messages:
            assert msg.source.value == "replay"
            assert VALID_CHANNELS[msg.channel] == msg.team

    def test_volume(self, messages):
        assert 400 <= len(messages) <= 700


class TestAnswerKey:
    def test_all_referenced_message_ids_exist(self, messages, answer_key):
        known = {m.id for m in messages}
        for section in ("decisions", "blockers", "statuses"):
            for entry in answer_key[section]:
                for mid in entry["source_msg_ids"]:
                    assert mid in known, f"{entry['key']} cites unknown {mid}"
        for d in answer_key["distractors"]:
            assert set(d["msg_ids"]) <= known
        for q in answer_key["qa_questions"]:
            assert set(q["expected_citation_msg_ids"]) <= known

    def test_planted_counts(self, answer_key):
        decisions = answer_key["decisions"]
        blockers = answer_key["blockers"]
        assert len(decisions) == 8
        assert sum(1 for d in decisions if d["supersedes"]) == 2
        assert len(blockers) == 5
        assert any(b["implicit"] for b in blockers)
        assert len(answer_key["statuses"]) >= 12
        assert len(answer_key["qa_questions"]) == 3

    def test_supersession_links_resolve(self, answer_key):
        keys = {d["key"] for d in answer_key["decisions"]}
        for d in answer_key["decisions"]:
            if d["supersedes"]:
                assert d["supersedes"] in keys

    def test_markers_only_in_marked_ground_truth(self, messages, answer_key):
        marked_ids: set[str] = set()
        for section in ("decisions", "blockers", "statuses"):
            for entry in answer_key[section]:
                if entry.get("marked"):
                    marked_ids.update(entry["source_msg_ids"])
        for msg in messages:
            if MARKER_RE.search(msg.text):
                assert msg.id in marked_ids, f"stray marker in {msg.id}: {msg.text!r}"

    def test_transcript_records_reference_real_turns(self, answer_key):
        start = dt.datetime(2026, 6, 28, 15, 0, tzinfo=dt.timezone(dt.timedelta(hours=7)))
        turns = parse_transcript(TRANSCRIPT, start=start)
        stamps = {t.ts for t in turns}
        assert len(turns) >= 60
        for rec in answer_key["transcript_records"]:
            for turn in rec["source_turns"]:
                minutes, seconds = map(int, turn.split(":"))
                assert start + dt.timedelta(minutes=minutes, seconds=seconds) in stamps, (
                    f"{rec['key']} cites missing turn [{turn}]"
                )


class TestGoldenSet:
    def test_window_count_and_negatives(self, golden_set):
        windows = golden_set["windows"]
        assert 18 <= len(windows) <= 22
        negatives = [w for w in windows if not w["expected_records"]]
        assert len(negatives) == 5

    def test_windows_are_contiguous_channel_slices(self, messages, golden_set):
        per_channel = {}
        for msg in messages:
            per_channel.setdefault(msg.channel, []).append(msg.id)
        for w in golden_set["windows"]:
            seq = per_channel[w["channel"]]
            ids = w["message_ids"]
            assert 8 <= len(ids) <= 20, f"{w['window_id']} has {len(ids)} messages"
            start = seq.index(ids[0])
            assert seq[start : start + len(ids)] == ids, f"{w['window_id']} not contiguous"

    def test_expected_records_resolve_to_answer_key(self, answer_key, golden_set):
        known = {
            e["key"]
            for section in ("decisions", "blockers", "statuses")
            for e in answer_key[section]
        }
        expected = set()
        for w in golden_set["windows"]:
            for r in w["expected_records"]:
                assert r["key"] in known, f"{w['window_id']} expects unknown {r['key']}"
                expected.add(r["key"])
        decision_keys = {d["key"] for d in answer_key["decisions"]}
        assert decision_keys <= expected, "every planted chat decision needs a golden window"
