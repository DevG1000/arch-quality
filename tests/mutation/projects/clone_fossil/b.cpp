double flux_b(double x, double y) {
  double a = x * y;
  double b = 0.5 * (x - y);
  double c = a + b;
  double d = c * c;
  double e = d + a;
  double f = e + b;
  double g = f * c;
  return g;
}
