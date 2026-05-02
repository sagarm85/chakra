import pytest
from unittest.mock import patch
from chakra.tools.approval_tool import prompt_approval, ApprovalRejected


def test_prompt_approval_y_returns_true():
    with patch("builtins.input", return_value="y"):
        result = prompt_approval("Test Label", "Test content")
    assert result is True


def test_prompt_approval_n_raises_approval_rejected():
    with patch("builtins.input", side_effect=["n", ""]):
        with pytest.raises(ApprovalRejected):
            prompt_approval("Test Label", "Test content")


def test_prompt_approval_n_with_reason_stores_reason():
    with patch("builtins.input", side_effect=["n", "needs more detail"]):
        with pytest.raises(ApprovalRejected) as exc_info:
            prompt_approval("Test Label", "Test content")
    assert exc_info.value.reason == "needs more detail"


def test_prompt_approval_invalid_then_y_accepts():
    with patch("builtins.input", side_effect=["maybe", "y"]):
        result = prompt_approval("Test Label", "Test content")
    assert result is True


def test_prompt_approval_prints_label(capsys):
    with patch("builtins.input", return_value="y"):
        prompt_approval("My Label", "some content")
    captured = capsys.readouterr()
    assert "My Label" in captured.out


def test_prompt_approval_prints_content(capsys):
    with patch("builtins.input", return_value="y"):
        prompt_approval("Label", "important content here")
    captured = capsys.readouterr()
    assert "important content here" in captured.out


def test_approval_rejected_has_message():
    exc = ApprovalRejected("bad plan")
    assert "bad plan" in str(exc)
    assert exc.reason == "bad plan"
