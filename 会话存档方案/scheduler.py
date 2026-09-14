"""容器内单进程调度。用 APScheduler 定时触发拉取器和日检。

- 每小时:archive_fetcher.fetch_and_persist()  防止服务端 5 天过期
- 每天 22:00:daily_check.run(today)
- 每周一 09:00:sync_rooms.sync()  拉取新群名并回填 roomid

也可以拆两个 sidecar 用 supervisor 管。这里选单进程,依赖简单。
"""
from __future__ import annotations

import logging
import signal
import sys
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger("scheduler")


def _job_fetch():
    from archive_fetcher import fetch_and_persist
    try:
        n = fetch_and_persist()
        log.info(f"fetch: {n} 条新消息")
    except Exception as e:
        log.exception(f"fetch 失败: {e}")


def _job_daily_check():
    from daily_check import run
    try:
        run(date.today())
    except Exception as e:
        log.exception(f"daily_check 失败: {e}")


def _job_sync_rooms():
    from sync_rooms import sync
    try:
        result = sync()
        log.info(f"sync_rooms: {result}")
    except Exception as e:
        log.exception(f"sync_rooms 失败: {e}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    scheduler.add_job(_job_fetch, IntervalTrigger(hours=1),
                      id="fetch_hourly", name="拉取存档消息", max_instances=1)
    scheduler.add_job(_job_daily_check, CronTrigger(hour=22, minute=0),
                      id="daily_check", name="每日判定", max_instances=1)
    scheduler.add_job(_job_sync_rooms, CronTrigger(day_of_week="mon", hour=9, minute=0),
                      id="sync_rooms", name="群映射同步", max_instances=1)

    # 启动时先跑一次拉取,让容器起来就工作
    scheduler.add_job(_job_fetch, id="fetch_boot", name="启动拉取一次")

    def _shutdown(*_):
        log.info("shutdown signal received")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("scheduler started")
    scheduler.start()


if __name__ == "__main__":
    main()
