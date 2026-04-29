import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from agents.backend import AgentBackend

logger = logging.getLogger(__name__)


class SDLCAgent:
    def __init__(self, backend: AgentBackend):
        self._backend = backend

    def _call(self, system: str, user: str) -> str:
        logger.debug("LLM prompt: %s", user[:500])
        result = self._backend.call(system, user)
        logger.debug("LLM response: %s", result[:500])
        return result

    def _extract_json(self, text: str):
        match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return json.loads(match.group(1).strip())
        for opener, closer in [("[", "]"), ("{", "}")]:
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"No JSON found in response: {text[:200]!r}")

    def plan(self, story: str, rejection_feedback: str = "") -> list[dict]:
        feedback_section = (
            f"\n\nPrevious rejection feedback: {rejection_feedback}"
            if rejection_feedback
            else ""
        )
        user = (
            f"Analyze this user story and break it into implementation tasks."
            f"{feedback_section}\n\nUser story:\n{story}\n\n"
            f"Return a JSON array of tasks, each with \"task\" (short name) and "
            f"\"description\" (what to implement).\n"
            f'Format: ```json\n[{{"task": "...", "description": "..."}}]\n```'
        )
        system = (
            "You are a senior software engineer breaking user stories into "
            "implementation tasks. Be specific and actionable."
        )
        response = self._call(system, user)
        tasks = self._extract_json(response)
        logger.info("Planned %d tasks", len(tasks))
        return tasks

    def code(self, story: str, tasks: list[dict]) -> dict[str, str]:
        tasks_text = "\n".join(
            f"- {t['task']}: {t['description']}" for t in tasks
        )
        user = (
            f"Generate Python implementation code for this user story.\n\n"
            f"User story: {story}\n\nTasks to implement:\n{tasks_text}\n\n"
            f"Return a JSON object mapping filename to file content.\n"
            f'Format: ```json\n{{"path/to/file.py": "# file content"}}\n```'
        )
        system = (
            "You are a senior Python developer. "
            "Write clean, well-structured Python 3.12 code."
        )
        response = self._call(system, user)
        files = self._extract_json(response)
        logger.info("Generated %d code files", len(files))
        return files

    def test(
        self,
        story: str,
        code: dict[str, str],
        coverage_feedback: str = "",
    ) -> dict[str, str]:
        code_summary = "\n\n".join(
            f"# {fname}\n{content}" for fname, content in code.items()
        )
        feedback_section = (
            f"\n\nCoverage feedback (improve to reach 95%):\n{coverage_feedback}"
            if coverage_feedback
            else ""
        )
        user = (
            f"Generate pytest tests achieving >=95% line coverage for this code."
            f"{feedback_section}\n\nUser story: {story}\n\nCode to test:\n{code_summary}\n\n"
            f"Return a JSON object mapping test filename to test content.\n"
            f'Format: ```json\n{{"tests/test_file.py": "# test content"}}\n```'
        )
        system = (
            "You are a senior Python test engineer. "
            "Write thorough pytest tests targeting >=95% line coverage."
        )
        response = self._call(system, user)
        files = self._extract_json(response)
        logger.info("Generated %d test files", len(files))
        return files

    def measure_coverage(
        self,
        code_files: dict[str, str],
        test_files: dict[str, str],
    ) -> tuple[float, str]:
        if not test_files:
            logger.warning("No test files provided — coverage is 0%%")
            return 0.0, "No test files"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for fname, content in {**code_files, **test_files}.items():
                fpath = tmp_path / fname
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content)

            result = subprocess.run(
                ["python3", "-m", "pytest", "--cov=.", "--cov-report=term-missing", "-q"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            logger.debug("Coverage output:\n%s", output)

            match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
            coverage = float(match.group(1)) if match else 0.0
            logger.info("Coverage measured: %.0f%%", coverage)
            return coverage, output
