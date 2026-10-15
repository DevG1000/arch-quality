#include <vtkUnstructuredGrid.h>
#include <gmsh.h>
class MeshField {
    vtkSmartPointer<vtkUnstructuredGrid> vtk_;
public:
    double mass(int i) {
        vtkCell* cell = vtk_->GetCell(i);
        return gmsh::model::getMass(0, i, vtk_->GetPoint(cell->GetPointId(0)));
    }
    void set(size_t i, double v) { f->data_[0] = 1.0; (void)i; (void)v; }
};
struct Raw { double* coords; double* normals; };
