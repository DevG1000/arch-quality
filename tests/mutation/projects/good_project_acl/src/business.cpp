#include "../wrapper/cad_ops.h"
#include "step_io.h"

void process(const MatShape& a, const MatShape& b, const char* path) {
    CadEngine e;
    MatShape m = e.do_fuse(a, b);
    export_step(m, path);
    MatShape back = import_step(path);
}