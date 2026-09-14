# workbuddy 执行指令合集

> **给 workbuddy 的操作员/AI 助手看**。以下每一段都是完整的任务描述,直接粘进 workbuddy 让它翻译成对应的 skill / 定时任务 / RPA 脚本。
>
> **架构:** 主路 = MCP(wecom-cli 授权用户身份读消息)+ 定时调度。备路 = RPA(Mac Accessibility API,当 MCP 覆盖不了外部群时才启用)。
>
> **执行顺序:** A → B → C → D。B 是主路核心。C 是每周一次的映射同步。D 是每周一次的授权 renew 提醒。

---

## A. 每日定时任务(workbuddy 定时调度)

**贴给 workbuddy:**

```
帮我在这台机器上创建一个 workbuddy 定时任务。

任务名:督学服务日检
触发时间:每天 22:00 (北京时间)
工作目录:/Users/<客户用户名>/督学交付质量监控
执行命令:/usr/bin/python3 main.py

环境变量:
  USE_MOCK=false
  READER=mcp
  ROSTER_XLSX=/Users/<客户用户名>/督学交付质量监控/督学服务整理.xlsx
  DATA_DIR=/Users/<客户用户名>/督学交付质量监控/data
  RULES_YAML=/Users/<客户用户名>/督学交付质量监控/rules.yaml
  WECOM_BOT_WEBHOOK=<主管稍后填>
  RETENTION_DAYS=7

失败处理:
  - exit code != 0 → 5 分钟后重试一次
  - 再失败 → 通过 workbuddy 自身通知渠道推一条"督学日检脚本挂了,已连续两次失败"

日志:
  - stdout / stderr 落 /Users/<客户用户名>/督学交付质量监控/logs/YYYY-MM-DD.log
  - 保留最近 30 天日志

健康检查:
  - 每天 22:40 检查 data/checks.csv 是否有今日日期的行
  - 无则再推一条告警
```

---

## B. MCP 主路实现(mcp_reader.py + wecom-cli)

**任务性质**:在客户机上装 Node + wecom-cli,补齐 `mcp_reader.py` 里字段映射,替换掉 RPA 抓屏。

**前置**:
1. 主管在企微管理后台建 API 模式机器人 → 拿 BotID + Secret
2. 用户(在所有督学群里的那位)授权机器人「消息」使用权限(7 天 renew)

**贴给 workbuddy:**

```
帮我在这台 macOS 上配置 wecom-cli 并补齐 mcp_reader.py。

## 一、环境准备
1) 装 Node.js 20+(brew install node)
2) 装 wecom-cli:
     npm install -g @wecom/cli
     npx skills add WeComTeam/wecom-cli -y -g
3) 交互式配置凭证(填 BotID / Secret):
     wecom-cli init

## 二、smoke test:确认拿得到会话列表 + 外部群
在终端跑:
  wecom-cli msg get_msg_chat_list '{"begin_time": "<7 天前日期> 00:00:00", "end_time": "<今天> 23:59:59"}'

预期看到 chats[] 数组,其中包含 chat_name 里带 "e/d/s/w/v/j/a" 前缀+编号+科目
格式(如 "e123 政治+英语")的记录。**关键验证**:里面必须有外部群
(客户群),不能只有内部群。

如果没有外部群 → 停下来告诉我,别继续,回退 RPA 路线。

## 三、修改 mcp_reader.py 里的字段名映射
mcp_reader.py 里的 _to_message() 函数按官方 API 返回字段名映射即可
(时间戳字段、发送人字段、正文字段、消息类型字段)。
_iter_messages() 里的分页字段 next_cursor / has_more 同理。
以本地 smoke test 的实际 JSON 输出为准。

## 四、跑通端到端
1) 手工找一个真实督学群,记下它的 chat_id
2) 手工在 data/students.csv 里对应学生行填入 chat_id
3) USE_MOCK=false READER=mcp python3 main.py <今天日期>
4) 看输出的 checks.csv 和 markdown 预览是否正确判定

## 五、交付
- 修改 mcp_reader.py 里字段名映射
- 附一个 tests/test_mcp_smoke.py 单群冒烟
- 记录 wecom-cli 授权失效(7 天)如何 renew 的操作步骤

## 反检测(比 RPA 少)
- wecom-cli 底层是官方 API,无需拟人化控速
- 500 群串行调用大概 3-5 分钟(每群 200-500ms)
- 如遇限流,加个 sleep(0.1) 就够
```

---

## C. sync_chats 映射同步(每周一次)

**任务性质**:遍历用户所有会话拿到 (chat_id, chat_name),按群名解析学生编号,回填到 students.csv。

**贴给 workbuddy:**

```
帮我实现 sync_chats.py 并配一个每周任务。

## 一、实现 sync_chats.py
读入:data/students.csv(现有学生列表)
动作:
  1) 调 wecom-cli msg get_msg_chat_list 拉近 7 天所有会话
     - 分页收集所有 chats
     - 只留群聊(chat_type=2 或按 chat_name 判断)
  2) 对每个 chat,从 chat_name 里解析学生编号
     - 群名格式:"<编号> <科目>" 例如 "e123 政治+英语" / "d456 行测"
     - 用正则 ^([a-zA-Z]\\d+)\\s+ 抓 group_id
  3) 匹配 students.csv 里的 group_id,回填 chat_id 列
     - 匹配到:更新 chat_id
     - 匹配不到(可能新群):写一份 unmatched_chats.csv 让主管确认
     - students.csv 有编号但没匹配到群(可能未建群):日志提示
  4) 保存 students.csv

## 二、配周任务
任务名:督学群映射同步
触发:每周一 09:00
命令:/usr/bin/python3 sync_chats.py
环境:同 A 里的定时任务
失败告警:同 A
```

---

## D. 授权 renew 提醒(每周一次)

**任务性质**:MCP 授权 7 天失效,过期就没数据。提前提醒用户手动 renew。

**贴给 workbuddy:**

```
帮我配一个每周提醒。

任务名:企微机器人授权 renew
触发:每周日 20:00
动作:
  - 通过 workbuddy 通知渠道推一条:
    "本周需 renew 企微机器人「消息」授权。
     步骤:打开企微 → 机器人管理 → <机器人名> → 消息权限 → 重新授权
     完成后回复"已 renew""
  - 收到"已 renew"回复后,自动跑一次 wecom-cli msg get_msg_chat_list
    验证授权成功,失败再推一次告警
```

---

## E. 备路:RPA(仅在 B 阶段外部群验证失败时启用)

**如果 B 的 smoke test 显示外部群拿不到消息,才切到这条路。**

<details>
<summary>展开 RPA 实现指令</summary>

```
帮我在 macOS 上实现 wecom_reader.py 里的 read_today_chat 函数。

## 函数签名
def read_today_chat(group_id: str, subject: str, today: date) -> list[Message]

## 运行环境
- macOS,企业微信 Mac 客户端已登录
- 已加入所有督学群
- 群命名规则:"<学生编号> <科目>",例如 "e123 政治+英语"

## 只需要抓什么
判定只关心两类 hashtag:
  - #今日打卡
  - #<科目>今日计划
抓到即可停,不用滚整屏。

## 实现路径(推荐 1)
1) macOS Accessibility API + pyobjc:读企微聊天窗口 UI 树,不用 OCR
2) PyAutoGUI + Vision framework OCR:兜底
3) 企微本地 SQLite 逆向:别碰

## 反封号
- 每群操作后 sleep(random.uniform(3, 5))
- 500 群一轮 30-40 分钟
- 鼠标移动加随机偏移
- 不用 headless
```

</details>

---

## 部署顺序备忘

1. **主管每天导出 xlsx** → 同步到客户机
2. **A + D 先配起来**(定时调度骨架 + 授权提醒)
3. **B 走 smoke test** → 验证外部群覆盖是否成立
 - 通过 → 继续 B 主路
 - 不通过 → 切 E 备路,workbuddy 侧改环境变量 `READER=rpa`
4. **C 一周跑一次映射同步**,填 chat_id
5. **配 WECOM_BOT_WEBHOOK** 到 A 的环境变量
6. **观察一周**,规则跑不准回 rules.yaml 调
