#include <pybind11/pybind11.h>
#include "mathlib.h"
PYBIND11_MODULE(mathlib, m) {
    m.def("internal_add", &internal_add, "add");
}
