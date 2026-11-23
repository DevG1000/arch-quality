// kernel_smoke.cpp - minimal OCCT kernel probe: substrate for H3 runtime detection (B2/B3/B5).
// Verifies the pinned OCCT build loads and can construct + validate a B-Rep solid.
#include <Standard_Version.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <TopoDS_Shape.hxx>
#include <TopExp_Explorer.hxx>
#include <TopAbs_ShapeEnum.hxx>
#include <NCollection_IndexedMap.hxx>
#include <TopTools_ShapeMapHasher.hxx>
#include <TopExp.hxx>
#include <iostream>

int main() {
  std::cout << "OCCT version: " << OCC_VERSION_COMPLETE << std::endl;

  TopoDS_Shape box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape();
  if (box.IsNull()) {
    std::cerr << "FAIL: null shape" << std::endl;
    return 2;
  }

  BRepCheck_Analyzer analyzer(box);
  const bool valid = analyzer.IsValid();

  TopTools_IndexedMapOfShape faceMap;
  TopExp::MapShapes(box, TopAbs_FACE, faceMap);
  const int faces = faceMap.Extent();

  std::cout << "box valid=" << (valid ? "true" : "false") << " faces=" << faces << std::endl;
  return (valid && faces == 6) ? 0 : 3;
}