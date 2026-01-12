"""
UASC-M2M MVP Profile Executor

Executes steps defined in execution profiles.
"""

import subprocess
import json
import time
import platform
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class StepResult:
    """Result of executing a single step."""
    name: str
    step_type: str
    status: str  # success, failed, skipped
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class ExecutionResult:
    """Result of executing a full profile."""
    profile_id: str
    version: int
    status: str  # success, failed
    steps: List[StepResult] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    total_duration_ms: int = 0
    error: Optional[str] = None


class ProfileExecutor:
    """
    Executes UASC execution profiles.

    Supports step types:
    - shell: Run shell command
    - http: Make HTTP request
    - log: Log a message
    - condition: Conditional branching (TODO)
    """

    def __init__(self, working_dir: str = '.'):
        self.working_dir = working_dir
        self.variables: Dict[str, Any] = {}
        self.current_platform = 'windows' if platform.system() == 'Windows' else 'unix'

    def execute(self, profile: dict, inputs: dict = None) -> ExecutionResult:
        """
        Execute a profile.

        Args:
            profile: Profile definition dict
            inputs: Input parameters

        Returns:
            ExecutionResult with step-by-step results
        """
        start_time = time.time()
        self.variables = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'platform': self.current_platform
        }

        # Apply inputs
        if inputs:
            self.variables.update(inputs)

        # Apply profile inputs defaults
        for input_def in profile.get('inputs', []):
            name = input_def['name']
            if name not in self.variables and 'default' in input_def:
                self.variables[name] = input_def['default']

        result = ExecutionResult(
            profile_id=profile['id'],
            version=profile['version'],
            status='success'
        )

        # Execute steps
        for step in profile.get('steps', []):
            step_result = self._execute_step(step)
            result.steps.append(step_result)

            # Store output if requested
            if step.get('store_as') and step_result.output:
                self.variables[step['store_as']] = step_result.output.strip()
                result.outputs[step['store_as']] = step_result.output.strip()

            # Check for failure
            if step_result.status == 'failed':
                if not step.get('continue_on_error', False):
                    result.status = 'failed'
                    result.error = f"Step '{step['name']}' failed: {step_result.error}"
                    break

        result.total_duration_ms = int((time.time() - start_time) * 1000)

        # Execute on_success or on_failure handler
        handler = profile.get('on_success') if result.status == 'success' else profile.get('on_failure')
        if handler:
            self._execute_step(handler)

        return result

    def _execute_step(self, step: dict) -> StepResult:
        """Execute a single step."""
        name = step.get('name', 'unnamed')
        step_type = step.get('type', 'shell')

        # Check platform filter
        step_platform = step.get('platform')
        if step_platform and step_platform != self.current_platform:
            return StepResult(
                name=name,
                step_type=step_type,
                status='skipped',
                output=f'Skipped: platform {step_platform} != {self.current_platform}'
            )

        # Check condition
        condition = step.get('condition')
        if condition and not self._evaluate_condition(condition):
            return StepResult(
                name=name,
                step_type=step_type,
                status='skipped',
                output=f'Skipped: condition not met'
            )

        start_time = time.time()

        try:
            if step_type == 'shell':
                result = self._execute_shell(step)
            elif step_type == 'http':
                result = self._execute_http(step)
            elif step_type == 'log':
                result = self._execute_log(step)
            else:
                result = StepResult(
                    name=name,
                    step_type=step_type,
                    status='failed',
                    error=f'Unknown step type: {step_type}'
                )
        except Exception as e:
            result = StepResult(
                name=name,
                step_type=step_type,
                status='failed',
                error=str(e)
            )

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _execute_shell(self, step: dict) -> StepResult:
        """Execute a shell command."""
        cmd = self._interpolate(step.get('cmd', ''))
        timeout = step.get('timeout_seconds', 60)

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir
            )

            output = result.stdout
            if result.stderr:
                output += '\n' + result.stderr

            # Check fail_if condition
            fail_if = step.get('fail_if')
            if fail_if:
                store_var = step.get('store_as', 'output')
                self.variables[store_var] = output.strip()
                if self._evaluate_condition(fail_if):
                    return StepResult(
                        name=step.get('name', 'shell'),
                        step_type='shell',
                        status='failed',
                        output=output,
                        error=f'fail_if condition met: {fail_if}'
                    )

            if result.returncode != 0 and not step.get('continue_on_error'):
                return StepResult(
                    name=step.get('name', 'shell'),
                    step_type='shell',
                    status='failed',
                    output=output,
                    error=f'Exit code: {result.returncode}'
                )

            return StepResult(
                name=step.get('name', 'shell'),
                step_type='shell',
                status='success',
                output=output
            )

        except subprocess.TimeoutExpired:
            return StepResult(
                name=step.get('name', 'shell'),
                step_type='shell',
                status='failed',
                error=f'Timeout after {timeout}s'
            )

    def _execute_http(self, step: dict) -> StepResult:
        """Execute an HTTP request."""
        method = step.get('method', 'GET')
        url = self._interpolate(step.get('url', ''))
        body = step.get('body')
        expected_status = step.get('expected_status', 200)
        timeout = step.get('timeout_seconds', 30)
        retries = step.get('retries', 1)

        for attempt in range(retries):
            try:
                data = json.dumps(body).encode() if body else None
                req = urllib.request.Request(
                    url,
                    data=data,
                    method=method,
                    headers={'Content-Type': 'application/json'} if body else {}
                )

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    response_body = resp.read().decode()
                    status_code = resp.status

                    if status_code == expected_status:
                        return StepResult(
                            name=step.get('name', 'http'),
                            step_type='http',
                            status='success',
                            output=response_body
                        )
                    else:
                        if attempt < retries - 1:
                            time.sleep(1)
                            continue
                        return StepResult(
                            name=step.get('name', 'http'),
                            step_type='http',
                            status='failed',
                            error=f'Status {status_code} != {expected_status}'
                        )

            except urllib.error.URLError as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return StepResult(
                    name=step.get('name', 'http'),
                    step_type='http',
                    status='failed',
                    error=str(e)
                )

        return StepResult(
            name=step.get('name', 'http'),
            step_type='http',
            status='failed',
            error='All retries exhausted'
        )

    def _execute_log(self, step: dict) -> StepResult:
        """Execute a log step."""
        message = self._interpolate(step.get('message', ''))
        level = step.get('level', 'info')

        print(f"[{level.upper()}] {message}")

        return StepResult(
            name=step.get('name', 'log'),
            step_type='log',
            status='success',
            output=message
        )

    def _interpolate(self, text: str) -> str:
        """Replace {variable} placeholders with values."""
        for key, value in self.variables.items():
            text = text.replace(f'{{{key}}}', str(value))
        return text

    def _evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate a simple condition expression.

        Supports: var == 'value', var != 'value', var != ''
        """
        condition = condition.strip()

        # Handle != ''
        if "!= ''" in condition:
            var_name = condition.replace("!= ''", '').strip()
            return bool(self.variables.get(var_name, ''))

        # Handle == ''
        if "== ''" in condition:
            var_name = condition.replace("== ''", '').strip()
            return not bool(self.variables.get(var_name, ''))

        # Handle == value
        if '==' in condition:
            parts = condition.split('==')
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                actual = str(self.variables.get(var_name, ''))
                return actual == expected

        # Handle != value
        if '!=' in condition:
            parts = condition.split('!=')
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                actual = str(self.variables.get(var_name, ''))
                return actual != expected

        # Handle boolean variables
        if condition in self.variables:
            return bool(self.variables[condition])

        # Handle false/true literals
        if condition.lower() == 'true':
            return True
        if condition.lower() == 'false':
            return False

        return False


if __name__ == '__main__':
    # Demo execution
    import os

    print("=== UASC-M2M Executor Demo ===\n")

    # Load WORK profile
    profile_path = os.path.join(os.path.dirname(__file__), 'profiles', 'WORK_v1.json')
    with open(profile_path) as f:
        profile = json.load(f)

    print(f"Profile: {profile['id']} v{profile['version']}")
    print(f"Description: {profile['description']}")
    print(f"Steps: {len(profile['steps'])}")
    print()

    # Execute
    executor = ProfileExecutor()
    result = executor.execute(profile)

    print(f"\n=== Execution Result ===")
    print(f"Status: {result.status}")
    print(f"Duration: {result.total_duration_ms}ms")
    print(f"\nSteps:")
    for step in result.steps:
        status_icon = '[OK]' if step.status == 'success' else '[SKIP]' if step.status == 'skipped' else '[FAIL]'
        print(f"  {status_icon} {step.name} ({step.duration_ms}ms)")
        if step.error:
            print(f"       Error: {step.error}")
