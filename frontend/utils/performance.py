"""性能监控模块 — 记录 API 调用耗时并展示统计信息"""

import time
import threading
from collections import defaultdict
import streamlit as st
import pandas as pd


class PerformanceCollector:
    """性能数据收集器"""

    def __init__(self):
        self.api_calls = defaultdict(int)
        self.api_times = defaultdict(float)
        self.page_loads = 0
        self.start_time = time.time()
        self._lock = threading.Lock()

    def record_api_call(self, endpoint: str, duration: float):
        with self._lock:
            self.api_calls[endpoint] += 1
            self.api_times[endpoint] += duration

    def record_page_load(self):
        with self._lock:
            self.page_loads += 1

    def get_uptime(self) -> float:
        return time.time() - self.start_time

    def get_api_stats(self) -> dict:
        with self._lock:
            total_calls = sum(self.api_calls.values())
            total_time = sum(self.api_times.values())
            return {
                "total_calls": total_calls,
                "total_time": round(total_time, 2),
                "avg_time": round(total_time / total_calls, 2) if total_calls else 0,
                "calls_by_endpoint": dict(self.api_calls),
                "time_by_endpoint": dict(self.api_times),
            }

    def reset(self):
        with self._lock:
            self.api_calls.clear()
            self.api_times.clear()
            self.page_loads = 0
            self.start_time = time.time()


def get_collector() -> PerformanceCollector:
    if "performance_collector" not in st.session_state:
        st.session_state.performance_collector = PerformanceCollector()
    return st.session_state.performance_collector


def monitor_performance(endpoint: str = None):
    """装饰器：记录函数耗时"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            try:
                collector = get_collector()
                collector.record_api_call(endpoint or func.__name__, duration)
            except Exception:
                pass
            return result
        return wrapper
    return decorator


def init_performance_monitoring():
    """应用启动时初始化性能收集"""
    collector = get_collector()
    collector.record_page_load()
    return collector


def display_performance_stats():
    """在调试面板中展示性能统计"""
    collector = get_collector()
    stats = collector.get_api_stats()

    # ——— 总览 ———
    st.subheader("应用性能总览")
    uptime = collector.get_uptime()
    days, rem = divmod(uptime, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"

    col1, col2, col3 = st.columns(3)
    col1.metric("运行时间", uptime_str)
    col2.metric("API 调用次数", stats["total_calls"])
    col3.metric("平均响应时间", f"{stats['avg_time']:.2f}s")

    # ——— 明细表 ———
    if stats["total_calls"] > 0:
        st.subheader("调用明细")
        rows = []
        for ep, count in stats["calls_by_endpoint"].items():
            t_total = stats["time_by_endpoint"].get(ep, 0)
            t_avg = round(t_total / count, 2) if count else 0
            rows.append({"端点": ep, "调用次数": count, "总时间(s)": t_total, "平均时间(s)": t_avg})

        df = pd.DataFrame(rows).sort_values("调用次数", ascending=False)
        st.dataframe(df, width="stretch", hide_index=True)

        # 柱状图
        if len(df) > 1:
            st.subheader("调用次数分布")
            st.bar_chart(df.set_index("端点")["调用次数"])

    # ——— 响应时间趋势 ———
    if "performance_metrics" in st.session_state and st.session_state.performance_metrics:
        msg_times = [m["duration"] for m in st.session_state.performance_metrics if m.get("operation") == "send_message"]
        if len(msg_times) > 1:
            st.subheader("消息响应趋势")
            trend_df = pd.DataFrame({"消息序号": range(1, len(msg_times) + 1), "耗时(s)": msg_times})
            st.line_chart(trend_df.set_index("消息序号"))


def clear_performance_data():
    """清除性能数据"""
    if "performance_collector" in st.session_state:
        st.session_state.performance_collector.reset()
    if "performance_metrics" in st.session_state:
        st.session_state.performance_metrics = []
    return True
