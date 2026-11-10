void f() {
#pragma omp parallel
  {
#pragma omp parallel
    { }
  }
}
