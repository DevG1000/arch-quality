"""
Derive rhoCentralFoam MMS source terms using SymPy
Euler equations (inviscid, no heat conduction):
  Continuity: d(rho)/dt + div(rho*U) = S_c
  Momentum:   d(rhoU)/dt + div(rhoU*U) + grad(p) = S_m
  Energy:     d(rhoE)/dt + div(U*(rhoE + p)) = S_e
  
Ideal gas: p = rho*R*T, E = cv*T + 0.5*|U|^2
"""
import sympy as sp

# Symbols
x, y, pi = sp.symbols('x y pi', real=True)
R, cv, gamma = sp.symbols('R cv gamma', positive=True, real=True)
cp = cv * gamma

# Constants
rho0, rho1 = 1.2, 0.1
T0, T1 = 300.0, 20.0
R_val = 287.0
cv_val = 718.0
gamma_val = cp / cv

# Manufactured solutions (steady state)
rho = rho0 + rho1 * sp.sin(pi*x) * sp.sin(pi*y)
u = sp.sin(pi*x) * sp.cos(pi*y)
v = -sp.cos(pi*x) * sp.sin(pi*y)
T = T0 + T1 * sp.sin(pi*x) * sp.sin(pi*y)

# Derived quantities
p = rho * R_val * T  # ideal gas
K = 0.5 * (u**2 + v**2)  # kinetic energy per unit mass
E = cv_val * T + K  # total energy per unit mass

# Continuity: d(rho)/dt + div(rho*U) = S_c
# d(rho)/dt = 0 (steady)
rhoU = sp.Matrix([rho * u, rho * v])
div_rhoU = sp.diff(rhoU[0], x) + sp.diff(rhoU[1], y)
S_c = sp.simplify(div_rhoU)
print("=" * 60)
print("CONTINUITY")
print("=" * 60)
print(f"  div(rho*U) = {div_rhoU}")
print(f"  S_c = {S_c}")

# Momentum: div(rhoU*U) + grad(p) = S_m
# rhoU * U = [rho*u*u, rho*u*v; rho*v*u, rho*v*v]
rhoUU_xx = sp.diff(rho * u * u, x)
rhoUU_xy = sp.diff(rho * u * v, y)
div_rhoUU_x = sp.simplify(rhoUU_xx + rhoUU_xy)

rhoUU_yx = sp.diff(rho * v * u, x)
rhoUU_yy = sp.diff(rho * v * v, y)
div_rhoUU_y = sp.simplify(rhoUU_yx + rhoUU_yy)

dp_dx = sp.diff(p, x)
dp_dy = sp.diff(p, y)

S_mx = sp.simplify(div_rhoUU_x + dp_dx)
S_my = sp.simplify(div_rhoUU_y + dp_dy)

print("\n" + "=" * 60)
print("MOMENTUM")
print("=" * 60)
print(f"  S_mx = {S_mx}")
print(f"  S_my = {S_my}")

# Energy: div(U*(rhoE + p)) = S_e
# U*(rhoE + p) = [u*(rhoE+p), v*(rhoE+p)]
u_rhoE_p = u * (rho * E + p)
v_rhoE_p = v * (rho * E + p)

div_rhoE = sp.simplify(sp.diff(u_rhoE_p, x) + sp.diff(v_rhoE_p, y))
S_e = div_rhoE

print("\n" + "=" * 60)
print("ENERGY")
print("=" * 60)
print(f"  S_e = {S_e}")

# Spot-check at x=0.25, y=0.25
subs = {pi: sp.pi, x: 0.25, y: 0.25}
print("\n" + "=" * 60)
print("SPOT CHECK at x=0.25, y=0.25")
print("=" * 60)

print(f"  rho = {float(rho.subs(subs))}")
print(f"  u = {float(u.subs(subs))}")
print(f"  v = {float(v.subs(subs))}")
print(f"  T = {float(T.subs(subs))}")
print(f"  p = {float(p.subs(subs))}")
print(f"  E = {float(E.subs(subs))}")
print(f"  S_c = {float(S_c.subs(subs))}")
print(f"  S_mx = {float(S_mx.subs(subs))}")
print(f"  S_my = {float(S_my.subs(subs))}")
print(f"  S_e = {float(S_e.subs(subs))}")

# Write output as C++ source code for copy-paste
print("\n" + "=" * 60)
print("C++ CODE FOR FVOPTIONS")
print("=" * 60)

import re
def cpp_expr(expr, name):
    s = str(expr)
    s = s.replace('pi', 'M_PI')
    s = s.replace('**', '')
    # Replace functions
    s = s.replace('sin', 'Foam::sin')
    s = s.replace('cos', 'Foam::cos')
    s = s.replace('pow', 'Foam::pow')
    # Replace numeric constants
    s = s.replace('R_val', str(R_val))
    s = s.replace('cv_val', str(cv_val))
    s = s.replace('rho0', str(rho0))
    s = s.replace('rho1', str(rho1))
    s = s.replace('T0', str(T0))
    s = s.replace('T1', str(T1))
    return s

print(f"  // S_c = {cpp_expr(S_c, 'S_c')}")
print(f"  // S_mx = {cpp_expr(S_mx, 'S_mx')}")
print(f"  // S_my = {cpp_expr(S_my, 'S_my')}")
print(f"  // S_e = {cpp_expr(S_e, 'S_e')}")
