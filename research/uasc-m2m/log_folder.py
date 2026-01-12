import os
import datetime
from pathlib import Path

# Define the directory path (same folder as this script)
BASE = Path(__file__).parent.resolve()
directory_path = str(BASE)

# Define the log file path
log_file = str(BASE / "folder_contents_log.txt")

def log_directory_contents(directory, log_path):
    try:
        # Get the current timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # List all files and directories
        contents = os.listdir(directory)

        # Write to log file
        with open(log_path, "w", encoding="utf-8") as log:
            log.write(f"Directory Log - {timestamp}\n")
            log.write(f"Contents of: {directory}\n")
            log.write("=" * 50 + "\n")
            for item in contents:
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    log.write(f"[DIR]  {item}\n")
                else:
                    log.write(f"[FILE] {item}\n")

        print(f"Log saved to: {log_path}")
    except Exception as e:
        print(f"Error logging directory contents: {e}")

# Run the function
log_directory_contents(directory_path, log_file)
