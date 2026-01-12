#!/usr/bin/env python3
"""
UASC-M2M CLI Client

Send commands to the UASC server with proper authentication.
"""

import argparse
import json
import time
import sys
import os
import urllib.request
import urllib.error

# Add parent to path for auth import
sys.path.insert(0, os.path.dirname(__file__))
from auth import compute_signature


# Default configuration
DEFAULT_SERVER = 'http://localhost:8420'
DEFAULT_CLIENT_ID = 'cli-local'
DEFAULT_SECRET = 'uasc-local-secret'  # Change this!

# Config file path
CONFIG_PATH = os.path.expanduser('~/.uasc/config.json')


def load_config() -> dict:
    """Load configuration from file."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """Save configuration to file."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get_config(args) -> dict:
    """Get merged configuration from file and args."""
    config = load_config()
    return {
        'server': args.server or config.get('server', DEFAULT_SERVER),
        'client_id': args.client or config.get('client_id', DEFAULT_CLIENT_ID),
        'secret': args.secret or config.get('secret', DEFAULT_SECRET)
    }


def make_request(
    method: str,
    url: str,
    body: dict = None,
    client_id: str = None,
    secret: str = None
) -> dict:
    """
    Make authenticated request to UASC server.

    Args:
        method: HTTP method
        url: Full URL
        body: Request body (for POST)
        client_id: Client ID for auth
        secret: Shared secret for signing

    Returns:
        Response as dict
    """
    body_str = json.dumps(body) if body else ''
    timestamp = str(int(time.time()))

    headers = {
        'Content-Type': 'application/json'
    }

    # Add auth headers if credentials provided
    if client_id and secret:
        signature = compute_signature(secret, timestamp, body_str)
        headers.update({
            'X-UASC-Client': client_id,
            'X-UASC-Timestamp': timestamp,
            'X-UASC-Signature': signature
        })

    data = body_str.encode() if body_str else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            return json.loads(error_body)
        except:
            return {'error': error_body, 'status': e.code}
    except urllib.error.URLError as e:
        return {'error': str(e)}


def cmd_exec(args):
    """Execute a command."""
    config = get_config(args)

    # Build request body
    body = {'cmd': args.command}

    # Add any additional inputs
    if args.inputs:
        for inp in args.inputs:
            if '=' in inp:
                key, value = inp.split('=', 1)
                # Try to parse as JSON for complex values
                try:
                    body[key] = json.loads(value)
                except:
                    body[key] = value

    url = f"{config['server']}/exec"

    print(f"Executing: {args.command}")
    print(f"Server: {config['server']}")
    print()

    result = make_request(
        'POST', url, body,
        config['client_id'], config['secret']
    )

    if 'error' in result and result.get('status') == 401:
        print(f"[AUTH ERROR] {result['error']}")
        print("\nMake sure your credentials are correct.")
        print(f"Config file: {CONFIG_PATH}")
        return 1

    if 'error' in result and 'run_id' not in result:
        print(f"[ERROR] {result['error']}")
        return 1

    # Print result
    status_icon = '[OK]' if result.get('status') == 'success' else '[FAIL]'
    print(f"{status_icon} {args.command}")
    print(f"    Run ID: {result.get('run_id', 'N/A')}")
    print(f"    Duration: {result.get('duration_ms', 0)}ms")

    if result.get('steps'):
        print(f"\n    Steps:")
        for step in result['steps']:
            step_icon = '[OK]' if step['status'] == 'success' else '[SKIP]' if step['status'] == 'skipped' else '[FAIL]'
            print(f"      {step_icon} {step['name']} ({step['duration_ms']}ms)")

    if result.get('outputs'):
        print(f"\n    Outputs:")
        for key, value in result['outputs'].items():
            print(f"      {key}: {value[:100]}..." if len(str(value)) > 100 else f"      {key}: {value}")

    if result.get('error'):
        print(f"\n    Error: {result['error']}")

    return 0 if result.get('status') == 'success' else 1


def cmd_list(args):
    """List available commands."""
    config = get_config(args)
    url = f"{config['server']}/commands"

    result = make_request('GET', url)

    if 'error' in result:
        print(f"[ERROR] {result['error']}")
        return 1

    print("Available commands:")
    print()
    for cmd in result.get('commands', []):
        status = '[ON]' if cmd['enabled'] else '[OFF]'
        print(f"  {status} {cmd['cmd']:12} -> {cmd['profile_id']}")

    return 0


def cmd_config(args):
    """Configure client."""
    if args.show:
        config = load_config()
        if config:
            print("Current configuration:")
            print(json.dumps(config, indent=2))
        else:
            print("No configuration saved.")
            print(f"Config file: {CONFIG_PATH}")
        return 0

    config = load_config()

    if args.set_server:
        config['server'] = args.set_server
        print(f"Server set to: {args.set_server}")

    if args.set_client:
        config['client_id'] = args.set_client
        print(f"Client ID set to: {args.set_client}")

    if args.set_secret:
        config['secret'] = args.set_secret
        print("Secret updated.")

    save_config(config)
    print(f"Configuration saved to: {CONFIG_PATH}")
    return 0


def cmd_health(args):
    """Check server health."""
    config = get_config(args)
    url = f"{config['server']}/health"

    result = make_request('GET', url)

    if result.get('status') == 'ok':
        print(f"[OK] Server is healthy: {config['server']}")
        return 0
    else:
        print(f"[FAIL] Server error: {result.get('error', 'Unknown')}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='UASC-M2M Command Line Client',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  uasc @WORK                    Execute @WORK command
  uasc @BUILD project=./myapp   Execute @BUILD with input
  uasc list                     List available commands
  uasc config --set-server http://localhost:8420

Quick Setup:
  1. Start server:  python server.py
  2. Configure:     uasc config --set-secret your-secret
  3. Execute:       uasc @WORK
'''
    )

    # Global options
    parser.add_argument('--server', '-s', help='Server URL')
    parser.add_argument('--client', '-c', help='Client ID')
    parser.add_argument('--secret', '-k', help='Shared secret')

    subparsers = parser.add_subparsers(dest='subcommand')

    # exec (default when command starts with @)
    exec_parser = subparsers.add_parser('exec', help='Execute a command')
    exec_parser.add_argument('command', help='Command to execute (e.g., @WORK)')
    exec_parser.add_argument('inputs', nargs='*', help='Input parameters (key=value)')
    exec_parser.set_defaults(func=cmd_exec)

    # list
    list_parser = subparsers.add_parser('list', help='List available commands')
    list_parser.set_defaults(func=cmd_list)

    # config
    config_parser = subparsers.add_parser('config', help='Configure client')
    config_parser.add_argument('--show', action='store_true', help='Show current config')
    config_parser.add_argument('--set-server', help='Set server URL')
    config_parser.add_argument('--set-client', help='Set client ID')
    config_parser.add_argument('--set-secret', help='Set shared secret')
    config_parser.set_defaults(func=cmd_config)

    # health
    health_parser = subparsers.add_parser('health', help='Check server health')
    health_parser.set_defaults(func=cmd_health)

    # Parse args
    args = parser.parse_args()

    # Handle direct command execution (e.g., "uasc @WORK")
    if not args.subcommand and len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg.startswith('@') or first_arg.startswith('#') or first_arg.startswith('$'):
            # Treat as exec command
            args.command = first_arg
            args.inputs = sys.argv[2:]
            args.func = cmd_exec
        else:
            parser.print_help()
            return 1

    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
