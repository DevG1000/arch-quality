// runtime_checks.cpp - H3 WP-5 B2/B3 runtime probes (non-blocking).
// Extends G0 kernel_smoke.cpp with topology (Euler) and closure checks.
// B5 (cross-version API compat) is emitted as SKIPPED; the Python aggregator records the reason.
#include <Standard_Version.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <TopoDS_Shape.hxx>
#include <TopExp_Explorer.hxx>
#include <TopAbs_ShapeEnum.hxx>
#include <TopTools_IndexedMapOfShape.hxx>
#include <TopExp.hxx>
#include <iostream>
#include <string>

static int count_shape(const TopoDS_Shape& s, TopAbs_ShapeEnum t) {
  TopTools_IndexedMapOfShape map;
  TopExp::MapShapes(s, t, map);
  return map.Extent();
}

int main() {
  TopoDS_Shape box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape();
  const int v = count_shape(box, TopAbs_VERTEX);
  const int e = count_shape(box, TopAbs_EDGE);
  const int f = count_shape(box, TopAbs_FACE);
  const int euler = v - e + f;
  BRepCheck_Analyzer analyzer(box);
  const bool valid = analyzer.IsValid();
  const std::string euler_status = (euler == 2) ? "PASS" : "WARN";
  const std::string closure_status = (valid && f == 6) ? "PASS" : "WARN";

  std::cout << "{\"occt_version\":\"" << OCC_VERSION_COMPLETE << "\",\"checks\":["
            << "{\"check\":\"euler\",\"status\":\"" << euler_status << "\","
            << "\"vertices\":" << v << ",\"edges\":" << e << ",\"faces\":" << f
            << ",\"euler\":" << euler << ",\"expected\":2},"
            << "{\"check\":\"closure\",\"status\":\"" << closure_status << "\","
            << "\"valid\":" << (valid ? "true" : "false") << ",\"faces\":" << f << "},"
            << "{\"check\":\"api_compat\",\"status\":\"SKIPPED\","
            << "\"reason\":\"cross-version build comparison requires two OCCT installs\"}"
            << "]}" << std::endl;
  return 0;
}
