
from engine import SimplifierEngine
import json

engine = SimplifierEngine()
test_exprs = [
    "X[k]",
    "Sum(X[k]*exp(i*k), (k, 0, N-1))",
    "H[f] * X[f]",
    "x[n]"
]

for expr in test_exprs:
    print(f"Testing: {expr}")
    res = engine.simplify_full(expr)
    if "error" in res:
        print(f"  Result: ERROR -> {res['error']}")
    else:
        print(f"  Result: SUCCESS -> {res['final_latex']}")
