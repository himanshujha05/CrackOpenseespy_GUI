"""Auto-generated OpenSeesPy script (run where OpenSeesPy is installed)."""
import json
import numpy as np

import sys, json
import numpy as np

def run_model(p):
    import openseespy.opensees as ops

    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 2)

    L = float(p['bar_length'])
    A = float(p['bar_area'])
    Es = float(p['Es'])
    fsy = float(p['fsy'])
    ele_type = p.get('ele_type', 'Truss')

    crack_data = sorted(p.get('crack_data', []), key=lambda c: c['y'])
    crack_data = [c for c in crack_data if 0.001 * L < c['y'] < 0.999 * L]

    # --- rebar material ---
    rebar_mat = 1
    mat_type = p.get('mat_type', 'Elastic')
    if mat_type == 'ElasticPP':
        eps_y = fsy / Es
        ops.uniaxialMaterial('ElasticPP', rebar_mat, Es, eps_y)
    elif mat_type == 'Steel02':
        b = float(p.get('hardening_ratio', 0.01))
        R0 = float(p.get('R0', 15.0))
        cR1 = float(p.get('cR1', 0.925))
        cR2 = float(p.get('cR2', 0.15))
        ops.uniaxialMaterial('Steel02', rebar_mat, fsy, Es, b, R0, cR1, cR2)
    else:
        ops.uniaxialMaterial('Elastic', rebar_mat, Es)

    # --- counters ---
    n_tag = 0
    e_tag = 0

    def mk_node(x, y, fix_x=1, fix_y=0):
        nonlocal n_tag
        n_tag += 1
        ops.node(n_tag, x, y)
        ops.fix(n_tag, fix_x, fix_y)
        return n_tag

    def mk_truss(i, j):
        nonlocal e_tag
        e_tag += 1
        ops.element(ele_type, e_tag, i, j, A, rebar_mat)
        return e_tag

    def mk_crack(i, j, kn, kt, ci):
        nonlocal e_tag
        mx = 10 + ci * 2
        my = 11 + ci * 2
        ops.uniaxialMaterial('Elastic', mx, max(float(kt), 1.0))
        ops.uniaxialMaterial('Elastic', my, float(kn))
        e_tag += 1
        ops.element('zeroLength', e_tag, i, j, '-mat', mx, my, '-dir', 1, 2)
        return e_tag

    # --- topology ---
    base = mk_node(0.0, 0.0, fix_x=1, fix_y=1)
    prev = base

    truss_eles = []
    crack_nodes = []   # [(nb, na, y), ...]

    for ci, crack in enumerate(crack_data):
        y_c = float(crack['y'])
        nb = mk_node(0.0, y_c, fix_x=1, fix_y=0)
        truss_eles.append(mk_truss(prev, nb))

        na = mk_node(0.0, y_c, fix_x=1, fix_y=0)
        mk_crack(nb, na, crack['kn'], crack['kt'], ci)
        crack_nodes.append((nb, na, y_c))
        prev = na

    top = mk_node(0.0, L, fix_x=1, fix_y=0)
    truss_eles.append(mk_truss(prev, top))

    loaded_node = top
    free_dof = 2
    force_ele = truss_eles[0]  # first truss

    # --- loading ---
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ref_load = fsy * A

    analysis_type = p.get('analysis_type', 'DisplacementControl')
    if analysis_type == 'LoadControl':
        ops.load(loaded_node, 0.0, ref_load)
    else:
        ops.load(loaded_node, 0.0, 1.0)

    # --- analysis system ---
    ops.constraints('Plain')
    ops.numberer('Plain')
    ops.system('BandGeneral')
    ops.algorithm(p.get('algorithm', 'Newton'))
    ops.test('NormDispIncr', float(p.get('tol', 1e-6)), int(p.get('max_iter', 100)))

    disp_list = []
    force_list = []
    crack_openings = [[] for _ in crack_nodes]

    def collect():
        disp_list.append(ops.nodeDisp(loaded_node, free_dof))
        force_list.append(-ops.eleForce(force_ele, free_dof))
        for k, (nb, na, _) in enumerate(crack_nodes):
            crack_openings[k].append(
                ops.nodeDisp(na, free_dof) - ops.nodeDisp(nb, free_dof)
            )

    ops.analysis('Static')

    if analysis_type == 'LoadControl':
        incr = float(p.get('load_incr', 0.01))
        steps = max(1, int(1.0 / incr))
        ops.integrator('LoadControl', incr)
        for _ in range(steps):
            if ops.analyze(1) == 0:
                collect()
            else:
                break
    else:
        target = float(p.get('target_disp', 0.5))
        incr = float(p.get('disp_incr', 0.001))
        steps = max(1, int(abs(target) / max(abs(incr), 1e-12)))
        ops.integrator('DisplacementControl', loaded_node, free_dof, incr)
        for _ in range(steps):
            if ops.analyze(1) == 0:
                collect()
            else:
                break

    # Pack results
    disp = np.array(disp_list, dtype=float)
    force = np.array(force_list, dtype=float)
    crack_openings_np = [np.array(x, dtype=float) for x in crack_openings]
    crack_positions = [float(y) for (_, _, y) in crack_nodes]

    return {
        "disp": disp,
        "force": force,
        "crack_openings": crack_openings_np,
        "crack_positions": np.array(crack_positions, dtype=float),
        "status": "ok" if len(disp_list) else "failed",
        "message": f"{len(disp_list)} steps converged | {len(crack_nodes)} crack(s)",
        "fy": float(ref_load),
    }

def main():
    if len(sys.argv) != 3:
        print("Usage: runner.py params.json results.npz")
        sys.exit(2)

    params_path = sys.argv[1]
    out_path = sys.argv[2]

    with open(params_path, "r") as f:
        p = json.load(f)

    result = run_model(p)

    # Save into npz (arrays + metadata)
    np.savez(
        out_path,
        disp=result["disp"],
        force=result["force"],
        crack_positions=result["crack_positions"],
        status=np.array([result["status"]]),
        message=np.array([result["message"]]),
        fy=np.array([result["fy"]]),
        # variable length lists -> store as object array
        crack_openings=np.array(result["crack_openings"], dtype=object),
    )

    print(result["message"])
    sys.exit(0 if result["status"] == "ok" else 1)

if __name__ == "__main__":
    main()


if __name__ == '__main__':
    # Example usage:
    #   python script.py params.json results.npz
    main()
