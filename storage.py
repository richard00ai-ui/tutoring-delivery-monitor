"""两张 CSV 组成的本地数据库:

  students.csv  —— 主表,每次跑从 roster xlsx 增量 upsert
                    保留 first_seen / last_seen / active,即使学生下架了
                    也留档,避免历史 checks 找不到人
  checks.csv    —— 历史表,append-only。每天每个学生一行判定结果。
                    RETENTION_DAYS 天前的行自动清理。

设计动机(用户 2026-07-27 指示):
  - 原方案每天生成 checks_YYYY-MM-DD.csv/json 快照,7 天删掉
  - 新方案:主表 + 历史流水,累加记录,方便回溯任何一天的判定
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from judge import Verdict
from roster import Roster

STUDENTS_HEADER = [
    "group_id", "raw_id", "subject", "tutor",
    "start", "expiry", "source_sheet",
    "chat_id",
    "first_seen", "last_seen", "active",
]

CHECKS_HEADER = [
    "date", "group_id", "subject", "tutor",
    "status", "missing", "evidence", "checked_at",
]


def _fmt_date(d: date | None) -> str:
    return d.isoformat() if d else ""


def students_path(data_dir: Path) -> Path:
    return data_dir / "students.csv"


def checks_path(data_dir: Path) -> Path:
    return data_dir / "checks.csv"


def _read_students(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        return {row["group_id"]: row for row in csv.DictReader(f)}


def upsert_students(data_dir: Path, roster: list[Roster], today: date) -> tuple[int, int, int]:
    """把本次 roster 合并进 students.csv。返回 (新增, 更新, 本次未出现被标 inactive 的)。"""
    path = students_path(data_dir)
    existing = _read_students(path)
    today_str = today.isoformat()

    seen_now = set()
    new_n = updated_n = 0
    for r in roster:
        seen_now.add(r.group_id)
        prev = existing.get(r.group_id)
        row = {
            "group_id": r.group_id,
            "raw_id": r.raw_id,
            "subject": r.subject,
            "tutor": r.tutor,
            "start": _fmt_date(r.start),
            "expiry": _fmt_date(r.expiry),
            "source_sheet": r.source_sheet,
            # chat_id 由 sync_chats 单独维护:xlsx 不带,这里 upsert 时保留前值
            "chat_id": prev["chat_id"] if prev else "",
            "first_seen": prev["first_seen"] if prev else today_str,
            "last_seen": today_str,
            "active": "yes",
        }
        if prev is None:
            new_n += 1
        elif any(prev.get(k, "") != row[k] for k in ("subject", "tutor", "start", "expiry", "active")):
            updated_n += 1
        existing[r.group_id] = row

    inactive_n = 0
    for gid, row in existing.items():
        if gid not in seen_now and row.get("active", "yes") == "yes":
            row["active"] = "no"
            inactive_n += 1

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STUDENTS_HEADER)
        w.writeheader()
        for row in existing.values():
            w.writerow(row)

    return new_n, updated_n, inactive_n


def append_checks(data_dir: Path, verdicts: list[Verdict]) -> None:
    """把本次判定结果 append 到 checks.csv。同 (date, group_id) 已有的行会先删,再写,避免重复。"""
    path = checks_path(data_dir)
    existing = []
    if path.exists():
        with open(path, "r", encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))

    replace_keys = {(v.date, v.group_id) for v in verdicts}
    kept = [row for row in existing if (row["date"], row["group_id"]) not in replace_keys]

    now = datetime.now().isoformat(timespec="seconds")
    new_rows = []
    for v in verdicts:
        evidence_flat = " | ".join(
            f"{k}: {vals[0]}" for k, vals in v.evidence.items() if vals
        )
        new_rows.append({
            "date": v.date, "group_id": v.group_id, "subject": v.subject, "tutor": v.tutor,
            "status": v.status, "missing": "|".join(v.missing),
            "evidence": evidence_flat, "checked_at": now,
        })

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHECKS_HEADER)
        w.writeheader()
        for row in kept:
            w.writerow(row)
        for row in new_rows:
            w.writerow(row)


def cleanup_old_checks(data_dir: Path, retention_days: int, today: date) -> int:
    """删除 checks.csv 中 today - retention_days 之前的行。返回删除条数。"""
    path = checks_path(data_dir)
    if not path.exists():
        return 0
    cutoff = today - timedelta(days=retention_days)
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    kept = []
    dropped = 0
    for row in rows:
        try:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            kept.append(row)
            continue
        if d < cutoff:
            dropped += 1
        else:
            kept.append(row)
    if dropped:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CHECKS_HEADER)
            w.writeheader()
            for row in kept:
                w.writerow(row)
    return dropped
