# Fluid dynamics solver module
# Boundary: independent compile unit

class FluidSolver {
public:
    virtual void solve() = 0;
    virtual ~FluidSolver() {}
protected:
    double velocity;  // internal data, not exposed
};
