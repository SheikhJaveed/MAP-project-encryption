import psutil
import time
from threading import Thread, Event

def sample_cpu(interval: float, stop_event: Event, records: list):
    while not stop_event.is_set():
        records.append(psutil.cpu_percent(interval=None))
        time.sleep(interval)

def run_with_cpu_profile(func, *args, sample_interval=0.05, **kwargs):
    """
    Runs func(*args, **kwargs) while sampling CPU percent every sample_interval seconds.
    Returns: (func_result, elapsed_time, cpu_avg)
    """
    stop_event = Event()
    records = []
    sampler = Thread(target=sample_cpu, args=(sample_interval, stop_event, records))
    t0 = time.perf_counter()
    sampler.start()
    try:
        res = func(*args, **kwargs)
    finally:
        stop_event.set()
        sampler.join()
    t1 = time.perf_counter()
    cpu_avg = sum(records) / len(records) if records else 0.0
    return res, (t1 - t0), cpu_avg
