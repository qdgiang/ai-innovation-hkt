"""Demo seeder — replays `data-v2/answer_key.json`'s hand-verified ground truth
through the REAL universal command gateway (`decisions.service.handle`), then
folds the projections. It stands in for the unbuilt LLM extraction (ING, P2):
every decision/task/update below enters exactly the way extraction will emit
them — as `contracts.commands` — so the whole read side (board, decision log,
feed, inbox, blockers, digest, Q&A) lights up with the corpus's story.

Idempotent: every command carries a deterministic `client_command_id`
(uuid5 of a script key), so re-runs replay recorded outcomes [EVM-021].

Run (inside the api container, after /tmp/{org.json,corpus.jsonl} are copied):

    python -m evermind.demo /tmp/org.json /tmp/corpus.jsonl
    python -m evermind.demo /tmp/org.json /tmp/corpus.jsonl --until m0100  # mid-story beat

`--until mNNNN` stops the story at that corpus message (e.g. m0100 leaves
T-02 still blocked on Kim Long — the live-blocker demo beat); rerunning
without it plays the story to its final state.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from evermind.connectors.models import Message
from evermind.connectors.replay import ReplayConnector
from evermind.contracts.commands import (
    ApproveProposal, CitationSpec, OpSpec, ProposeDecision, RecordTaskUpdate,
)
from evermind.contracts.enums import CitationKind, CreatedFrom, DecisionScope
from evermind.decisions.service import DecisionsService
from evermind.org.seed import load_org_seed
from evermind.org.service import OrgService
from evermind.surfacing.consumer import SurfacingConsumer
from evermind.tasks.consumer import TasksConsumer
from evermind.tasks.service import TasksService

NAMESPACE = uuid.NAMESPACE_URL


def cid(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"evermind-demo:{key}")


def mid(marker: str) -> int:
    return int(marker.lstrip("m"))


def evidence(*markers: str) -> list[CitationSpec]:
    return [CitationSpec(message_id=mid(m), kind=CitationKind.EVIDENCE, rev_at_capture=1)
            for m in markers]


class DemoSeeder:
    def __init__(self, session: Session, ids: dict[str, dict[str, int]],
                 until: str | None = None):
        self.session = session
        self.ids = ids
        self.until = mid(until) if until else None
        self.org = OrgService(session)
        self.gateway = DecisionsService(session, task_port=TasksService(session))
        self.task_ids: dict[str, int] = {}  # answer-key slug ("T-01") -> db id
        self.decision_ids: dict[str, int] = {}  # answer-key id ("D-03") -> db id
        self.report: list[str] = []

    # ── plumbing ─────────────────────────────────────────────────────────

    def user(self, handle: str) -> int:
        return self.ids["users"][handle]

    def fold(self) -> None:
        TasksConsumer(self.session).poll_and_apply()
        SurfacingConsumer(self.session).poll_and_apply()
        self.session.commit()

    def skip(self, anchor: str) -> bool:
        return self.until is not None and mid(anchor) > self.until

    def handle(self, key: str, command) -> dict:
        outcome = self.gateway.handle(command)
        self.fold()
        self.report.append(f"{key:<22} -> {outcome.get('status')}"
                           + (" (replayed)" if outcome.get("duplicate") else ""))
        return outcome

    def message_text(self, marker: str) -> str:
        message = self.session.get(Message, mid(marker))
        return message.text if message else marker

    # ── the story ────────────────────────────────────────────────────────

    def propose(self, key: str, anchor: str, *, by: str, scope: DecisionScope,
                target: str, description: str, ops: list[OpSpec],
                citations: list[CitationSpec], group: str | None = None,
                created_from: CreatedFrom = CreatedFrom.LLM,
                confidence: float | None = 0.9, context: str | None = None,
                note: str | None = None, effect_window=None) -> dict | None:
        if self.skip(anchor):
            return None
        command = ProposeDecision(
            client_command_id=cid(key), persona=by, created_from=created_from,
            confidence=confidence, source_message_id=mid(anchor),
            decided_by_user_id=self.user(by), scope=scope, scope_target=target,
            description=description, context=context, note=note, ops=ops,
            citations=citations, effect_window=effect_window,
            context_group_id=self.ids["groups"][group] if group else None,
        )
        outcome = self.handle(key, command)
        if outcome.get("decision_id"):
            self.decision_ids[key] = outcome["decision_id"]
        return outcome

    def approve(self, key: str, anchor: str, *, of: str, by: str) -> dict | None:
        if self.skip(anchor) or of not in self.decision_ids:
            return None
        command = ApproveProposal(
            client_command_id=cid(key), persona=by, created_from=CreatedFrom.LLM,
            source_message_id=mid(anchor), decision_id=self.decision_ids[of],
            approved_by_user_id=self.user(by), ack_revalidation=True,
        )
        return self.handle(key, command)

    def new_task(self, key: str, anchor: str, *, by: str, title: str,
                 group: str, team: str, pics: list[str],
                 created_from: CreatedFrom = CreatedFrom.LLM,
                 confidence: float | None = 0.9,
                 extra_ops: list[OpSpec] | None = None,
                 citations: list[str] | None = None,
                 note: str | None = None) -> None:
        if self.skip(anchor):
            return
        ops = [OpSpec(target="NEW_TASK", facet="description", op="set", value=title),
               OpSpec(target="NEW_TASK", facet="team", op="add",
                      value=self.ids["teams"][team])]
        for pic in pics:
            ops.append(OpSpec(target="NEW_TASK", facet="assignment", op="add",
                              value=self.user(pic)))
        ops.extend(extra_ops or [])
        outcome = self.propose(
            key, anchor, by=by, scope=DecisionScope.TASK, target="NEW_TASK",
            description=title, ops=ops, group=group, created_from=created_from,
            confidence=confidence, note=note,
            citations=evidence(*(citations or [anchor])),
        )
        if outcome and outcome.get("new_task_id"):
            self.task_ids[key] = outcome["new_task_id"]

    def task_target(self, task_key: str) -> str:
        return f"task:{self.task_ids[task_key]}"

    def update(self, key: str, anchor: str, *, task: str, by: str, kind: str,
               payload: dict, created_from: CreatedFrom = CreatedFrom.LLM) -> None:
        if self.skip(anchor) or task not in self.task_ids:
            return
        command = RecordTaskUpdate(
            client_command_id=cid(key), persona=by, created_from=created_from,
            source_message_id=mid(anchor), task_id=self.task_ids[task],
            actor_user_id=self.user(by), update_kind=kind, payload=payload,
        )
        self.handle(key, command)

    def ensure_trang(self) -> None:
        """G44 arrival lane: trang is deliberately absent from org.json — she
        appears at m0071 and claims the games-stations task."""
        user = self.org.create_provisional_user(
            name="Nguyen Thu Trang", platform="generic-chat",
            connector_scope="default", platform_user_id="u1010",
            team_id=self.ids["teams"]["TEAM-EV"],
        )
        if user.handle is None:
            user.handle = "trang"  # demo: makes her selectable in the switcher
        self.ids["users"]["trang"] = user.id
        self.session.commit()

    def run(self) -> None:
        teams, projects = self.ids["teams"], self.ids["projects"]
        parties = self.ids["parties"]

        # ── standing policies (markers fire instantly at ingest) ─────────
        self.propose("D-01", "m0003", by="linh", scope=DecisionScope.PROJECT,
                     target=f"project:{projects['P-TT']}",
                     description="Đêm hội tối thứ 7 26/9, 18h-21h, sân trường Nguyen Du",
                     ops=[OpSpec(target=f"project:{projects['P-TT']}",
                                 facet="attr:event-plan", op="set",
                                 value="tối thứ 7 26/9, 18:00-21:00, sân trường Nguyen Du")],
                     citations=evidence("m0003"), created_from=CreatedFrom.MARKER)
        self.propose("DC-01", "m0009", by="mai", scope=DecisionScope.TEAM,
                     target=f"team:{teams['TEAM-ED']}",
                     description="Lịch học cố định CN 14:00, phòng B",
                     ops=[OpSpec(target=f"team:{teams['TEAM-ED']}",
                                 facet="attr:class-schedule", op="set",
                                 value="Chủ nhật 14:00, phòng B")],
                     citations=evidence("m0009"), created_from=CreatedFrom.MARKER)

        # ── task-creating decisions ──────────────────────────────────────
        self.new_task("T-01", "m0011", by="linh", title="Xin giấy phép phường",
                      group="G-TT", team="TEAM-EV", pics=["linh"], citations=["m0011"])
        # D-03: member proposal + lead approval-by-reply — both messages cited
        self.new_task("T-02", "m0016", by="minh", title="Đặt lồng đèn (Kim Long)",
                      group="G-TT", team="TEAM-EV", pics=["minh"],
                      citations=["m0016", "m0018"],
                      extra_ops=[OpSpec(target="NEW_TASK", facet="attr:order", op="set",
                                        value="200 lồng đèn giấy Kim Long ~2tr4")],
                      note="proposal by member + approval-by-reply 'ok chốt nhé'")
        self.decision_ids["D-03"] = self.decision_ids.get("T-02", 0)
        self.approve("D-03-approve", "m0018", of="T-02", by="linh")
        self.new_task("T-03", "m0022", by="linh",
                      title="Truyền thông sự kiện: bài đăng, poster, đếm ngược",
                      group="G-TT", team="TEAM-EV", pics=["an"], citations=["m0022"])
        self.new_task("T-04", "m0030", by="linh", title="Trang trí sân khấu + sân trường",
                      group="G-TT", team="TEAM-EV", pics=["duc"], citations=["m0030"])
        if not self.skip("m0032") and "T-02" in self.task_ids and "T-04" in self.task_ids:
            # DEP-1: đèn về (T-02) trước khi ráp trang trí (T-04) — lead confirmed
            self.propose("DEP-1", "m0032", by="linh", scope=DecisionScope.TASK,
                         target=self.task_target("T-02"),
                         description="Trang trí chờ đèn về — T-02 chặn T-04",
                         ops=[OpSpec(target=self.task_target("T-02"), facet="dependency",
                                     op="add",
                                     value={"successor_task_id": self.task_ids["T-04"]})],
                         citations=evidence("m0031", "m0032"))
        self.new_task("T-C1", "m0020", by="mai", title="Soạn giáo án tháng 9",
                      group="G-CL", team="TEAM-ED", pics=["tuan"], citations=["m0020"])
        self.new_task("T-C2", "m0035", by="mai", title="Tập 2 tiết mục Trung Thu",
                      group="G-CL", team="TEAM-ED", pics=["thao"], citations=["m0035"])

        # D-11: member budget proposal — held (below authority), later swept by D-12
        if "T-02" in self.task_ids:
            self.propose("D-11", "m0039", by="duc", scope=DecisionScope.TASK,
                         target=self.task_target("T-02"),
                         description="Đề xuất nâng budget đèn lên 3tr",
                         ops=[OpSpec(target=self.task_target("T-02"), facet="attr:budget",
                                     op="set", value="3.000.000 VND")],
                         citations=evidence("m0039"))

        self.new_task("T-05", "m0041", by="linh", title="Thuê loa trường + 2 micro",
                      group="G-TT", team="TEAM-EV", pics=["duc"],
                      created_from=CreatedFrom.MARKER, citations=["m0041"])
        self.new_task("T-06", "m0045", by="linh", title="Tiết mục văn nghệ thiếu nhi",
                      group="G-TT", team="TEAM-EV", pics=["khoa"], citations=["m0045"])

        # D-12: lead sets the budget — effective write sweeps D-11 → rejected(overruled)
        if "T-02" in self.task_ids:
            self.propose("D-12", "m0049", by="linh", scope=DecisionScope.TASK,
                         target=self.task_target("T-02"), description="Budget đèn 2tr5",
                         ops=[OpSpec(target=self.task_target("T-02"), facet="attr:budget",
                                     op="set", value="2.500.000 VND")],
                         citations=evidence("m0049"))

        self.update("U-01", "m0051", task="T-C1", by="tuan", kind="status",
                    payload={"status": "done"})

        # D-13 (propose half): duc's layout plan — approved by reply much later (m0088)
        if "T-04" in self.task_ids:
            self.propose("D-13", "m0054", by="duc", scope=DecisionScope.TASK,
                         target=self.task_target("T-04"),
                         description="Phương án sân khấu: backdrop 6m, đèn 2 cụm, "
                                     "trò chơi dọc hàng rào, thoát hiểm bên trái",
                         ops=[OpSpec(target=self.task_target("T-04"), facet="attr:layout",
                                     op="set",
                                     value="backdrop 6m | đèn 2 cụm | trò chơi dọc hàng rào "
                                           "| thoát hiểm trái")],
                         citations=evidence("m0054", "m0088"),
                         note="hydration hero: reply-target m0054 is in an earlier window")

        self.new_task("T-07", "m0056", by="linh", title="Gian trò chơi (6 trạm)",
                      group="G-TT", team="TEAM-EV", pics=[], citations=["m0056"],
                      note="born PIC-null — trang claims it later (G44)")

        if not self.skip("m0067") and "T-C2" in self.task_ids and "T-06" in self.task_ids:
            # DEP-2: campaign↔program edge — upstream lead confirmed in her group
            self.propose("DEP-2", "m0067", by="mai", scope=DecisionScope.TASK,
                         target=self.task_target("T-C2"),
                         description="Văn nghệ đêm hội cần 2 tiết mục lớp học tập xong",
                         ops=[OpSpec(target=self.task_target("T-C2"), facet="dependency",
                                     op="add",
                                     value={"successor_task_id": self.task_ids["T-06"]})],
                         citations=evidence("m0065", "m0067"))

        # ── trang arrives (G44) and claims the games task ────────────────
        if not self.skip("m0073") and "T-07" in self.task_ids:
            self.propose("D-09", "m0073", by="trang", scope=DecisionScope.TASK,
                         target=self.task_target("T-07"),
                         description="trang nhận gian trò chơi",
                         ops=[OpSpec(target=self.task_target("T-07"), facet="assignment",
                                     op="add", value=self.user("trang"))],
                         citations=evidence("m0073", "m0074"))
            self.approve("D-09-approve", "m0074", of="D-09", by="linh")
            self.org.confirm_membership(self.user("trang"), actor="linh")
            self.session.commit()

        self.new_task("T-C3", "m0076", by="mai", title="Tổng duyệt 14:00 thứ 7 19/9 tại sân trường",
                      group="G-CL", team="TEAM-ED", pics=["mai"],
                      citations=["m0076", "m0078"],
                      note="relay: tuan posted for mai; mai confirmed next day")

        # D-10: supersedes the paper-lantern order (child safety, all-hands 09-07)
        if "T-02" in self.task_ids:
            self.propose("D-10", "m0082", by="linh", scope=DecisionScope.TASK,
                         target=self.task_target("T-02"),
                         description="Đổi sang 150 đèn LED thay cho 200 đèn giấy (an toàn)",
                         ops=[OpSpec(target=self.task_target("T-02"), facet="attr:order",
                                     op="set", value="150 đèn LED Kim Long (mẫu 16k) ~2tr4")],
                         citations=evidence("m0082"),
                         context="an toàn trẻ em — bàn ở all-hands 09-07 (turns 05:30-06:10)")

        # ── all-hands transcript records (bulk source, G29) ──────────────
        self.propose("TD-1", "m0083", by="linh", scope=DecisionScope.PROJECT,
                     target=f"project:{projects['P-TT']}",
                     description="Mở cổng 18:00, chương trình 18:30-21:00, "
                                 "văn nghệ thiếu nhi 19:00, dọn xong trước 22:00",
                     ops=[OpSpec(target=f"project:{projects['P-TT']}",
                                 facet="attr:program-times", op="set",
                                 value="cổng 18:00 | chương trình 18:30-21:00 | "
                                       "văn nghệ 19:00 | dọn xong 22:00")],
                     citations=[], created_from=CreatedFrom.TRANSCRIPT, confidence=1.0,
                     context="all-hands 2026-09-07, turns 00:52-01:31")
        self.propose("TD-2", "m0083", by="linh", scope=DecisionScope.PROJECT,
                     target=f"project:{projects['P-TT']}",
                     description="Ngân sách trần 15 triệu; vượt phải hỏi linh; "
                                 "nếu cắt thì cắt quà trước",
                     ops=[OpSpec(target=f"project:{projects['P-TT']}",
                                 facet="attr:budget-cap", op="set",
                                 value="15.000.000 VND — vượt hỏi linh, cắt quà trước")],
                     citations=[CitationSpec(message_id=mid("m0109"),
                                             kind=CitationKind.CORROBORATION,
                                             rev_at_capture=1)],
                     created_from=CreatedFrom.TRANSCRIPT, confidence=1.0,
                     context="all-hands 2026-09-07, turns 02:08-02:52")

        # ── the blocker beat + progress updates ──────────────────────────
        self.update("U-06", "m0085", task="T-02", by="minh", kind="status",
                    payload={"status": "blocked",
                             "waiting_on_party_id": parties.get("PTY-KL"),
                             "waiting_on_text": "Kim Long"},
                    created_from=CreatedFrom.MARKER)
        self.approve("D-13-approve", "m0088", of="D-13", by="linh")
        self.update("U-02", "m0092", task="T-C2", by="thao", kind="note",
                    payload={"text": self.message_text("m0092")})
        self.update("U-05", "m0095", task="T-01", by="linh", kind="status",
                    payload={"status": "done"})

        # DC-05: EXCEPTION HERO — windowed decision shadows DC-01 on 20/9 only
        from datetime import datetime
        self.propose("DC-05", "m0098", by="mai", scope=DecisionScope.TEAM,
                     target=f"team:{teams['TEAM-ED']}",
                     description="Nghỉ học CN 20/9 (trường chấm thi) — một tuần duy nhất",
                     ops=[OpSpec(target=f"team:{teams['TEAM-ED']}",
                                 facet="attr:class-schedule", op="set",
                                 value="NGHỈ 20/9 — trường mượn phòng chấm thi")],
                     citations=evidence("m0098"),
                     effect_window=(datetime(2026, 9, 20, 0, 0),
                                    datetime(2026, 9, 20, 23, 59)),
                     note="shadows DC-01 for one Sunday; the standing schedule survives")

        self.update("U-12", "m0101", task="T-03", by="an", kind="note",
                    payload={"text": self.message_text("m0100")})
        self.update("U-08", "m0104", task="T-07", by="trang", kind="note",
                    payload={"text": self.message_text("m0104")})
        self.update("U-07", "m0107", task="T-02", by="minh", kind="status",
                    payload={"status": "doing"})
        self.update("U-03", "m0110", task="T-C2", by="thao", kind="status",
                    payload={"status": "done"})
        self.update("U-04", "m0111", task="T-C3", by="mai", kind="status",
                    payload={"status": "done"})
        self.update("U-11", "m0112", task="T-06", by="khoa", kind="status",
                    payload={"status": "done"})
        self.update("U-10", "m0113", task="T-05", by="duc", kind="status",
                    payload={"status": "done"})
        self.update("U-09", "m0115", task="T-07", by="trang", kind="note",
                    payload={"text": self.message_text("m0115")})

        # ── one live pending proposal — the dashboard approve/reject beat ─
        self.new_task("DEMO-P1", "m0117", by="huong",
                      title="Chuẩn bị 200 phần quà Trung Thu cho các bé",
                      group="G-TT", team="TEAM-EV", pics=["huong"],
                      citations=["m0117"],
                      note="member proposal — chờ linh duyệt (demo write path)")


def main() -> None:
    from evermind.db.session import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("org_json", nargs="?", default="../data-v2/org.json")
    parser.add_argument("corpus", nargs="?", default="../data-v2/corpus.jsonl")
    parser.add_argument("--until", default=None,
                        help="stop the story at this corpus message id (e.g. m0100)")
    args = parser.parse_args()

    with SessionLocal() as session:
        ids = load_org_seed(session, args.org_json)  # idempotent
        org_data = json.loads(Path(args.org_json).read_text(encoding="utf-8"))
        channel_map = {g["channel_name"]: ids["groups"][g["id"]]
                       for g in org_data.get("chat_groups", []) if g.get("channel_name")}
        replayed = ReplayConnector(session).replay(
            Path(args.corpus), channel_group_ids=channel_map, pace_ms=0)
        session.commit()

        seeder = DemoSeeder(session, ids, until=args.until)
        seeder.ensure_trang()
        seeder.run()

        print(f"corpus: {replayed} new messages")
        for line in seeder.report:
            print(" ", line)
        print(f"tasks: { {k: v for k, v in sorted(seeder.task_ids.items())} }")


if __name__ == "__main__":
    main()
