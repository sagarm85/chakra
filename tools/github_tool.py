import logging
import time

import requests
from github import Github, InputGitTreeElement

logger = logging.getLogger(__name__)


class GitHubTool:
    def __init__(self, token: str, repo_name: str):
        self._token = token
        self._gh = Github(token)
        self._repo = self._gh.get_repo(repo_name)

    def create_branch(self, branch_name: str, base_branch: str = "main") -> None:
        base = self._repo.get_branch(base_branch)
        self._repo.create_git_ref(f"refs/heads/{branch_name}", base.commit.sha)
        logger.info("Created branch: %s from %s", branch_name, base_branch)

    def commit_files(self, branch: str, files: dict[str, str], message: str) -> str:
        ref = self._repo.get_git_ref(f"heads/{branch}")
        base_commit = self._repo.get_git_commit(ref.object.sha)
        tree_elements = []
        for path, content in files.items():
            blob = self._repo.create_git_blob(content, "utf-8")
            tree_elements.append(
                InputGitTreeElement(path=path, mode="100644", type="blob", sha=blob.sha)
            )
        new_tree = self._repo.create_git_tree(tree_elements, base_commit.tree)
        new_commit = self._repo.create_git_commit(message, new_tree, [base_commit])
        ref.edit(new_commit.sha)
        logger.info("Committed %d files to %s: %s", len(files), branch, new_commit.sha)
        return new_commit.sha

    def open_pr(self, branch: str, base_branch: str, title: str, body: str) -> tuple[str, int]:
        pr = self._repo.create_pull(title=title, body=body, head=branch, base=base_branch)
        logger.info("Opened PR #%d: %s", pr.number, pr.html_url)
        return pr.html_url, pr.number

    def open_draft_pr(self, branch: str, base_branch: str, title: str, body: str) -> tuple[str, int]:
        pr = self._repo.create_pull(
            title=title, body=body, head=branch, base=base_branch, draft=True
        )
        logger.info("Opened draft PR #%d: %s", pr.number, pr.html_url)
        return pr.html_url, pr.number

    def mark_pr_ready(self, pr_number: int) -> None:
        pr = self._repo.get_pull(pr_number)
        mutation = """
        mutation($id: ID!) {
          markPullRequestReadyForReview(input: {pullRequestId: $id}) {
            pullRequest { isDraft }
          }
        }
        """
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": mutation, "variables": {"id": pr.node_id}},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL error marking PR ready: {data['errors']}")
        logger.info("PR #%d marked ready for review", pr_number)

    def poll_merge(self, pr_number: int, interval_seconds: int = 30) -> None:
        logger.info("Polling PR #%d for merge every %ds...", pr_number, interval_seconds)
        while True:
            pr = self._repo.get_pull(pr_number)
            if pr.merged:
                logger.info("PR #%d merged", pr_number)
                return
            if pr.state == "closed":
                raise RuntimeError(f"PR #{pr_number} was closed without merging")
            logger.debug("PR #%d still open, checking again in %ds", pr_number, interval_seconds)
            time.sleep(interval_seconds)

    def trigger_cicd(self, workflow: str, ref: str) -> None:
        workflow_obj = self._repo.get_workflow(workflow)
        workflow_obj.create_dispatch(ref)
        logger.info("Triggered workflow %s on ref %s", workflow, ref)
