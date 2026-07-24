// MMS test: diffusion equation
// This file triggers MMS verification detection (NVR-005)

#include <cmath>

// Manufactured solution: u = sin(pi*x)*cos(pi*y)
double exact_solution(double x, double y, double t) {
    return sin(M_PI * x) * cos(M_PI * y) * exp(-t);
}

// Forcing function derived from manufactured solution
double forcing(double x, double y, double t) {
    double u = exact_solution(x, y, t);
    return -2.0 * M_PI * M_PI * u - u; // -laplacian(u) - du/dt
}

// Observed order of accuracy calculation
void verify_order() {
    double L2_h = 1.2e-2;  // L2 error on coarse mesh
    double L2_h2 = 3.0e-3; // L2 error on fine mesh
    double p_obs = log(L2_h / L2_h2) / log(2.0);
    // Expected: p_obs ≈ 2.0 for second-order scheme
    assert(fabs(p_obs - 2.0) < 0.1);
}
