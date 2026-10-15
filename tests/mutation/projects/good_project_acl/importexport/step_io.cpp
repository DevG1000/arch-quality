#include <STEPControl_Writer.hxx>
#include <STEPControl_Reader.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <stdexcept>
#include "MatShape.hh"

double export_len(const double v) {
    return unit::convert(v, unit::INCH, unit::MM);
}

void export_step(const MatShape& shape, const char* path) {
#if SUPPORT_AP242
    STEPControl_Writer w;
    if (w.Write(path) != IFSelect_RetDone) throw std::runtime_error("write fail");
#else
    #error "AP242 required"
#endif
}

MatShape import_step(const char* path) {
    STEPControl_Reader r;
    if (r.ReadFile(path) != IFSelect_RetDone) throw std::runtime_error("read fail");
    r.TransferRoots();
    return MatShape::wrap(r.OneShape());
}