# workbuddy 执行指令合集 — 会话存档方案

> **给客户机 workbuddy 的操作员/AI 助手看**。每一段都是完整任务描述,可直接粘给 workbuddy 让它翻译成 Skill / 定时任务 / Docker 操作。
>
> **执行顺序:A(许可到位前) → B(许可到位后一次性) → C(常态运维) → D(定期人工)**

---

## A. 前置准备 (许可到位前,workbuddy 可辅助)

**贴给 workbuddy:**

```
帮我准备好客户机跑督学监控项目的环境。今天要做的:

1) 检查客户机是否已装 Docker Desktop for Mac。
   - 没装:提示我去官网下载安装。
2) 检查项目目录 /Users/<客户用户名>/会话存档方案/ 是否已就位
   (含 Dockerfile / docker-compose.yml / *.py / rules.yaml 等)。
3) 检查 lib/ 和 keys/ 目录存在(初始为空,等许可到位放东西)。
4) 建 .env 文件(从 .env.example 复制),
   填 WECOM_BOT_WEBHOOK(内部管理群机器人 URL)。
   企微存档相关 4 项(CORPID/SECRET/SDK_LIB_PATH/PRIVATE_KEY_PATH)先留空。
5) mock 端到端验证:
     cd /Users/<客户用户名>/会话存档方案
     python3 -m pip install -r requirements.txt
     USE_MOCK=true python3 daily_check.py
     python3 mock_data.py
     USE_MOCK=true python3 daily_check.py
   看到"共 XXX 群, 完成 1, 待跟进 XXX" 就算通过。
```

---

## B. 许可到位后接入真 SDK(一次性)

**前提**:主管拿到 corpid / secret,已生成 RSA 密钥对,官方管理端已配好存档成员范围,并把公钥填了进去。

**贴给 workbuddy:**

```
帮我把企业微信「会话内容存档」SDK 接入到项目里,并起容器。

## 一、放 SDK 二进制
从企微开发者中心下载官方 SDK 包 (Linux 版),里面包含:
  libWeWorkFinanceSdk_C.so
把 .so 文件放到 /Users/<客户用户名>/会话存档方案/lib/ 下。

## 二、放私钥
把主管生成的 RSA 私钥文件放到 keys/wecom.pri.pem
chmod 600 keys/wecom.pri.pem

## 三、填 .env
编辑 /Users/<客户用户名>/会话存档方案/.env,填 4 项:
  WECOM_CORPID=<企业 ID>
  WECOM_SECRET=<会话存档 secret,不是通讯录 secret>
  SDK_LIB_PATH=/app/lib/libWeWorkFinanceSdk_C.so
  PRIVATE_KEY_PATH=/app/keys/wecom.pri.pem
  USE_MOCK=false

## 四、补齐 archive_fetcher.py 的 ctypes 调用
文件 archive_fetcher.py 里 ArchiveSdk 类的 get_chat_data() / decrypt() 是骨架,
标了 TODO。按官方 C 头文件 (WeWorkFinanceSdk_C.h) 对齐 ctypes 签名:
  - NewSdk() → WeWorkFinanceSdk_t*
  - Init(sdk, corpid, secret) → int
  - GetChatData(sdk, seq, limit, proxy, passwd, timeout, chatData) → int
  - DecryptData(random_key, chat_msg, priv_key, msg) → int
  - Slice_t 结构:{content: char*, len: int}
  - NewSlice / FreeSlice / GetContentFromSlice / GetSliceLen
参考: https://developer.work.weixin.qq.com/document/path/91774

## 五、起容器
cd /Users/<客户用户名>/会话存档方案
docker compose build
docker compose up -d

## 六、验证
docker compose logs -f
预期:每小时看到 "fetch: NNN 条新消息",每天 22:00 看到 "daily_check ..."

## 七、首次 sync_rooms(把 roomid 关联到学生)
第一次拉到消息后(等 1-2 小时),进容器手动跑一次 sync_rooms:
  docker compose exec archive-monitor python sync_rooms.py
看 data/unmatched_rooms.csv 里剩多少群没匹配上,主管补 group_id 或修正群名。
```

---

## C. 常态运维

### C1. 定时健康检查

**贴给 workbuddy:**

```
帮我配 3 个 workbuddy 定时任务,监控督学监控项目的健康状态。

任务 1 — 每天 22:40 健康检查:
  检查 /Users/<客户用户名>/会话存档方案/data/checks.csv
  是否有今日日期的行。无则告警。

任务 2 — 每小时 fetch 心跳:
  检查 data/seq.txt 的 mtime 是否在最近 90 分钟内更新过。
  没更新说明拉取器挂了。docker restart 一次,再挂告警。

任务 3 — Docker 容器存活:
  每 10 分钟检查 `docker inspect archive-monitor` 状态。
  Exited → 立即 restart 并告警。
```

### C2. xlsx 每日同步

**贴给 workbuddy:**

```
帮我配一个规则:
  监听 /Users/<客户用户名>/会话存档方案/督学服务整理.xlsx
  文件 mtime 变化 → 无操作(daily_check 会自己读最新)
  但如果连续 2 天 mtime 没变 → 提醒主管"今天忘导表了"
```

---

## D. 定期人工动作(workbuddy 只做提醒)

### D1. 主管每天导出 xlsx

工具/流程:主管在腾讯文档打开多维表格 → 导出 Excel → 保存到 OneDrive/微云同步文件夹 → 客户机自动同步到 `督学服务整理.xlsx`。workbuddy 无需介入,只在 D 里的规则触发时提醒。

### D2. 主管每周查 unmatched_rooms.csv

新加的群自动映射不上时,会记录到这里。主管人工确认 → 在 students.csv 里手动关联(或改群名后 sync_rooms 会自动匹配上)。

---

## 部署顺序总览

```
Day 0  → 主管报价采购许可
Day 0-14 → 走 A 段(装 Docker、跑 mock,把管道跑通)
Day 14 → 许可到位,走 B 段(接 SDK + 起容器 + 首次 sync_rooms)
Day 14+  → C 段常态运维 + D 段人工动作
```
