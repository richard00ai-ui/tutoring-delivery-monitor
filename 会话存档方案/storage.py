"""三张 CSV 组成的本地数据库:

  students.csv     —— 学生主表(xlsx 每天 upsert)
  checks.csv       —— 每日判定历史(append-only, RETENTION_DAYS 天前清理)
  archive_msgs.csv —— 存档 SDK 拉下来的原始消息缓冲
                       (ARCHIVE_MSGS_RETENTION_DAYS 天前清理)

seq.txt 单独放,记录 SDK 上次拉到哪一条。
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from judge import Message, Verdict
from roster import Roster

STUDENTS_HEADER = [
    "group_id", "raw_id", "subject", "tutor",
    "start", "expiry", "source_sheet",
    "roomid",
    "first_seen", "last_seen", "active",
]

CHECKS_HEADER = [
    "date", "group_id", "subject", "tutor",
    "status", "missing", "evidence", "checked_at",
]

ARCHIVE_MSGS_HEADER = [
    "seq", "msgid", "action", "from_id", "roomid",
    "ts", "msgtype", "content",
]


def _fmt_date(d: date | None) -> str:
    return d.isoformat() if d else ""


def students_path(data_dir: Path) -> Path:
    return data_dir / "students.csv"


def checks_path(data_dir: Path) -> Path:
    return data_dir / "checks.csv"


def archive_msgs_path(data_dir: Path) -> Path:
    return data_dir / "archive_msgs.csv"


def seq_path(data_dir: Path) -> Path:
    return data_dir / "seq.txt"


# ── students ────────────────────────────────────────────

def _read_students(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        return {row["group_id"]: row for row in csv.DictReader(f)}


def upsert_students(data_dir: Path, roster: list[Roster], today: date) -> tuple[int, int, int]:
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
            "roomid": prev["roomid"] if prev else "",  # sync_rooms 维护
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


def update_roomid(data_dir: Path, mapping: dict[str, str]) -> int:
    """把 {group_id → roomid} 写回 students.csv。返回更新条数。"""
    path = students_path(data_dir)
    if not path.exists() or not mapping:
        return 0
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    updated = 0
    for row in rows:
        new_rid = mapping.get(row["group_id"])
        if new_rid and row.get("roomid") != new_rid:
            row["roomid"] = new_rid
            updated += 1
    if updated:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=STUDENTS_HEADER)
            w.writeheader()
            for row in rows:
                w.writerow(row)
    return updated


# ── checks ─────────────────────────────────────────────

def append_checks(data_dir: Path, verdicts: list[Verdict]) -> None:
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


# ── archive_msgs ───────────────────────────────────────

def append_archive_msgs(data_dir: Path, rows: list[dict]) -> None:
    """append 到 archive_msgs.csv。每行是 SDK 解密后归一化的消息字段。"""
    if not rows:
        return
    path = archive_msgs_path(data_dir)
    exists = path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ARCHIVE_MSGS_HEADER)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in ARCHIVE_MSGS_HEADER})


def read_archive_msgs_for_day(data_dir: Path, roomid: str, target_date: date) -> list[Message]:
    """从 archive_msgs.csv 筛出 (roomid, target_date) 的消息,归一化为 Message。"""
    path = archive_msgs_path(data_dir)
    if not path.exists() or not roomid:
        return []
    out: list[Message] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("roomid") != roomid:
                continue
            try:
                ts = datetime.fromisoformat(row["ts"])
            except (ValueError, KeyError):
                continue
            if ts.date() != target_date:
                continue
            out.append(Message(
                ts=ts,
                sender=row.get("from_id", ""),
                text=row.get("content", ""),
                msg_type=row.get("msgtype", "text"),
            ))
    out.sort(key=lambda m: m.ts)
    return out


def cleanup_old_archive_msgs(data_dir: Path, retention_days: int, today: date) -> int:
    path = archive_msgs_path(data_dir)
    if not path.exists():
        return 0
    cutoff = datetime.combine(today - timedelta(days=retention_days), datetime.min.time())
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    kept, dropped = [], 0
    for row in rows:
        try:
            ts = datetime.fromisoformat(row["ts"])
        except (ValueError, KeyError):
            kept.append(row)
            continue
        if ts < cutoff:
            dropped += 1
        else:
            kept.append(row)
    if dropped:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ARCHIVE_MSGS_HEADER)
            w.writeheader()
            for row in kept:
                w.writerow(row)
    return dropped


# ── seq 游标 ───────────────────────────────────────────

def read_seq(data_dir: Path) -> int:
    p = seq_path(data_dir)
    if not p.exists():
        return 0
    try:
        return int(p.read_text().strip())
    except ValueError:
        return 0


def write_seq(data_dir: Path, seq: int) -> None:
    seq_path(data_dir).write_text(str(seq))
