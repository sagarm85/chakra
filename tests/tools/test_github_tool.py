import pytest
from unittest.mock import MagicMock, patch
from chakra.tools.github_tool import GitHubTool


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def github_tool(mock_repo):
    with patch("chakra.tools.github_tool.Github") as mock_gh_class:
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        tool = GitHubTool("fake-token", "owner/repo")
        tool._repo = mock_repo
        yield tool


def test_create_branch_calls_create_git_ref(github_tool, mock_repo):
    mock_branch = MagicMock()
    mock_branch.commit.sha = "abc123"
    mock_repo.get_branch.return_value = mock_branch
    github_tool.create_branch("chakra/CHAKRA-001-feature", "main")
    mock_repo.create_git_ref.assert_called_once_with(
        "refs/heads/chakra/CHAKRA-001-feature", "abc123"
    )


def test_commit_files_creates_blob_tree_and_commit(github_tool, mock_repo):
    mock_ref = MagicMock()
    mock_ref.object.sha = "ref-sha"
    mock_repo.get_git_ref.return_value = mock_ref
    mock_base_commit = MagicMock()
    mock_base_commit.tree = MagicMock()
    mock_repo.get_git_commit.return_value = mock_base_commit
    mock_blob = MagicMock()
    mock_blob.sha = "blob-sha"
    mock_repo.create_git_blob.return_value = mock_blob
    mock_tree = MagicMock()
    mock_repo.create_git_tree.return_value = mock_tree
    mock_new_commit = MagicMock()
    mock_new_commit.sha = "new-commit-sha"
    mock_repo.create_git_commit.return_value = mock_new_commit

    sha = github_tool.commit_files("chakra/CHAKRA-001", {"src/app.py": "print('hi')"}, "feat: add feature")
    mock_repo.create_git_blob.assert_called_once_with("print('hi')", "utf-8")
    mock_repo.create_git_tree.assert_called_once()
    mock_repo.create_git_commit.assert_called_once()
    mock_ref.edit.assert_called_once_with("new-commit-sha")
    assert sha == "new-commit-sha"


def test_open_pr_returns_url_and_number(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/owner/repo/pull/42"
    mock_pr.number = 42
    mock_repo.create_pull.return_value = mock_pr
    url, number = github_tool.open_pr("chakra/branch", "main", "title", "body")
    assert url == "https://github.com/owner/repo/pull/42"
    assert number == 42


def test_poll_merge_returns_when_merged(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.merged = True
    mock_pr.state = "closed"
    mock_repo.get_pull.return_value = mock_pr
    github_tool.poll_merge(42, interval_seconds=0)
    mock_repo.get_pull.assert_called_once_with(42)


def test_poll_merge_retries_until_merged(github_tool, mock_repo):
    open_pr = MagicMock()
    open_pr.merged = False
    open_pr.state = "open"
    merged_pr = MagicMock()
    merged_pr.merged = True
    mock_repo.get_pull.side_effect = [open_pr, merged_pr]
    with patch("chakra.tools.github_tool.time.sleep"):
        github_tool.poll_merge(42, interval_seconds=1)
    assert mock_repo.get_pull.call_count == 2


def test_poll_merge_raises_on_closed_without_merge(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.merged = False
    mock_pr.state = "closed"
    mock_repo.get_pull.return_value = mock_pr
    with pytest.raises(RuntimeError, match="closed without merging"):
        github_tool.poll_merge(42, interval_seconds=0)


def test_trigger_cicd_dispatches_workflow(github_tool, mock_repo):
    mock_workflow = MagicMock()
    mock_repo.get_workflow.return_value = mock_workflow
    github_tool.trigger_cicd("ci.yml", "main")
    mock_repo.get_workflow.assert_called_once_with("ci.yml")
    mock_workflow.create_dispatch.assert_called_once_with("main")


def test_open_draft_pr_creates_draft_pull(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/owner/repo/pull/10"
    mock_pr.number = 10
    mock_repo.create_pull.return_value = mock_pr
    url, number = github_tool.open_draft_pr("chakra/branch", "main", "Draft title", "body")
    mock_repo.create_pull.assert_called_once_with(
        title="Draft title", body="body", head="chakra/branch", base="main", draft=True
    )
    assert url == "https://github.com/owner/repo/pull/10"
    assert number == 10


def test_mark_pr_ready_calls_graphql(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.node_id = "PR_kwAB"
    mock_repo.get_pull.return_value = mock_pr
    with patch("chakra.tools.github_tool.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}
        }
        mock_post.return_value = mock_resp
        github_tool.mark_pr_ready(10)
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    assert "markPullRequestReadyForReview" in call_kwargs["json"]["query"]
    assert call_kwargs["json"]["variables"]["id"] == "PR_kwAB"


def test_mark_pr_ready_raises_on_graphql_error(github_tool, mock_repo):
    mock_pr = MagicMock()
    mock_pr.node_id = "PR_kwAB"
    mock_repo.get_pull.return_value = mock_pr
    with patch("chakra.tools.github_tool.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errors": [{"message": "not allowed"}]}
        mock_post.return_value = mock_resp
        with pytest.raises(RuntimeError, match="GraphQL error"):
            github_tool.mark_pr_ready(10)


def test_github_tool_stores_token():
    with patch("chakra.tools.github_tool.Github"):
        tool = GitHubTool("my-secret-token", "owner/repo")
    assert tool._token == "my-secret-token"
