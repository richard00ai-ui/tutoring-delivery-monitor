"""每日判定入口(每天 22:00 触发)。

流程:读 xlsx → upsert students → 遍历学生 → 从 archive_msgs.csv 筛出当日该群消息
      → 规则判定 → append checks + 清理旧数据 → 推送企微

跑法:
  开发 (Mac, mock):  USE_MOCK=true python3 daily_check.py 2026-07-26
                     先跑 mock_data.py 造数据 + 分配 roomid,再跑本脚本
  容器内 (每天 22:00): APScheduler 调度触发(见 scheduler.py)
"""
from __future__ import annotations

import sys
from datetime import date, datetime

import config
from judge import Verdict, judge, load_rules
from notify import build_markdown, push_wecom_bot
from roster import Roster, load_roster
from storage import (
    append_checks,
    cleanup_old_archive_msgs,
    cleanup_old_checks,
    read_archive_msgs_for_day,
    upsert_students,
)


def run(target_date: date) -> None:
    date_str = target_date.strftime("%Y-%m-%d")
    print(f"[daily_check] 判定日期: {date_str}, USE_MOCK={config.USE_MOCK}")

    roster = load_roster(config.ROSTER_XLSX, target_date)
    rules_cfg = load_rules(config.RULES_YAML)
    print(f"[daily_check] roster: {len(roster)} 个在服务学生")

    new_n, upd_n, inact_n = upsert_students(config.DATA_DIR, roster, target_date)
    print(f"[daily_check] students.csv: 新增 {new_n}, 更新 {upd_n}, 标 inactive {inact_n}")

    # 用 upsert 后最新的 students.csv 来拿 roomid
    import csv
    with open(config.DATA_DIR / "students.csv", "r", encoding="utf-8", newline="") as f:
        by_gid = {row["group_id"]: row for row in csv.DictReader(f)}

    verdicts: list[Verdict] = []
    no_roomid = 0
    for r in roster:
        tutor = r.tutor or "未指派"
        roomid = by_gid.get(r.group_id, {}).get("roomid", "")
        if not roomid:
            no_roomid += 1
            verdicts.append(Verdict(
                r.group_id, r.group_id, r.subject, tutor,
                date_str, "数据不全", missing=["未映射 roomid(先跑 sync_rooms)"],
            ))
            continue

        msgs = read_archive_msgs_for_day(config.DATA_DIR, roomid, target_date)
        v = judge(msgs, r.subject, rules_cfg,
                  group_id=r.group_id, student=r.group_id, tutor=tutor,
                  date_str=date_str)
        verdicts.append(v)

    if no_roomid:
        print(f"[daily_check] {no_roomid} 个学生缺 roomid,标记数据不全")

    append_checks(config.DATA_DIR, verdicts)
    print(f"[daily_check] checks.csv: 追加 {len(verdicts)} 条")

    dropped_c = cleanup_old_checks(config.DATA_DIR, config.RETENTION_DAYS, target_date)
    dropped_m = cleanup_old_archive_msgs(config.DATA_DIR, config.ARCHIVE_MSGS_RETENTION_DAYS, target_date)
    if dropped_c or dropped_m:
        print(f"[daily_check] 清理: checks {dropped_c} 条, archive_msgs {dropped_m} 条")

    md = build_markdown(date_str, verdicts)
    print("---- 通知内容预览 ----")
    print(md)
    print("---- END ----")
    push_wecom_bot(config.WECOM_BOT_WEBHOOK, md)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        d = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    else:
        d = date.today()
    run(d)
