"""通过 wecom-cli(MCP 授权用户身份)读取指定群的当日消息。

架构变更点(2026-07-27):
  原方案:RPA 抓 Mac 企微客户端 UI (wecom_reader.py)
  新方案:MCP 机器人以用户身份调 API,不依赖 UI、不依赖客户机在线

前置条件:
  1. 已在企微创建 API 模式机器人,拿到 BotID / Secret
  2. 客户机装 Node.js + wecom-cli:  npm install -g @wecom/cli
  3. 用户已授权机器人「消息」权限(7 天 renew,workbuddy 周提醒)
  4. students.csv 里的 chat_id 已由 sync_chats.py 填充

实现方式:subprocess 调 wecom-cli(客户机上装 wecom-cli 即可,Python 侧零依赖)
"""
from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, timedelta
from typing import Iterator

from judge import Message


def _run_cli(category: str, method: str, args: dict) -> dict:
    """通用 wecom-cli 调用。失败 raise RuntimeError,携带 stderr。"""
    proc = subprocess.run(
        ["wecom-cli", category, method, json.dumps(args, ensure_ascii=False)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"wecom-cli {category} {method} 失败 (code={proc.returncode}): {proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"wecom-cli 输出非 JSON: {proc.stdout[:200]}") from e


def _iter_messages(chat_id: str, begin: datetime, end: datetime) -> Iterator[dict]:
    """封装 get_message 的 cursor 分页。"""
    cursor = ""
    while True:
        args = {
            "chat_type": 2,  # 群聊
            "chatid": chat_id,
            "begin_time": begin.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if cursor:
            args["cursor"] = cursor
        resp = _run_cli("msg", "get_message", args)
        # ⚠️ 实际字段名待联调时确认;这里按截图/官方 API 常见形态假设
        for m in resp.get("messages", []) or resp.get("chats", []):
            yield m
        cursor = resp.get("next_cursor") or ""
        if not resp.get("has_more") or not cursor:
            break


def _to_message(raw: dict) -> Message:
    """把 API 返回的原始消息 dict 归一化为 judge.Message。

    ⚠️ 字段名以官方最终返回为准,联调时修正。
    """
    ts_raw = raw.get("send_time") or raw.get("ts") or raw.get("timestamp")
    if isinstance(ts_raw, str):
        ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
    elif isinstance(ts_raw, (int, float)):
        ts = datetime.fromtimestamp(ts_raw)
    else:
        ts = datetime.now()

    return Message(
        ts=ts,
        sender=raw.get("from") or raw.get("sender") or raw.get("from_name") or "",
        text=raw.get("content") or raw.get("text") or "",
        msg_type=raw.get("msgtype") or raw.get("type") or "text",
    )


def read_today_chat(group_id: str, subject: str, today: date, chat_id: str = "") -> list[Message]:
    """主接口。跟 wecom_reader.read_today_chat 签名兼容,多一个 chat_id 参数。"""
    if not chat_id:
        raise LookupError(f"学生 {group_id} 未映射 chat_id(先跑 sync_chats.py)")

    begin = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time().replace(microsecond=0))
    return [_to_message(raw) for raw in _iter_messages(chat_id, begin, end)]
