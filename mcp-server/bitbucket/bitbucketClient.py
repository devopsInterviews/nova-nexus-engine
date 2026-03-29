"""
bitbucketClient.py
==================
Async-friendly wrapper around the ``atlassian-python-api`` Bitbucket Server
client.  Every public method that touches the network is **async** (offloads
the blocking HTTP call to a thread via ``asyncio.to_thread``).

Capabilities
------------
- File operations: fetch raw content, list files, blame
- Pull-request operations: metadata, diff, changed files, comments,
  activities, tasks, commits
- Build / CI status for a commit
- Repository code search
"""

from __future__ import annotations

import asyncio
import difflib
import requests
import logging
from typing import Any, Dict, List, Optional, Tuple

from atlassian import Bitbucket

logger = logging.getLogger(__name__)


class BitbucketClient:
    """Bitbucket Server client for interacting with repositories and pull requests."""

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #

    def __init__(
        self,
        base_url: str,
        access_token: str,
        bitbucket_ssl_verify: str = "False",
    ) -> None:
        verify = str(bitbucket_ssl_verify).strip().lower() in {
            "true", "1", "yes", "y", "on",
        }
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.verify_ssl = verify

        self.client = Bitbucket(
            url=base_url,
            token=access_token,
            cloud=False,
            verify_ssl=verify,
        )

    # --------------------------------------------------------------------- #
    #  Low-level helpers
    # --------------------------------------------------------------------- #

    def _get(self, api_path: str, params: Optional[dict] = None) -> Any:
        """Synchronous GET against the Bitbucket REST API (blocking)."""
        return self.client.get(api_path, params=params or {})

    def _post(self, api_path: str, data: Optional[dict] = None) -> Any:
        """Synchronous POST against the Bitbucket REST API (blocking)."""
        return self.client.post(api_path, data=data)

    def _put(self, api_path: str, data: Optional[dict] = None) -> Any:
        """Synchronous PUT against the Bitbucket REST API (blocking)."""
        return self.client.put(api_path, data=data)

    async def _async_get(self, api_path: str, params: Optional[dict] = None) -> Any:
        """Run a GET in a worker thread so the async loop stays responsive."""
        return await asyncio.to_thread(self._get, api_path, params)

    async def _async_post(self, api_path: str, data: Optional[dict] = None) -> Any:
        """Run a POST in a worker thread."""
        return await asyncio.to_thread(self._post, api_path, data)

    async def _async_put(self, api_path: str, data: Optional[dict] = None) -> Any:
        """Run a PUT in a worker thread."""
        return await asyncio.to_thread(self._put, api_path, data)

    def _pr_base(self, project: str, repo: str) -> str:
        """Return the REST base path for pull-requests."""
        return f"/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests"

    def _repo_base(self, project: str, repo: str) -> str:
        """Return the REST base path for a repository."""
        return f"/rest/api/1.0/projects/{project}/repos/{repo}"

    async def _paginate_get(
        self,
        api_path: str,
        params: Optional[dict] = None,
        limit: int = 500,
    ) -> List[Any]:
        """
        Transparently paginate a Bitbucket paged-API response.

        Bitbucket Server returns ``{ "values": [...], "isLastPage": bool,
        "nextPageStart": int }``.  This helper collects all pages into a
        single flat list of values.
        """
        params = dict(params or {})
        params.setdefault("limit", str(limit))
        all_values: List[Any] = []
        start = 0

        while True:
            params["start"] = str(start)
            resp = await self._async_get(api_path, params)
            if not isinstance(resp, dict):
                # Some endpoints return raw text; bail out gracefully.
                break
            all_values.extend(resp.get("values", []))
            if resp.get("isLastPage", True):
                break
            start = resp.get("nextPageStart", start + limit)

        return all_values

    # --------------------------------------------------------------------- #
    #  Repository information
    # --------------------------------------------------------------------- #

    async def list_repositories(
        self,
        project: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List all repositories in a Bitbucket project.

        :param project: Bitbucket project key.
        :param limit:   Maximum number of repositories to return.
        :returns:       List of repository dicts.
        """
        api_path = f"/rest/api/1.0/projects/{project}/repos"
        return await self._paginate_get(api_path, {"limit": str(limit)}, limit=limit)

    async def get_repository_info(
        self,
        project: str,
        repo: str,
    ) -> Dict[str, Any]:
        """
        Fetch metadata for a specific repository.

        :param project: Bitbucket project key.
        :param repo:    Repository slug.
        :returns:       Repository metadata dict.
        """
        api_path = f"{self._repo_base(project, repo)}"
        return await self._async_get(api_path)

    async def get_default_branch(
        self,
        project: str,
        repo: str,
    ) -> str:
        """
        Return the default branch display name (e.g. ``main``, ``master``).
        """
        api_path = f"{self._repo_base(project, repo)}/default-branch"
        resp = await self._async_get(api_path)
        return (resp or {}).get("displayId", "master")

    # --------------------------------------------------------------------- #
    #  Health / connectivity
    # --------------------------------------------------------------------- #

    def ping(self, project: str) -> bool:
        """Ping the Bitbucket server by fetching project metadata."""
        try:
            self.client.project(project)
            return True
        except Exception as e:
            logger.error("Bitbucket connection failed: %s", e)
            return False

    def pr_exists(self, project: str, repo: str, pr_id: int) -> bool:
        """Return *True* if *pr_id* exists, *False* otherwise."""
        try:
            pr = self.client.get_pull_request(project, repo, pr_id)
            return pr is not None
        except Exception as e:
            logger.warning("PR #%d not found: %s", pr_id, e)
            return False

    # --------------------------------------------------------------------- #
    #  File operations
    # --------------------------------------------------------------------- #

    async def fetch_file_path(
        self,
        project: str,
        repo: str,
        file_path: str,
        branch: Optional[str] = None,
        as_text: bool = True,
        encoding: str = "utf-8",
    ) -> str | bytes:
        """
        Fetch a file's raw contents from a Bitbucket repository.

        :param project:   Bitbucket project key.
        :param repo:      Repository slug.
        :param file_path: Path inside the repo (e.g. ``src/main.py``).
        :param branch:    Branch / tag / commit ref.  ``None`` → server default.
        :param as_text:   Decode to ``str`` when *True*, return ``bytes`` otherwise.
        :param encoding:  Encoding used when *as_text* is True.
        :returns:         File content as ``str`` or ``bytes``.
        :raises Exception: On any HTTP / decoding failure.
        """
        try:
            data = await asyncio.to_thread(
                self.client.get_content_of_file,
                project,
                repo,
                file_path,
                branch,
                None,  # markup → keep raw
            )
            if as_text and isinstance(data, (bytes, bytearray)):
                return data.decode(encoding, errors="replace")
            return data if not as_text else str(data)
        except Exception as e:
            logger.error(
                "Failed to fetch file (project=%s repo=%s path=%s at=%s): %s",
                project, repo, file_path, branch, e,
            )
            raise

    async def get_file_content(
        self,
        project: str,
        repo: str,
        path: str,
        at_ref: str = "refs/heads/master",
    ) -> str:
        """
        Retrieve the raw (decoded-UTF-8) content of *path* at *at_ref*.

        :param project: Bitbucket project key.
        :param repo:    Repository slug.
        :param path:    File path inside the repository.
        :param at_ref:  Branch, tag, or commit (``refs/heads/…`` or short name).
        :returns:       The file content as a string.
        """
        if not at_ref.startswith("refs/"):
            at_ref = f"refs/heads/{at_ref}"

        raw_bytes = await asyncio.to_thread(
            self.client.get_content_of_file,
            project,
            repo,
            path.lstrip("/"),
            at_ref,
            None,
        )

        try:
            return raw_bytes.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            if isinstance(raw_bytes, str):
                return raw_bytes
            return raw_bytes.decode("latin-1", errors="ignore")

    async def list_files(
        self,
        project: str,
        repo: str,
        path: str = "",
        at_ref: str = "refs/heads/master",
    ) -> List[str]:
        """
        List file paths under *path* at *at_ref*.

        :returns: Flat list of file paths (strings).
        """
        api_path = f"{self._repo_base(project, repo)}/files"
        if path:
            api_path += "/" + path.lstrip("/")

        return await self._paginate_get(api_path, {"at": at_ref})

    async def search_repository(
        self,
        project: str,
        repo: str,
        query: str,
        extension: Optional[str] = None,
        at_ref: str = "refs/heads/master",
        max_matches: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search for *query* across all files in the repository.

        Uses the Bitbucket Server code-search REST endpoint
        (``/rest/search/latest``).

        :param query:      Search string (keyword, regex fragment, etc.).
        :param extension:  Optional file extension filter (e.g. ``py``).
        :param at_ref:     Branch reference.
        :param max_matches: Cap on returned hits.
        :returns:          List of dicts ``{path, hitCount, lines: [...]}``.
        """
        # Bitbucket Server code search endpoint
        search_path = "/rest/search/latest/search"
        search_query = f"project:{project} repo:{repo} {query}"
        if extension:
            search_query += f" ext:{extension}"

        params = {
            "query": search_query,
            "type": "content",
            "limit": str(max_matches),
        }

        try:
            resp = await self._async_get(search_path, params)
            results: List[Dict[str, Any]] = []
            for val in (resp or {}).get("values", []):
                hit = val.get("hit", val)
                file_info = hit.get("file", {})
                results.append({
                    "path": file_info.get("path", hit.get("path", "")),
                    "hitCount": hit.get("hitCount", 0),
                    "lines": hit.get("lines", []),
                })
            return results
        except Exception as e:
            logger.error("Repository search failed: %s", e)
            # Fallback: use grep-style via file listing
            logger.info("Falling back to file-list + content search")
            return await self._fallback_search(project, repo, query, extension, at_ref, max_matches)

    async def _fallback_search(
        self,
        project: str,
        repo: str,
        query: str,
        extension: Optional[str],
        at_ref: str,
        max_matches: int,
    ) -> List[Dict[str, Any]]:
        """Simple fallback search: list files and check names for the query."""
        all_files = await self.list_files(project, repo, "", at_ref)
        results: List[Dict[str, Any]] = []
        for f in all_files:
            if extension and not f.endswith(f".{extension}"):
                continue
            if query.lower() in f.lower():
                results.append({"path": f, "hitCount": 0, "lines": []})
            if len(results) >= max_matches:
                break
        return results

    async def get_blame_line(
        self,
        project: str,
        repo: str,
        path: str,
        at_ref: str = "refs/heads/master",
    ) -> Dict[int, dict]:
        """
        Return blame info per line: ``{line_number: {author, commit}}``.
        """
        api_path = f"{self._repo_base(project, repo)}/annotate"
        params = {"path": path.lstrip("/"), "at": at_ref}
        resp = await self._async_get(api_path, params)

        blame_map: Dict[int, dict] = {}
        for seg in (resp or {}).get("segments", []):
            author = seg.get("author", {}).get("name", "unknown")
            commit = seg.get("commit", {}).get("id", "unknown")
            start = seg.get("startLine", 0)
            count = seg.get("lineCount", 0)
            for i in range(start, start + count):
                blame_map[i] = {"author": author, "commit": commit}
        return blame_map

    # --------------------------------------------------------------------- #
    #  Pull-request metadata
    # --------------------------------------------------------------------- #

    async def get_pull_request(
        self,
        project: str,
        repo: str,
        pr_id: int,
    ) -> Dict[str, Any]:
        """
        Fetch full metadata for a single pull request.

        :returns: Dict with keys like ``title``, ``description``, ``state``,
                  ``author``, ``fromRef``, ``toRef``, ``reviewers``,
                  ``createdDate``, ``updatedDate``, etc.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}"
        return await self._async_get(api_path)

    async def list_pull_requests(
        self,
        project: str,
        repo: str,
        state: str = "OPEN",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        List pull requests for *repo*.

        :param state: ``OPEN``, ``MERGED``, ``DECLINED``, or ``ALL``.
        :param limit: Maximum number of PRs to return.
        """
        api_path = self._pr_base(project, repo)
        params = {"state": state, "limit": str(limit)}
        return await self._paginate_get(api_path, params, limit=limit)

    # --------------------------------------------------------------------- #
    #  PR changed files & diff
    # --------------------------------------------------------------------- #

    async def list_pull_request_files(
        self,
        project: str,
        repo: str,
        pr_id: int,
    ) -> List[Dict[str, Any]]:
        """
        List *all* files changed in a pull request (paginated).

        :returns: List of ``{path, type}`` dicts.  ``type`` is one of
                  ``ADD``, ``MODIFY``, ``DELETE``, ``RENAME``, ``COPY``.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/changes"
        raw_changes = await self._paginate_get(api_path)
        files: List[Dict[str, Any]] = []
        for change in raw_changes:
            path_obj = change.get("path") or {}
            # Bitbucket Server returns the path as an object with a ``toString``
            # string field (not a Python method).  Fall back to joining components
            # when the shorthand key is absent.
            p: str = (
                path_obj.get("toString")
                or "/".join(path_obj.get("components", []))
                or path_obj.get("name", "")
            )
            ctype = change.get("type", "MODIFY")
            src_obj = change.get("srcPath") or {}
            entry: Dict[str, Any] = {"path": p, "type": ctype}
            if src_obj:
                entry["srcPath"] = (
                    src_obj.get("toString")
                    or "/".join(src_obj.get("components", []))
                    or src_obj.get("name", "")
                )
            files.append(entry)
        return files


    async def get_pull_request_diff(
        self,
        project: str,
        repo: str,
        pr_id: int,
        file_path: Optional[str] = None,
        context_lines: int = 10,
        src_path: Optional[str] = None,
    ) -> str:
        """
        Produce a unified diff for a pull request without touching any
        ``/diff`` or ``/raw`` endpoint.

        Strategy
        --------
        Both the Bitbucket Server ``/diff`` endpoint and the ``/raw/{path}``
        endpoint return HTTP 406 in many proxy / older-server setups.

        This implementation uses **only** endpoints that are proven to work:
        - ``/pull-requests/{id}``           → PR metadata (same as get_pull_request tool)
        - ``/pull-requests/{id}/changes``   → changed files  (same as list_pull_request_files tool)
        - ``/browse/{path}?at={commit}``    → file content as paginated JSON lines
                                              (JSON endpoint, same Accept: application/json
                                               pattern as every other working tool)

        The diff itself is computed locally with ``difflib.unified_diff``.
        """
        repo_base = self._repo_base(project, repo)

        # ── 1. Resolve commit SHAs from PR metadata ───────────────────────────
        logger.info(
            "get_pull_request_diff: fetching PR metadata  project=%s repo=%s pr=%d",
            project, repo, pr_id,
        )
        pr = await self.get_pull_request(project, repo, pr_id)
        from_ref  = pr.get("fromRef", {})
        to_ref    = pr.get("toRef",   {})

        # Prefer the exact commit SHA; fall back to the branch ref so the
        # browse endpoint still works on servers that omit latestCommit.
        from_commit: str = (
            from_ref.get("latestCommit")
            or from_ref.get("id", "")
        )
        to_commit: str = (
            to_ref.get("latestCommit")
            or to_ref.get("id", "")
        )
        logger.info(
            "get_pull_request_diff: from=%s  to=%s", from_commit[:12], to_commit[:12],
        )

        if not from_commit or not to_commit:
            raise ValueError(
                f"Could not resolve refs from PR #{pr_id} metadata: "
                f"fromRef={from_ref}  toRef={to_ref}"
            )

        # ── 2. Build file list ────────────────────────────────────────────────
        if file_path:
            entries: List[Tuple[str, str, str]] = [
                (src_path or file_path, file_path, "MODIFY")
            ]
        else:
            logger.info("get_pull_request_diff: fetching changed files")
            changed = await self.list_pull_request_files(project, repo, pr_id)
            entries = [
                (
                    f.get("srcPath") or f.get("path", ""),
                    f.get("path", ""),
                    f.get("type", "MODIFY"),
                )
                for f in changed
                if f.get("path")
            ]
        logger.info("get_pull_request_diff: %d file(s) to diff", len(entries))

        # ── 3. File-content helper via /browse/{path} ─────────────────────────
        async def _browse_lines(path: str, ref: str) -> List[str]:
            """
            Fetch file content using the /browse endpoint, which returns JSON
            with a ``lines`` array.  Paginates automatically.

            This is the same JSON-over-HTTP pattern used by all other working
            tools (get_pull_request, list_pull_request_files, etc.) so it is
            not subject to the 406 issues of /diff or /raw.
            """
            api_path = f"{repo_base}/browse/{path.lstrip('/')}"
            all_lines: List[str] = []
            start = 0

            while True:
                params = {"at": ref, "limit": "5000", "start": str(start)}
                logger.debug(
                    "browse  %s%s  params=%s", self.base_url, api_path, params
                )
                resp = await self._async_get(api_path, params)

                if not isinstance(resp, dict):
                    logger.warning(
                        "browse returned non-dict for %s@%s: %r", path, ref[:12], resp
                    )
                    break

                for line_obj in resp.get("lines", []):
                    all_lines.append(line_obj.get("text", "") + "\n")

                if resp.get("isLastPage", True):
                    break
                start = resp.get("nextPageStart", start + 5000)

            return all_lines

        async def _safe_browse(path: str, ref: str, label: str) -> List[str]:
            try:
                return await _browse_lines(path, ref)
            except Exception as exc:
                logger.warning(
                    "get_pull_request_diff: could not fetch %s (%s@%s): %s",
                    label, path, ref[:12], exc,
                )
                return []

        # ── 4. Diff each file concurrently ────────────────────────────────────
        async def _diff_one(old_p: str, new_p: str, change_type: str) -> str:
            old_lines: List[str] = (
                [] if change_type == "ADD"
                else await _safe_browse(old_p, from_commit, f"old:{old_p}")
            )
            new_lines: List[str] = (
                [] if change_type == "DELETE"
                else await _safe_browse(new_p, to_commit, f"new:{new_p}")
            )

            patch = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{old_p}",
                    tofile=f"b/{new_p}",
                    n=context_lines,
                )
            )
            return "".join(patch)

        results = await asyncio.gather(
            *[_diff_one(o, n, t) for o, n, t in entries]
        )
        diff_parts = [r for r in results if r]

        logger.info(
            "get_pull_request_diff: done, %d file(s) with changes", len(diff_parts)
        )
        return "\n".join(diff_parts) if diff_parts else "(no changes)"

    # --------------------------------------------------------------------- #
    #  PR comments
    # --------------------------------------------------------------------- #

    def post_comment(self, project: str, repo: str, pr_id: int, text: str) -> bool:
        """
        Add a top-level comment to an existing pull request (synchronous).

        :returns: *True* if Bitbucket accepted the comment.
        """
        logger.debug("Attempting to comment on PR #%d → %s/%s", pr_id, project, repo)

        if not self.ping(project):
            logger.error("Bitbucket unreachable – aborting comment post.")
            return False
        if not self.pr_exists(project, repo, pr_id):
            logger.error("PR #%d does not exist – cannot post comment.", pr_id)
            return False

        try:
            self.client.add_pull_request_comment(project, repo, pr_id, text)
            logger.info("Posted comment to PR #%d", pr_id)
            return True
        except Exception as e:
            logger.error("Failed to post PR comment: %s", e)
            return False

    async def post_comment_async(
        self,
        project: str,
        repo: str,
        pr_id: int,
        text: str,
    ) -> Dict[str, Any]:
        """
        Post a general (top-level) comment on a pull request.

        :returns: The comment payload returned by Bitbucket.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/comments"
        data = {"text": text}
        return await self._async_post(api_path, data)

    async def post_inline_comment(
        self,
        project: str,
        repo: str,
        pr_id: int,
        text: str,
        file_path: str,
        line: int,
        line_type: str = "ADDED",
        file_type: str = "TO",
    ) -> Dict[str, Any]:
        """
        Post an inline comment on a specific file and line in a PR.

        :param file_path:  The path of the file to comment on.
        :param line:       The line number to attach the comment to.
        :param line_type:  ``ADDED``, ``REMOVED``, or ``CONTEXT``.
        :param file_type:  ``FROM`` (old file) or ``TO`` (new file).
        :returns:          The comment payload from Bitbucket.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/comments"
        data = {
            "text": text,
            "anchor": {
                "path": file_path,
                "line": line,
                "lineType": line_type,
                "fileType": file_type,
            },
        }
        return await self._async_post(api_path, data)

    async def get_pull_request_comments(
        self,
        project: str,
        repo: str,
        pr_id: int,
    ) -> List[Dict[str, Any]]:
        """
        List *all* comments (top-level + inline) on a pull request.

        Each returned dict contains at least ``id``, ``text``, ``author``,
        ``createdDate``, and optionally ``anchor`` for inline comments.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/comments"
        return await self._paginate_get(api_path)

    # --------------------------------------------------------------------- #
    #  PR activities
    # --------------------------------------------------------------------- #

    async def get_pull_request_activities(
        self,
        project: str,
        repo: str,
        pr_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the activity stream for a pull request.

        Activities include approvals, review status changes, comment events,
        merge events, rescoped (force-push) events, etc.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/activities"
        return await self._paginate_get(api_path)

    # --------------------------------------------------------------------- #
    #  PR commits
    # --------------------------------------------------------------------- #

    async def get_pull_request_commits(
        self,
        project: str,
        repo: str,
        pr_id: int,
    ) -> List[Dict[str, Any]]:
        """
        List commits included in a pull request.

        Each commit dict contains ``id``, ``displayId``, ``message``,
        ``author``, ``authorTimestamp``, etc.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/commits"
        return await self._paginate_get(api_path)

    # --------------------------------------------------------------------- #
    #  PR tasks
    # --------------------------------------------------------------------- #

    async def get_pull_request_tasks(
        self,
        project: str,
        repo: str,
        pr_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve tasks (review items) attached to a pull request.
        """
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/tasks"
        try:
            return await self._paginate_get(api_path)
        except Exception:
            # Fallback for older Bitbucket versions that don't have /tasks
            logger.info("PR tasks endpoint not available, trying blocker endpoint")
            api_path_alt = f"{self._pr_base(project, repo)}/{pr_id}/blocker-comments"
            try:
                return await self._paginate_get(api_path_alt)
            except Exception as e2:
                logger.warning("Could not fetch PR tasks: %s", e2)
                return []

    async def add_pull_request_task(
        self,
        project: str,
        repo: str,
        pr_id: int,
        text: str,
    ) -> Dict[str, Any]:
        """
        Create a new task (review item) on a pull request.

        :param text: The task description / text.
        :returns:    The task payload from Bitbucket.
        """
        # First, we need to post a comment, then create a task anchored to it
        # Or use the tasks endpoint directly (Bitbucket 7.2+)
        api_path = f"{self._pr_base(project, repo)}/{pr_id}/tasks"
        # Newer Bitbucket API: direct task creation
        data = {
            "text": text,
            "state": "OPEN",
        }
        try:
            return await self._async_post(api_path, data)
        except Exception:
            # Fallback: post a comment first, then anchor a task to it
            logger.info("Direct task creation failed; posting comment-based task")
            comment = await self.post_comment_async(project, repo, pr_id, text)
            comment_id = comment.get("id")
            if not comment_id:
                raise ValueError("Failed to create anchor comment for task.")
            task_path = "/rest/api/1.0/tasks"
            task_data = {
                "anchor": {
                    "id": comment_id,
                    "type": "COMMENT",
                },
                "text": text,
                "state": "OPEN",
            }
            return await self._async_post(task_path, task_data)

    # --------------------------------------------------------------------- #
    #  Build / CI status
    # --------------------------------------------------------------------- #

    async def get_build_status(
        self,
        project: str,
        repo: str,
        pr_id: Optional[int] = None,
        commit_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get CI / pipeline build statuses for a commit.

        If *pr_id* is provided and *commit_id* is not, the latest commit
        on the PR is used automatically.

        :returns: List of build status dicts with ``state``, ``key``,
                  ``name``, ``url``, ``description``.
        """
        if not commit_id and pr_id:
            commits = await self.get_pull_request_commits(project, repo, pr_id)
            if not commits:
                return []
            commit_id = commits[0].get("id", "")

        if not commit_id:
            raise ValueError("Either pr_id or commit_id must be provided.")

        api_path = f"/rest/build-status/1.0/commits/{commit_id}"
        return await self._paginate_get(api_path)
