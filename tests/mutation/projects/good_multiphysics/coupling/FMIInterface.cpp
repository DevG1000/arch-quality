// FMI co-simulation interface implementation
class FMIInterface {
public:
    void fmi2DoStep(double t) {}
    double fmi2GetReal(int v) { return 0.0; }
    void fmi2SetReal(int v, double x) {}
};
