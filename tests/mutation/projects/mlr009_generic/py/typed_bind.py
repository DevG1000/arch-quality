"""typed_bind.py — type-safe binding with concrete types (does NOT trigger MLR-009)"""
import ctypes

lib = ctypes.CDLL("libnative.so")

# Concrete int pointer / int types — type-safe binding
lib.create_handle.restype = ctypes.POINTER(ctypes.c_int)
lib.use_handle.argtypes = [ctypes.POINTER(ctypes.c_int)]

handle = lib.create_handle()
result = lib.use_handle(handle)