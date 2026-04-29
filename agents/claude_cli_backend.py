import subprocess


class ClaudeCliBackend:
    def __init__(self, model: str | None = None, timeout: int = 120):
        self._model = model
        self._timeout = timeout

    def call(self, system: str, user: str) -> str:
        prompt = f"{system}\n\n{user}" if system else user
        cmd = ["claude", "-p", prompt]
        if self._model:
            cmd += ["--model", self._model]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI timed out after {self._timeout}s")
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            raise ValueError("Claude CLI returned empty response")
        return output
