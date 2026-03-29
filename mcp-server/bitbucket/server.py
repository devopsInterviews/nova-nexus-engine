"""
server.py
=========
FastMCP-based Bitbucket Server MCP gateway.

Exposes a rich set of tools for interacting with Bitbucket Server:

Repository operations
    - ``list_repositories``         – list all repos in a project
    - ``get_repository_info``       – metadata, default branch, clone URLs
    - ``list_bitbucket_files``      – list files in a repo directory
    - ``get_bitbucket_file``        – fetch decoded / base64 file content
    - ``get_file_content``          – fetch raw file content (text)
    - ``search_repository``         – search code / config / patterns

Pull-request operations
    - ``list_pull_requests``        – list PRs (open / merged / declined)
    - ``get_pull_request``          – PR title, description, author, state, reviewers, branches
    - ``list_pull_request_files``   – changed files in a PR
    - ``get_pull_request_diff``     – unified diff (full or per-file)
    - ``get_pull_request_comments`` – existing PR comments
    - ``get_pull_request_activities`` – approvals, updates, reviews
    - ``get_build_status``          – CI / pipeline / scan results
    - ``get_commit_list``           – commits in a PR
    - ``get_pull_request_tasks``    – open review tasks
    - ``create_pr_comment_draft``   – compose a local draft (no network)
    - ``post_pr_comment``           – post a general comment
    - ``post_inline_pr_comment``    – comment on a specific file + line
    - ``add_pull_request_task``     – create a review task
"""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from appConfig import configure_logging, settings
from bitbucketClient import BitbucketClient
from usageTracker import UsageTrackingMiddleware

logger = logging.getLogger(__name__)
configure_logging()

# ------------------------------------------------------------------ #
#  MCP & FastAPI wiring
# ------------------------------------------------------------------ #

mcp = FastMCP(name="Bitbucket McpServer")
logger.info("✅  MCP Server started successfully")

mcp_app = mcp.http_app()


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    async with mcp_app.lifespan(app):
        yield


app = FastAPI(lifespan=combined_lifespan)

# ------------------------------------------------------------------ #
#  Usage-tracking middleware (optional — requires portal env vars)    #
# ------------------------------------------------------------------ #

if settings.portal_base_url and settings.mcp_server_marketplace_name:
    _portal_ping_url = (
        f"{settings.portal_base_url.rstrip('/')}/api/marketplace/ping"
    )
    _portal_ssl = str(settings.portal_ssl_verify).strip().lower() in {
        "true", "1", "yes", "y", "on",
    }
    app.add_middleware(
        UsageTrackingMiddleware,
        portal_ping_url=_portal_ping_url,
        entity_name=settings.mcp_server_marketplace_name,
        ssl_verify=_portal_ssl,
    )
    logger.info(
        "Usage tracking enabled  entity='%s'  portal=%s",
        settings.mcp_server_marketplace_name,
        settings.portal_base_url,
    )
else:
    logger.info(
        "Usage tracking disabled "
        "(set PORTAL_BASE_URL and MCP_SERVER_MARKETPLACE_NAME to enable)"
    )


# ------------------------------------------------------------------ #
#  Auth helper
# ------------------------------------------------------------------ #

def get_bitbucket_client() -> BitbucketClient:
    """
    Create a :class:`BitbucketClient` using the Bearer token from the
    incoming HTTP request headers.

    :raises HTTPException: 401 if no token is present.
    """
    headers = get_http_headers()
    auth_header = headers.get("authorization", "")
    token: Optional[str] = None

    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]

    if not token:
        logger.warning("No auth token in headers.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing in headers.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return BitbucketClient(
        base_url=settings.bitbucket_base_url,
        access_token=token,
        bitbucket_ssl_verify=settings.bitbucket_ssl_verify,
    )


# ------------------------------------------------------------------ #
#  Health-check
# ------------------------------------------------------------------ #

@app.get("/health")
async def health_check(request: Request) -> PlainTextResponse:
    """Simple health check.  Returns HTTP 200 with ``OK``."""
    return PlainTextResponse("OK", status_code=200)


# ================================================================== #
#                        FILE TOOLS                                   #
# ================================================================== #

@mcp.tool()
async def get_bitbucket_file(
    file_path: str,
    repo: str,
    project: str,
    as_text: bool = True,
    encoding: str = "utf-8",
    branch: str = "master",
) -> dict:
    """
    Fetch a file's content from Bitbucket Server.

    :param file_path: Path inside the repo (e.g. ``src/main.py``).
    :param repo:      Repository slug.
    :param project:   Bitbucket project key.
    :param as_text:   If True  → decoded text in ``content``.
                      If False → base64-encoded bytes in ``content_b64``.
    :param encoding:  Text encoding when *as_text* is True (default ``utf-8``).
    :param branch:    Branch / tag / commit (default ``master``).

    :returns: dict with ``status``, ``project``, ``repo``, ``file_path``,
              ``branch``, ``as_text``, ``mime``, and ``content`` or
              ``content_b64``.
    :raises ValueError: If fetching fails.
    """
    client = get_bitbucket_client()

    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path is mandatory and cannot be empty.")

    try:
        raw = await client.fetch_file_path(
            project=project,
            repo=repo,
            file_path=file_path,
            branch=branch,
            as_text=as_text,
            encoding=encoding,
        )

        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or "application/octet-stream"

        result: Dict[str, Any] = {
            "status": "success",
            "project": project,
            "repo": repo,
            "file_path": file_path,
            "branch": branch,
            "as_text": as_text,
            "mime": mime,
        }

        if as_text:
            result["encoding"] = encoding
            result["content"] = raw
        else:
            if isinstance(raw, str):
                raw = raw.encode(encoding, errors="replace")
            result["content_b64"] = base64.b64encode(raw).decode("ascii")

        logger.info(
            "Successfully fetched %s/%s:%s (mode=%s)",
            project, repo, file_path, "text" if as_text else "bytes",
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to fetch file (project=%s repo=%s path=%s branch=%s): %s",
            project, repo, file_path, branch, e,
        )
        raise ValueError(f"Failed to fetch file '{file_path}' (branch={branch}): {e}") from e


@mcp.tool()
async def get_file_content(
    project: str,
    repo: str,
    path: str,
    at_ref: str = "master",
) -> Dict[str, Any]:
    """
    Fetch the current raw text content of a file from a Bitbucket repository.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param path:    File path inside the repository.
    :param at_ref:  Branch / tag / commit (short or full ref).

    :returns: dict ``{status, project, repo, path, at_ref, content}``.
    :raises ValueError: On failure.
    """
    client = get_bitbucket_client()
    try:
        content = await client.get_file_content(project, repo, path, at_ref)
        return {
            "status": "success",
            "project": project,
            "repo": repo,
            "path": path,
            "at_ref": at_ref,
            "content": content,
        }
    except Exception as e:
        logger.error("get_file_content failed: %s", e)
        raise ValueError(f"Failed to get file content for '{path}': {e}") from e


@mcp.tool()
async def list_bitbucket_files(
    project: str,
    repo: str,
    path: str = "",
    at_ref: str = "refs/heads/master",
) -> Dict[str, List[str]]:
    """
    List all files in a Bitbucket repo under a given path and branch.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param path:    Sub-directory to list (empty → entire repo).
    :param at_ref:  Branch reference.

    :returns: ``{"files": ["path1", "path2", …]}``.
    """
    client = get_bitbucket_client()
    files = await client.list_files(project, repo, path, at_ref)
    logger.debug("list_bitbucket_files: %d files found", len(files))
    return {"files": files}


@mcp.tool()
async def list_repositories(
    project: str,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    List all repositories in a Bitbucket project.

    :param project: Bitbucket project key.
    :param limit:   Maximum number of repos to return (default 100).

    :returns: ``{status, project, repos: [{slug, name, description, state, defaultBranch, cloneUrls}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        raw = await client.list_repositories(project, limit)
        repos = [
            {
                "slug": r.get("slug", ""),
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "state": r.get("state", ""),
                "forkable": r.get("forkable", False),
                "cloneUrls": [
                    {"name": lnk.get("name", ""), "href": lnk.get("href", "")}
                    for lnk in r.get("links", {}).get("clone", [])
                ],
            }
            for r in raw
        ]
        return {"status": "success", "project": project, "repos": repos}
    except Exception as e:
        logger.error("list_repositories failed for project %s: %s", project, e)
        raise ValueError(f"Failed to list repositories for project '{project}': {e}") from e


@mcp.tool()
async def get_repository_info(
    project: str,
    repo: str,
) -> Dict[str, Any]:
    """
    Fetch metadata for a specific Bitbucket repository: name, slug, description,
    clone URLs, default branch, and links.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.

    :returns: ``{status, project, repo, name, description, state, defaultBranch, cloneUrls}``.
    """
    client = get_bitbucket_client()
    try:
        info = await client.get_repository_info(project, repo)
        default_branch = await client.get_default_branch(project, repo)
        return {
            "status": "success",
            "project": project,
            "repo": repo,
            "name": info.get("name", ""),
            "description": info.get("description", ""),
            "state": info.get("state", ""),
            "forkable": info.get("forkable", False),
            "defaultBranch": default_branch,
            "cloneUrls": [
                {"name": lnk.get("name", ""), "href": lnk.get("href", "")}
                for lnk in info.get("links", {}).get("clone", [])
            ],
            "links": info.get("links", {}),
        }
    except Exception as e:
        logger.error("get_repository_info failed for %s/%s: %s", project, repo, e)
        raise ValueError(f"Failed to get repository info for '{project}/{repo}': {e}") from e


@mcp.tool()
async def search_repository(
    project: str,
    repo: str,
    query: str,
    extension: Optional[str] = None,
    at_ref: str = "refs/heads/master",
    max_matches: int = 50,
) -> Dict[str, Any]:
    """
    Search for code, config, or patterns in a Bitbucket repository.

    :param project:     Bitbucket project key.
    :param repo:        Repository slug.
    :param query:       Search string (keyword, regex fragment, etc.).
    :param extension:   Optional file extension filter (e.g. ``py``, ``sql``).
    :param at_ref:      Branch reference.
    :param max_matches: Maximum number of results.

    :returns: ``{status, results: [{path, hitCount, lines}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        results = await client.search_repository(
            project, repo, query, extension, at_ref, max_matches,
        )
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error("search_repository failed: %s", e)
        raise ValueError(f"Repository search failed: {e}") from e


# ================================================================== #
#                   PULL-REQUEST TOOLS                                #
# ================================================================== #

@mcp.tool()
async def list_pull_requests(
    project: str,
    repo: str,
    state: str = "OPEN",
    limit: int = 25,
) -> Dict[str, Any]:
    """
    List pull requests for a repository.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param state:   ``OPEN`` (default), ``MERGED``, ``DECLINED``, or ``ALL``.
    :param limit:   Maximum number of PRs to return (default 25).

    :returns: ``{status, prs: [{id, title, state, author, fromBranch, toBranch, createdDate}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        raw = await client.list_pull_requests(project, repo, state, limit)
        prs = [
            {
                "id": pr.get("id"),
                "title": pr.get("title", ""),
                "state": pr.get("state", ""),
                "author": pr.get("author", {}).get("user", {}).get(
                    "displayName",
                    pr.get("author", {}).get("user", {}).get("name", ""),
                ),
                "fromBranch": pr.get("fromRef", {}).get("displayId", ""),
                "toBranch": pr.get("toRef", {}).get("displayId", ""),
                "createdDate": pr.get("createdDate"),
                "updatedDate": pr.get("updatedDate"),
            }
            for pr in raw
        ]
        return {"status": "success", "prs": prs}
    except Exception as e:
        logger.error("list_pull_requests failed for %s/%s: %s", project, repo, e)
        raise ValueError(f"Failed to list pull requests for '{project}/{repo}': {e}") from e


@mcp.tool()
async def get_pull_request(
    project: str,
    repo: str,
    pr_id: int,
) -> Dict[str, Any]:
    """
    Get full metadata for a pull request: title, description, author,
    source/target branches, state, reviewers, dates.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param pr_id:   Pull request ID.

    :returns: Structured dict with the key PR fields.
    :raises ValueError: If the PR cannot be fetched.
    """
    client = get_bitbucket_client()
    try:
        pr = await client.get_pull_request(project, repo, pr_id)

        author_info = pr.get("author", {}).get("user", {})
        reviewers = [
            {
                "user": r.get("user", {}).get("displayName", r.get("user", {}).get("name", "")),
                "role": r.get("role", ""),
                "status": r.get("status", ""),
            }
            for r in pr.get("reviewers", [])
        ]
        from_ref = pr.get("fromRef", {})
        to_ref = pr.get("toRef", {})

        return {
            "status": "success",
            "id": pr.get("id"),
            "title": pr.get("title", ""),
            "description": pr.get("description", ""),
            "state": pr.get("state", ""),
            "author": {
                "name": author_info.get("displayName", author_info.get("name", "")),
                "email": author_info.get("emailAddress", ""),
            },
            "from_branch": from_ref.get("displayId", ""),
            "from_ref": from_ref.get("id", ""),
            "to_branch": to_ref.get("displayId", ""),
            "to_ref": to_ref.get("id", ""),
            "reviewers": reviewers,
            "created_date": pr.get("createdDate"),
            "updated_date": pr.get("updatedDate"),
            "closed_date": pr.get("closedDate"),
            "links": pr.get("links", {}),
        }
    except Exception as e:
        logger.error("get_pull_request failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to fetch PR #{pr_id}: {e}") from e


@mcp.tool()
async def list_pull_request_files(
    project: str,
    repo: str,
    pr_id: int,
    path_prefix: str = "",
    extension_filter: str = "",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    List all files changed in a pull request, with optional filters.

    :param project:          Bitbucket project key.
    :param repo:             Repository slug.
    :param pr_id:            Pull request ID.
    :param path_prefix:      Only return files under this directory prefix.
    :param extension_filter: Only return files with this extension (e.g. ``sql``).

    :returns: ``{"files": [{path, type, srcPath?}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        all_files = await client.list_pull_request_files(project, repo, pr_id)

        filtered: List[Dict[str, Any]] = []
        for f in all_files:
            p = f.get("path", "")
            if path_prefix and not p.startswith(path_prefix):
                continue
            if extension_filter and not p.endswith(f".{extension_filter.lstrip('.')}"):
                continue
            filtered.append(f)

        return {"files": filtered}
    except Exception as e:
        logger.error("list_pull_request_files failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to list changed files for PR #{pr_id}: {e}") from e


@mcp.tool()
async def get_pull_request_diff(
    project: str,
    repo: str,
    pr_id: int,
    file_path: Optional[str] = None,
    context_lines: int = 10,
    src_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get the raw diff for a pull request, or for a specific file in that pull request.

    When ``file_path`` is not provided, this returns the full unified diff for the PR.
    When ``file_path`` is provided, this returns the diff only for that file.

    :param project:       Bitbucket project key.
    :param repo:          Repository slug.
    :param pr_id:         Pull request ID.
    :param file_path:     Optional file path inside the PR to fetch diff for.
    :param context_lines: Number of context lines around each change (default 10).
    :param src_path:      Optional original path for renamed or moved files.

    :returns: ``{status, pr_id, file_path, src_path, diff}``.
    :raises ValueError: On failure.
    """
    client = get_bitbucket_client()
    try:
        diff_text = await client.get_pull_request_diff(
            project=project,
            repo=repo,
            pr_id=pr_id,
            file_path=file_path,
            context_lines=context_lines,
            src_path=src_path,
        )
        return {
            "status": "success",
            "pr_id": pr_id,
            "file_path": file_path,
            "src_path": src_path,
            "diff": diff_text,
        }
    except Exception as e:
        logger.error("get_pull_request_diff failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to get diff for PR #{pr_id}: {e}") from e

@mcp.tool()
async def get_pull_request_comments(
    project: str,
    repo: str,
    pr_id: int,
) -> Dict[str, Any]:
    """
    List all existing comments (top-level and inline) on a pull request.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param pr_id:   Pull request ID.

    :returns: ``{status, comments: [{id, text, author, createdDate, anchor?}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        raw = await client.get_pull_request_comments(project, repo, pr_id)
        comments = []
        for c in raw:
            entry: Dict[str, Any] = {
                "id": c.get("id"),
                "text": c.get("text", ""),
                "author": c.get("author", {}).get("displayName",
                          c.get("author", {}).get("name", "")),
                "createdDate": c.get("createdDate"),
                "updatedDate": c.get("updatedDate"),
                "state": c.get("state", ""),
                "severity": c.get("severity", "NORMAL"),
            }
            anchor = c.get("anchor")
            if anchor:
                entry["anchor"] = {
                    "path": anchor.get("path", ""),
                    "line": anchor.get("line"),
                    "lineType": anchor.get("lineType", ""),
                    "fileType": anchor.get("fileType", ""),
                }
            comments.append(entry)
        return {"status": "success", "comments": comments}
    except Exception as e:
        logger.error("get_pull_request_comments failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to list comments for PR #{pr_id}: {e}") from e


@mcp.tool()
async def get_pull_request_activities(
    project: str,
    repo: str,
    pr_id: int,
) -> Dict[str, Any]:
    """
    Fetch the activity stream for a pull request: approvals, status changes,
    review activity, comment events, merge events.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param pr_id:   Pull request ID.

    :returns: ``{status, activities: [{id, action, createdDate, user, …}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        raw = await client.get_pull_request_activities(project, repo, pr_id)
        activities = []
        for a in raw:
            entry: Dict[str, Any] = {
                "id": a.get("id"),
                "action": a.get("action", ""),
                "createdDate": a.get("createdDate"),
            }
            user = a.get("user", {})
            entry["user"] = user.get("displayName", user.get("name", ""))
            # Include comment text if it's a comment activity
            comment = a.get("comment")
            if comment:
                entry["comment"] = {
                    "id": comment.get("id"),
                    "text": comment.get("text", ""),
                }
            activities.append(entry)
        return {"status": "success", "activities": activities}
    except Exception as e:
        logger.error("get_pull_request_activities failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to fetch activities for PR #{pr_id}: {e}") from e


@mcp.tool()
async def get_build_status(
    project: str,
    repo: str,
    pr_id: Optional[int] = None,
    commit_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve CI / pipeline / build statuses for a commit or the latest commit
    on a pull request.

    Covers pipeline results, security scan results, lint/test summaries – any
    status reported via the Bitbucket Build Status API.

    :param project:   Bitbucket project key.
    :param repo:      Repository slug.
    :param pr_id:     Pull request ID (used to find the latest commit).
    :param commit_id: Explicit commit hash.  Takes priority over *pr_id*.

    :returns: ``{status, commit_id, builds: [{state, key, name, url, description}, …]}``.
    :raises ValueError: If neither *pr_id* nor *commit_id* is provided.
    """
    if not pr_id and not commit_id:
        raise ValueError("Provide at least one of pr_id or commit_id.")

    client = get_bitbucket_client()
    try:
        builds = await client.get_build_status(project, repo, pr_id, commit_id)
        # Resolve effective commit id for response
        effective_commit = commit_id
        if not effective_commit and pr_id:
            commits = await client.get_pull_request_commits(project, repo, pr_id)
            effective_commit = commits[0].get("id", "") if commits else ""

        simplified = [
            {
                "state": b.get("state", ""),
                "key": b.get("key", ""),
                "name": b.get("name", ""),
                "url": b.get("url", ""),
                "description": b.get("description", ""),
                "dateAdded": b.get("dateAdded"),
            }
            for b in builds
        ]
        return {
            "status": "success",
            "commit_id": effective_commit,
            "builds": simplified,
        }
    except Exception as e:
        logger.error("get_build_status failed: %s", e)
        raise ValueError(f"Failed to fetch build status: {e}") from e


@mcp.tool()
async def get_commit_list(
    project: str,
    repo: str,
    pr_id: int,
) -> Dict[str, Any]:
    """
    List all commits included in a pull request.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param pr_id:   Pull request ID.

    :returns: ``{status, commits: [{id, displayId, message, author, timestamp}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        raw = await client.get_pull_request_commits(project, repo, pr_id)
        commits = [
            {
                "id": c.get("id", ""),
                "displayId": c.get("displayId", ""),
                "message": c.get("message", ""),
                "author": c.get("author", {}).get("name", ""),
                "authorEmail": c.get("author", {}).get("emailAddress", ""),
                "timestamp": c.get("authorTimestamp"),
            }
            for c in raw
        ]
        return {"status": "success", "commits": commits}
    except Exception as e:
        logger.error("get_commit_list failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to list commits for PR #{pr_id}: {e}") from e


@mcp.tool()
async def get_pull_request_tasks(
    project: str,
    repo: str,
    pr_id: int,
) -> Dict[str, Any]:
    """
    Retrieve open tasks (review items) on a pull request.

    :param project: Bitbucket project key.
    :param repo:    Repository slug.
    :param pr_id:   Pull request ID.

    :returns: ``{status, tasks: [{id, text, state, author}, …]}``.
    """
    client = get_bitbucket_client()
    try:
        raw = await client.get_pull_request_tasks(project, repo, pr_id)
        tasks = [
            {
                "id": t.get("id"),
                "text": t.get("text", ""),
                "state": t.get("state", "OPEN"),
                "author": t.get("author", {}).get("displayName",
                          t.get("author", {}).get("name", "")),
            }
            for t in raw
        ]
        return {"status": "success", "tasks": tasks}
    except Exception as e:
        logger.error("get_pull_request_tasks failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to fetch tasks for PR #{pr_id}: {e}") from e


# ================================================================== #
#                   COMMENT / TASK TOOLS                              #
# ================================================================== #

@mcp.tool()
async def create_pr_comment_draft(
    pr_id: int,
    comment: str,
    project: str,
    repo: str,
    file_path: Optional[str] = None,
    line: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a **local** draft comment — does NOT post to Bitbucket.

    This is useful for composing and previewing comments before submitting.
    Use ``post_pr_comment`` or ``post_inline_pr_comment`` to actually send.

    :param pr_id:     Pull request ID the draft is intended for.
    :param comment:   The draft comment body (Markdown).
    :param project:   Bitbucket project key.
    :param repo:      Repository slug.
    :param file_path: (Optional) file path for an inline comment draft.
    :param line:      (Optional) line number for an inline comment draft.

    :returns: The draft payload (for review before posting).
    """
    draft: Dict[str, Any] = {
        "status": "draft",
        "pr_id": pr_id,
        "project": project,
        "repo": repo,
        "comment": comment,
        "is_inline": file_path is not None,
    }
    if file_path:
        draft["file_path"] = file_path
    if line is not None:
        draft["line"] = line

    logger.info("Draft comment created for PR #%d (inline=%s)", pr_id, draft["is_inline"])
    return draft


@mcp.tool()
async def post_pr_comment(
    pr_id: int,
    comment: str,
    project: str,
    repo: str,
) -> Dict[str, Any]:
    """
    Post a general (top-level) comment on a Bitbucket pull request.

    :param pr_id:   Pull request ID to comment on.
    :param comment: The comment body (Markdown supported).
    :param project: Bitbucket project key.
    :param repo:    Repository slug.

    :returns: ``{status, message, comment_id}``.
    :raises ValueError: If posting fails.
    """
    client = get_bitbucket_client()
    logger.info("post_pr_comment called for PR #%d in %s/%s", pr_id, project, repo)

    try:
        result = await client.post_comment_async(project, repo, pr_id, comment)
        comment_id = result.get("id") if isinstance(result, dict) else None
        return {
            "status": "success",
            "message": f"Comment posted to PR #{pr_id} in {project}/{repo}",
            "comment_id": comment_id,
        }
    except Exception as e:
        logger.error("Failed to post comment to PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to post comment to PR #{pr_id}: {e}") from e


@mcp.tool()
async def post_inline_pr_comment(
    pr_id: int,
    comment: str,
    file_path: str,
    line: int,
    project: str,
    repo: str,
    line_type: str = "ADDED",
    file_type: str = "TO",
) -> Dict[str, Any]:
    """
    Post an inline comment on a specific file and line in a pull request.

    :param pr_id:     Pull request ID.
    :param comment:   The comment body (Markdown).
    :param file_path: Path of the file to comment on.
    :param line:      Line number to attach the comment to.
    :param project:   Bitbucket project key.
    :param repo:      Repository slug.
    :param line_type: ``ADDED``, ``REMOVED``, or ``CONTEXT`` (default ``ADDED``).
    :param file_type: ``FROM`` (old side) or ``TO`` (new side, default).

    :returns: ``{status, message, comment_id}``.
    :raises ValueError: If posting fails.
    """
    client = get_bitbucket_client()
    logger.info(
        "post_inline_pr_comment: PR #%d, %s:%d in %s/%s",
        pr_id, file_path, line, project, repo,
    )

    try:
        result = await client.post_inline_comment(
            project, repo, pr_id, comment, file_path, line, line_type, file_type,
        )
        comment_id = result.get("id") if isinstance(result, dict) else None
        return {
            "status": "success",
            "message": f"Inline comment posted on {file_path}:{line} in PR #{pr_id}",
            "comment_id": comment_id,
        }
    except Exception as e:
        logger.error("post_inline_pr_comment failed for PR #%d: %s", pr_id, e)
        raise ValueError(
            f"Failed to post inline comment on {file_path}:{line} in PR #{pr_id}: {e}"
        ) from e


@mcp.tool()
async def add_pull_request_task(
    pr_id: int,
    text: str,
    project: str,
    repo: str,
) -> Dict[str, Any]:
    """
    Create a new review task on a pull request.

    :param pr_id:   Pull request ID.
    :param text:    Task description.
    :param project: Bitbucket project key.
    :param repo:    Repository slug.

    :returns: ``{status, message, task_id}``.
    :raises ValueError: If task creation fails.
    """
    client = get_bitbucket_client()
    logger.info("add_pull_request_task: PR #%d in %s/%s", pr_id, project, repo)

    try:
        result = await client.add_pull_request_task(project, repo, pr_id, text)
        task_id = result.get("id") if isinstance(result, dict) else None
        return {
            "status": "success",
            "message": f"Task created on PR #{pr_id} in {project}/{repo}",
            "task_id": task_id,
        }
    except Exception as e:
        logger.error("add_pull_request_task failed for PR #%d: %s", pr_id, e)
        raise ValueError(f"Failed to create task on PR #{pr_id}: {e}") from e


# ================================================================== #
#  Legacy tool kept for backward-compatibility (now delegates)        #
# ================================================================== #

@mcp.tool()
async def post_bitbucket_comment(
    pr_id: int,
    comment: str,
    project: str,
    repo: str,
) -> dict:
    """
    **Legacy wrapper** – posts a top-level PR comment.
    Prefer ``post_pr_comment`` for new integrations.

    :param pr_id:   Pull request ID.
    :param comment: Comment body.
    :param project: Bitbucket project key.
    :param repo:    Repository slug.

    :returns: ``{status, message}``.
    :raises ValueError: If posting fails.
    """
    return await post_pr_comment(pr_id, comment, project, repo)


# ================================================================== #
#  Mount & run
# ================================================================== #

app.mount("/", mcp_app)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.mcp_server_host, port=settings.mcp_server_port)
