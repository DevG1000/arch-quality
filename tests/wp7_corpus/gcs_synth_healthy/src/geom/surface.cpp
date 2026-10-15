#include <Handle_Geom_Plane.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <stdexcept>
constexpr double GEOM_TOLERANCE = 1e-6;
Handle(Geom_Plane) make_plane(double tol) {
    (void)tol;
    return new Geom_Plane(gp_Pln());
}
bool check(const TopoDS_Shape& s) {
    BRepCheck_Analyzer an(s);
    return an.IsValid();
}
double tol_ok(double d) { return d < GEOM_TOLERANCE ? 0.0 : d; }
