# -*- coding: utf-8 -*-
"""Compressible NS MMS - buoyantPimpleFoam + steadyState + many correctors
rho=1.2+0.1*s, u=sincos, v=-cossin, T=500+20*x. Momentum-only sources from SymPy.
"""
import os, math, shutil, subprocess, re

ROOT = os.path.dirname(os.path.abspath(__file__))
MESHES = [("coarse", 10, 10), ("medium", 20, 20), ("fine", 40, 40)]
PI = math.pi
FOAM_BASH = ". /usr/lib/openfoam/openfoam2512/etc/bashrc"

def run(cmd, cwd, timeout=600):
    r = subprocess.run(["bash", "-c", f"{FOAM_BASH} && {{ {cmd}; }} 2>&1"],
                       cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r

def hdr(cls, obj):
    return f"FoamFile\n{{ version 2.0; format ascii; class {cls}; object {obj}; }}\n"

def write_0_U(nx, ny):
    vals = lambda n,fn: [fn((j+0.5)/n) for j in range(n)]
    internal = " ".join([f"({math.sin(PI*(i+0.5)/nx)*math.cos(PI*(j+0.5)/ny):.12f} {-math.cos(PI*(i+0.5)/nx)*math.sin(PI*(j+0.5)/ny):.12f} 0)" for j in range(ny) for i in range(nx)])
    def blk(k,n,v): return f"    {k} {{ type fixedValue; value nonuniform List<vector> {n}\n("+"\n".join(v)+"\n); }\n"
    s = hdr("volVectorField","U")+f"dimensions [0 1 -1 0 0 0 0];\ninternalField nonuniform List<vector> {nx*ny}\n({internal}\n);\nboundaryField\n{{\n"
    s += blk("left",ny,vals(ny,lambda y:f"(0 {-math.sin(PI*y):.12f} 0)"))
    s += blk("right",ny,vals(ny,lambda y:f"(0 {math.sin(PI*y):.12f} 0)"))
    s += blk("bottom",nx,vals(nx,lambda x:f"({math.sin(PI*x):.12f} 0 0)"))
    s += blk("top",nx,vals(nx,lambda x:f"({-math.sin(PI*x):.12f} 0 0)"))
    s += "  frontAndBack { type empty; }\n}\n"
    return s

def write_0_T(nx, ny):
    internal = " ".join([f"{500+20*(i+0.5)/nx:.6f}" for j in range(ny) for i in range(nx)])
    def blk(k,n,v): return f"    {k} {{ type fixedValue; value nonuniform List<scalar> {n}\n("+"\n".join(v)+"\n); }\n"
    s = hdr("volScalarField","T")+f"dimensions [0 0 0 1 0 0 0];\ninternalField nonuniform List<scalar> {nx*ny}\n({internal}\n);\nboundaryField\n{{\n"
    s += blk("left",ny,["500" for _ in range(ny)])
    s += blk("right",ny,["520" for _ in range(ny)])
    s += blk("bottom",nx,[f"{500+20*(i+0.5)/nx:.6f}" for i in range(nx)])
    s += blk("top",nx,[f"{500+20*(i+0.5)/nx:.6f}" for i in range(nx)])
    s += "  frontAndBack { type empty; }\n}\n"
    return s

def write_0_p():
    return hdr("volScalarField","p")+"dimensions [1 -1 -2 0 0 0 0];\ninternalField uniform 100000;\nboundaryField\n{ left { type zeroGradient; } right { type zeroGradient; }\n  bottom { type zeroGradient; } top { type zeroGradient; }\n  frontAndBack { type empty; } }\n"

def write_0_p_rgh(nx, ny):
    R = 287.0; rho0 = 1.2
    internal = " ".join([f"{rho0*R*(500+20*(i+0.5)/nx):.6f}" for j in range(ny) for i in range(nx)])
    def blk(k,n,v): return f"    {k} {{ type fixedValue; value nonuniform List<scalar> {n}\n("+"\n".join(v)+"\n); }\n"
    s = hdr("volScalarField","p_rgh")+f"dimensions [1 -1 -2 0 0 0 0];\ninternalField nonuniform List<scalar> {nx*ny}\n({internal}\n);\nboundaryField\n{{\n"
    s += blk("left",ny,["172200" for _ in range(ny)])
    s += blk("right",ny,["179088" for _ in range(ny)])
    s += blk("bottom",nx,[f"{rho0*R*(500+20*(i+0.5)/nx):.6f}" for i in range(nx)])
    s += blk("top",nx,[f"{rho0*R*(500+20*(i+0.5)/nx):.6f}" for i in range(nx)])
    s += "  frontAndBack { type empty; }\n}\n"
    return s

def write_thermo():
    return hdr("dictionary","thermophysicalProperties")+"""thermoType
{ type heRhoThermo; mixture pureMixture; transport const;
  thermo hConst; equationOfState perfectGas; specie specie;
  energy sensibleInternalEnergy; }
mixture { specie { molWeight 28.9; }
  thermodynamics { Cp 1005; Hf 0; }
  transport { mu 1.8e-05; Pr 0.7; } }
"""

def write_turb(): return hdr("dictionary","turbulenceProperties")+"simulationType  laminar;\n"
def write_g(): return hdr("uniformDimensionedVectorField","g")+"dimensions [0 1 -2 0 0 0 0];\nvalue (0 0 0);\n"

SRC_MOM = """
        const scalarField& V = mesh_.V();
        const vectorField& C = mesh_.C();
        forAll(C, cellI)
        {
            scalar x = C[cellI].x(); scalar y = C[cellI].y();
            scalar sx = M_PI*Foam::cos(M_PI*x)*(
                574.0*x*Foam::sin(M_PI*y) + 1.2*Foam::sin(M_PI*x)
              - 0.1*Foam::sin(M_PI*y)*Foam::sqr(Foam::cos(M_PI*x))
              + 14350.1*Foam::sin(M_PI*y))
              + 574.0*Foam::sin(M_PI*x)*Foam::sin(M_PI*y) + 6888.0;
            scalar sy = M_PI*Foam::cos(M_PI*y)*(
                574.0*x*Foam::sin(M_PI*x)
              + 0.1*Foam::sin(M_PI*x)*Foam::sqr(Foam::sin(M_PI*y))
              + 14350.0*Foam::sin(M_PI*x) + 1.2*Foam::sin(M_PI*y));
            eqn.source()[cellI] -= vector(sx, sy, 0.0) * V[cellI];
        }
"""

def write_fv_options():
    return hdr("dictionary","fvOptions")+"""
MMSMom
{ type vectorCodedSource; active true; name MMSMom; selectionMode all; fields (U);
  codeInclude #{ #};
  codeAddSup #{""" + SRC_MOM + """#};
  codeAddSupRho #{""" + SRC_MOM + """#};
  codeAddSupRHS #{ #}; codeSetValue #{ #}; codeCorrect #{ #}; codeConstrain #{ #}; }
"""

def write_control():
    return hdr("dictionary","controlDict")+"application buoyantPimpleFoam;\nstartFrom startTime; startTime 0; stopAt endTime; endTime 1;\ndeltaT 1; writeControl timeStep; writeInterval 1; purgeWrite 2;\nwriteFormat ascii; writePrecision 12;\n"

def write_fv_schemes():
    return hdr("dictionary","fvSchemes")+"""ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default Gauss linear;
  div(phi,U) Gauss linearUpwind grad(U);
  div(phi,he) Gauss linearUpwind grad(he);
  div(phi,K) Gauss linearUpwind grad(K);
  div(phiv,p) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
"""

def write_fv_solution():
    return hdr("dictionary","fvSolution")+"""solvers
{ p { solver PCG; preconditioner DIC; tolerance 1e-8; relTol 0; }
  p_rgh { $p; } p_rghFinal { $p; }
  rho { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0; }
  rhoFinal { $rho; }
  U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0; }
  UFinal { $U; }
  e { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0; }
  eFinal { $e; } }
PIMPLE { nOuterCorrectors 20; nCorrectors 1; nNonOrthogonalCorrectors 0;
  pRefCell 0; pRefValue 100000; }
relaxationFactors { U 0.7; e 0.7; p 0.3; }
"""

def write_block_mesh(nx, ny):
    return hdr("dictionary","blockMeshDict")+f"convertToMeters 1;\nvertices ( (0 0 0) (1 0 0) (1 1 0) (0 1 0) (0 0 0.1) (1 0 0.1) (1 1 0.1) (0 1 0.1) );\nblocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1) );\npatches ( patch left ( (0 4 7 3) ) patch right ( (1 5 6 2) ) patch bottom ( (0 1 5 4) ) patch top ( (3 7 6 2) ) empty frontAndBack ( (0 3 2 1) (4 5 6 7) ) );\n"

def create_case(case_dir, nx, ny):
    if os.path.exists(case_dir): shutil.rmtree(case_dir)
    for d in ["0","constant","system"]: os.makedirs(os.path.join(case_dir, d))
    files = {
        "0/U": write_0_U(nx,ny), "0/T": write_0_T(nx,ny),
        "0/p": write_0_p(), "0/p_rgh": write_0_p_rgh(nx,ny),
        "constant/thermophysicalProperties": write_thermo(),
        "constant/turbulenceProperties": write_turb(),
        "constant/g": write_g(),
        "constant/fvOptions": write_fv_options(),
        "system/controlDict": write_control(),
        "system/fvSchemes": write_fv_schemes(),
        "system/fvSolution": write_fv_solution(),
        "system/blockMeshDict": write_block_mesh(nx,ny),
    }
    for rel, cnt in files.items():
        with open(os.path.join(case_dir, rel), "w") as f: f.write(cnt)
    for cmd in ("blockMesh","buoyantPimpleFoam"):
        r = run(cmd, cwd=case_dir)
        if r.returncode != 0:
            print(f"  [{cmd}] FAILED"); return False
    return True

def latest_time(case_dir):
    ts = [(float(e),e) for e in os.listdir(case_dir) if os.path.isdir(os.path.join(case_dir,e)) and re.match(r'^\d+(\.?\d*)?$',e) and e!='0']
    return max(ts, key=lambda x:x[0])[1] if ts else None

def read_scalar(path):
    with open(path) as f: txt = f.read()
    i = txt.find("nonuniform")
    if i<0: m = re.search(r'uniform\s+([\d.eE+-]+)', txt); return [float(m.group(1))] if m else None
    p = txt.find("(", i)
    if p<0: return None
    m = re.search(r'\n\)\s*\n', txt[p:])
    if not m: return None
    vals = []
    for line in txt[p+1:p+m.start()].split("\n"):
        l = line.strip()
        if not l or l.startswith("//"): continue
        for t in l.split():
            try: vals.append(float(t.rstrip(";")))
            except: pass
    return vals

def read_vector(path):
    with open(path) as f: txt = f.read()
    i = txt.find("nonuniform")
    if i<0: m = re.search(r'uniform\s*\(([^)]+)\)', txt)
    if not m: return None
    p = txt.find("(", i)
    if p<0: return None
    m = re.search(r'\n\)\s*\n', txt[p:])
    if not m: return None
    vecs = []
    for line in txt[p+1:p+m.start()].split("\n"):
        l = line.strip().replace("("," ").replace(")"," ").strip()
        parts = l.split()
        if len(parts)>=3:
            try: vecs.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except: pass
    return vecs

def l2_err(case_dir, nx, ny, field, exact_fn):
    t = latest_time(case_dir)
    if not t: return None
    v = read_vector(os.path.join(case_dir, t, field)) if field == "U" else read_scalar(os.path.join(case_dir, t, field))
    if not v: return None
    n = nx*ny
    if field == "U":
        v = [(v[i][0] if i<len(v) else 0, v[i][1] if i<len(v) else 0, 0) for i in range(n)]
    else:
        v = (v[:n] if len(v)>=n else v+[0]*(n-len(v)))
    dx = 1.0/nx; e = 0.0
    for j in range(ny):
        for i in range(nx):
            k = j*nx+i
            if k>=len(v): break
            xc, yc = (i+0.5)*dx, (j+0.5)*dx
            ex = exact_fn(xc, yc)
            if field == "U":
                e += (v[k][0]-ex[0])**2 + (v[k][1]-ex[1])**2
            else:
                e += (v[k]-ex)**2
    return math.sqrt(e/n)

def main():
    errU, hs, ns = [], [], []
    for name, nx, ny in MESHES:
        cd = os.path.join(ROOT, f"rhopimple_mms_{name}")
        print(f"[{name}] ({nx}x{ny})...", end=" ", flush=True)
        if not create_case(cd, nx, ny): return
        eu = l2_err(cd, nx, ny, "U", lambda x,y: (math.sin(PI*x)*math.cos(PI*y), -math.cos(PI*x)*math.sin(PI*y)))
        et = l2_err(cd, nx, ny, "T", lambda x,y: 500+20*x)
        er = l2_err(cd, nx, ny, "rho", lambda x,y: 1.2+0.1*math.sin(PI*x)*math.sin(PI*y))
        if None in (eu, et, er): print("read FAIL"); return
        h = 1.0/nx; errU.append(eu); hs.append(h); ns.append(name)
        print(f"h={h:.4f} L2(U)={eu:.3e} L2(T)={et:.3e} L2(rho)={er:.3e}")

    print("\n"+"="*60+"\nMMS - buoyantPimpleFoam steadyState\n"+"="*60)
    for label, errs in [("U",errU),("rho",[0]),("T",[0])]:
        if len(errs)<2: continue
        print(f"\n  {label}:")
        orders = []
        for i in range(1,len(errs)):
            p = math.log(errs[i]/errs[i-1])/math.log(hs[i]/hs[i-1])
            orders.append(p)
            st = "PASS" if abs(p-2.0)<=0.1 else "FAIL"
            print(f"    {ns[i-1]:>8}->{ns[i]:>8}: p={p:.3f} [{st}]")
        if orders:
            pa=sum(orders)/len(orders)
            ap=all(abs(o-2.0)<=0.1 for o in orders)
            print(f"    avg: {pa:.3f} [{'PASS' if ap else 'FAIL'}]")
    print("="*60)

if __name__ == "__main__":
    main()
