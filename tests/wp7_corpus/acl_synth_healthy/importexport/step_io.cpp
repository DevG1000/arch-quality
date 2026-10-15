#include <STEPControl_Reader.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <stdexcept>
void import_step(const char* path) {
    STEPControl_Reader r;
    if (r.ReadFile(path) != IFSelect_RetDone) throw std::runtime_error("rf");
    r.TransferRoots();
}
