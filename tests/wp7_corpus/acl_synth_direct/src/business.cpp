#include <BRepAlgoAPI_Fuse.hxx>
TopoDS_Shape merge(TopoDS_Shape a, TopoDS_Shape b) {
    BRepAlgoAPI_Fuse op(a, b);
    return op.Shape();
}
