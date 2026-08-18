"""
Derive solidDisplacementFoam MMS source terms
Linear elasticity: div(sigma) = f
sigma = 2*mu*epsilon + lambda*tr(epsilon)*I
epsilon = 0.5*(grad(D) + grad(D)^T)

Manufactured solution: D = (sin(pi*x)*sin(pi*y), 0, 0)
"""
import sympy as sp

x, y, pi = sp.symbols('x y pi', real=True)
mu, lam = sp.symbols('mu lam', positive=True, real=True)

# Displacement
u = sp.sin(pi*x) * sp.sin(pi*y)

# Strain
eps_xx = sp.diff(u, x)
eps_yy = 0
eps_xy = sp.Rational(1,2) * sp.diff(u, y)

tr_eps = eps_xx + eps_yy

# Stress (plane strain, 2D)
sig_xx = 2*mu*eps_xx + lam*tr_eps
sig_yy = 2*mu*eps_yy + lam*tr_eps
sig_xy = 2*mu*eps_xy

# Body force f = div(sigma)
fx = sp.simplify(sp.diff(sig_xx, x) + sp.diff(sig_xy, y))
fy = sp.simplify(sp.diff(sig_xy, x) + sp.diff(sig_yy, y))

print(f"u = {u}")

print(f"\nfx = {fx}")
print(f"fy = {fy}")

# With mu=1, lambda=1
subs = {pi: sp.pi, mu: 1, lam: 1, x: 0.25, y: 0.25}
print(f"\nAt x=0.25, y=0.25:")
print(f"  u = {float(u.subs(subs))}")
print(f"  fx = {float(fx.subs(subs))}")
print(f"  fy = {float(fy.subs(subs))}")

# C++ code
print(f"\n// fx = {fx}")
print(f"// fy = {fy}")
