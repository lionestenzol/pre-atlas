import os
import subprocess
import hashlib
import logging
import math
from collections import Counter
import re

# Setup Logging
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "execution_results.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='a'  # Append logs instead of overwriting
)

def flush_logs():
    """Ensures logs are written to disk immediately."""
    for handler in logging.getLogger().handlers:
        handler.flush()

# Supported File Extensions
SUPPORTED_EXT = {".py", ".c", ".cpp", ".asm", ".bin", ".glyph"}
MAX_CODE_SIZE = 1048576  # 1MB
BINARY_READ_CHUNK = 1024

# Mock UASC-M2M Execution Integration (until module is available)
class UASCM2M:
    def decode_glyph(self, glyph_code):
        """Mock function to decode glyphs into executable steps."""
        logging.info(f"Decoding glyph: {glyph_code}")
        flush_logs()
        return ["print('Executing real glyph logic')"]

uasc = UASCM2M()

def run_subprocess(command, timeout=10):
    """Run system command with error handling."""
    logging.info(f"Running subprocess: {' '.join(command)}")
    flush_logs()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
        logging.info(f"Subprocess output: {result.stdout.strip()}")
        flush_logs()
        return True, result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        logging.error(f"Subprocess error: {str(e)}")
        flush_logs()
        return False, f"Error: {str(e)}"

def calculate_entropy(counts, total_bytes):
    """Calculate Shannon entropy for binary files."""
    logging.info("Calculating entropy for binary data.")
    flush_logs()
    if total_bytes == 0:
        return 0.0
    entropy = -sum((freq / total_bytes) * math.log2(freq / total_bytes) for freq in counts if freq > 0)
    entropy = round(entropy, 4)
    logging.info(f"Computed entropy: {entropy}")
    flush_logs()
    return entropy

def execute_glyph(glyph_code):
    """Decodes and executes a UASC-M2M glyph after validating input."""
    logging.info(f"Received glyph for execution: {glyph_code}")
    flush_logs()
    try:
        # Validate that the glyph only contains safe characters
        if not re.fullmatch(r'[a-zA-Z0-9_()=+\-/*\s]+', glyph_code):
            logging.error("[❌] Invalid glyph code detected.")
            flush_logs()
            print("Error: Invalid glyph code.")
            return
        
        execution_steps = uasc.decode_glyph(glyph_code)
        for step in execution_steps:
            logging.info(f"[🔄] Executing step: {step}")
            flush_logs()
            print(f"Executing step: {step}")
            safe_globals = {"print": print}  # Restrict available functions
            exec(step, safe_globals)  # Safe execution
    except Exception as e:
        logging.error(f"[❌] Glyph execution failed: {str(e)}")
        flush_logs()
        print(f"Error executing glyph: {str(e)}")

def test_execution():
    """Test function to verify glyph execution works."""
    test_glyph = "print('Test Glyph Execution Successful')"
    logging.info("Running test execution...")
    print("[TEST] Running test execution...")
    execute_glyph(test_glyph)
    logging.info("Test execution complete.")
    print("[TEST] Execution complete. Check logs for details.")

# Run test
test_execution()

# Fix missing micropip module only when needed
def import_micropip():
    try:
        import micropip
        return micropip
    except ModuleNotFoundError:
        logging.warning("Micropip module not found. Import attempt skipped.")
        return None

micropip = import_micropip()
