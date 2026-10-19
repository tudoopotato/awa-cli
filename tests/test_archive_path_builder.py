"""归档目录命名规则的最小测试（纯字符串/路径逻辑，无外部依赖）。"""

from __future__ import annotations

import re
from pathlib import Path

from awa.modules.archive.archive_path_builder import ArchivePathBuilder

# 目录名形如：2026-05-06 07-08 <清洗后的标题>__<12 位小写十六进制>
_DIRECTORY_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}-\d{2} .+__[0-9a-f]{12}$")
_INVALID_WINDOWS_CHARS = set('<>:"/\\|?*')


def test_build_directory_name_sanitizes_illegal_chars(tmp_path: Path) -> None:
    """验证点：目录名符合 'YYYY-MM-DD HH-MM <清洗标题>__<12位小写hex>'，且不含 Windows 非法字符。"""

    builder = ArchivePathBuilder(storage_root=tmp_path)
    archive = builder.build(
        account_name="示例账号:测试",
        article_title="标题?含*非法|字符",
        published_article_time="2026-05-06 07:08",
        article_link="https://mp.weixin.qq.com/s/abcdefghijk",
    )

    directory_name = archive.article_directory.name
    assert _DIRECTORY_NAME_RE.fullmatch(directory_name), directory_name
    assert directory_name.startswith("2026-05-06 07-08 ")
    assert "标题" in directory_name  # 非法字符只被替换，可读部分保留
    assert not (_INVALID_WINDOWS_CHARS & set(directory_name))

    # 文章身份键为 12 位小写十六进制。
    assert re.fullmatch(r"[0-9a-f]{12}", archive.article_key)

    # 相对路径为 posix 表示，且位于 storages 根之下；账号段同样被清洗。
    assert archive.relative_archive_dir.endswith(directory_name)
    assert archive.article_directory.is_relative_to(Path(tmp_path).resolve())
    account_segment = archive.article_directory.parent.name
    assert not (_INVALID_WINDOWS_CHARS & set(account_segment))
