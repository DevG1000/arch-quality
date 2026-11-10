#include <algorithm>

void copy_in(double* d, const double* h, int n) {
#ifdef USE_CUDA
  int cnt = 0;
  if (cudaGetDeviceCount(&cnt) == 0 && cnt > 0) {
    cudaMemcpy(d, h, n * sizeof(double), cudaMemcpyHostToDevice);
    return;
  }
#endif
  std::copy(h, h + n, d);
}
