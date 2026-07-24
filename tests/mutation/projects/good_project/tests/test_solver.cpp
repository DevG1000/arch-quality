// Unit test for solver
#include <cassert>
#include <cmath>

void test_solver_convergence() {
    double result = solve_pde();
    double expected = 1.0;
    double tolerance = 1e-6;
    assert(fabs(result - expected) < tolerance);
}

void test_kahan_summation() {
    double data[] = {1.0, 1e-8, -1.0, 1e-8};
    double sum = kahan_sum(data, 4);
    double expected = 2e-8;
    assert(fabs(sum - expected) < 1e-15);
}
