#include "StructuralSolver.h"

class StructuralSolverImpl : public StructuralSolver {
public:
    void solve() override {
        // residual convergence control
        double residual = 1e-8;
        double tolerance = 1e-6;
        // time stepping with CFL control
        double maxCo = 0.5;
        double courantNumber = 0.3;
    }
};
