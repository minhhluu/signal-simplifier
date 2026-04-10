from sympy import (exp, I, pi, oo, Integral, Symbol, simplify, expand, factor,
                    powsimp, collect, latex, Wild, sqrt, erfc, erf, Sum,
                    IndexedBase, Function, log, sin, cos, tan, Abs,
                    Add, Mul, Pow, Integer, Float, Rational, Indexed,
                    conjugate, re, im, Piecewise, DiracDelta, Heaviside, limit)
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, convert_xor, implicit_multiplication_application
import tokenize

# All SymPy functions/constants/classes that should NOT become IndexedBase
SYMPY_BUILTINS = {
    'exp': exp, 'Sum': Sum, 'Integral': Integral, 'sqrt': sqrt,
    'erf': erf, 'erfc': erfc, 'log': log, 'sin': sin, 'cos': cos,
    'tan': tan, 'Abs': Abs, 'I': I, 'pi': pi, 'oo': oo,
    'i': I, 'j': I, 'E': exp(1),
    'conjugate': conjugate, 'conj': conjugate,
    're': re, 'im': im,
    'expand': expand, 'factor': factor, 'simplify': simplify,
    'limit': limit, 'lim': limit,
    'Piecewise': Piecewise, 'delta': DiracDelta, 'DiracDelta': DiracDelta,
    'Heaviside': Heaviside,
    'Add': Add, 'Mul': Mul, 'Pow': Pow, 'Symbol': Symbol,
    'Integer': Integer, 'Float': Float, 'Rational': Rational,
    'Indexed': Indexed, 'IndexedBase': IndexedBase
}

def index_transformation(tokens, local_dict, global_dict):
    """
    SymPy transformation to handle indexing like x[n] or X[k].
    If a NAME is followed by '[', it must be an IndexedBase.
    """
    result = []
    for i in range(len(tokens)):
        token = tokens[i]
        # token[0] is the type, token[1] is the string
        if token[0] == tokenize.NAME and i + 1 < len(tokens) and tokens[i+1][1] == '[':
            name = token[1]
            if name not in SYMPY_BUILTINS:
                # Force it to be an IndexedBase in local_dict
                local_dict[name] = IndexedBase(name)
        result.append(token)
    return result

class SignalSymbolDict(dict):
    """Custom dict for signal processing parsing:
    - UPPERCASE names (X, Y, H) -> IndexedBase
    - lowercase names (n, k, t) -> Symbol
    - Known SymPy functions/constants -> Builtin
    """
    def __init__(self):
        super().__init__(SYMPY_BUILTINS)

    def __missing__(self, key):
        if key in SYMPY_BUILTINS:
            return SYMPY_BUILTINS[key]
        if key.isupper():
            # Signals (X, Y, H) are assumed complex
            obj = IndexedBase(key, complex=True)
        else:
            # Indices and time/freq variables (n, k, t, f) are real
            obj = Symbol(key, real=True)
        self[key] = obj
        return obj

class SimplifierEngine:
    def __init__(self):
        pass

    def get_ast_tree(self, expr):
        """Converts SymPy expr into a recursive dict structure for graph visualization."""
        name_map = {
            "Add": "+", "Mul": "*", "Pow": "^", "exp": "exp",
            "Integral": "∫", "Sum": "Σ", "Symbol": str(expr), 
            "Integer": str(expr), "Float": str(expr), 
            "ImaginaryUnit": "i", "Pi": "π", "Indexed": "[]",
            "IndexedBase": str(expr),
            "Half": "1/2", "NegativeOne": "-1"
        }
        
        class_name = expr.__class__.__name__
        display_name = name_map.get(class_name, class_name)
        
        # Override for specific atoms
        if expr == I: display_name = "i"
        elif expr == pi: display_name = "π"
        elif expr.is_Symbol or expr.is_Integer or expr.is_Float:
            display_name = str(expr)

        if not expr.args:
            return {"name": display_name, "type": "atom", "children": []}
        
        tree = {
            "name": display_name,
            "type": "operator",
            "children": [self.get_ast_tree(arg) for arg in expr.args]
        }
        return tree

    def to_verilog(self, expr):
        """Simple conversion to Verilog module/assignment with Real/Imag separation."""
        from sympy import Symbol, Integer, Float, Indexed, Add, Mul, Pow, I, pi, IndexedBase, re, im
        
        def _fmt(e):
            if e == I: return "imag_i"
            if e == pi: return "32'd103993" 
            if isinstance(e, Symbol): return str(e)
            if isinstance(e, (Integer, Float)): return str(int(float(e)*1024))
            
            if isinstance(e, Indexed):
                base = str(e.base)
                idx = _fmt(e.indices[0])
                # We expect the caller to distinguish re/im
                return f"{base}[{idx}]"
            
            if e.__class__.__name__ == "re":
                content = _fmt(e.args[0])
                if "[" in content: return f"{content}_re"
                # If SymPy returns re(X) and X is an IndexedBase, we should return X_re
                if isinstance(e.args[0], IndexedBase): return f"{str(e.args[0])}_re"
                return content
            if e.__class__.__name__ == "im":
                content = _fmt(e.args[0])
                if "[" in content: return f"{content}_im"
                if isinstance(e.args[0], IndexedBase): return f"{str(e.args[0])}_im"
                return "32'b0"

            if isinstance(e, Add):
                return " + ".join([f"({_fmt(a)})" for a in e.args])
            if isinstance(e, Mul):
                return " * ".join([f"({_fmt(a)})" for a in e.args])
            return f"/* {e.__class__.__name__} */"

        symbols = [s for s in expr.free_symbols if isinstance(s, Symbol)]
        indexed_bases = [s for s in expr.free_symbols if isinstance(s, IndexedBase)]
        
        input_list = ["input clk", "input reset"]
        for s in symbols:
            if not str(s).isupper():
                input_list.append(f"input [15:0] {s}")
        for b in indexed_bases:
            input_list.append(f"input [15:0] {b}_re [0:1023]")
            input_list.append(f"input [15:0] {b}_im [0:1023]")
        
        expr_re = re(expr)
        expr_im = im(expr)
        
        v_inputs_str = ",\n    ".join(input_list)
        
        verilog_code = f"""// Auto-generated Verilog component
module signal_processor (
    {v_inputs_str},
    output [31:0] out_re,
    output [31:0] out_im
);
    // Computation logic mirrored from AST
    assign out_re = {_fmt(expr_re)}; 
    assign out_im = {_fmt(expr_im)}; 

endmodule
"""
        return verilog_code

    def to_systemverilog(self, expr, fractional_bits=10):
        """Generates modern SystemVerilog with configurable fixed-point precision."""
        from sympy import Symbol, Integer, Float, Indexed, Add, Mul, Pow, I, pi, IndexedBase
        
        # Scaling factor: 2^fractional_bits
        scale = 2**fractional_bits
        
        def _fmt(e):
            if e == I: 
                val = int(1.0 * scale)
                return f"16'sh{val:04x} /* 1.0 @ Q{fractional_bits} */"
            if e == pi: 
                val = int(float(pi) * scale)
                return f"16'sh{val:04x} /* pi @ Q{fractional_bits} */"
            
            if isinstance(e, Symbol): return str(e)
            if isinstance(e, (Integer, Float)): 
                val = int(float(e) * scale)
                return f"16'sd{val}" 
            
            if isinstance(e, Indexed):
                return f"{_fmt(e.base)}[{_fmt(e.indices[0])}]"
            if isinstance(e, IndexedBase):
                return str(e)
            
            if e.__class__.__name__ == "exp":
                return f"exp_lookup({_fmt(e.args[0])})"
            
            if e.__class__.__name__ == "re":
                # Check if it's an Indexed variable that we can access .re
                content = _fmt(e.args[0])
                if "[" in content: return f"{content}.re"
                if isinstance(e.args[0], IndexedBase): return f"{str(e.args[0])}.re"
                return content
            
            if e.__class__.__name__ == "im":
                content = _fmt(e.args[0])
                if "[" in content: return f"{content}.im"
                if isinstance(e.args[0], IndexedBase): return f"{str(e.args[0])}.im"
                return "16'b0"
            
            if isinstance(e, Add):
                return " + ".join([f"({_fmt(a)})" for a in e.args])
            if isinstance(e, Mul):
                return " * ".join([f"({_fmt(a)})" for a in e.args])
            
            return f"{e.__class__.__name__}_op"

        symbols = [s for s in expr.free_symbols if isinstance(s, Symbol)]
        indexed_bases = [s for s in expr.free_symbols if isinstance(s, IndexedBase)]
        
        input_list = ["input logic clk", "input logic rst_n"]
        for s in symbols:
            if not str(s).isupper():
                input_list.append(f"input logic [15:0] {s}")
        for b in indexed_bases:
            input_list.append(f"input complex_t {b} [1024]")
        
        inputs_str = ",\n    ".join(input_list)
        
        # Split expression into Real and Imaginary parts for hardware
        from sympy import re, im
        expr_re = re(expr)
        expr_im = im(expr)

        # Basic complexity count based on AST
        ops = str(expr).count('+') + str(expr).count('*') + str(expr).count('exp')
        
        sv_code = f"""// Auto-generated SystemVerilog Component
// Optimized for DSP arithmetic
// Hardware Complexity Audit: ~{ops} operations detected

package dsp_pkg;
    typedef struct packed {{
        logic signed [15:0] re;
        logic signed [15:0] im;
    }} complex_t;
endpackage

import dsp_pkg::*;

module signal_processor (
    {inputs_str},
    output complex_t out
);
    
    // Internal computation logic
    // Simplified Formula: {expr}
    
    always_comb begin
        out.re = {_fmt(expr_re)}; 
        out.im = {_fmt(expr_im)}; 
    end

endmodule
"""
        return sv_code

    def apply_rules(self, expr):
        # Rule 0: Evaluate identities (exp(i*pi) -> -1)
        # We skip Sum/Integral here to preserve their step-by-step reduction in Rule 2
        if not isinstance(expr, (Integral, Sum)):
            try:
                evaluated = expr.doit()
                if evaluated != expr:
                    return evaluated, "Evaluated identities / functions"
            except:
                pass

        # Rule 1: Combine exponentials
        combined = powsimp(expr, combine='exp')
        if combined != expr:
             return combined, "Combined exponentials / powers"

        # Rule 2: Integral/Sum Evaluation
        if isinstance(expr, (Integral, Sum)):
            res = expr.doit()
            if res != expr:
                if isinstance(expr, Integral) and ("sqrt(pi)" in str(res) or "erf" in str(res)):
                    return res, "Gaussian: Evaluated standard integral"
                return res, f"Evaluated {expr.__class__.__name__.lower()}"

        # Rule 3: Factor
        factored = factor(expr)
        if factored != expr:
             return factored, "Factored expression"

        # Rule 4: Expand
        expanded = expand(expr)
        if expanded != expr:
             return expanded, "Expanded expression"

        return None, None

    def simplify_full(self, expr_str, fractional_bits=10):
        try:
            # Pre-process: replace 'j' (engineering imaginary) with 'I' (SymPy imaginary)
            # But only standalone 'j', not inside words like 'conj'
            import re
            clean_str = re.sub(r'\bj\b', 'I', expr_str)
            # Also support ^ as power via convert_xor
            
            local_dict = SignalSymbolDict()
            from sympy.parsing.sympy_parser import auto_symbol
            # Add index_transformation to handle x[n] and X[k]
            # Add implicit_multiplication_application for 2pi, j2pi, etc.
            transformations = tuple(t for t in standard_transformations if t != auto_symbol) + \
                              (implicit_multiplication_application, index_transformation, convert_xor)
            
            expr = parse_expr(clean_str, local_dict=local_dict,
                             transformations=transformations,
                             evaluate=False)
        except Exception as e:
            return {"error": f"Parsing error: {str(e)}. Use Python math syntax (e.g. Sum(X[k]*exp(i*k), (k, 0, N-1)))"}

        steps = []
        current_expr = expr
        seen = {current_expr}
        
        steps.append({
            "expression": latex(current_expr),
            "rule": "Initial Expression",
            "tree": self.get_ast_tree(current_expr)
        })

        insight = None
        s = str(expr).lower()
        if "exp" in s:
            if "u" in s and "x" in s and "xi" in s:
                insight = "Detected: Multiplication in frequency domain corresponds to Convolution in time domain."
            elif "j" in s or "i" in s:
                if "pi" in s:
                    insight = "Insight: Complex exponentials with π terms often represent phase rotations or periodic signals."
                else:
                    insight = "Insight: Euler's formula can be used to convert between complex exponentials and trigonometric forms."
        elif "sum" in s and "exp" in s:
            insight = "Detected: This structure looks like a Discrete Fourier Transform (DFT) or a periodic series."
        elif "integral" in s and "exp" in s:
            insight = "Detected: This structure follows the form of a Continuous-Time Fourier Transform (CTFT)."
        elif "conjugate" in s or "conj" in s:
            insight = "Tip: Conjugation in the frequency domain usually corresponds to time reversal in the time domain."
        elif "abs" in s and ("exp" in s or "i" in s):
            insight = "Analysis: Taking the absolute value of a complex signal removes phase information, showing the magnitude spectrum."

        max_steps = 10
        for _ in range(max_steps):
            new_expr, rule = self.apply_rules(current_expr)
            if new_expr is None or new_expr in seen:
                break
            current_expr = new_expr
            seen.add(current_expr)
            steps.append({
                "expression": latex(current_expr),
                "rule": rule,
                "tree": self.get_ast_tree(current_expr)
            })

        return {
            "steps": steps,
            "final_latex": latex(current_expr),
            "final_str": str(current_expr),
            "final_verilog": self.to_verilog(current_expr),
            "final_sv": self.to_systemverilog(current_expr, fractional_bits),
            "insight": insight
        }

if __name__ == "__main__":
    engine = SimplifierEngine()
    print(engine.simplify_full("exp(-u**2*t + i*u*x - i*u*xi)")["steps"])
