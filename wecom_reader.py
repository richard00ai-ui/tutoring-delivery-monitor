"""RPA 读取企微 Mac 客户端聊天记录。

⚠️ 尚未实现。这层要在客户机上装企微、登录、加进目标群之后才能真跑。
留三条备选路径,联调时挑一条落地:

1) macOS Accessibility API (推荐)
   通过 pyobjc + AXUIElement 读企微窗口的 UI 元素,拿到可见文本。
   不需要 OCR,准确率高。缺点:企微版本升级 UI 可能变。
   参考:https://developer.apple.com/documentation/applicationservices/axuielement_h

2) PyAutoGUI + 屏幕 OCR
   截屏 + 本地 OCR (PaddleOCR / macOS Vision framework)。
   稳定性中等,慢。作为兜底。

3) 逆向企微本地缓存
   企微 Mac 版本地有加密 SQLite 缓存,社区有解密方案。
   风险最高,升级最容易崩,合规灰色。**除非另两条都不行,否则不碰。**

主入口签名固定,联调时把 raise 换成真实实现即可。
"""
from __future__ import annotations

from datetime import date

from judge import Message


def read_today_chat(group_id: str, group_name: str, today: date) -> list[Message]:
    """打开指定群,滚动读取当日消息,返回结构化列表。"""
    raise NotImplementedError(
        "RPA 层未实现。开发时设 USE_MOCK=true 走 mock_data。"
    )
