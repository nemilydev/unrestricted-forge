#!/usr/bin/env python3
"""Diff vm.py against main.py (tree-walker) on every example file."""
import subprocess, sys, io, contextlib, time

EXAMPLES = ["fibonacci.fl", "fizzbuzz.fl", "higher_order.fl",
            "stress_test.fl", "bug_hunt.fl"]

def run(mod, path):
    """Run a .fl file by importing the module's main machinery."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(mod, f"{mod}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with open(path) as f:
        src = f.read()
    buf = io.StringIO()
    t0 = time.perf_counter()
    try:
        with contextlib.redirect_stdout(buf):
            if mod == "main":
                m.Interpreter().run(src)
            else:
                m.VM().run(src)
        err = None
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    return buf.getvalue(), err, dt

fails = 0
for ex in EXAMPLES:
    out_a, err_a, t_a = run("main", f"examples/{ex}")
    out_b, err_b, t_b = run("vm", f"examples/{ex}")
    status = "PASS" if (out_a == out_b and err_a == err_b) else "FAIL"
    if status == "FAIL":
        fails += 1
    print(f"[{status}] {ex}  (tree {t_a*1000:.1f}ms / vm {t_b*1000:.1f}ms)")
    if status == "FAIL":
        if err_a or err_b:
            print(f"  tree err: {err_a}\n  vm err:   {err_b}")
        la, lb = out_a.splitlines(), out_b.splitlines()
        for i in range(max(len(la), len(lb))):
            a = la[i] if i < len(la) else "<missing>"
            b = lb[i] if i < len(lb) else "<missing>"
            if a != b:
                print(f"  line {i+1}: tree={a!r}\n           vm  ={b!r}")

sys.exit(1 if fails else 0)
