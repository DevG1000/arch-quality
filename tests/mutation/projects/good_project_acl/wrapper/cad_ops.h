#include "MatShape.hh"
#include <BRepAlgoAPI_Fuse.hxx>
#if OCC_VERSION >= 70800
#pragma once
class CadEngine {
public:
    MatShape do_fuse(const MatShape& a, const MatShape& b);
    MatShape do_cut(const MatShape& a, const MatShape& b);
};
#endif