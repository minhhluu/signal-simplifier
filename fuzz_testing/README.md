# DSP Expression Fuzzer — Upgraded

## What's new vs the original

| Area | Before | After |
|---|---|---|
| Expression gen | Uniform random ops | **Weighted ops** (add/mul favoured, sum/delay rare) with min-depth guards |
| Reproducibility | None | **Seed-tracked** — every test case has a unique deterministic seed |
| Engine | `sp.simplify` only | **DSP-aware rewrite rules** (conjugate identity, trig→exp normalisation) before simplify |
| Codegen | `assign out = <str>;` one-liner | **Full SV module scaffold** with parameterised header, `DATA_W`/`FRAC_W`, endmodule |
| Validation | Regex on string | **4-stage pipeline**: numeric → engine → SV lint → round-trip equivalence |
| Round-trip | None | **8-point numeric equivalence check** original ↔ simplified |
| Logging | `print()` | **Structured JSONL** log + human-readable `.log`, both timestamped |
| Parallelism | Serial | `ProcessPoolExecutor` — configurable worker count |
| Coverage | None | **Per-op hit counts**, depth histogram, symbol type distribution |
| CLI | Hardcoded constants | `argparse`: `-n`, `-s`, `-w`, `-d`, `-v`, `-o` |
| Dashboard | None | **HTML dashboard** — drop JSONL or JSON report, see pass-rate donut, op bars, failure table |

---

## Quickstart

```bash
pip install sympy numpy

# Run 200 tests, seed 1337, 8 workers, save JSON report
python fuzzer.py -n 200 -s 1337 -w 8 -o report.json

# Verbose (print every PASS)
python fuzzer.py -n 50 -v

# Deeper expression trees
python fuzzer.py -n 100 -d 6
```

Logs land in `logs/fuzz_<timestamp>.jsonl` and `logs/fuzz_<timestamp>.log`.

---

## Plugging in your real engine

Replace the body of `run_engine()` in `fuzzer.py`:

```python
def run_engine(expr: sp.Expr):
    try:
        rewritten  = _apply_dsp_rules(expr)      # keep this
        simplified = your_rule_engine(rewritten)  # ← your pipeline here
        sv         = your_sv_exporter(simplified) # ← your hardware exporter
        return True, simplified, None, sv
    except Exception as e:
        return False, None, str(e), ""
```

Add domain rules in `_apply_dsp_rules()`:
```python
# Example: replace exp(jω) with DFT kernel pattern
expr = expr.replace(
    lambda e: e.is_Mul and ...,
    lambda e: ...
)
```

---

## Dashboard

Open `dashboard.html` in any browser.  
Drop your `logs/fuzz_*.jsonl` or `report.json` file — no server needed.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All tests passed or only numeric/SV failures |
| `1` | Any ENGINE_FAIL or EQUIV_FAIL (hard errors) |

Use in CI: `python fuzzer.py -n 500 || exit 1`
