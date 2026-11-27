#include <vtkSmartPointer.h>
#include <vtkPolyData.h>

#if VTK_VERSION_NUMBER >= 90000000000
vtkSmartPointer<vtkPolyData> makePolyData() {
    return vtkSmartPointer<vtkPolyData>::New();
}
#endif
