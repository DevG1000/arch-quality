"""loop_bind.py — calls CDLL inside a for-loop (triggers MLR-011 small data transfers)"""
import ctypes

lib = ctypes.CDLL("libnative.so")


def process_all(items):
    results = []
    for item in items:
        results.append(ctypes.c_void_p(lib.process(item)))
    return results