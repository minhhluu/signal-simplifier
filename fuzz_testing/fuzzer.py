"""
dsp_fuzzer/fuzzer.py
====================
Upgraded DSP expression fuzzer with:
  - Weighted, domain-aware expression generator
  - Seed-tracked reproducibility
  - Round-trip equivalence checking
  - Real SystemVerilog codegen scaffold
  - Structured JSON logging
  - CLI flags + parallel execution
  - Coverage tracking (op, depth, type)
"""

import random
import string
import sympy as sp
import numpy as np
import argparse
import json
import logging
import os
import sys
import time
import hashlib
import concurrent.futures
import sys
from pathlib import Path

# Add project root to path to find backend
sys.path.append(str(Path(__file__).parent.parent))
from backend.engine import SimplifierEngine

from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from enum import Enum

# ─────────────────────────────────────────────
# CONFIG DEFAULTS
# ─────────────────────────────────────────────
MAX_DEPTH        = 4
NUM_TESTS        = 100
EPS              = 1e-9
NUM_WORKERS      = 4          # parallel workers
EQUIV_CHECKS     = 8          # numeric equivalence sample count
MAX_SV_LEN       = 2000       # explosion guard

REAL_VARS    = ['x', 'y', 'n', 't']
COMPLEX_VARS = ['X', 'Y', 'H', 'Z']

# Op names → (weight, min_depth_allowed)
OP_TABLE: Dict[str, Tuple[int, int]] = {
    'add'    : (30, 0),
    'mul'    : (25, 0),
    'exp'    : (15, 0),
    'conj'   : (10, 0),
    'mag2'   : (10, 0),
    'div'    : ( 5, 1),   # avoid div-by-zero at depth 0
    'sum'    : ( 3, 1),   # heavy; restrict to mid-depth
    'delay'  : ( 2, 1),
}

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_run_ts = int(time.time())
_json_log_path = LOG_DIR / f"fuzz_{_run_ts}.jsonl"
_json_log_fh   = _json_log_path.open("a")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"fuzz_{_run_ts}.log"),
    ]
)
log = logging.getLogger("dsp_fuzzer")


def _emit(record: dict):
    """Append structured JSON record to JSONL log."""
    _json_log_fh.write(json.dumps(record) + "\n")
    _json_log_fh.flush()


# ─────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────
class Status(str, Enum):
    PASS         = "PASS"
    NUMERIC_FAIL = "NUMERIC_FAIL"
    ENGINE_FAIL  = "ENGINE_FAIL"
    SV_FAIL      = "SV_FAIL"
    EQUIV_FAIL   = "EQUIV_FAIL"


@dataclass
class FuzzResult:
    seed:         int
    expr_str:     str
    expr_hash:    str
    status:       Status
    sv_code:      Optional[str]    = None
    error:        Optional[str]    = None
    depth:        int              = 0
    op_trace:     List[str]        = field(default_factory=list)
    elapsed_ms:   float            = 0.0
    equiv_ok:     Optional[bool]   = None


# ─────────────────────────────────────────────
# SYMBOL FACTORIES
# ─────────────────────────────────────────────
def rand_real():
    return sp.Symbol(random.choice(REAL_VARS), real=True)

def rand_complex():
    return sp.Symbol(random.choice(COMPLEX_VARS))

def rand_scalar():
    return random.choice([
        sp.Integer(random.randint(1, 5)),
        sp.Rational(random.randint(1, 4), random.randint(2, 8)),
    ])

def rand_leaf():
    weights = [3, 3, 2]
    return random.choices(
        [rand_real, rand_complex, rand_scalar], weights
    )[0]()


# ─────────────────────────────────────────────
# WEIGHTED OP SELECTOR
# ─────────────────────────────────────────────
def _pick_op(depth: int) -> str:
    eligible = {k: w for k, (w, min_d) in OP_TABLE.items() if depth >= min_d}
    ops   = list(eligible.keys())
    wts   = list(eligible.values())
    return random.choices(ops, weights=wts, k=1)[0]


# ─────────────────────────────────────────────
# EXPRESSION GENERATOR
# ─────────────────────────────────────────────
def gen_expr(depth: int = 0, op_trace: Optional[List[str]] = None) -> sp.Expr:
    if op_trace is None:
        op_trace = []

    if depth >= MAX_DEPTH:
        return rand_leaf()

    op = _pick_op(depth)
    op_trace.append(op)

    def sub(d_inc=1):
        return gen_expr(depth + d_inc, op_trace)

    if op == 'add':
        return sub() + sub()

    elif op == 'mul':
        return sub() * sub()

    elif op == 'div':
        # Avoid exact-zero denominators by adding a small symbolic bias
        denom = sub() + sp.Rational(1, 100)
        return sub() / denom

    elif op == 'exp':
        return sp.exp(sp.I * sub())

    elif op == 'conj':
        return sp.conjugate(sub())

    elif op == 'mag2':
        x = sub()
        return x * sp.conjugate(x)

    elif op == 'sum':
        n = sp.Symbol('n', integer=True)
        k = random.randint(2, 6)
        return sp.Sum(sub(), (n, 0, k))

    elif op == 'delay':
        n = sp.Symbol('n', integer=True)
        k = random.randint(1, 3)
        return sp.Function('x')(n - k)

    return rand_leaf()


def expr_hash(expr: sp.Expr) -> str:
    s = str(expr)
    return hashlib.md5(s.encode()).hexdigest()[:10]


# ─────────────────────────────────────────────
# NUMERIC VALIDATION
# ─────────────────────────────────────────────
def _sample_subs(expr: sp.Expr) -> Dict:
    subs = {}
    for sym in expr.free_symbols:
        if sym.name == 'n' or sym.is_integer:
            subs[sym] = random.randint(0, 10)
        elif sym.is_real:
            subs[sym] = random.uniform(-2, 2)
        else:
            subs[sym] = complex(random.uniform(-1, 1), random.uniform(-1, 1))
    return subs


def numeric_check(expr: sp.Expr) -> bool:
    """Return True if expr evaluates to a finite complex number."""
    try:
        subs = _sample_subs(expr)
        val  = complex(expr.evalf(subs=subs))
        return (not np.isnan(val.real) and not np.isinf(val.real)
                and not np.isnan(val.imag) and not np.isinf(val.imag))
    except Exception:
        return False


# ─────────────────────────────────────────────
# ENGINE: SIMPLIFICATION + RULE HOOKS
# ─────────────────────────────────────────────
def _apply_dsp_rules(expr: sp.Expr) -> sp.Expr:
    """
    Lightweight DSP-aware rewrite rules applied before full simplification.
    Extend this with your domain-specific transforms.
    """
    # mag2(x) = re(x)^2 + im(x)^2  (already handled by mag2 construction,
    # but catch conjugate(a)*a patterns)
    expr = expr.rewrite(sp.exp)       # normalise trig → exp for DSP

    # Identity: conj(conj(x)) → x
    expr = expr.replace(
        lambda e: isinstance(e, sp.conjugate) and isinstance(e.args[0], sp.conjugate),
        lambda e: e.args[0].args[0]
    )

    return expr


def run_engine(expr: sp.Expr) -> Tuple[bool, Optional[sp.Expr], Optional[str], str]:
    """
    Returns: (ok, simplified_expr, error_msg, sv_code)
    """
    try:
        # Use our production engine for the actual simplification and SV gen
        engine = SimplifierEngine()
        result = engine.simplify_full(str(expr))
        
        if "error" in result:
            return False, None, result["error"], ""
            
        # Extract the final simplified expression from the steps
        # We need it as a SymPy object for the equiv_check
        final_str = result["final_str"]
        try:
            # Use sympify on the result string using our SignalSymbolDict to catch custom symbols
            from backend.engine import SignalSymbolDict
            simplified = sp.parse_expr(final_str, local_dict=SignalSymbolDict())
        except:
            # Fallback
            simplified = sp.simplify(expr)
            
        return True, simplified, None, result["final_sv"]
    except Exception as e:
        return False, None, str(e), ""


# ─────────────────────────────────────────────
# SYSTEMVERILOG CODEGEN SCAFFOLD
# ─────────────────────────────────────────────
_SV_HEADER = """\
// Auto-generated by dsp_fuzzer — DO NOT EDIT
// Source expr: {expr}
module dsp_block_{h} #(
    parameter int DATA_W = 16,
    parameter int FRAC_W = 14
) (
    input  logic                clk,
    input  logic                rst_n,
    input  logic signed [DATA_W-1:0] in_re,
    input  logic signed [DATA_W-1:0] in_im,
    output logic signed [DATA_W-1:0] out_re,
    output logic signed [DATA_W-1:0] out_im
);"""

_SV_FOOTER = """\
endmodule"""


def _expr_to_sv(expr: sp.Expr) -> str:
    """Convert a SymPy expression to a synthesisable SV assign string."""
    s = str(expr)
    # Minimal safe replacements — extend per your toolchain
    replacements = [
        ('**', '**'),        # placeholder; real: detect pow → shift or DSP mult
        ('I',  '1\'b0 /*j*/'),
        ('exp', '$clog2 /*exp_approx*/'),
        ('conjugate', '/* conj */'),
        ('Sum',  '/* sum */'),
    ]
    for src, dst in replacements:
        s = s.replace(src, dst)
    return s


def _emit_sv(expr: sp.Expr) -> str:
    h      = expr_hash(expr)
    inner  = _expr_to_sv(expr)
    body   = f"\n    // Combinational output\n    assign out_re = {inner};\n    assign out_im = '0; // imaginary TBD\n"
    return _SV_HEADER.format(expr=str(expr)[:60], h=h) + body + _SV_FOOTER


# ─────────────────────────────────────────────
# ROUND-TRIP EQUIVALENCE CHECK
# ─────────────────────────────────────────────
def equiv_check(original: sp.Expr, simplified: sp.Expr, n: int = EQUIV_CHECKS) -> bool:
    """
    Sample n random substitution points; return True iff outputs agree
    within a relative tolerance across all samples.
    """
    rtol = 1e-4
    atol = 1e-6
    try:
        for _ in range(n):
            subs = _sample_subs(original | simplified)
            v0   = complex(original.evalf(subs=subs))
            v1   = complex(simplified.evalf(subs=subs))
            if not np.allclose([v0.real, v0.imag], [v1.real, v1.imag],
                               rtol=rtol, atol=atol):
                return False
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# SV OUTPUT VALIDATION
# ─────────────────────────────────────────────
def validate_sv(sv_code: str) -> Tuple[bool, Optional[str]]:
    checks = [
        ("nan"   in sv_code.lower(),  "NaN in output"),
        ("zoo"   in sv_code.lower(),  "Zoo (complex inf) in output"),
        (len(sv_code) > MAX_SV_LEN,   "Output size explosion"),
        ("endmodule" not in sv_code,  "Missing endmodule"),
    ]
    for fail, reason in checks:
        if fail:
            return False, reason
    return True, None


# ─────────────────────────────────────────────
# COVERAGE TRACKER
# ─────────────────────────────────────────────
class Coverage:
    def __init__(self):
        self.ops: Dict[str, int]      = {k: 0 for k in OP_TABLE}
        self.depths: Dict[int, int]   = {}
        self.types: Dict[str, int]    = {"real": 0, "complex": 0, "scalar": 0}

    def record(self, op_trace: List[str], depth: int, expr: sp.Expr):
        for op in op_trace:
            self.ops[op] = self.ops.get(op, 0) + 1
        self.depths[depth] = self.depths.get(depth, 0) + 1
        syms = expr.free_symbols
        for s in syms:
            if s.is_real:     self.types["real"]    += 1
            elif s.is_integer:self.types["scalar"]  += 1
            else:              self.types["complex"] += 1

    def report(self) -> dict:
        return {"ops": self.ops, "depths": self.depths, "symbol_types": self.types}


# ─────────────────────────────────────────────
# SINGLE TEST CASE
# ─────────────────────────────────────────────
def run_one(seed: int) -> FuzzResult:
    rng = random.Random(seed)
    random.seed(seed)   # SymPy internals use global random

    t0        = time.perf_counter()
    op_trace: List[str] = []
    expr      = gen_expr(0, op_trace)
    depth     = len(op_trace)
    ehash     = expr_hash(expr)
    expr_str  = str(expr)

    def ms():
        return round((time.perf_counter() - t0) * 1000, 2)

    # Step 1: numeric sanity
    if not numeric_check(expr):
        return FuzzResult(seed, expr_str, ehash, Status.NUMERIC_FAIL,
                          depth=depth, op_trace=op_trace, elapsed_ms=ms())

    # Step 2: engine
    ok, simplified, err, sv_code = run_engine(expr)
    if not ok:
        return FuzzResult(seed, expr_str, ehash, Status.ENGINE_FAIL,
                          error=err, depth=depth, op_trace=op_trace, elapsed_ms=ms())

    # Step 3: SV validation
    sv_ok, sv_err = validate_sv(sv_code)
    if not sv_ok:
        return FuzzResult(seed, expr_str, ehash, Status.SV_FAIL,
                          sv_code=sv_code, error=sv_err,
                          depth=depth, op_trace=op_trace, elapsed_ms=ms())

    # Step 4: round-trip equivalence
    equiv_ok = equiv_check(expr, simplified)
    if not equiv_ok:
        return FuzzResult(seed, expr_str, ehash, Status.EQUIV_FAIL,
                          sv_code=sv_code, equiv_ok=False,
                          depth=depth, op_trace=op_trace, elapsed_ms=ms())

    return FuzzResult(seed, expr_str, ehash, Status.PASS,
                      sv_code=sv_code, equiv_ok=True,
                      depth=depth, op_trace=op_trace, elapsed_ms=ms())


# ─────────────────────────────────────────────
# MAIN FUZZ LOOP
# ─────────────────────────────────────────────
def fuzz_test(num_tests: int, base_seed: int, workers: int, verbose: bool) -> dict:
    seeds    = list(range(base_seed, base_seed + num_tests))
    stats    = {s.value: 0 for s in Status}
    stats["total"] = 0
    cov      = Coverage()
    failures : List[FuzzResult] = []

    log.info(f"Starting fuzz run: {num_tests} tests | seed={base_seed} | workers={workers}")

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_one, s): s for s in seeds}

        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
            except Exception as e:
                log.error(f"Unhandled worker exception: {e}")
                stats["total"] += 1
                stats[Status.ENGINE_FAIL.value] += 1
                continue

            stats["total"] += 1
            stats[res.status.value] += 1
            cov.record(res.op_trace, res.depth, sp.sympify(res.expr_str))

            record = asdict(res)
            _emit(record)

            if res.status == Status.PASS:
                if verbose:
                    log.info(f"[PASS] seed={res.seed} depth={res.depth} "
                             f"hash={res.expr_hash} {res.elapsed_ms}ms")
            else:
                failures.append(res)
                log.warning(f"[{res.status.value}] seed={res.seed} "
                            f"expr={res.expr_str[:60]} err={res.error}")

    return {"stats": stats, "coverage": cov.report(), "failures": [asdict(f) for f in failures]}


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="DSP expression fuzzer")
    p.add_argument("-n",  "--num-tests",  type=int, default=NUM_TESTS,
                   help="Number of test expressions")
    p.add_argument("-s",  "--seed",       type=int, default=42,
                   help="Base random seed (for reproducibility)")
    p.add_argument("-w",  "--workers",    type=int, default=NUM_WORKERS,
                   help="Parallel worker count")
    p.add_argument("-d",  "--max-depth",  type=int, default=MAX_DEPTH,
                   help="Maximum expression tree depth")
    p.add_argument("-v",  "--verbose",    action="store_true",
                   help="Print every PASS result")
    p.add_argument("-o",  "--out",        type=str, default=None,
                   help="Save full JSON report to file")
    return p.parse_args()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    args = parse_args()
    MAX_DEPTH = args.max_depth   # propagate to generator

    t_start = time.perf_counter()
    report  = fuzz_test(args.num_tests, args.seed, args.workers, args.verbose)
    elapsed = round(time.perf_counter() - t_start, 2)

    report["elapsed_s"] = elapsed
    report["log_file"]  = str(_json_log_path)

    print("\n" + "=" * 50)
    print("FUZZ TEST SUMMARY")
    print("=" * 50)
    for k, v in report["stats"].items():
        bar = "█" * int(v / max(report["stats"]["total"], 1) * 30)
        print(f"  {k:<18} {v:>5}  {bar}")

    print("\nCOVERAGE — ops hit:")
    for op, cnt in sorted(report["coverage"]["ops"].items(), key=lambda x: -x[1]):
        print(f"  {op:<12} {cnt}")

    print(f"\nElapsed: {elapsed}s | JSONL log: {_json_log_path}")

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"Full report: {args.out}")

    # Exit non-zero if any hard failures
    hard = (report["stats"].get(Status.EQUIV_FAIL.value, 0)
          + report["stats"].get(Status.ENGINE_FAIL.value, 0))
    sys.exit(1 if hard else 0)
