"""日检入口:读 roster xlsx → upsert 学生主表 → 遍历学生拿聊天 → 规则判定
              → 追加 checks 历史表 → 未完成推送。

跑法:
  开发模式 (Mac, 假数据):     USE_MOCK=true python3 main.py
  真跑     (客户机, 真 RPA): USE_MOCK=false python3 main.py [YYYY-MM-DD]
默认判定 "今天";带日期参数可回溯某天。
"""
from __future__ import annotations

import sys
from datetime import date, datetime

import config
from judge import Message, Verdict, judge, load_rules
from notify import build_markdown, push_wecom_bot
from roster import Roster, load_roster
from storage import append_checks, cleanup_old_checks, upsert_students


def get_chat(r: Roster, today: date) -> list[Message]:
    if config.USE_MOCK:
        from mock_data import get_mock_chat
        return get_mock_chat(r.group_id)
    if config.READER == "mcp":
        from mcp_reader import read_today_chat
        return read_today_chat(r.group_id, r.subject, today, chat_id=r.chat_id)
    from wecom_reader import read_today_chat
    return read_today_chat(r.group_id, r.subject, today)


def run(target_date: date) -> None:
    date_str = target_date.strftime("%Y-%m-%d")
    print(f"[main] 判定日期: {date_str}, USE_MOCK={config.USE_MOCK}")

    roster = load_roster(config.ROSTER_XLSX, target_date)
    rules_cfg = load_rules(config.RULES_YAML)
    print(f"[main] roster: {len(roster)} 个在服务学生")

    new_n, upd_n, inact_n = upsert_students(config.DATA_DIR, roster, target_date)
    print(f"[main] students.csv: 新增 {new_n}, 更新 {upd_n}, 标 inactive {inact_n}")

    verdicts: list[Verdict] = []
    for r in roster:
        tutor = r.tutor or "未指派"
        try:
            chat = get_chat(r, target_date)
        except NotImplementedError as e:
            print(f"[main] {r.group_id} RPA 未实现: {e}")
            v = Verdict(r.group_id, r.group_id, r.subject, tutor,
                        date_str, "数据不全", missing=["RPA 未实现"])
        else:
            v = judge(chat, r.subject, rules_cfg,
                      group_id=r.group_id, student=r.group_id, tutor=tutor,
                      date_str=date_str)
        verdicts.append(v)

    append_checks(config.DATA_DIR, verdicts)
    print(f"[main] checks.csv: 追加 {len(verdicts)} 条")

    dropped = cleanup_old_checks(config.DATA_DIR, config.RETENTION_DAYS, target_date)
    if dropped:
        print(f"[main] 清理 {config.RETENTION_DAYS} 天前的 checks 记录 {dropped} 条")

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
