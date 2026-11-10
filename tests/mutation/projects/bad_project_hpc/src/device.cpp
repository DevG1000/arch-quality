void copy_bad(double* d, const double* h, int n) {
  cudaMalloc((void**)&d, n * sizeof(double)); // no guard -> HPC-002
}
