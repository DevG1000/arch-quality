"""
Re-derive rhoPimpleFoam MMS source terms with T0=500K
rho = 1.2 + 0.1*sin(pix)*sin(piy)
u = sin(pix)*cos(piy), v = -cos(pix)*sin(piy)
T = 500 + 20*sin(pix)*sin(piy)   (range: 480-520K, always well above ref)
p = rho*R*T
R = 287, Cp = 1005, Cv = 718
"""
import sympy as sp

x, y, pi = sp.symbols('x y pi', real=True)
R, cv = 287.0, 718.0

rho0, rho1 = 1.2, 0.1
T0, T1 = 500.0, 20.0

rho = rho0 + rho1 * sp.sin(pi*x) * sp.sin(pi*y)
u = sp.sin(pi*x) * sp.cos(pi*y)
v = -sp.cos(pi*x) * sp.sin(pi*y)
T = T0 + T1 * sp.sin(pi*x) * sp.sin(pi*y)
p = rho * R * T
K = 0.5 * (u**2 + v**2)
E = cv * T + K  # total energy per unit mass

# Continuity
rhoU_vec = sp.Matrix([rho*u, rho*v])
S_c = sp.simplify(sp.diff(rhoU_vec[0], x) + sp.diff(rhoU_vec[1], y))
print(f"S_c = {S_c}")
assert S_c == 0, "Continuity source should be zero!"

# Momentum
d_rhoUU_xx = sp.diff(rho*u*u, x)
d_rhoUU_xy = sp.diff(rho*u*v, y)
d_rhoUU_yx = sp.diff(rho*v*u, x)
d_rhoUU_yy = sp.diff(rho*v*v, y)

S_mx = sp.simplify(d_rhoUU_xx + d_rhoUU_xy + sp.diff(p, x))
S_my = sp.simplify(d_rhoUU_yx + d_rhoUU_yy + sp.diff(p, y))

print(f"\nS_mx = {S_mx}")
print(f"S_my = {S_my}")

# Total energy: div(U*(rho*E + p)) = S_e
u_rhoE_p = u*(rho*E + p)
v_rhoE_p = v*(rho*E + p)
S_e = sp.simplify(sp.diff(u_rhoE_p, x) + sp.diff(v_rhoE_p, y))

print(f"\nS_e = {S_e}")

# Spot check
subs = {pi: sp.pi, x: 0.25, y: 0.25}
p_mms = float(rho.subs(subs)) * R * float(T.subs(subs))
print(f"\n--- Spot check at (0.25,0.25) ---")
print(f"  rho = {float(rho.subs(subs))}")
print(f"  u,v = {float(u.subs(subs))}, {float(v.subs(subs))}")
print(f"  T = {float(T.subs(subs))}")
print(f"  p = {p_mms:.1f}")
print(f"  S_c = {float(S_c.subs(subs))}")
print(f"  S_mx = {float(S_mx.subs(subs)):.2f}")
print(f"  S_my = {float(S_my.subs(subs)):.2f}")
print(f"  S_e = {float(S_e.subs(subs)):.2f}")

# C++ code output
def to_cpp(expr, name):
    s = str(expr)
    s = s.replace('pi', 'M_PI')
    s = s.replace('**', '')
    s = s.replace('sin', 'Foam::sin')
    s = s.replace('cos', 'Foam::cos')
    return f"  // {name} = {s}"

print(f"\n--- C++ ---")
print(to_cpp(S_c, "S_c"))
print(to_cpp(S_mx, "S_mx"))
print(to_cpp(S_my, "S_my"))
print(to_cpp(S_e, "S_e"))
