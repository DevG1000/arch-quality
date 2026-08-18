#include "ThermalSolver.h"

class ThermalSolverImpl : public ThermalSolver {
public:
    void solve() override {
        double residual = 1e-8;
        double tolerance = 1e-6;
        double maxCo = 0.5;
    }
};
