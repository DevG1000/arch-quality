# -*- coding: utf-8 -*-
"""
solidDisplacementFoam MMS — 线弹性力学

制造解: D = (sin(πx)·sin(πy), 0, 0)
体力:    f_x = -π²·(λ + 3μ)·sin(πx)·sin(πy)
         f_y =  π²·(λ + μ)·cos(πx)·cos(πy)
         f_z = 0
理论阶: 2（二阶中心差分）
"""
import os, math, shutil, subprocess, re

ROOT = os.path.dirname(os.path.abspath(__file__))
MESHES = [("coarse", 10, 10), ("medium", 20, 20), ("fine", 40, 40)]
PI = math.pi
FOAM_BASH = ". /usr/lib/openfoam/openfoam2512/etc/bashrc"

E_mod = 200.0  # Young's modulus
nu = 0.3       # Poisson ratio
mu_val = E_mod / (2.0 * (1.0 + nu))
lam_val = nu * E_mod / ((1.0 + nu) * (1.0 - 2.0 * nu))

def run(cmd, cwd, timeout=600):
    r = subprocess.run(["bash", "-c", f"{FOAM_BASH} && {{ {cmd}; }} 2>&1"],
                       cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"  [{cmd.split()[0]}] FAILED")
        print((r.stderr or r.stdout)[-300:])
        return None
    return r

def hdr(cls, obj):
    return f"FoamFile\n{{ version 2.0; format ascii; class {cls}; object {obj}; }}\n"

def write_0_D(nx, ny):
    pi = PI
    internal = " ".join([f"({math.sin(pi*(i+0.5)/nx)*math.sin(pi*(j+0.5)/ny):.12f} 0 0)" for j in range(ny) for i in range(nx)])
    def blk(k,n,v): return f"    {k} {{ type fixedValue; value nonuniform List<vector> {n}\n("+"\n".join(v)+"\n); }\n"
    s = hdr("volVectorField","D")+f"dimensions [0 1 0 0 0 0 0];\ninternalField nonuniform List<vector> {nx*ny}\n({internal}\n);\nboundaryField\n{{\n"
    s += blk("left",ny,["(0 0 0)" for _ in range(ny)])
    s += blk("right",ny,["(0 0 0)" for _ in range(ny)])
    s += blk("bottom",nx,["(0 0 0)" for _ in range(nx)])
    s += blk("top",nx,["(0 0 0)" for _ in range(nx)])
    s += "  frontAndBack { type empty; }\n}\n"
    return s

def write_mechanical():
    return hdr("dictionary","mechanicalProperties")+f"""planeStress    no;
rho  {{ type uniform; value 1.0; }}
E    {{ type uniform; value {E_mod}; }}
nu   {{ type uniform; value {nu}; }}
"""

def write_fv_options():
    # Body force: f_x = -pi^2*(lam+3*mu)*sin(pix)*sin(piy), f_y = pi^2*(lam+mu)*cos(pix)*cos(piy)
    # fvOptions(D) adds to the RHS: laplacian(2mu+lam, D) + divSigmaExp + fvOptions(D) = 0
    const_x = -PI * PI * (lam_val + 3.0 * mu_val)
    const_y = PI * PI * (lam_val + mu_val)
    return hdr("dictionary","fvOptions")+f"""
MMSBodyForce
{{
    type            vectorCodedSource;
    active          true;
    name            MMSBodyForce;
    selectionMode   all;
    fields          (D);
    codeInclude
    #{{
    #}};
    codeAddSup
    #{{
        const scalarField& V = mesh_.V();
        const vectorField& C = mesh_.C();
        forAll(C, cellI)
        {{
            scalar x = C[cellI].x();
            scalar y = C[cellI].y();
            scalar fx = {const_x} * Foam::sin(M_PI*x) * Foam::sin(M_PI*y);
            scalar fy = {const_y} * Foam::cos(M_PI*x) * Foam::cos(M_PI*y);
            eqn.source()[cellI] -= vector(fx, fy, 0.0) * V[cellI];
        }}
    #}};
    codeAddSupRHS
    #{{
    #}};
    codeSetValue
    #{{
    #}};
    codeCorrect
    #{{
    #}};
    codeConstrain
    #{{
    #}};
}}
"""

def write_control():
    return hdr("dictionary","controlDict")+"application solidDisplacementFoam;\nstartFrom startTime; startTime 0; stopAt endTime; endTime 2;\ndeltaT 1; writeControl timeStep; writeInterval 1; purgeWrite 2;\nwriteFormat ascii; writePrecision 12;\n"

def write_fv_schemes():
    return hdr("dictionary","fvSchemes")+"""ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
"""

def write_fv_solution():
    return hdr("dictionary","fvSolution")+"""solvers
{
    D
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-10;
        relTol          0;
        nSweeps         1;
    }
}
stressAnalysis
{
    nCorrectors         100;
    D                   1e-8;
    compactNormalStress no;
}
"""

def write_block_mesh(nx, ny):
    return hdr("dictionary","blockMeshDict")+f"convertToMeters 1;\nvertices ( (0 0 0) (1 0 0) (1 1 0) (0 1 0) (0 0 0.1) (1 0 0.1) (1 1 0.1) (0 1 0.1) );\nblocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1) );\npatches ( patch left ( (0 4 7 3) ) patch right ( (1 5 6 2) ) patch bottom ( (0 1 5 4) ) patch top ( (3 7 6 2) ) empty frontAndBack ( (0 3 2 1) (4 5 6 7) ) );\n"

def create_case(case_dir, nx, ny):
    if os.path.exists(case_dir): shutil.rmtree(case_dir)
    for d in ["0","constant","system"]: os.makedirs(os.path.join(case_dir, d))
    files = {
        "0/D": write_0_D(nx, ny),
        "constant/mechanicalProperties": write_mechanical(),
        "constant/fvOptions": write_fv_options(),
        "constant/thermalProperties": hdr("dictionary","thermalProperties")+"thermalStress off;\n",
        "system/controlDict": write_control(),
        "system/fvSchemes": write_fv_schemes(),
        "system/fvSolution": write_fv_solution(),
        "system/blockMeshDict": write_block_mesh(nx, ny),
    }
    for rel, cnt in files.items():
        with open(os.path.join(case_dir, rel), "w") as f: f.write(cnt)
    for cmd in ("blockMesh","solidDisplacementFoam"):
        r = run(cmd, cwd=case_dir)
        if r is None: return False
    return True

def latest_time(case_dir):
    ts = [(float(e),e) for e in os.listdir(case_dir) if os.path.isdir(os.path.join(case_dir,e)) and re.match(r'^\d+(\.?\d*)?$',e) and e!='0']
    return max(ts, key=lambda x:x[0])[1] if ts else None

def read_vector(path):
    with open(path) as f: txt = f.read()
    i = txt.find("nonuniform")
    if i<0:
        m = re.search(r'uniform\s*\(([^)]+)\)', txt)
        if not m: return None
        p = m.group(1).split()
        return [(float(p[0]), float(p[1]), float(p[2]))]
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

def l2_D(case_dir, nx, ny):
    t = latest_time(case_dir)
    if not t: return None
    v = read_vector(os.path.join(case_dir, t, "D"))
    if not v: return None
    n = nx*ny
    v = [(v[i][0] if i<len(v) else 0, v[i][1] if i<len(v) else 0, 0) for i in range(n)]
    dx = 1.0/nx; e = 0.0
    for j in range(ny):
        for i in range(nx):
            k = j*nx+i
            if k>=len(v): break
            xc, yc = (i+0.5)*dx, (j+0.5)*dx
            ue = math.sin(PI*xc)*math.sin(PI*yc)
            e += (v[k][0]-ue)**2 + (v[k][1]-0)**2
    return math.sqrt(e/n)

def main():
    errs, hs, ns = [], [], []
    for name, nx, ny in MESHES:
        cd = os.path.join(ROOT, f"solid_mms_{name}")
        print(f"[{name}] ({nx}x{ny})...", end=" ", flush=True)
        if not create_case(cd, nx, ny): return
        e = l2_D(cd, nx, ny)
        if e is None: print("read FAIL"); return
        h = 1.0/nx; errs.append(e); hs.append(h); ns.append(name)
        print(f"h={h:.4f} L2(D)={e:.3e}")

    print("\n"+"="*60+"\nMMS - solidDisplacementFoam\n"+"="*60)
    print("  D = (sin(πx)·sin(πy), 0, 0)")
    print(f"  E={E_mod}, ν={nu}, μ={mu_val:.1f}, λ={lam_val:.1f}")
    print("  Expected order: 2.0\n")
    if len(errs) >= 2:
        print("  D convergence:")
        for i in range(1,len(errs)):
            p = math.log(errs[i]/errs[i-1])/math.log(hs[i]/hs[i-1])
            st = "PASS" if abs(p-2.0)<=0.1 else "FAIL"
            print(f"    {ns[i-1]:>8}->{ns[i]:>8}: p={p:.3f} [{st}]")
        pa = sum([math.log(errs[i]/errs[i-1])/math.log(hs[i]/hs[i-1]) for i in range(1,len(errs))])/(len(errs)-1)
        ap = all(abs(math.log(errs[i]/errs[i-1])/math.log(hs[i]/hs[i-1])-2.0)<=0.1 for i in range(1,len(errs)))
        print(f"    avg: {pa:.3f} [{'PASS' if ap else 'FAIL'}]")
    print("="*60)

if __name__ == "__main__":
    main()
