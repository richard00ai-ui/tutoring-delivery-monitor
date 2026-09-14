"""集中读取环境配置。生产上跑在客户机时,workbuddy 会注入这些变量。"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent

# 结果输出目录 (每日 CSV + JSON 快照)
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 主管从腾讯文档导出的学生名单 (xlsx),多 sheet 结构
ROSTER_XLSX = Path(os.getenv("ROSTER_XLSX", ROOT / "督学服务整理.xlsx"))

# 规则配置
RULES_YAML = Path(os.getenv("RULES_YAML", ROOT / "rules.yaml"))

# 企微内部管理群 - 群机器人 webhook (未完成告警推这里)
WECOM_BOT_WEBHOOK = os.getenv("WECOM_BOT_WEBHOOK", "").strip()

# 数据保留天数
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))

# 开发模式:True 用 mock_data,False 走真实 reader
USE_MOCK = os.getenv("USE_MOCK", "true").lower() in ("1", "true", "yes")

# 真实 reader 走哪条路径:
#   "mcp" — 用 wecom-cli MCP 授权,走 API(默认,不依赖 UI)
#   "rpa" — 用 macOS Accessibility API,走客户端 UI(备用/兜底)
READER = os.getenv("READER", "mcp").lower()
