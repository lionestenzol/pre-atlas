"""
Verification engine — runs Python and C++ code, compares outputs.
Proves that the conversion produced equivalent behavior.
"""

import subprocess
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class VerificationResult:
    match: bool
    python_output: str
    cpp_output: str
    python_error: str = ""
    cpp_error: str = ""
    cpp_compile_error: str = ""
    status: str = "success"  # success, python_error, cpp_compile_error, cpp_runtime_error, mismatch


TIMEOUT_SECONDS = 10


def run_python(code: str) -> tuple[str, str]:
    """Execute Python code and return (stdout, stderr)."""
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "Timeout: execution exceeded 10 seconds"
    except FileNotFoundError:
        return "", "Python not found on PATH"


def run_cpp(code: str) -> tuple[str, str, str]:
    """Compile and run C++ code. Returns (stdout, stderr, compile_error)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "verify.cpp")
        exe_path = os.path.join(tmpdir, "verify.exe")

        with open(src_path, "w") as f:
            f.write(code)

        try:
            compile_result = subprocess.run(
                ["g++", "-std=c++20", "-o", exe_path, src_path],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return "", "", "Compilation timed out"
        except FileNotFoundError:
            return "", "", "g++ not found on PATH. Install MinGW or MSYS2."

        if compile_result.returncode != 0:
            return "", "", compile_result.stderr.strip()

        try:
            run_result = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
            return run_result.stdout.strip(), run_result.stderr.strip(), ""
        except subprocess.TimeoutExpired:
            return "", "Runtime timeout: execution exceeded 10 seconds", ""


def verify(python_code: str, cpp_code: str) -> VerificationResult:
    """Run both Python and C++ code, compare their outputs."""

    py_out, py_err = run_python(python_code)

    if py_err and not py_out:
        return VerificationResult(
            match=False,
            python_output=py_out,
            cpp_output="",
            python_error=py_err,
            status="python_error",
        )

    cpp_out, cpp_err, compile_err = run_cpp(cpp_code)

    if compile_err:
        return VerificationResult(
            match=False,
            python_output=py_out,
            cpp_output="",
            cpp_compile_error=compile_err,
            status="cpp_compile_error",
        )

    if cpp_err and not cpp_out:
        return VerificationResult(
            match=False,
            python_output=py_out,
            cpp_output=cpp_out,
            cpp_error=cpp_err,
            status="cpp_runtime_error",
        )

    # Normalize whitespace for comparison
    py_normalized = "\n".join(line.rstrip() for line in py_out.splitlines())
    cpp_normalized = "\n".join(line.rstrip() for line in cpp_out.splitlines())

    match = py_normalized == cpp_normalized

    return VerificationResult(
        match=match,
        python_output=py_out,
        cpp_output=cpp_out,
        python_error=py_err,
        cpp_error=cpp_err,
        status="success" if match else "mismatch",
    )


if __name__ == "__main__":
    py = "for i in range(5):\n    print(i)"
    cpp = '''#include <iostream>
using namespace std;

int main() {
    for (int i = 0; i < 5; i++) {
        cout << i << endl;
    }
    return 0;
}'''

    result = verify(py, cpp)
    print(f"Match: {result.match}")
    print(f"Python output:\n{result.python_output}")
    print(f"C++ output:\n{result.cpp_output}")
    if result.cpp_compile_error:
        print(f"Compile error:\n{result.cpp_compile_error}")
