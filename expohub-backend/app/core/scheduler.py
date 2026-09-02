"""
后台任务调度骨架（P2）

- 依赖 APScheduler(AsyncIOScheduler)；默认关闭（settings.SCHEDULER_ENABLED=False），
  开启后才启动，因此对存量服务零行为影响。
- 提供注册表：域模块用 register_job(name, trigger, func) 登记任务；
  start_scheduler_if_enabled() 在应用 lifespan 中调用。
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# 任务注册表: name -> (trigger_kwargs, func)
_registry: List[Dict] = []


def register_job(name: str, trigger: str, func: Callable, **trigger_kwargs) -> None:
    """登记一个周期任务（幂等：同名任务只登记一次）"""
    for job in _registry:
        if job["name"] == name:
            return
    _registry.append({"name": name, "trigger": trigger, "trigger_kwargs": trigger_kwargs, "func": func})
    logger.info("[scheduler] registered job: %s (%s)", name, trigger)


_scheduler = None  # AsyncIOScheduler 惰性初始化


def start_scheduler_if_enabled() -> bool:
    """按配置启动调度器；返回是否已启动（默认 False 不启动）"""
    if not settings.SCHEDULER_ENABLED:
        logger.info("[scheduler] disabled (SCHEDULER_ENABLED=False)")
        return False
    global _scheduler
    if _scheduler is not None:
        return True
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:  # pragma: no cover
        logger.error("[scheduler] APScheduler 未安装：pip install apscheduler")
        return False

    _scheduler = AsyncIOScheduler()
    for job in _registry:
        if job["trigger"] == "interval":
            trig = IntervalTrigger(**job["trigger_kwargs"])
        elif job["trigger"] == "cron":
            trig = CronTrigger(**job["trigger_kwargs"])
        else:
            continue
        _scheduler.add_job(job["func"], trig, id=job["name"], replace_existing=True)
        logger.info("[scheduler] started job: %s", job["name"])
    _scheduler.start()
    return True


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            pass
        _scheduler = None
