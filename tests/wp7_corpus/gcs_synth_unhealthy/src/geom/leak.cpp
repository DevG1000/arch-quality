#include <Geom_Plane.hxx>
Geom_Plane* make_plane() {
    return new Geom_Plane(gp_Pln());
}
double tol_bad(double d) { return d < 1e-8 ? 0.0 : d; }
