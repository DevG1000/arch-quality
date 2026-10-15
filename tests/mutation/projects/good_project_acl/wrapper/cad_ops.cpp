#include "cad_ops.h"
#include <BRepAlgoAPI_Fuse.hxx>
#include <stdexcept>
MatShape CadEngine::do_fuse(const MatShape& a, const MatShape& b) {
    BRepAlgoAPI_Fuse op(a.inner(), b.inner());
    if (!op.IsDone()) throw std::runtime_error("fuse failed");
    return MatShape::wrap(op.Shape());
}
MatShape CadEngine::do_cut(const MatShape& a, const MatShape& b) {
    BRepAlgoAPI_Cut op(a.inner(), b.inner());
    if (!op.IsDone()) throw std::runtime_error("cut failed");
    return MatShape::wrap(op.Shape());
}