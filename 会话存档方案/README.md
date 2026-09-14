# 督学交付质量监控 — 会话存档方案

> 这是**独立、自包含**的一份实施包。跟旧的 MCP 方案不共用代码,可以单独交付到客户机。

## 跟旧方案的区别

| 维度 | 旧 (MCP) | 本方案 (存档) |
|---|---|---|
| 数据来源 | wecom-cli 授权用户身份读消息 | 企微官方「会话内容存档」SDK |
| 授权 | 每 7 天 renew | 一次开通,长期有效 |
| 合规 | 灰色偏中 | 官方合规通道 |
| 成本 | 免费 | 服务版许可 ~900 元/人/年(5 人起) |
| 外部群覆盖 | 未验证 | 官方明确支持 |
| SDK 平台 | 跨平台 | 只有 Linux/Windows,**Mac 客户机必须用 Docker** |
| 拉取模式 | 用户在线 → 现读 | 服务器缓存 5 天 → 增量拉(seq 游标) |

## 前置条件(许可到位那天前完成)

1. 企业已完成企微认证,开通「会话内容存档」许可(服务版起,~900 元/员工/年)
2. 已在管理端配置存档成员范围(把督学老师勾进去)
3. 拿到 corpid / secret,生成 RSA 密钥对(公钥填管理端,私钥保管好)
4. 客户机装了 Docker Desktop
5. 主管每天导出 `督学服务整理.xlsx` 到本目录

## 快速开始

```bash
# 1. 准备 SDK 二进制(许可到位后从官方下载)
#    放入 lib/ 目录: libWeWorkFinanceSdk_C.so (Linux)

# 2. 准备密钥
cp .env.example .env
# 编辑 .env 填 corpid / secret / private_key 路径
cp <你的私钥> keys/wecom.pri.pem

# 3. 起容器
docker compose up -d

# 4. 看日志
docker compose logs -f
```

## 开发/测试(Mac 本机,不需要 SDK)

```bash
pip install -r requirements.txt
USE_MOCK=true python3 daily_check.py 2026-07-27
```

## 目录结构

```
会话存档方案/
├── daily_check.py       # 日检入口(每天 22:00 触发)
├── fetch_worker.py      # 拉取入口(每小时循环调 SDK 拉增量)
├── scheduler.py         # 单进程 APScheduler,容器内跑
├── archive_fetcher.py   # SDK ctypes 封装 + 增量拉逻辑
├── sync_rooms.py        # roomid ↔ 学生编号 映射同步
├── roster.py            # xlsx 学生名单读取
├── judge.py             # 规则引擎(hashtag 判定)
├── storage.py           # CSV 落盘 (students/checks/archive_msgs)
├── notify.py            # 企微群机器人推送
├── mock_data.py         # 假数据(开发用)
├── config.py            # 环境配置
├── rules.yaml           # 判定规则(可改不用动代码)
├── lib/                 # 官方 SDK 二进制(许可到位后放)
├── keys/                # RSA 私钥(严格权限)
├── data/                # 输出数据(挂载卷,Mac 侧直接看)
│   ├── students.csv     # 学生主表
│   ├── checks.csv       # 每日判定历史
│   ├── archive_msgs.csv # 存档消息缓冲(近 N 天)
│   └── seq.txt          # SDK 拉取游标
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── 技术方案.md
└── workbuddy指令.md
```

## 部署顺序

见 [workbuddy指令.md](workbuddy指令.md)。
