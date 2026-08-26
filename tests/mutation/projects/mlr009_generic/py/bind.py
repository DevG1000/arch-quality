"""bind.py — uses ctypes generic types (c_void_p) to bind C native functions (triggers MLR-009)"""
import ctypes

lib = ctypes.CDLL("libnative.so")

# Generic void pointer binding — no type safety
lib.create_handle.restype = ctypes.c_void_p
lib.use_handle.argtypes = [ctypes.c_void_p]

handle = lib.create_handle()
result = lib.use_handle(handle)