import os
import logging
import re
import ast
import readline
from flask import Flask, request, jsonify, render_template

# ---- Logging Setup ----
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "uasc_assistant.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='a'
)

def flush_logs():
    """Ensures logs are written to disk immediately."""
    for handler in logging.getLogger().handlers:
        handler.flush()

# ---- Knowledge Graph ----
# Maps Python functions to their most commonly associated patterns
knowledge_graph = {
    "open": ["os.path.exists", "with open()", "read", "write"],
    "list": ["append", "sort", "reverse", "extend"],
    "dict": ["keys()", "values()", "items()", "update()"],
    "import os": ["os.path.join", "os.remove", "os.getcwd"],
    "requests.get": ["json.loads", "requests.post", "try/except"],
    "numpy array": ["np.array", "np.zeros", "np.ones", "np.reshape"],
    "pandas": ["pd.DataFrame", "pd.read_csv", "df.head()", "df.describe()"],
    "file handling": ["open", "os.path.exists", "os.path.join", "with open()"],
    "error handling": ["try/except", "except Exception as e", "finally", "raise"],
    "string manipulation": ["split()", "join()", "replace()", "strip()"],
    "print": ["f-strings", "format()", "str()"],
    "os.path": ["os.path.join", "os.path.exists", "os.path.dirname"],
    "math": ["math.sqrt", "math.pi", "math.floor", "math.ceil"],
    "random": ["random.choice", "random.randint", "random.shuffle"],
    "datetime": ["datetime.now()", "datetime.strftime", "datetime.strptime"],
    "json": ["json.loads", "json.dumps", "with open() as f"],
    "plot": ["matplotlib.pyplot", "plt.figure", "plt.plot", "plt.show"]
}

# ---- Extended knowledge patterns ----
# Associates code patterns with example implementations
code_patterns = {
    "file reading": """
# Example file reading pattern
with open('filename.txt', 'r') as file:
    content = file.read()
    lines = content.split('\\n')
""",
    "csv handling": """
# Example CSV handling with pandas
import pandas as pd
df = pd.read_csv('data.csv')
result = df.groupby('column').mean()
""",
    "web request": """
# Example web request pattern
import requests
response = requests.get('https://api.example.com/data')
data = response.json()
""",
    "error handling": """
# Example error handling pattern
try:
    result = risky_operation()
except Exception as e:
    print(f"Error occurred: {e}")
finally:
    cleanup_resources()
"""
}

# ---- UASC-M2M Integration ----
class UASCM2M:
    def decode_glyph(self, glyph_code):
        """Decodes glyphs into executable steps with validation."""
        logging.info(f"Decoding glyph: {glyph_code}")
        flush_logs()
        
        # For this version, we'll use the glyph code as an executable step
        return [glyph_code]

    def _validate_step(self, step):
        """Ensures decoded steps contain only allowed operations."""
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

# ---- AI Assistant Functions ----
def get_suggestions(input_text):
    """Get AI-powered suggestions based on user input."""
    suggestions = []
    
    # Check for direct matches in knowledge graph
    for key in knowledge_graph:
        if input_text.lower() in key.lower():
            suggestions.extend(knowledge_graph[key])
    
    # Check for code pattern matches
    for pattern in code_patterns:
        if input_text.lower() in pattern.lower():
            suggestions.append(f"Code Pattern: {pattern}")
    
    # If we found direct matches, return them
    if suggestions:
        return suggestions
    
    # If no direct matches, try to find related concepts
    for key in knowledge_graph:
        for value in knowledge_graph[key]:
            if input_text.lower() in value.lower():
                suggestions.append(key)
                suggestions.extend([v for v in knowledge_graph[key] if v != value])
    
    return suggestions

def get_code_example(pattern):
    """Get example code for a specific pattern."""
    if pattern in code_patterns:
        return code_patterns[pattern]
    return None

def execute_glyph(glyph_code):
    """Safely executes UASC-M2M glyphs and returns the output."""
    logging.info(f"Received glyph: {glyph_code}")
    flush_logs()
    
    try:
        # Syntax validation using regex
        if not re.fullmatch(r'^[a-zA-Z0-9_+\-*/=\s().\'\"[\],:]+$', glyph_code):
            raise ValueError("Invalid glyph syntax")
        
        # Get execution steps from the glyph decoder
        execution_steps = uasc.decode_glyph(glyph_code)
        
        output = []
        for step in execution_steps:
            # Validate the step before execution
            uasc._validate_step(step)
            
            logging.info(f"[🔄] Executing: {step}")
            
            # Custom print function to capture output
            def custom_print(*args, **kwargs):
                message = " ".join(str(arg) for arg in args)
                output.append(message)
            
            # Create a restricted execution environment
            safe_globals = {
                "__builtins__": {
                    "print": custom_print,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "range": range,
                    "enumerate": enumerate,
                    "zip": zip,
                    "map": map,
                    "filter": filter,
                    "sum": sum,
                    "min": min,
                    "max": max,
                    "sorted": sorted,
                    "any": any,
                    "all": all,
                    "round": round
                }
            }
            
            # Execute the step in the restricted environment
            exec(step, safe_globals)
        
        return {"success": True, "output": output}
            
    except Exception as e:
        logging.error(f"[❌] Execution failed: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        flush_logs()

# ---- CLI Interface ----
def completer(text, state):
    """Auto-complete function for user input."""
    options = []
    
    # Add all knowledge graph keys that match the text
    options.extend([cmd for cmd in knowledge_graph.keys() if cmd.lower().startswith(text.lower())])
    
    # Add all pattern names that match the text
    options.extend([pattern for pattern in code_patterns.keys() if pattern.lower().startswith(text.lower())])
    
    # Add common Python functions and keywords for autocompletion
    python_keywords = [
        "def", "class", "import", "from", "return", "if", "else", "elif", 
        "for", "while", "try", "except", "finally", "with", "as", "and", 
        "or", "not", "in", "is", "None", "True", "False", "print", "input"
    ]
    options.extend([kw for kw in python_keywords if kw.lower().startswith(text.lower())])
    
    return options[state] if state < len(options) else None

# ---- Flask Web API Setup ----
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/execute", methods=["POST"])
def api_execute():
    """API endpoint to execute UASC-M2M glyphs."""
    data = request.json
    glyph_code = data.get("glyph", "")
    
    if not glyph_code:
        return jsonify({"success": False, "error": "No glyph provided"})
    
    result = execute_glyph(glyph_code)
    return jsonify(result)

@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    """API endpoint to get AI suggestions."""
    data = request.json
    input_text = data.get("input", "")
    
    if not input_text:
        return jsonify({"success": False, "error": "No input provided"})
    
    suggestions = get_suggestions(input_text)
    return jsonify({"success": True, "suggestions": suggestions})

@app.route("/api/example", methods=["POST"])
def api_example():
    """API endpoint to get code examples."""
    data = request.json
    pattern = data.get("pattern", "")
    
    if not pattern:
        return jsonify({"success": False, "error": "No pattern provided"})
    
    example = get_code_example(pattern)
    if example:
        return jsonify({"success": True, "example": example})
    else:
        return jsonify({"success": False, "error": "Pattern not found"})

# Create a templates directory and an index.html file with a simple UI
os.makedirs("templates", exist_ok=True)
with open("templates/index.html", "w") as f:
    f.write("""<!DOCTYPE html>
<html>
<head>
    <title>UASC-M2M AI Assistant</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            display: flex;
            gap: 20px;
        }
        .input-section, .output-section {
            flex: 1;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        h2 {
            color: #444;
            margin-top: 20px;
        }
        textarea {
            width: 100%;
            height: 150px;
            padding: 10px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-family: monospace;
        }
        #output, #suggestions {
            background-color: #f0f0f0;
            padding: 10px;
            border: 1px solid #ccc;
            min-height: 100px;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
        }
        button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
            font-weight: bold;
        }
        button:hover {
            background-color: #45a049;
        }
        .suggestion-item {
            margin: 5px 0;
            padding: 5px;
            background-color: #e7f3ff;
            border-radius: 4px;
            cursor: pointer;
        }
        .suggestion-item:hover {
            background-color: #d0e7ff;
        }
        #exampleCode {
            background-color: #f0f0f0;
            padding: 10px;
            border: 1px solid #ccc;
            min-height: 100px;
            max-height: 200px;
            overflow-y: auto;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre;
            margin-top: 10px;
            display: none;
        }
        .actions {
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <h1>UASC-M2M AI Assistant</h1>
    
    <div class="container">
        <div class="input-section">
            <h2>Input</h2>
            <textarea id="glyphCode" placeholder="Enter your Python code or type a concept for suggestions..." oninput="getSuggestions()">print("Hello from UASC-M2M AI Assistant!")</textarea>
            
            <div class="actions">
                <button onclick="executeGlyph()">Execute Code</button>
                <button onclick="getSuggestions()">Get Suggestions</button>
            </div>
            
            <h2>AI Suggestions</h2>
            <div id="suggestions">Type in the input box to get AI suggestions...</div>
            
            <div id="exampleCode"></div>
        </div>
        
        <div class="output-section">
            <h2>Execution Output</h2>
            <div id="output">Output will appear here...</div>
        </div>
    </div>

    <script>
        async function executeGlyph() {
            const glyphCode = document.getElementById('glyphCode').value;
            const outputDiv = document.getElementById('output');
            
            outputDiv.innerHTML = "Executing...";
            
            try {
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ glyph: glyphCode })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    outputDiv.innerHTML = result.output.join('\\n') || "Execution successful (no output)";
                } else {
                    outputDiv.innerHTML = `Error: ${result.error}`;
                }
            } catch (error) {
                outputDiv.innerHTML = `Error: ${error.message}`;
            }
        }
        
        async function getSuggestions() {
            const inputText = document.getElementById('glyphCode').value;
            const suggestionsDiv = document.getElementById('suggestions');
            
            // Skip if input is too short
            if (inputText.length < 2) {
                suggestionsDiv.innerHTML = "Type more to get suggestions...";
                return;
            }
            
            try {
                const response = await fetch('/api/suggest', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ input: inputText })
                });
                
                const result = await response.json();
                
                if (result.success && result.suggestions.length > 0) {
                    suggestionsDiv.innerHTML = "";
                    
                    result.suggestions.forEach(suggestion => {
                        const suggestionItem = document.createElement('div');
                        suggestionItem.className = 'suggestion-item';
                        suggestionItem.textContent = suggestion;
                        suggestionItem.onclick = function() {
                            if (suggestion.startsWith("Code Pattern: ")) {
                                getCodeExample(suggestion.replace("Code Pattern: ", ""));
                            } else {
                                insertSuggestion(suggestion);
                            }
                        };
                        suggestionsDiv.appendChild(suggestionItem);
                    });
                } else {
                    suggestionsDiv.innerHTML = "No suggestions found for this input.";
                }
            } catch (error) {
                suggestionsDiv.innerHTML = `Error getting suggestions: ${error.message}`;
            }
        }
        
        function insertSuggestion(suggestion) {
            const codeArea = document.getElementById('glyphCode');
            codeArea.value += "\\n" + suggestion;
        }
        
        async function getCodeExample(pattern) {
            const exampleDiv = document.getElementById('exampleCode');
            
            try {
                const response = await fetch('/api/example', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ pattern: pattern })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    exampleDiv.textContent = result.example;
                    exampleDiv.style.display = 'block';
                } else {
                    exampleDiv.textContent = `Error: ${result.error}`;
                    exampleDiv.style.display = 'block';
                }
            } catch (error) {
                exampleDiv.textContent = `Error getting example: ${error.message}`;
                exampleDiv.style.display = 'block';
            }
        }
    </script>
</body>
</html>""")

# ---- Run CLI or Web Interface ----
def run_cli():
    """Run the interactive CLI interface."""
    print("\nUASC-M2M AI Assistant CLI")
    print("==========================")
    print("Type 'help' for commands, 'exit' to quit, or '?' for assistance.")
    print("Press TAB for autocomplete.")
    
    # Set up tab completion
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    
    while True:
        try:
            user_input = input("\n>> ")
            
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
                
            elif user_input.lower() == 'help':
                print("\nCommands:")
                print("  exit - Exit the program")
                print("  help - Show this help message")
                print("  ? - Get AI assistance")
                print("  [python code] - Execute Python code")
                
            elif user_input.startswith('?'):
                query = user_input[1:].strip()
                suggestions = get_suggestions(query if query else "python")
                
                print("\n🔮 AI Suggestions:")
                for suggestion in suggestions:
                    print(f"  - {suggestion}")
                    
            elif user_input.strip():
                # Execute as Python code
                result = execute_glyph(user_input)
                
                if result["success"]:
                    if result["output"]:
                        for line in result["output"]:
                            print(line)
                    else:
                        print("(No output)")
                else:
                    print(f"Error: {result['error']}")
                    
                    # Provide helpful suggestions if there's an error
                    print("\n🔮 AI Suggestions:")
                    suggestions = get_suggestions(user_input.split()[0] if user_input.split() else "error")
                    for suggestion in suggestions[:3]:
                        print(f"  - {suggestion}")
                
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
        except Exception as e:
            print(f"\nError: {str(e)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        run_cli()
    else:
        print("Starting web interface. For CLI mode, run with --cli")
        app.run(debug=True)
