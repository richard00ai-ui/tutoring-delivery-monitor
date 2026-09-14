"""开发调试用假存档消息。写入 archive_msgs.csv 供 daily_check 使用。

跑法:python3 mock_data.py  会重置 archive_msgs.csv 到几组样本数据
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import config
import storage


def _row(seq: int, roomid: str, from_id: str, hh: int, mm: int, content: str, mtype: str = "text") -> dict:
    return {
        "seq": seq,
        "msgid": f"mock_{seq}",
        "action": "send",
        "from_id": from_id,
        "roomid": roomid,
        "ts": datetime(2026, 7, 26, hh, mm).isoformat(),
        "msgtype": mtype,
        "content": content,
    }


def sample_rows() -> list[dict]:
    """三种典型状态,对应 3 个学生 3 个 roomid。"""
    return [
        # G001 → 完成 (发计划 + 打卡)
        _row(1, "wrmockG001", "老师张", 9, 10, "各位家长,#行测今日计划:模拟卷 P30-P45,晚上 21:00 前提交"),
        _row(2, "wrmockG001", "家长李", 21, 15, "#今日打卡 已完成"),
        # G002 → 缺打卡
        _row(3, "wrmockG002", "老师张", 9, 30, "#职测今日计划:数量关系专题 20 题"),
        # G003 → 有打卡但缺一门科(缺 #政治今日计划)
        _row(4, "wrmockG003", "老师王", 9, 5, "#英语今日计划:阅读 Text3 + 精读"),
        _row(5, "wrmockG003", "老师王", 9, 6, "#专业课今日计划:311 教育心理学第 5 章"),
        _row(6, "wrmockG003", "学生小明", 22, 20, "#今日打卡 都做完了"),
    ]


def install_mock_students() -> None:
    """把 mock roomid 硬填到 students.csv 前 3 个 active 学生上,方便端到端跑通。"""
    import csv
    path = storage.students_path(config.DATA_DIR)
    if not path.exists():
        print("[mock] students.csv 不存在,先跑一次 daily_check.py 生成")
        return
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    mock_ids = ["wrmockG001", "wrmockG002", "wrmockG003"]
    assigned = 0
    for row in rows:
        if row.get("active") != "yes":
            continue
        if assigned >= 3:
            break
        row["roomid"] = mock_ids[assigned]
        assigned += 1
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=storage.STUDENTS_HEADER)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"[mock] 给前 {assigned} 个 active 学生分配了 mock roomid")


def reset_archive_msgs() -> None:
    p = storage.archive_msgs_path(config.DATA_DIR)
    if p.exists():
        p.unlink()
    storage.append_archive_msgs(config.DATA_DIR, sample_rows())
    print(f"[mock] 写入 {len(sample_rows())} 条 mock 消息到 {p}")


if __name__ == "__main__":
    reset_archive_msgs()
    install_mock_students()
