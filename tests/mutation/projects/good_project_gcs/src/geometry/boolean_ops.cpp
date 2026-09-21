#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <stdexcept>
TopoDS_Shape fuse_shapes(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_Fuse op(a, b);
    if (!op.IsDone()) throw std::runtime_error("fuse failed");
    BRepCheck_Analyzer analyzer(op.Shape());
    if (!analyzer.IsValid()) throw std::runtime_error("invalid shape");
    return op.Shape();
}