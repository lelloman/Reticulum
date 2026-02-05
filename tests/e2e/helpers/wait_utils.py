"""Utility functions for waiting on conditions."""

import time
from typing import Callable, TypeVar, Optional

T = TypeVar("T")


def poll_until(
    condition: Callable[[], T],
    timeout: float = 10.0,
    interval: float = 0.1,
    message: str = "Condition not met within timeout",
) -> T:
    """
    Poll until a condition returns a truthy value.

    Args:
        condition: Callable that returns a value (truthy = done)
        timeout: Maximum time to wait in seconds
        interval: Time between polls in seconds
        message: Error message if timeout occurs

    Returns:
        The truthy value returned by condition

    Raises:
        TimeoutError: If condition doesn't become truthy within timeout
    """
    start = time.time()
    while True:
        result = condition()
        if result:
            return result
        if time.time() - start > timeout:
            raise TimeoutError(message)
        time.sleep(interval)


def wait_for_condition(
    check: Callable[[], bool],
    timeout: float = 10.0,
    interval: float = 0.1,
) -> bool:
    """
    Wait for a boolean condition to become True.

    Args:
        check: Callable that returns a boolean
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds

    Returns:
        True if condition was met, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        if check():
            return True
        time.sleep(interval)
    return False


def sleep_for_propagation(hops: int = 1, base_delay: float = 0.5) -> None:
    """
    Sleep to allow network propagation.

    Args:
        hops: Expected number of hops
        base_delay: Base delay per hop in seconds
    """
    time.sleep(base_delay * (hops + 1))
