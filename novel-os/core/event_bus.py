"""Novel-OS 轻量级内部事件总线 —— 解耦流水线各阶段。

支持的事件类型（约定常量）:
    chapter_start         — 开始写某章
    chapter_complete      — 某章完成
    chapter_error         — 某章失败
    agent_call_start      — Agent 调用开始
    agent_call_complete   — Agent 调用完成
    quality_gate_blocking — 质量门拦截
    pipeline_start        — 流水线启动
    pipeline_pause        — 流水线暂停
    pipeline_complete     — 流水线完成

设计约束:
    - 禁止阻塞生产者（handler 异步执行）
    - 跨同级模块通信的唯一合法通道
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger("novel-os.event_bus")

# 约定事件类型常量，供订阅方使用
CHAPTER_START = "chapter_start"
CHAPTER_COMPLETE = "chapter_complete"
CHAPTER_ERROR = "chapter_error"
AGENT_CALL_START = "agent_call_start"
AGENT_CALL_COMPLETE = "agent_call_complete"
QUALITY_GATE_BLOCKING = "quality_gate_blocking"
INTERCEPTOR_SCAN_START = "interceptor_scan_start"
INTERCEPTOR_SCAN_COMPLETE = "interceptor_scan_complete"
PIPELINE_START = "pipeline_start"
PIPELINE_PAUSE = "pipeline_pause"
PIPELINE_COMPLETE = "pipeline_complete"

# 外层 CrewAI 事件
OUTER_CREW_INSPECTION_START = "outer_crew_inspection_start"
OUTER_CREW_INSPECTION_COMPLETE = "outer_crew_inspection_complete"
OUTER_CREW_RETCON_TRIGGERED = "outer_crew_retcon_triggered"

EVENT_TYPES: set[str] = {
    CHAPTER_START,
    CHAPTER_COMPLETE,
    CHAPTER_ERROR,
    AGENT_CALL_START,
    AGENT_CALL_COMPLETE,
    QUALITY_GATE_BLOCKING,
    INTERCEPTOR_SCAN_START,
    INTERCEPTOR_SCAN_COMPLETE,
    PIPELINE_START,
    PIPELINE_PAUSE,
    PIPELINE_COMPLETE,
    OUTER_CREW_INSPECTION_START,
    OUTER_CREW_INSPECTION_COMPLETE,
    OUTER_CREW_RETCON_TRIGGERED,
}


class EventBus:
    """轻量级内部事件总线，解耦流水线各阶段。"""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._lock = threading.Lock()

    def on(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """订阅事件。

        Args:
            event_type: 事件类型标识符。
            handler: 回调函数，接收 payload dict。
        """
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def off(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """取消订阅。

        若 event_type 或 handler 不存在，静默忽略。
        """
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
                if not handlers:
                    del self._handlers[event_type]

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """发布事件（异步执行 handler，不阻塞生产者）。

        Args:
            event_type: 事件类型标识符。
            payload: 传递给所有订阅者的字典。
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        if not handlers:
            return

        # 异步执行，避免阻塞生产者线程
        def _run() -> None:
            for handler in handlers:
                try:
                    handler(event_type, payload)
                except Exception:
                    logger.exception("事件 handler 异常: %s", event_type)

        threading.Thread(target=_run, daemon=True).start()
