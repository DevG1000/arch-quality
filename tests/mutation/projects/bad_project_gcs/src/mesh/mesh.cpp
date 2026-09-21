#include <vtkUnstructuredGrid.h>
#include <vector>
class MeshField {
    std::vector<double> data_;
public:
    double at(size_t i) const { return data_.at(i); }
    void set(size_t i, double v) { data_.at(i) = v; }
};
class MeshAdapter {
    vtkSmartPointer<vtkUnstructuredGrid> vtk_;
public:
    vtkUnstructuredGrid* getVTK() { return vtk_; }
};