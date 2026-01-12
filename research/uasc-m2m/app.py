import os
import logging
import re
import ast  # For safer code validation
from flask import Flask, request, jsonify
import subprocess  # Use subprocess instead of Pyodide for server-side execution

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

# ---- Flask Web API Setup ----
app = Flask(__name__)

# ---- Python Execution via Subprocess ----
@app.route("/execute", methods=["POST"])
def execute_code():
    data = request.json
    code = data.get("code", "")
    
    logging.info(f"Executing Code: {code}")
    flush_logs()
    
    try:
        # Validate code safety
        ast.parse(code)  # This will raise an exception for syntax errors
        
        # Write code to a temporary file
        temp_file = "temp_execution.py"
        with open(temp_file, "w") as f:
            f.write(code)
        
        # Execute the code in a subprocess
        result = subprocess.run(
            ["python", temp_file], 
            capture_output=True,
            text=True,
            timeout=5  # Timeout after 5 seconds
        )
        
        if result.returncode == 0:
            output = result.stdout
            response = {"output": output}
        else:
            response = {"error": result.stderr}
            
    except SyntaxError as e:
        logging.error(f"Syntax error: {str(e)}")
        response = {"error": f"Syntax error: {str(e)}"}
    except subprocess.TimeoutExpired:
        logging.error("Execution timed out")
        response = {"error": "Execution timed out (5 seconds limit)"}
    except Exception as e:
        logging.error(f"Execution failed: {str(e)}")
        response = {"error": str(e)}
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        flush_logs()
    
    return jsonify(response)

# ---- Run Web App ----
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)