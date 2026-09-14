"""规则引擎。跟旧方案完全一致,只保留 hashtag 判定。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    ts: datetime
    sender: str
    text: str
    msg_type: str = "text"


@dataclass
class Verdict:
    group_id: str
    student: str
    subject: str
    tutor: str
    date: str  # YYYY-MM-DD
    status: str  # 完成 / 未完成 / 数据不全
    missing: list[str] = field(default_factory=list)
    evidence: dict[str, list[str]] = field(default_factory=dict)


def _summarize(m: Message) -> str:
    return f"[{m.ts.strftime('%H:%M')}] {m.sender}: {m.text[:60]}"


def split_subjects(s: str, sep_regex: str = r"[,+、,/]+") -> list[str]:
    if not s:
        return []
    parts = re.split(sep_regex, s)
    return [p.strip() for p in parts if p.strip()]


def judge(messages: list[Message], subject_str: str, rules_cfg: dict,
          group_id: str, student: str, tutor: str, date_str: str) -> Verdict:
    checkin_tag = rules_cfg["checkin_tag"]
    plan_tpl = rules_cfg["plan_tag_template"]
    sep = rules_cfg.get("subject_split_regex", r"[,+、,/]+")
    subjects = split_subjects(subject_str, sep)

    missing: list[str] = []
    evidence: dict[str, list[str]] = {}

    hits = [m for m in messages if checkin_tag in m.text]
    if hits:
        evidence[checkin_tag] = [_summarize(m) for m in hits[:2]]
    else:
        missing.append(checkin_tag)

    for subj in subjects:
        tag = plan_tpl.replace("{subject}", subj)
        hits = [m for m in messages if tag in m.text]
        if hits:
            evidence[tag] = [_summarize(m) for m in hits[:2]]
        else:
            missing.append(tag)

    return Verdict(
        group_id=group_id, student=student, subject=subject_str, tutor=tutor,
        date=date_str,
        status="完成" if not missing else "未完成",
        missing=missing, evidence=evidence,
    )


def load_rules(yaml_path) -> dict:
    import yaml
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
