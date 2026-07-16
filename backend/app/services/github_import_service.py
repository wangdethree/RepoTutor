from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.utils.safe_zip import MAX_ZIP_BYTES


class GitHubImportError(ValueError):
    """GitHub 仓库导入失败时抛出，API 层会转换成 400 响应。"""


@dataclass(frozen=True)
class GitHubRepositoryRef:
    """已校验的公开 GitHub 仓库引用。"""

    owner: str
    repo: str
    url: str

    @property
    def zipball_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}/zipball"

    @property
    def archive_filename(self) -> str:
        return f"{self.owner}-{self.repo}.zip"

    def to_dict(self) -> dict[str, str]:
        return {
            "owner": self.owner,
            "repo": self.repo,
            "url": self.url,
            "zipball_url": self.zipball_url,
        }


class GitHubImportService:
    """只下载公开 GitHub 仓库 ZIP，不执行仓库代码。"""

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout

    def parse_repository_url(self, value: str) -> GitHubRepositoryRef:
        """严格限制为 https://github.com/{owner}/{repo}，拒绝分支、子目录和查询参数。"""

        raw_url = value.strip()
        parsed = urlparse(raw_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise GitHubImportError("仅支持 https://github.com/{owner}/{repo} 形式的公开仓库地址")
        if parsed.query or parsed.fragment:
            raise GitHubImportError("GitHub 仓库地址不能包含查询参数或锚点")

        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) != 2:
            raise GitHubImportError("仅支持仓库根地址，不支持分支、子目录或文件地址")

        owner, repo = parts
        if not self._is_valid_owner(owner) or not self._is_valid_repo(repo):
            raise GitHubImportError("GitHub owner 或 repo 名称格式不合法")

        return GitHubRepositoryRef(owner=owner, repo=repo, url=f"https://github.com/{owner}/{repo}")

    def download_zip(self, github_url: str, target_zip: Path) -> GitHubRepositoryRef:
        """下载公开仓库 zipball，并在写入过程中限制最大体积。"""

        repo_ref = self.parse_repository_url(github_url)
        target_zip.parent.mkdir(parents=True, exist_ok=True)

        request = urllib.request.Request(
            repo_ref.zipball_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "RepoTutor/1.1",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content_length = self._content_length(response.headers.get("Content-Length"))
                if content_length and content_length > MAX_ZIP_BYTES:
                    raise GitHubImportError("GitHub 仓库 ZIP 超过 20 MB 限制")

                written = 0
                with target_zip.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > MAX_ZIP_BYTES:
                            raise GitHubImportError("GitHub 仓库 ZIP 超过 20 MB 限制")
                        output.write(chunk)
        except urllib.error.HTTPError as exc:
            target_zip.unlink(missing_ok=True)
            if exc.code == 404:
                raise GitHubImportError("无法下载公开仓库，请确认仓库存在且可访问") from exc
            if exc.code == 403:
                raise GitHubImportError("GitHub 暂时拒绝下载请求，可能触发了访问频率限制") from exc
            raise GitHubImportError(f"GitHub 下载失败，HTTP 状态码: {exc.code}") from exc
        except urllib.error.URLError as exc:
            target_zip.unlink(missing_ok=True)
            raise GitHubImportError(f"GitHub 下载失败: {exc.reason}") from exc
        except GitHubImportError:
            target_zip.unlink(missing_ok=True)
            raise

        return repo_ref

    def detect_repo_root(self, extract_dir: Path) -> Path:
        """GitHub zipball 通常带单个顶层目录，这里把仓库根目录收敛到该目录。"""

        children = [path for path in extract_dir.iterdir() if path.name != "__MACOSX"]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return extract_dir

    def _is_valid_owner(self, value: str) -> bool:
        if not 1 <= len(value) <= 39:
            return False
        if value.startswith("-") or value.endswith("-"):
            return False
        return all(char.isalnum() or char == "-" for char in value)

    def _is_valid_repo(self, value: str) -> bool:
        if not value:
            return False
        if value.endswith(".git"):
            return False
        return all(char.isalnum() or char in {"-", "_", "."} for char in value)

    def _content_length(self, value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
