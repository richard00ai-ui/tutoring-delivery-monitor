"""把「群 roomid」跟「学生编号」对齐,回填到 students.csv。

两条路径:
  1) 自动:从 archive_msgs.csv 收集所有 roomid,调 msgaudit/groupchat/get 拿群名,
     用正则从群名解析学生编号,匹配 students.csv 回填。
  2) 手动兜底:如果自动匹配失败(群名不规范或 API 不通),生成 unmatched_rooms.csv
     让主管人工填写 group_id 后重跑。

⚠️ msgaudit/groupchat/get 需要额外 access_token(企微 API,非 SDK),这里留骨架。
"""
from __future__ import annotations

import csv
import logging
import re
from collections import defaultdict
from pathlib import Path

import config
import storage

log = logging.getLogger(__name__)

# 群名格式约定: "<编号> <科目>",如 "e123 政治+英语" / "d456 行测"
_GROUP_NAME_RE = re.compile(r"^\s*([a-zA-Z]+\d+[!！]?)\s+")


def _parse_id_from_group_name(name: str) -> str:
    m = _GROUP_NAME_RE.match(name or "")
    if not m:
        return ""
    # 去掉末尾感叹号,归一化大小写
    raw = m.group(1).rstrip("!！").lower()
    return raw


def collect_roomids_from_archive(data_dir: Path) -> set[str]:
    path = storage.archive_msgs_path(data_dir)
    if not path.exists():
        return set()
    roomids = set()
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            r = row.get("roomid")
            if r:
                roomids.add(r)
    return roomids


def fetch_room_name(roomid: str) -> str:
    """调 msgaudit/groupchat/get 拿群名。

    ⚠️ 这里留 stub,联调时接:
      POST https://qyapi.weixin.qq.com/cgi-bin/msgaudit/groupchat/get?access_token=<>
      body: {"roomid": roomid}
      response: {"roomname": "...", "creator": "...", "members": [...], ...}
    """
    raise NotImplementedError("msgaudit/groupchat/get 待联调时实现")


def sync() -> dict:
    """遍历存档里的所有 roomid,尽量匹配学生编号,回填 students.csv。"""
    roomids = collect_roomids_from_archive(config.DATA_DIR)
    log.info(f"共 {len(roomids)} 个 unique roomid")

    mapping: dict[str, str] = {}   # group_id → roomid
    unmatched: list[tuple[str, str]] = []  # (roomid, room_name)

    for rid in roomids:
        try:
            name = fetch_room_name(rid)
        except NotImplementedError:
            unmatched.append((rid, "<未实现>"))
            continue
        except Exception as e:
            log.warning(f"fetch_room_name({rid}) 失败: {e}")
            unmatched.append((rid, "<获取失败>"))
            continue

        gid = _parse_id_from_group_name(name)
        if gid:
            mapping[gid] = rid
        else:
            unmatched.append((rid, name))

    updated = storage.update_roomid(config.DATA_DIR, mapping)

    if unmatched:
        p = config.DATA_DIR / "unmatched_rooms.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["roomid", "room_name", "hint"])
            for rid, name in unmatched:
                w.writerow([rid, name, "请人工填写对应 group_id 并合并回 students.csv"])
        log.info(f"{len(unmatched)} 个群未匹配,已写入 {p}")

    return {"total_rooms": len(roomids), "matched": len(mapping), "updated": updated, "unmatched": len(unmatched)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = sync()
    print(result)
