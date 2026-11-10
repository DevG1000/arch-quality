void race_bad(const double* a, int n) {
  double s = 0.0;
#pragma omp parallel for
  for (int i = 0; i < n; ++i) { s += a[i]; } // no reduction -> HPC-011
}
