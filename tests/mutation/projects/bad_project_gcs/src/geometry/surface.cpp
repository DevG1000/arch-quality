#include <Geom_Plane.hxx>
Geom_Plane* make_plane() {
    return new Geom_Plane(gp_Pln());
}