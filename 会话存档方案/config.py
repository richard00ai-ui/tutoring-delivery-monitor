"""集中读取环境配置。容器内 workbuddy / docker-compose 注入。"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent

# 数据目录(挂载到宿主机 ./data)
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# xlsx 学生名单(主管每天覆盖)
ROSTER_XLSX = Path(os.getenv("ROSTER_XLSX", ROOT / "督学服务整理.xlsx"))

# 规则配置
RULES_YAML = Path(os.getenv("RULES_YAML", ROOT / "rules.yaml"))

# 企微内部管理群 - 群机器人 webhook(告警推这里)
WECOM_BOT_WEBHOOK = os.getenv("WECOM_BOT_WEBHOOK", "").strip()

# 保留天数(daily_check.py 清理 checks.csv 用)
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))

# archive_msgs.csv 保留天数(存档拉下来的原始消息)
ARCHIVE_MSGS_RETENTION_DAYS = int(os.getenv("ARCHIVE_MSGS_RETENTION_DAYS", "10"))

# 开发模式:True 用 mock_data,False 走真实 SDK
USE_MOCK = os.getenv("USE_MOCK", "true").lower() in ("1", "true", "yes")

# ── 会话存档 SDK 相关 ──────────────────────────────────

SDK_LIB_PATH = Path(os.getenv("SDK_LIB_PATH", ROOT / "lib" / "libWeWorkFinanceSdk_C.so"))
CORPID = os.getenv("WECOM_CORPID", "").strip()
SECRET = os.getenv("WECOM_SECRET", "").strip()
PRIVATE_KEY_PATH = Path(os.getenv("PRIVATE_KEY_PATH", ROOT / "keys" / "wecom.pri.pem"))

# 每次 GetChatData 批大小
FETCH_BATCH_SIZE = int(os.getenv("FETCH_BATCH_SIZE", "1000"))
# 单次调度最多拉多少条(防止无限拉)
FETCH_MAX_PER_RUN = int(os.getenv("FETCH_MAX_PER_RUN", "50000"))
