from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from engine import SimplifierEngine
import uvicorn
import sys
import os
import time

# Add root to path to import fuzz_testing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SimplifierEngine()

class SimplifyRequest(BaseModel):
    expression: str
    fractional_bits: int = 10

@app.post("/simplify")
async def simplify_expression(request: SimplifyRequest):
    try:
        result = engine.simplify_full(request.expression, request.fractional_bits)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fuzz")
async def run_fuzzing():
    try:
        from fuzz_testing import fuzzer
        # Run the advanced fuzz test with fewer iterations for the UI responsiveness
        # The new fuzzer returns a complex dict
        report = fuzzer.fuzz_test(num_tests=10, base_seed=int(time.time()), workers=2, verbose=False)
        
        # Format the report for the existing UI expectations or return full report
        return {
            "success_rate": f"{(report['stats']['PASS']/report['stats']['total'])*100:.1f}%",
            "iterations": report['stats']['total'],
            "details": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
