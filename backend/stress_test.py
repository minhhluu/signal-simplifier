import time
from engine import SimplifierEngine
import json
from sympy import pi, I

def run_benchmark():
    engine = SimplifierEngine()
    
    test_cases = [
        # --- CATEGORY A: Algebraic & Basic ---
        ("x + x + y", "Basic addition"),
        ("(x + 1)**2 - (x - 1)**2", "Algebraic expansion"),
        ("0 * x + 1", "Identity reduction"),
        ("1/x * x", "Cancellation"),
        ("0", "Minimalist input (Zero)"),
        
        # --- CATEGORY B: Complex Identities & Euler ---
        ("exp(i*pi)", "Euler identity (pi)"),
        ("exp(j*pi/2)", "Euler identity (j*pi/2)"),
        ("exp(I*pi/4)", "Fixed-point twiddle (45 deg)"),
        ("Abs(exp(i*theta))", "Complex magnitude on unit circle"),
        ("conjugate(a + i*b)", "Complex conjugation (Symbolic)"),
        ("conjugate(conjugate(X[k]))", "Double conjugation (Risk: Identity)"),
        ("exp(j*theta1) * exp(j*theta2)", "Phase rotation chain"),
        
        # --- CATEGORY C: Discrete Signal Processing ---
        ("x[n] * delta[n]", "Impulse sampling"),
        ("X[k] + X[k-1]", "Spectral addition"),
        ("H[k] * X[k]", "DFT domain convolution"),
        ("Sum(X[k]*exp(i*k*n), (k, 0, N-1))", "Inverse DFT structure"),
        ("Sum(X[k]*exp(i*2*pi*k*n/N), (k,0,N-1)) / N", "IDFT standard notation"),
        ("a * y[n-1] + b * x[n]", "IIR/FIR hybrid indexing"),
        ("H1[k] * H2[k] * X[k]", "Cascaded filtering chain"),
        ("x[n-2] * X[k]", "Mixed domain delay test"),
        
        # --- CATEGORY D: Continuous Analysis ---
        ("Integral(exp(-t**2), (t, -oo, oo))", "Gaussian Integral (Definite)"),
        ("Integral(exp(-a*t), (t, 0, oo))", "Laplace structure"),
        
        # --- CATEGORY E: Engineering Notation & Risk ---
        ("2pi * f * t", "Implicit multiplication (2pi)"),
        ("j2pi", "Implicit multiplication (j2pi)"),
        ("x[n]*cos(theta) + i*x[n]*sin(theta)", "Mixed Real/Complex bug trap"),
        
        # --- CATEGORY F: Symbolic & Hardware Risks (Hardening) ---
        ("conjugate(H[f]) / (Abs(H[f])**2 + N0)", "MMSE Equalization structure"),
        ("conjugate(H[k]) / (Abs(H[k])**2 + N0/Es)", "Wiener Filter structure"),
        ("X[z] * z**(-1)", "Z-transform delay (z^-1)"),
        ("1 / (1 - a*z**(-1))", "Z-domain pole structure"),
        ("Abs(X[k])**2", "Power spectrum term (|X|^2)"),
        ("re(X[k])**2 + im(X[k])**2", "Symbolic realization of norm"),
        ("1 / (x + 1e-9)", "Near-zero division risk"),
        ("exp(exp(exp(x)))", "Deeply nested AST stress"),
        
        # --- CATEGORY G: Transform Consistency & Round-trip ---
        ("expand((x+1)*(x-1))", "Explicit expand rule"),
        ("factor(x**2 + 2*x + 1)", "Explicit factor rule"),
        ("simplify(sin(x)**2 + cos(x)**2)", "Explicit simplify (Trig)"),
        
        # --- EXTENDED SUITE (User requested HARDENING) ---
        ("x[n] * exp(j*2*pi*k*n/N)", "Phase shift in time"),
        ("Integral(Integral(f, x), y)", "Nested Integrals"),
        ("Sum(Sum(X[k,m], (k,0,N-1)), (m,0,M-1))", "2D Summation"),
        ("conjugate(H[k]) * X[k] + conjugate(X[k]) * H[k]", "Hermitian symmetry test"),
        ("log(Abs(X[k]))", "Log-magnitude (dB scale prep)"),
        ("sqrt(re(X[k])**2 + im(X[k])**2)", "Magnitude recovery"),
        ("X[k] / (H[k] + 0.0001)", "Regularized inverse filter"),
        ("re(exp(i*theta))", "Real part extraction (Cosine)"),
        ("im(exp(i*theta))", "Imag part extraction (Sine)"),
        ("re(A+i*B) * re(C+i*D) - im(A+i*B) * im(C+i*D)", "Manually expanded complex mul"),
        ("x[n] * Piecewise((1, n>=0), (0, True))", "Piecewise step function logic"),
        ("lim(sin(x)/x, x, 0)", "Symbolic limit check (Sinc)"),
        ("Sum(x[n], (n, -oo, oo))", "Asymptotic summation"),
        ("exp(1e6 * i * theta)", "Dynamic range overflow stress"),
        ("1 / (1/H[k])", "Reciprocal symmetry (Ground truth check)"),
        ("Integral(delta(t-tau)*x[t], (t, -oo, oo))", "Dirac sifting property"),
    ]
    
    results = []
    total_start = time.time()
    
    print(f"{'#' : <3} | {'CASE' : <40} | {'STATUS' : <10} | {'TIME' : <10}")
    print("-" * 75)
    
    for i, (expr, desc) in enumerate(test_cases, 1):
        start = time.time()
        try:
            res = engine.simplify_full(expr)
            elapsed = (time.time() - start) * 1000
            if "error" in res:
                status = "FAILED"
                err_msg = res["error"]
            else:
                status = "PASSED"
                err_msg = ""
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            status = "CRASHED"
            err_msg = str(e)
            
        print(f"{i: <3} | {desc: <40} | {status: <10} | {elapsed:>8.2f}ms")
        results.append({
            "case_id": i,
            "expression": expr,
            "description": desc,
            "status": status,
            "time_ms": elapsed,
            "error": err_msg,
            "result_latex": res.get("final_latex") if status == "PASSED" else None
        })
        
    total_time = time.time() - total_start
    passed = len([r for r in results if r["status"] == "PASSED"])
    total = len(test_cases)
    
    benchmark = {
        "summary": {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": f"{(passed/total)*100:.1f}%",
            "total_wall_time_s": total_time,
            "avg_latency_ms": (sum(r["time_ms"] for r in results) / total)
        },
        "results": results
    }
    
    with open("benchmark_results.json", "w") as f:
        json.dump(benchmark, f, indent=2)
        
    return benchmark

if __name__ == "__main__":
    run_benchmark()
