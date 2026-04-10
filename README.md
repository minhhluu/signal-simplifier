# Signal Simplifier

A rule-based mathematical reduction tool tailored for **Signals & Systems** theory. Verify complex DSP formulas, audit computational complexity via AST graphs, and generate precise SystemVerilog and Verilog hardware modules from symbolic mathematical inputs.

## Features

- **Symbolic Reduction Engine**: Parses complex mathematical expressions (including sums, integrals, and advanced primitives like `Piecewise`, `DiracDelta`, `limit`) and simplifies them step-by-step.
- **Hardware Code Generation**: Converts mathematically reduced AST paths into optimized `Verilog` and `SystemVerilog` modules using configurable Q-format fixed-point precision.
- **AST Visualization**: Interactive node-based graph rendering for visually auditing the operation paths and complexity of the signal processing functions.
- **Advanced Stability Fuzzing**: Built-in AST parallel fuzzing framework with numeric equivalence checking to validate SystemVerilog mathematical parity.

## Quick Start

This project uses a unified bash script to manage both the FastAPI backend and the Vite/React frontend.

### 1. Start the Application
```bash
./script.sh start
```
*   **Web UI**: [http://localhost:3000](http://localhost:3000)
    *   **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Stop the Application
```bash
./script.sh stop
```

### 3. Check Service Status
```bash
./script.sh status
```

## How to Use the UI

1.  **Input**: Type your mathematical expression in the left text area. 
    *   **Syntax**: Use standard **Python/SymPy syntax**.
    *   **Imaginary Unit**: Supported as either `i` or `j`.
    *   **Variables**: Uppercase letters define `complex` variables; lowercase define `real` variables.
    *   **Example (DFT)**: `Sum(X[k] * exp(j*2*pi*k*n/N), (k, 0, N-1)) / N`
2.  **Solve**: Click **Solve Steps**.
3.  **Analysis**:
    *   **Reduction Path**: The middle column lists the exact algorithmic simplifications performed (e.g., "Gaussian Integral recognized").
    *   **AST & Hardware Export**: The right column contains tabs to view the `AST Graph`, generate synthesized `Verilog`, or heavily-typed `SystemVerilog`. Drag the bottom-right corner of the code blocks to expand them for reading complex outputs.

## Supported Primitives

| Symbol / Function | Description |
| :--- | :--- |
| `i`, `j` | Imaginary Unit |
| `pi` | Pi constant |
| `exp(x)` | Exponential Function |
| `Integral(f, x)` | Integrals |
| `Sum(f, (k, a, b))`| Summation over range |
| `Piecewise(...)` | Conditional logic mapping |
| `DiracDelta(x)` | Mathematical impulse |

## Project Structure

- `/backend`: Core Python engine containing AST parsing (`engine.py`) and FastAPI server logic (`main.py`).
- `/fuzz_testing`: Professional-grade equivalence and stress testing suite for RTL verification.
- `/frontend`: React client with `Cytoscape` for graph rendering and Vite for HMR.
- `/script.sh`: Main service execution manager.

## Troubleshooting

- **Frontend Connectivity Issues**: Verify port 3000 operations in `frontend/frontend.log`.
- **Backend Crashes**: Check `backend/backend.log`. Ensure the virtual environment handles SymPy accurately.
- **Port Conflicts**: Run `./script.sh stop` twice consecutively to ensure any orphaned background tasks on ports 3000 and 8000 are killed.