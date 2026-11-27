#include <BRepBuilderAPI_MakeBox.hxx>
#include <STEPControl_Reader.hxx>
#include <TopoDS_Shape.hxx>

TopoDS_Shape makeBox() {
    BRepBuilderAPI_MakeBox mk(1.0, 2.0, 3.0);
    mk.Perform();
    return mk.Shape();
}

void loadStep(const char* path) {
    STEPControl_Reader reader;
    reader.ReadFile(path);
    reader.TransferRoots();
}
