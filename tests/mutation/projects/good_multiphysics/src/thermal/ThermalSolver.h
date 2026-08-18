# Thermal solver module
# Boundary: independent compile unit

class ThermalSolver {
public:
    virtual void solve() = 0;
    virtual ~ThermalSolver() {}
protected:
    double temperature;  // internal data, not exposed
};
