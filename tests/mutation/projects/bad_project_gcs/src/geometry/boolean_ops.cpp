#include <BRepAlgoAPI_Fuse.hxx>
#include <stdexcept>
TopoDS_Shape fuse_shapes(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_Fuse op(a, b);
    if (!op.IsDone()) throw std::runtime_error("fuse failed");
    return op.Shape();
}