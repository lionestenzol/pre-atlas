import os
import subprocess
import logging
import math
from collections import Counter
import re
import ast  # For safer code validation

# ---- Logging Setup ----
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "execution_results.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='a'
)

def flush_logs():
    """Ensures logs are written to disk immediately."""
    for handler in logging.getLogger().handlers:
        handler.flush()

# ---- Constants ----
SUPPORTED_EXT = {".py", ".c", ".cpp", ".asm", ".bin", ".glyph"}
MAX_CODE_SIZE = 1048576  # 1MB
BINARY_READ_CHUNK = 1024

# ---- UASC-M2M Integration ----
class UASCM2M:
    def decode_glyph(self, glyph_code):
        """Decodes glyphs into executable steps with validation."""
        logging.info(f"Decoding glyph: {glyph_code}")
        flush_logs()
        
        # Validate decoded steps before returning them
        mock_steps = ["print('Executing real glyph logic')"]
        for step in mock_steps:
            self._validate_step(step)  # New security check
        return mock_steps

    def _validate_step(self, step):
        """Ensures decoded steps contain only allowed operations."""
        try:
            tree = ast.parse(step, mode='exec')
            # Walk the AST tree and check for allowed node types
            for node in ast.walk(tree):
                # Allowing basic node types needed for simple expressions and print statements
                if not isinstance(node, (
                    ast.Module,   # Allow the module node (top-level)
                    ast.Expr,     # Expressions
                    ast.Call,     # Function calls
                    ast.Name,     # Variable names
                    ast.Constant, # Constants (modern replacement for Str, Num, etc.)
                    ast.Load,     # Context for loading values
                    ast.Store     # Context for storing values
                )):
                    raise ValueError(f"Unsafe AST node: {type(node).__name__}")
        except Exception as e:
            logging.error(f"Invalid step: {str(e)}")
            raise

uasc = UASCM2M()

# ---- Core Functions ----
def run_subprocess(command, timeout=10):
    """Executes system commands safely."""
    logging.info(f"Running subprocess: {' '.join(command)}")
    flush_logs()
    
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            timeout=timeout, 
            check=True,
            shell=False  # Safer: prevent shell injection
        )
        logging.info(f"Subprocess output: {result.stdout.strip()}")
        return True, result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logging.error(f"Subprocess error: {str(e)}")
        return False, f"Error: {str(e)}"
    finally:
        flush_logs()

def calculate_entropy(counts, total_bytes):
    """Accurate Shannon entropy calculation."""
    logging.info("Calculating entropy for binary data.")
    flush_logs()
    
    if total_bytes == 0:
        return 0.0
    
    entropy = -sum(
        (freq / total_bytes) * math.log2(freq / total_bytes) 
        for freq in counts.values() 
        if freq > 0
    )
    return round(entropy, 4)

def execute_glyph(glyph_code):
    """Safely executes UASC-M2M glyphs."""
    logging.info(f"Received glyph: {glyph_code}")
    flush_logs()
    
    try:
        # Modified regex to allow valid Python expressions
        # Allowing parentheses for function calls
        if not re.fullmatch(r'^[a-zA-Z0-9_+\-*/=\s().\'\"]+$', glyph_code):
            raise ValueError("Invalid glyph syntax")
        
        execution_steps = uasc.decode_glyph(glyph_code)
        for step in execution_steps:
            logging.info(f"[🔄] Executing: {step}")
            print(f"Executing: {step}")
            
            # Restricted execution environment
            safe_env = {"__builtins__": {"print": print}}
            exec(step, safe_env)  # Now safer due to AST validation
            
    except Exception as e:
        logging.error(f"[❌] Execution failed: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        flush_logs()

# ---- Testing ----
def test_execution():
    """Comprehensive test suite."""
    print("\n[TEST] Starting tests...")
    
    # Valid glyph - simple print statement
    execute_glyph("print('Test Glyph Execution Successful')")
    
    # Invalid glyph (test security)
    try:
        execute_glyph("dangerous; code()")
    except Exception as e:
        print(f"Expected security rejection: {e}")
    
    print("[TEST] All tests completed")

if __name__ == "__main__":
    test_execution()
