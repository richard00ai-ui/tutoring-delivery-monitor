"""开发调试用的假聊天数据。造几种典型状态给规则引擎试。"""
from __future__ import annotations

from datetime import datetime

from judge import Message


def _m(hh: int, mm: int, sender: str, text: str, mtype: str = "text") -> Message:
    return Message(ts=datetime(2026, 7, 26, hh, mm), sender=sender, text=text, msg_type=mtype)


# key = 学生编号(与 roster.group_id 对齐)
MOCK: dict[str, list[Message]] = {
    # 完整完成:发了打卡 + 每科计划都有
    "d001": [
        _m(9, 10, "老师张", "各位家长,#行测今日计划:模拟卷 P30-P45,晚上 21:00 前提交"),
        _m(21, 15, "家长李", "#今日打卡 已完成"),
    ],
    # 缺打卡
    "d002": [
        _m(9, 30, "老师张", "#职测今日计划:数量关系专题 20 题"),
    ],
    # 缺一科计划(有英语没政治)
    "e001": [
        _m(9, 5, "老师王", "#英语今日计划:阅读 Text3 + 精读"),
        _m(9, 6, "老师王", "#专业课今日计划:311 教育心理学第 5 章"),
        _m(22, 20, "学生小明", "#今日打卡 都做完了"),
        # 缺 #政治今日计划
    ],
    # 完全没动作
    "d003": [],
}


def get_mock_chat(group_id: str) -> list[Message]:
    return MOCK.get(group_id, [])
