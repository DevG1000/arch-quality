#include <vtkSmartPointer.h>
#include <vtkPolyData.h>

vtkSmartPointer<vtkPolyData> makePolyData() {
    auto data = vtkSmartPointer<vtkPolyData>::New();
    return data;
}
