#include <STEPControl_Writer.hxx>
#include <TopoDS_Shape.hxx>

void exportStep(const TopoDS_Shape& shape, const char* path) {
    STEPControl_Writer writer;
    writer.Transfer(shape, STEPControl_AsIs);
    writer.Write(path);
}
