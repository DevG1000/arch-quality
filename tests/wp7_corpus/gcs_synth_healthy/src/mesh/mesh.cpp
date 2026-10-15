#include <vtkSmartPointer.h>
#include <vtkUnstructuredGrid.h>
class MeshAdapter {
    vtkSmartPointer<vtkUnstructuredGrid> grid_;
public:
    vtkUnstructuredGrid* getVTK() { return grid_; }
};
