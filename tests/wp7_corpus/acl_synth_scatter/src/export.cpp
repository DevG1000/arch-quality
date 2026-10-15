#include <STEPControl_Writer.hxx>
#include <STEPControl_Reader.hxx>
void export_part() { STEPControl_Writer w; w.Write("part.stp"); }
void import_part(const char* p) { STEPControl_Reader r; r.ReadFile(p); r.TransferRoots(); }
