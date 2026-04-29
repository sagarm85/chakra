import pytest
from unittest.mock import MagicMock
from agents.sdlc_agent import SDLCAgent


PLAN_RESPONSE = '```json\n[{"task": "setup", "description": "Create project structure"}]\n```'
CODE_RESPONSE = '```json\n{"src/app.py": "def hello():\\n    return \'hello\'"}\n```'
TEST_RESPONSE = '```json\n{"tests/test_app.py": "from src.app import hello\\ndef test_hello():\\n    assert hello() == \'hello\'"}\n```'


@pytest.fixture
def backend():
    return MagicMock()


@pytest.fixture
def agent(backend):
    return SDLCAgent(backend)


def test_plan_returns_list_of_dicts(agent, backend):
    backend.call.return_value = PLAN_RESPONSE
    result = agent.plan("As a user I want a hello endpoint")
    assert isinstance(result, list)
    assert result[0]["task"] == "setup"
    assert result[0]["description"] == "Create project structure"


def test_plan_includes_rejection_feedback_in_prompt(agent, backend):
    backend.call.return_value = PLAN_RESPONSE
    agent.plan("story", rejection_feedback="too vague")
    _, user = backend.call.call_args[0]
    assert "too vague" in user


def test_plan_no_feedback_omits_feedback_section(agent, backend):
    backend.call.return_value = PLAN_RESPONSE
    agent.plan("story", rejection_feedback="")
    _, user = backend.call.call_args[0]
    assert "rejection" not in user.lower()


def test_code_returns_dict_of_files(agent, backend):
    backend.call.return_value = CODE_RESPONSE
    tasks = [{"task": "setup", "description": "Create project structure"}]
    result = agent.code("story", tasks)
    assert "src/app.py" in result
    assert "def hello" in result["src/app.py"]


def test_test_returns_dict_of_test_files(agent, backend):
    backend.call.return_value = TEST_RESPONSE
    code = {"src/app.py": "def hello():\n    return 'hello'"}
    result = agent.test("story", code)
    assert "tests/test_app.py" in result


def test_test_includes_coverage_feedback_in_prompt(agent, backend):
    backend.call.return_value = TEST_RESPONSE
    agent.test("story", {}, coverage_feedback="TOTAL 10 5 50%")
    _, user = backend.call.call_args[0]
    assert "TOTAL 10 5 50%" in user


def test_measure_coverage_returns_float_and_report(agent, tmp_path):
    code_files = {"src/app.py": "def hello():\n    return 'hello'\n"}
    test_files = {
        "tests/__init__.py": "",
        "tests/test_app.py": (
            "import sys, os\n"
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))\n"
            "from src.app import hello\n"
            "def test_hello():\n"
            "    assert hello() == 'hello'\n"
        ),
    }
    coverage, report = agent.measure_coverage(code_files, test_files)
    assert isinstance(coverage, float)
    assert isinstance(report, str)


def test_measure_coverage_returns_zero_on_no_tests(agent):
    coverage, report = agent.measure_coverage({"src/app.py": "x = 1"}, {})
    assert coverage == 0.0


def test_extract_json_fallback_no_code_fence(agent, backend):
    raw_json = '[{"task": "t1", "description": "d1"}]'
    backend.call.return_value = raw_json
    result = agent.plan("story")
    assert isinstance(result, list)
    assert result[0]["task"] == "t1"
