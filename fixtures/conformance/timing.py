"""観測時間を合否reportと分離する。正常・例外のどちらでも所要時間を残す。"""
from time import perf_counter


def timed_call(timings, phase, function, *args, **kwargs):
    if timings is None:
        return function(*args, **kwargs)
    start = perf_counter()
    try:
        return function(*args, **kwargs)
    finally:
        timings[phase] = timings.get(phase, 0.0) + (perf_counter() - start) * 1000
