"""
Code to Numeric Logic — API Server
FastAPI server exposing conversion + verification endpoints.
"""

import json
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from converter import convert_python_to_cpp
from verifier import verify


app = FastAPI(title="Code to Numeric Logic", version="0.1.0")

PATTERNS_PATH = Path(__file__).parent / "patterns.json"
STATIC_DIR = Path(__file__).parent / "static"
INDEX_PATH = Path(__file__).parent / "index.html"


class ConvertRequest(BaseModel):
    python_code: str


class ConvertResponse(BaseModel):
    cpp_code: str
    patterns_used: list[str]
    warnings: list[str]
    headers: list[str]
    verification: dict | None = None


@app.get("/")
async def serve_index():
    return FileResponse(INDEX_PATH)


@app.post("/convert", response_model=ConvertResponse)
async def convert(req: ConvertRequest):
    if not req.python_code.strip():
        raise HTTPException(400, "Empty Python code")

    if len(req.python_code) > 50_000:
        raise HTTPException(400, "Code too large (max 50KB)")

    result = convert_python_to_cpp(req.python_code)

    v = verify(req.python_code, result["cpp_code"])
    verification = {
        "match": v.match,
        "status": v.status,
        "python_output": v.python_output,
        "cpp_output": v.cpp_output,
        "python_error": v.python_error,
        "cpp_error": v.cpp_error,
        "cpp_compile_error": v.cpp_compile_error,
    }

    return ConvertResponse(
        cpp_code=result["cpp_code"],
        patterns_used=result["patterns_used"],
        warnings=result["warnings"],
        headers=result["headers"],
        verification=verification,
    )


@app.get("/patterns")
async def get_patterns():
    with open(PATTERNS_PATH) as f:
        return json.load(f)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "code-converter", "version": "0.1.0"}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3007)
