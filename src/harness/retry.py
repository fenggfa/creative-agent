"""
Harness 重试机制 - 反馈回路增强

提供装饰器级别的自动重试能力，用于 LLM 调用、API 请求等不稳定操作。

用法:
    from src.harness.retry import retry, RetryConfig

    @retry(max_attempts=3, delay=1.0)
    async def call_llm(prompt: str) -> str:
        ...

    # 或使用配置对象
    @retry(config=RetryConfig(max_attempts=5, exponential_backoff=True))
    async def fetch_data() -> dict:
        ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """重试配置。"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    jitter: bool = True
    exceptions: tuple[type[BaseException], ...] = (Exception,)

    def get_delay(self, attempt: int) -> float:
        """计算第 n 次重试的延迟时间。"""
        if self.exponential_backoff:
            delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        else:
            delay = self.base_delay

        if self.jitter:
            jitter_value = secrets.randbelow(1000) / 1000.0
            delay = delay * (0.5 + jitter_value)

        return float(delay)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    重试装饰器，支持同步和异步函数。

    Args:
        max_attempts: 最大尝试次数
        delay: 基础延迟秒数
        config: 完整配置对象（优先）
        **kwargs: 传递给 RetryConfig 的其他参数

    Returns:
        装饰后的函数

    Example:
        @retry(max_attempts=3, delay=1.0)
        async def fetch_data() -> dict:
            return await api.get("/data")
    """
    if config is None:
        config = RetryConfig(max_attempts=max_attempts, base_delay=delay, **kwargs)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            async_wrapper = _async_retry_wrapper(func, config)
            return async_wrapper  # type: ignore[return-value]
        return _sync_retry_wrapper(func, config)

    return decorator


def _sync_retry_wrapper(
    func: Callable[..., T], config: RetryConfig
) -> Callable[..., T]:
    """同步函数重试包装器。"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        last_exc: BaseException | None = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except config.exceptions as e:
                last_exc = e

                if attempt < config.max_attempts:
                    d = config.get_delay(attempt)
                    logger.warning(
                        f"[Retry {attempt}/{config.max_attempts}] "
                        f"{func.__name__} 失败: {e}, {d:.1f}s 后重试"
                    )
                    time.sleep(d)
                else:
                    logger.error(
                        f"[Retry] {func.__name__} 达到最大重试次数"
                    )

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("不应到达此处")

    return wrapper


def _async_retry_wrapper(
    func: Callable[..., Awaitable[T]], config: RetryConfig
) -> Callable[..., Awaitable[T]]:
    """异步函数重试包装器。"""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        last_exc: BaseException | None = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except config.exceptions as e:
                last_exc = e

                if attempt < config.max_attempts:
                    d = config.get_delay(attempt)
                    logger.warning(
                        f"[Retry {attempt}/{config.max_attempts}] "
                        f"{func.__name__} 失败: {e}, {d:.1f}s 后重试"
                    )
                    await asyncio.sleep(d)
                else:
                    logger.error(
                        f"[Retry] {func.__name__} 达到最大重试次数"
                    )

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("不应到达此处")

    return wrapper


# ========================================
# 预定义配置
# ========================================

LLM_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    exponential_backoff=True,
    exceptions=(ConnectionError, TimeoutError),
)

API_RETRY = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    exponential_backoff=True,
    exceptions=(ConnectionError, TimeoutError),
)
