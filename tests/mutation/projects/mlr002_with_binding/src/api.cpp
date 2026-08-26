/* api.cpp — implementation with pybind11 binding layer (does NOT trigger MLR-002) */
#include "api.h"
#include <pybind11/pybind11.h>

void Api::run() {
    // run
}

int Api::compute(int x) {
    return x + 1;
}

void Api::stop() {
    // stop
}

namespace py = pybind11;

PYBIND11_MODULE(api, m) {
    py::class_<Api>(m, "Api")
        .def(py::init<>())
        .def("run", &Api::run)
        .def("compute", &Api::compute)
        .def("stop", &Api::stop);
}