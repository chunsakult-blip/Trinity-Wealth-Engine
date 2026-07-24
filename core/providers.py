import os
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Tuple

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

class ProviderConfig:
    @staticmethod
    def get_tavily_api_key() -> Optional[str]:
        return os.getenv("TAVILY_API_KEY")

    @staticmethod
    def get_fred_api_key() -> Optional[str]:
        return os.getenv("FRED_API_KEY")

    @staticmethod
    def get_notebooklm_provider() -> str:
        return os.getenv("YOUTUBE_PITCH_PROVIDER", "google")


def with_provider_retry(
    provider_name: str,
    max_retries: int = 3,
    timeout_seconds: float = 10.0,
    fallback_factory: Optional[Callable[[], T]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator/Wrapper สำหรับจัดการ Timeout และ Rate Limit (API Limit) ของ Provider
    - Timeout: หากช้าหรือหมดเวลา จะใช้ fallback_factory (เช่น Mock/Cached data)
    - Rate Limit: Exponential Backoff + Retry สูงสุด `max_retries` ครั้ง
    - พิมพ์ลง Terminal (logger.warning/info) เพื่อให้อ่านง่ายว่า fallback หรือ retry ครั้งที่เท่าไหร่
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import requests
            for attempt in range(1, max_retries + 1):
                try:
                    # Note: You should ensure the wrapped function respects the timeout_seconds internally if possible
                    return func(*args, **kwargs)
                except requests.Timeout as e:
                    logger.warning("⏳ [%s] Timeout (เกิน %.1fs)", provider_name, timeout_seconds)
                    if fallback_factory:
                        logger.warning("🔄 [%s] Fallback ไปใช้ Mock/Cached data ชั่วคราว", provider_name)
                        return fallback_factory()
                    raise ValueError(f"{provider_name} request timed out") from e
                except Exception as e:
                    # Detect Rate Limit / Too Many Requests
                    err_msg = str(e).lower()
                    if "too many requests" in err_msg or "rate limit" in err_msg or "429" in err_msg:
                        if attempt < max_retries:
                            delay = 2 ** attempt
                            logger.warning("⏱️ [%s] Rate Limit เต็ม! กำลังหน่วงเวลา %ds แล้วลองใหม่ (ครั้งที่ %d/%d)", provider_name, delay, attempt, max_retries)
                            time.sleep(delay)
                            continue
                        else:
                            logger.error("❌ [%s] Rate Limit เต็ม และเกินจำนวนการ Retry แล้ว", provider_name)
                            raise ValueError(f"{provider_name} rate limited after {max_retries} attempts") from e
                    else:
                        # Other errors (e.g. Connection Error)
                        if attempt < max_retries:
                            delay = 2 ** attempt
                            logger.warning("⚠️ [%s] Error: %s -> กำลังลองใหม่ (ครั้งที่ %d/%d)", provider_name, e, attempt, max_retries)
                            time.sleep(delay)
                            continue
                        logger.error("❌ [%s] ล้มเหลวหลังจากลอง %d ครั้ง: %s", provider_name, max_retries, e)
                        
                        if fallback_factory:
                            logger.warning("🔄 [%s] Fallback ไปใช้ Mock/Cached data ชั่วคราว เนื่องจาก Error", provider_name)
                            return fallback_factory()
                            
                        raise ValueError(f"{provider_name} operation failed: {e}") from e
            
            # Should not reach here if exceptions are raised
            raise ValueError(f"{provider_name} failed unexpectedly")
        return wrapper
    return decorator

def resolve_provider(model_env: str, provider_env: str, default: str = "default_provider") -> str:
    """
    Centralize provider selection.
    Priority: model_env > provider_env > default
    """
    val = os.getenv(model_env)
    if val:
        return val
        
    val = os.getenv(provider_env)
    if val:
        return val
        
    return default
