import ctypes

lib = ctypes.CDLL("./mathlib.so")
lib.internal_add.argtypes = [ctypes.c_int, ctypes.c_int]
result = lib.internal_add(1, 2)
