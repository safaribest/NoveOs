"""Novel-OS 熔断器与重试策略 —— 防止 LLM API 故障时雪崩。

设计文档: 第 8 节「质量门与熔断机制」
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable


class ServiceUnavailable(Exception):
    """服务不可用异常，当熔断器处于 OPEN 状态时抛出。"""

    pass


class CircuitBreaker:
    """熔断器，防止 LLM API 故障时雪崩。

    状态机:
        CLOSED     → 正常调用，失败计数递增，达到阈值 → OPEN
        OPEN       → 直接抛 ServiceUnavailable；超过 recovery_timeout → HALF_OPEN
        HALF_OPEN  → 下一次调用成功 → CLOSED；失败 → OPEN
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"  # CLOSED / OPEN / HALF_OPEN

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """包装函数调用，自动熔断。

        Args:
            func: 被保护的函数（通常是 LLM API 调用）。
            *args, **kwargs: 传递给 func 的参数。

        Returns:
            func 的返回值。

        Raises:
            ServiceUnavailable: 熔断器处于 OPEN 且尚未超时。
            Exception: func 执行时抛出的原始异常（同时累加失败计数）。
        """
        if self.state == "OPEN":
            if (
                self.last_failure_time is not None
                and time.time() - self.last_failure_time > self.recovery_timeout
            ):
                self.state = "HALF_OPEN"
            else:
                raise ServiceUnavailable("LLM API 熔断中")

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise exc

        # 调用成功
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            self.last_failure_time = None
        return result

    def reset(self) -> None:
        """强制重置熔断器为 CLOSED 状态（运维手动恢复时使用）。"""
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None


class RetryPolicy:
    """重试策略：指数退避 + 随机抖动。

    设计文档: 第 8.3 节
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0, max_delay: float = 30.0) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的等待时间（秒）。

        Args:
            attempt: 当前重试次数，从 0 开始计数。

        Returns:
            建议等待的秒数（含抖动）。
        """
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        jitter = random.uniform(0, 1)
        return delay + jitter

    def should_retry(self, attempt: int) -> bool:
        """判断是否应该继续重试。

        Args:
            attempt: 已经尝试过的次数（含第一次调用）。

        Returns:
            True 表示还可以继续重试。
        """
        return attempt < self.max_retries
