#include <TopoDS_Shape.hxx>
class CadEngine {
public:
    TopoDS_Shape do_fuse(const TopoDS_Shape& a, const TopoDS_Shape& b);
};
