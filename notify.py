"""企微内部管理群 - 群机器人推送。"""
from __future__ import annotations

import json
from urllib import request

from judge import Verdict


def build_markdown(date_str: str, verdicts: list[Verdict]) -> str:
    """把当日结果拼成一段 markdown。只推未完成的群 + 汇总数字。"""
    total = len(verdicts)
    incomplete = [v for v in verdicts if v.status != "完成"]
    completed_n = total - len(incomplete)

    lines = [
        f"## {date_str} 督学服务日检",
        f"共 **{total}** 群, 完成 **{completed_n}**, 待跟进 **{len(incomplete)}**",
    ]
    if incomplete:
        lines.append("")
        lines.append("**未完成 / 数据不全:**")
        for v in incomplete[:30]:  # 单条 markdown 消息 4096 字符上限,截前 30
            miss = ", ".join(v.missing) if v.missing else v.status
            subj = f" [{v.subject}]" if v.subject else ""
            lines.append(f"- <font color=\"warning\">{v.student}</font>{subj} ({v.tutor}) — {miss}")
        if len(incomplete) > 30:
            lines.append(f"...另有 {len(incomplete) - 30} 个未列出,详见 CSV")
    return "\n".join(lines)


def push_wecom_bot(webhook: str, markdown: str) -> None:
    if not webhook:
        print("[notify] WECOM_BOT_WEBHOOK 未配置,跳过推送")
        return
    payload = {"msgtype": "markdown", "markdown": {"content": markdown}}
    req = request.Request(
        webhook,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        print(f"[notify] wecom bot resp: {body}")
