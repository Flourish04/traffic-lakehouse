import streamlit as st
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, Callable, Any


def cache_with_params(ttl: int = 300):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @st.cache_data(ttl=ttl)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)
        return wrapper
    return decorator


def ttl_for_dashboard(dashboard_name: str) -> int:
    ttl_map = {
        "D1": 300,
        "D2": 900,
        "D3": 600,
        "D4": 900,
        "D5": 600,
        "D6": 300,
        "D7": 1800,
        "D8": 60,
        "D9": 300,
        "D10": 300,
        "D11": 600,
        "D12": 600,
    }
    return ttl_map.get(dashboard_name, 300)


def format_number(num: float, fmt: str = ",.0f") -> str:
    if num is None:
        return "N/A"
    try:
        if fmt == ",d":
            return f"{int(num):,}"
        elif fmt == ",.1f":
            return f"{num:,.1f}"
        elif fmt == ",.2f":
            return f"{num:,.2f}"
        elif fmt == ",~s":
            if num >= 1_000_000:
                return f"{num/1_000_000:.1f}M"
            elif num >= 1_000:
                return f"{num/1_000:.0f}K"
            return f"{num:,.0f}"
        else:
            return f"{num:{fmt}}"
    except (ValueError, TypeError):
        return str(num)


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def percentile(data, p: float) -> float:
    import numpy as np
    if not data or len(data) == 0:
        return 0.0
    return float(np.percentile(data, p))
