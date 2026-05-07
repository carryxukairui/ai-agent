#!/usr/bin/env python3
"""
生成最终报表交付物空骨架：{报表名}.sql 与 {报表名}_说明.md
内容对齐 SKILL「交付物拆分」与 reference/报表说明文档模板.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from paths_util import (
    SKILL_DIR,
    resolve_workspace_path,
    workspace_base,
)

DEFAULT_CONFIG = SKILL_DIR / "config.yaml"
TEMPLATE_MD = SKILL_DIR / "reference" / "报表说明文档模板.md"

SQL_SKELETON = """-- ============================================
-- {title}
-- 标准报表 SQL（请基于「项目 output 目录」下 report_sql_context.md 中元数据补全）
-- ============================================

SELECT
    -- TODO: 仅使用元数据中的 schema.tableName 与 dbColumnName
    1 AS placeholder
WHERE 1 = 0;
"""


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _safe_filename_stem(name: str) -> str:
    """文件名用报表标题，去掉 Windows 非法字符。"""
    s = name.strip()
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, "_")
    return s or "未命名报表"


def _resolve_output_dir(cfg: dict, override: Path | None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    rel = (cfg.get("paths") or {}).get("report_deliverable_dir", "report_sql_output")
    return resolve_workspace_path(rel, cfg)


def _render_readme_template(report_name: str) -> str:
    if TEMPLATE_MD.exists():
        text = TEMPLATE_MD.read_text(encoding="utf-8")
        return text.replace("{报表名称}", report_name)
    return f"# {report_name} — 报表说明\n\n> 完整 SQL 见同目录 `{report_name}.sql`。\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="生成 {报表名}.sql 与 {报表名}_说明.md 空骨架（交付物拆分）。"
    )
    ap.add_argument(
        "report_title",
        nargs="?",
        help="报表名称，如：销售履约明细报表",
    )
    ap.add_argument(
        "-n",
        "--title",
        dest="title_opt",
        metavar="TITLE",
        help="与位置参数二选一，指定报表名称",
    )
    ap.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="config.yaml 路径（读取 paths.report_deliverable_dir）",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="覆盖输出目录；默认：项目 workspace 下 config 中的 report_deliverable_dir",
    )
    ap.add_argument(
        "--workspace-root",
        default=None,
        metavar="DIR",
        help="覆盖 paths.workspace_root（与 fetch_metadata 一致）",
    )
    ap.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="已存在同名文件时仍覆盖",
    )
    args = ap.parse_args()
    report_name = args.title_opt or args.report_title
    if not report_name or not str(report_name).strip():
        ap.error(
            "请提供报表名称，例如: python scaffold_report_deliverable.py '销售履约明细报表'\n"
            "或: python scaffold_report_deliverable.py --title '销售履约明细报表'"
        )

    report_name = str(report_name).strip()
    stem = _safe_filename_stem(report_name)

    cfg_path = Path(args.config).expanduser().resolve()
    cfg = _load_config(cfg_path)
    if getattr(args, "workspace_root", None) and str(args.workspace_root).strip():
        cfg.setdefault("paths", {})["workspace_root"] = str(args.workspace_root).strip()
    out_dir = _resolve_output_dir(cfg, args.output_dir)
    print(f"Workspace (outputs): {workspace_base(cfg)}", file=sys.stderr)
    out_dir.mkdir(parents=True, exist_ok=True)

    sql_path = out_dir / f"{stem}.sql"
    md_path = out_dir / f"{stem}_说明.md"

    for p in (sql_path, md_path):
        if p.exists() and not args.force:
            print(f"已存在，跳过（加 --force 覆盖）: {p}", file=sys.stderr)
            return 1

    sql_path.write_text(SQL_SKELETON.format(title=report_name), encoding="utf-8")
    md_path.write_text(_render_readme_template(report_name), encoding="utf-8")

    print(f"Wrote {sql_path}", file=sys.stderr)
    print(f"Wrote {md_path}", file=sys.stderr)
    print(str(sql_path))
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
