"""
UASC Executor — Profile Execution Engine

Executes steps defined in JSON profiles: shell, http, log.
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
    """Executes UASC profiles step-by-step."""

    def __init__(self, working_dir: str = '.') -> None:
        self.working_dir = working_dir
        self.variables: Dict[str, Any] = {}
        self.current_platform = 'windows' if platform.system() == 'Windows' else 'unix'

    def execute(self, profile: dict, inputs: Optional[dict] = None) -> ExecutionResult:
        start_time = time.time()
        self.variables = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'platform': self.current_platform,
        }

        if inputs:
            self.variables.update(inputs)

        for input_def in profile.get('inputs', []):
            name = input_def['name']
            if name not in self.variables and 'default' in input_def:
                self.variables[name] = input_def['default']

        result = ExecutionResult(
            profile_id=profile['id'],
            version=profile['version'],
            status='success',
        )

        for step in profile.get('steps', []):
            step_result = self._execute_step(step)
            result.steps.append(step_result)

            if step.get('store_as') and step_result.output:
                self.variables[step['store_as']] = step_result.output.strip()
                result.outputs[step['store_as']] = step_result.output.strip()

            if step_result.status == 'failed':
                if not step.get('continue_on_error', False):
                    result.status = 'failed'
                    result.error = f"Step '{step['name']}' failed: {step_result.error}"
                    break

        result.total_duration_ms = int((time.time() - start_time) * 1000)

        handler = profile.get('on_success') if result.status == 'success' else profile.get('on_failure')
        if handler:
            self._execute_step(handler)

        return result

    def _execute_step(self, step: dict) -> StepResult:
        name = step.get('name', 'unnamed')
        step_type = step.get('type', 'shell')

        step_platform = step.get('platform')
        if step_platform and step_platform != self.current_platform:
            return StepResult(
                name=name, step_type=step_type, status='skipped',
                output=f'Skipped: platform {step_platform} != {self.current_platform}',
            )

        condition = step.get('condition')
        if condition and not self._evaluate_condition(condition):
            return StepResult(
                name=name, step_type=step_type, status='skipped',
                output='Skipped: condition not met',
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
                    name=name, step_type=step_type, status='failed',
                    error=f'Unknown step type: {step_type}',
                )
        except Exception as e:
            result = StepResult(
                name=name, step_type=step_type, status='failed', error=str(e),
            )

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _execute_shell(self, step: dict) -> StepResult:
        cmd = self._interpolate(step.get('cmd', ''))
        timeout = step.get('timeout_seconds', 60)

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=self.working_dir,
            )

            output = result.stdout
            if result.stderr:
                output += '\n' + result.stderr

            fail_if = step.get('fail_if')
            if fail_if:
                store_var = step.get('store_as', 'output')
                self.variables[store_var] = output.strip()
                if self._evaluate_condition(fail_if):
                    return StepResult(
                        name=step.get('name', 'shell'), step_type='shell',
                        status='failed', output=output,
                        error=f'fail_if condition met: {fail_if}',
                    )

            if result.returncode != 0 and not step.get('continue_on_error'):
                return StepResult(
                    name=step.get('name', 'shell'), step_type='shell',
                    status='failed', output=output,
                    error=f'Exit code: {result.returncode}',
                )

            return StepResult(
                name=step.get('name', 'shell'), step_type='shell',
                status='success', output=output,
            )

        except subprocess.TimeoutExpired:
            return StepResult(
                name=step.get('name', 'shell'), step_type='shell',
                status='failed', error=f'Timeout after {timeout}s',
            )

    def _execute_http(self, step: dict) -> StepResult:
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
                    url, data=data, method=method,
                    headers={'Content-Type': 'application/json'} if body else {},
                )

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    response_body = resp.read().decode()
                    status_code = resp.status

                    if status_code == expected_status:
                        return StepResult(
                            name=step.get('name', 'http'), step_type='http',
                            status='success', output=response_body,
                        )
                    else:
                        if attempt < retries - 1:
                            time.sleep(1)
                            continue
                        return StepResult(
                            name=step.get('name', 'http'), step_type='http',
                            status='failed',
                            error=f'Status {status_code} != {expected_status}',
                        )

            except urllib.error.URLError as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return StepResult(
                    name=step.get('name', 'http'), step_type='http',
                    status='failed', error=str(e),
                )

        return StepResult(
            name=step.get('name', 'http'), step_type='http',
            status='failed', error='All retries exhausted',
        )

    def _execute_log(self, step: dict) -> StepResult:
        message = self._interpolate(step.get('message', ''))
        level = step.get('level', 'info')
        print(f"[{level.upper()}] {message}")

        return StepResult(
            name=step.get('name', 'log'), step_type='log',
            status='success', output=message,
        )

    def _interpolate(self, text: str) -> str:
        for key, value in self.variables.items():
            text = text.replace(f'{{{key}}}', str(value))
        return text

    def _evaluate_condition(self, condition: str) -> bool:
        condition = condition.strip()

        if "!= ''" in condition:
            var_name = condition.replace("!= ''", '').strip()
            return bool(self.variables.get(var_name, ''))

        if "== ''" in condition:
            var_name = condition.replace("== ''", '').strip()
            return not bool(self.variables.get(var_name, ''))

        if '==' in condition:
            parts = condition.split('==')
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                actual = str(self.variables.get(var_name, ''))
                return actual == expected

        if '!=' in condition:
            parts = condition.split('!=')
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                actual = str(self.variables.get(var_name, ''))
                return actual != expected

        if condition in self.variables:
            return bool(self.variables[condition])

        if condition.lower() == 'true':
            return True
        if condition.lower() == 'false':
            return False

        return False
