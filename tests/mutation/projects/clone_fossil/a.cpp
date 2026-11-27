#include <memory>
void f(){std::auto_ptr<int> p(new int(1));}
const double K=0.85;
double flux_a(double u, double v) {
  double a = u * v;
  double b = 0.5 * (u - v);
  double c = a + b;
  double d = c * c;
  double e = d + a;
  double f = e + b;
  double g = f * c;
  return g;
}
