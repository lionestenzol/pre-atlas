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
        
        # For this test version, we'll use the glyph code as the step directly
        # In a real implementation, this would decode complex glyph logic
        return [glyph_code]  # Return the glyph code as the execution step

    def _validate_step(self, step):
        """Ensures decoded steps contain only allowed operations.
        Checks for potentially dangerous operations."""
        try:
            # Parse the step into an AST
            tree = ast.parse(step, mode='exec')
            
            # Define unsafe operations
            unsafe_operations = {
                'exec', 'eval', 'compile', 'open', 'input', '__import__', 
                'globals', 'locals', 'getattr', 'setattr', 'delattr',
                'subprocess', 'os', 'sys', 'shutil', 'importlib'
            }
            
            # Walk the AST and look for unsafe operations
            for node in ast.walk(tree):
                # Check for calls to dangerous functions
                if isinstance(node, ast.Call) and hasattr(node, 'func'):
                    # Check function name if it's directly called
                    if isinstance(node.func, ast.Name) and node.func.id in unsafe_operations:
                        raise ValueError(f"Unsafe operation: {node.func.id}")
                    
                    # Check for attribute access that might be dangerous
                    if isinstance(node.func, ast.Attribute) and node.func.attr in unsafe_operations:
                        raise ValueError(f"Unsafe attribute: {node.func.attr}")
                
                # Check for import statements
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_name = node.names[0].name if hasattr(node, 'names') else getattr(node, 'module', '')
                    if module_name in unsafe_operations:
                        raise ValueError(f"Unsafe import: {module_name}")
            
            return True
        except Exception as e:
            logging.error(f"Invalid step: {str(e)}")
            raise

# Create an instance of UASCM2M
uasc = UASCM2M()

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
        # More permissive regex for valid Python expressions
        # This allows basic coding constructs while still blocking obviously malicious patterns
        if not re.fullmatch(r'^[a-zA-Z0-9_+\-*/=\s().\'\"]+$', glyph_code):
            raise ValueError("Invalid glyph syntax")
        
        # Get execution steps from the glyph decoder
        execution_steps = uasc.decode_glyph(glyph_code)
        
        for step in execution_steps:
            # Validate the step before execution
            uasc._validate_step(step)
            
            logging.info(f"[🔄] Executing: {step}")
            print(f"Executing: {step}")
            
            # Create a restricted execution environment
            # Only allow access to print function
            safe_globals = {"__builtins__": {"print": print}}
            
            # Execute the step in the restricted environment
            exec(step, safe_globals)
            
    except Exception as e:
        logging.error(f"[❌] Execution failed: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        flush_logs()

# ---- Testing ----
def test_execution():
    """Comprehensive test suite."""
    print("\n[TEST] Starting tests...")
    
    # Test 1: Simple print statement
    print("\nTest 1: Simple print statement")
    execute_glyph("print('Test Glyph Execution Successful')")
    
    # Test 2: Simple arithmetic
    print("\nTest 2: Simple arithmetic")
    execute_glyph("print(123 + 456)")
    
    # Test 3: Invalid syntax (semicolon)
    print("\nTest 3: Invalid syntax (should fail safely)")
    execute_glyph("dangerous; code()")
    
    # Test 4: Attempted unsafe operation
    print("\nTest 4: Attempted unsafe operation (should fail safely)")
    execute_glyph("print(eval('2 + 2'))")
    
    print("\n[TEST] All tests completed")

if __name__ == "__main__":
    test_execution()
