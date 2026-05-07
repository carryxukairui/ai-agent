#!/usr/bin/env python3
"""
运行数据库诊断 SQL 和校验用户交付的报表 SQL 文件。
支持 MySQL / PostgreSQL / Oracle，使用 --sql-file 时依赖 sqlparse 拆分语句。
"""
from __future__ import annotations

import argparse
import datetime
import decimal
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 确保 scripts 目录在 sys.path 中（支持直接执行脚本）
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# 添加common目录到sys.path，导入共享模块
_skills_dir = _scripts_dir.parent.parent
_common_dir = _skills_dir / "common"
if str(_common_dir) not in sys.path:
    sys.path.insert(0, str(_common_dir))

import yaml

from utils import (
    ExitCode,
    load_dotenv,
    load_yaml,
    resolve_config,
    str_to_bool,
    truncate_sql,
    validate_database_config,
)
from logging_config import get_logger, setup_logging
from python_version_check import require_python_version

from console_utf8 import configure_stdio_utf8

# 全局日志记录器
logger = get_logger("db_query")

_EXPLAIN_MAX_ROWS = 512


def _json_default(obj: Any) -> Any:
    """json.dumps default handler for DB driver types (datetime, Decimal, bytes, etc.)."""
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, datetime.timedelta):
        return str(obj)
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def _skill_dir() -> Path:
    return _scripts_dir().parent


def _env_flag(*names: str, default: str = "1") -> str:
    """First non-empty env among names wins; else default."""
    for n in names:
        if n in os.environ:
            v = os.environ[n].strip()
            if v:
                return v
    return default


def _auto_pip_enabled() -> bool:
    v = _env_flag(
        "YONBIP_C_REPORT_SQL_GEN_AUTO_PIP",
        "REPORT_SQL_GEN_AUTO_PIP",
    ).lower()
    return v not in ("0", "false", "no", "off")


def _auto_venv_enabled() -> bool:
    v = _env_flag(
        "YONBIP_C_REPORT_SQL_GEN_AUTO_VENV",
        "REPORT_SQL_GEN_AUTO_VENV",
    ).lower()
    return v not in ("0", "false", "no", "off")


def _requirements_path() -> Path:
    return _scripts_dir() / "requirements.txt"


def _pip_packages_for_driver(driver: str) -> List[str]:
    """
    Minimal wheels for db_query only (avoids full requirements.txt e.g. cx_Oracle
    failing to build and blocking pymysql install).
    """
    d = (driver or "mysql").lower()
    base = ["PyYAML>=6.0", "sqlparse>=0.4.4"]
    if d == "mysql":
        return base + ["pymysql>=1.1.0"]
    if d in ("postgresql", "postgres", "pg"):
        return base + ["psycopg2-binary>=2.9.9"]
    if d in ("oracle", "cx_oracle"):
        return base + ["cx-Oracle>=8.3.0"]
    if d in ("dm", "dmdb", "dameng"):
        return base + ["dmPython>=1.2.0"]
    if d in ("mssql", "sqlserver", "sql_server"):
        return base + ["pymssql>=2.2.0"]
    return base


def _pip_install_for_driver(py: Path, driver: str) -> bool:
    """pip install minimal packages for this driver using the given interpreter."""
    pkgs = _pip_packages_for_driver(driver)
    logger.info(f"Installing DB-check dependencies: {' '.join(pkgs)}")
    r = subprocess.run(
        [str(py), "-m", "pip", "install", *pkgs],
        check=False,
    )
    return r.returncode == 0


def _venv_python_path() -> Path:
    vdir = _scripts_dir() / ".venv"
    if sys.platform == "win32":
        return vdir / "Scripts" / "python.exe"
    return vdir / "bin" / "python"


def _skill_venv_root() -> Path:
    return (_scripts_dir() / ".venv").resolve()


def _using_skill_venv() -> bool:
    """
    True when this process was started with the skill's .venv (sys.prefix matches).
    Do not compare sys.executable to .venv/bin/python: on Homebrew, venv shims often
    resolve to the same binary as `python3`, but site-packages differ until re-exec.
    """
    vdir = _skill_venv_root()
    if not vdir.is_dir():
        return False
    try:
        return Path(sys.prefix).resolve() == vdir
    except OSError:
        return False


def _try_import(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _ensure_db_driver(driver: str) -> None:
    """
    Ensure DB driver module is importable: try same-interpreter pip, then optional
    scripts/.venv bootstrap + os.execv (PEP 668 / Homebrew Python).
    """
    driver = (driver or "mysql").lower()
    mod: Optional[str]
    if driver == "mysql":
        mod = "pymysql"
    elif driver in ("postgresql", "postgres", "pg"):
        mod = "psycopg2"
    elif driver in ("oracle", "cx_oracle"):
        mod = "cx_Oracle"
    elif driver in ("dm", "dmdb", "dameng"):
        mod = "dmPython"
    elif driver in ("mssql", "sqlserver", "sql_server"):
        mod = "pymssql"
    else:
        return

    if _try_import(mod):
        return

    if not _auto_pip_enabled():
        raise ImportError(
            f"Missing Python module {mod}. Set YONBIP_C_REPORT_SQL_GEN_AUTO_PIP=1 "
            f"or run: pip install {' '.join(_pip_packages_for_driver(driver))}"
        )

    if _pip_install_for_driver(Path(sys.executable), driver) and _try_import(mod):
        return

    if not _auto_venv_enabled():
        raise ImportError(
            f"Missing Python module {mod} and direct pip install failed. "
            f"Create scripts/.venv and pip install minimal deps, or set "
            f"YONBIP_C_REPORT_SQL_GEN_AUTO_VENV=1."
        )

    vpy = _venv_python_path()
    vdir = _scripts_dir() / ".venv"
    if not vpy.is_file():
        logger.info("Creating scripts/.venv (PEP 668 workaround)...")
        subprocess.run([sys.executable, "-m", "venv", str(vdir)], check=False)
    if not vpy.is_file():
        raise ImportError(
            f"Could not create venv at {vdir}. Install python3-venv, then retry."
        )

    if not _using_skill_venv():
        if not _pip_install_for_driver(vpy, driver):
            raise ImportError(f"pip install into {vpy} failed.")
        script = str(Path(__file__).resolve())
        argv = [str(vpy), script, *sys.argv[1:]]
        # PEP 668 workaround: re-exec in venv after creating and installing
        # Note: os.execv replaces the current process.
        # This does not work well within IDE debuggers or test runners,
        # but works correctly in normal shell environments.
        os.execv(str(vpy), argv)

    if not _pip_install_for_driver(vpy, driver) or not _try_import(mod):
        raise ImportError(f"Still missing Python module {mod} after installing into {vpy}.")


def _pip_install_sqlparse_only(py: Path) -> bool:
    logger.info("Installing sqlparse for --sql-file...")
    r = subprocess.run(
        [str(py), "-m", "pip", "install", "sqlparse>=0.4.4"],
        check=False,
    )
    return r.returncode == 0


def _ensure_sqlparse() -> None:
    """Import sqlparse for --sql-file; same auto-pip / venv re-exec policy as DB drivers."""
    if _try_import("sqlparse"):
        return
    if not _auto_pip_enabled():
        raise ImportError(
            "Missing sqlparse (needed for --sql-file). "
            "Set YONBIP_C_REPORT_SQL_GEN_AUTO_PIP=1 or run: pip install sqlparse>=0.4.4"
        )
    if _pip_install_sqlparse_only(Path(sys.executable)) and _try_import("sqlparse"):
        return
    if not _auto_venv_enabled():
        raise ImportError(
            "Missing sqlparse and pip install failed. "
            "Create scripts/.venv or set YONBIP_C_REPORT_SQL_GEN_AUTO_VENV=1."
        )
    vpy = _venv_python_path()
    vdir = _scripts_dir() / ".venv"
    if not vpy.is_file():
        logger.info("Creating scripts/.venv for sqlparse...")
        subprocess.run([sys.executable, "-m", "venv", str(vdir)], check=False)
    if not vpy.is_file():
        raise ImportError(f"Could not create venv at {vdir}.")
    if not _using_skill_venv():
        if not _pip_install_sqlparse_only(vpy):
            raise ImportError(f"pip install sqlparse into {vpy} failed.")
        logger.info(f"Re-executing with {vpy}...")
        script = str(Path(__file__).resolve())
        # PEP 668 workaround: re-exec in venv after creating and installing
        # Note: os.execv replaces the current process.
        # This does not work well within IDE debuggers or test runners,
        # but works correctly in normal shell environments.
        os.execv(str(vpy), [str(vpy), script, *sys.argv[1:]])
    if not _try_import("sqlparse"):
        raise ImportError(f"Still missing sqlparse after install.")


# ============================================================
# SQL 语句分类与处理
# ============================================================


def _strip_leading_comments_snippet(s: str) -> str:
    """Remove leading -- and /* */ comment blocks from a statement fragment."""
    t = s
    while True:
        t = t.lstrip()
        if not t:
            return ""
        if t.startswith("--"):
            nl = t.find("\n")
            if nl == -1:
                return ""
            t = t[nl + 1 :]
            continue
        if t.startswith("/*"):
            end = t.find("*/")
            if end == -1:
                return ""
            t = t[end + 2 :]
            continue
        break
    return t


def _classify_statement(stmt: str) -> str:
    """分类 SQL 语句类型"""
    head = _strip_leading_comments_snippet(stmt).strip()
    if not head:
        return "empty"
    if head.upper().startswith("EXPLAIN PLAN FOR"):
        return "explain"
    m = re.match(r"(\w+)", head, re.I)
    if not m:
        return "other"
    kw = m.group(1).upper()
    mapping: Dict[str, str] = {
        "SELECT": "select",
        "WITH": "select",
        "EXPLAIN": "explain",
        "INSERT": "dml",
        "UPDATE": "dml",
        "DELETE": "dml",
        "REPLACE": "dml",
        "MERGE": "dml",
        "CREATE": "ddl",
        "ALTER": "ddl",
        "DROP": "ddl",
        "TRUNCATE": "ddl",
        "RENAME": "ddl",
        "SHOW": "show",
        "DESCRIBE": "show",
        "DESC": "show",
        "USE": "session",
        "SET": "session",
        "CALL": "proc",
        "EXECUTE": "proc",
        "EXEC": "proc",
    }
    return mapping.get(kw, "other")


def _split_statements_sql(sql_text: str) -> List[str]:
    """Split script into statements (respects quotes/comments via sqlparse)."""
    import sqlparse

    parts = sqlparse.split(sql_text)
    return [p.strip() for p in parts if p.strip()]


def _already_explain(driver: str, stmt: str) -> bool:
    h = _strip_leading_comments_snippet(stmt).strip().upper()
    if h.startswith("EXPLAIN PLAN FOR"):
        return True
    if driver == "mysql" and h.startswith("EXPLAIN FORMAT=JSON"):
        return True
    if driver in ("mssql", "sqlserver", "sql_server") and "SET SHOWPLAN_XML" in h:
        return True
    return h.startswith("EXPLAIN ")


def _wrap_explain_sql(cfg: dict, driver: str, stmt: str) -> str:
    """Build EXPLAIN statement; MySQL uses FORMAT=JSON for optimizer tree when enabled."""
    st = stmt.strip()
    if _already_explain(driver, st):
        return st
    db = cfg.get("database") or {}
    if driver == "mysql":
        if db.get("report_sql_mysql_explain_json", True):
            return "EXPLAIN FORMAT=JSON " + st
        return "EXPLAIN " + st
    if driver in ("postgresql", "postgres", "pg"):
        return "EXPLAIN (FORMAT JSON) " + st
    if driver in ("oracle", "cx_oracle"):
        return "EXPLAIN PLAN FOR " + st
    if driver in ("dm", "dmdb", "dameng"):
        return "EXPLAIN PLAN FOR " + st
    if driver in ("mssql", "sqlserver", "sql_server"):
        return "SET SHOWPLAN_XML ON; " + st
    return st


# ============================================================
# 数据库连接与查询
# ============================================================


def _get_db_connection(cfg: dict, driver: str):
    """根据驱动类型创建数据库连接"""
    db = cfg.get("database") or {}

    try:
        if driver == "mysql":
            import pymysql

            return pymysql.connect(
                host=db.get("host", "127.0.0.1"),
                port=int(db.get("port", 3306)),
                user=db.get("user", ""),
                password=db.get("password", ""),
                database=db.get("database", ""),
                charset=db.get("charset", "utf8mb4"),
                cursorclass=pymysql.cursors.DictCursor,
            )

        elif driver in ("postgresql", "postgres", "pg"):
            import psycopg2
            import psycopg2.extras

            return psycopg2.connect(
                host=db.get("host", "127.0.0.1"),
                port=int(db.get("port", 5432)),
                user=db.get("user", ""),
                password=db.get("password", ""),
                dbname=db.get("database", ""),
                sslmode=db.get("sslmode", "prefer"),
            )

        elif driver in ("oracle", "cx_oracle"):
            import cx_Oracle

            host = db.get("host", "127.0.0.1")
            port = int(db.get("port", 1521))
            service_name = db.get("service_name", "ORCL")
            user = db.get("user", "")
            password = db.get("password", "")
            dsn = cx_Oracle.makedsn(host, port, service_name=service_name)
            return cx_Oracle.connect(user=user, password=password, dsn=dsn, encoding="UTF-8")

        elif driver in ("dm", "dmdb", "dameng"):
            import dmPython

            host = db.get("host", "127.0.0.1")
            port = int(db.get("port", 5236))
            user = db.get("user", "")
            password = db.get("password", "")
            database = (db.get("database") or "").strip()
            # dmPython支持多种连接方式；无 database 时只连 host:port（达梦无独立「库名」场景）
            try:
                if database:
                    return dmPython.connect(
                        user=user,
                        password=password,
                        host=host,
                        port=port,
                        database=database,
                    )
                return dmPython.connect(
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                )
            except TypeError:
                if database:
                    return dmPython.connect(user, password, host, port, database)
                return dmPython.connect(user, password, host, port)

        elif driver in ("mssql", "sqlserver", "sql_server"):
            import pymssql

            host = db.get("host", "127.0.0.1")
            port = int(db.get("port", 1433))
            user = db.get("user", "")
            password = db.get("password", "")
            database = db.get("database", "")
            charset = db.get("charset", "utf8")
            return pymssql.connect(
                server=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset=charset,
            )

        else:
            raise ValueError(f"Unsupported driver: {driver}")

    except (ValueError, ImportError):
        raise
    except Exception as e:
        raise ConnectionError(
            f"数据库连接失败！\n"
            f"  数据库类型: {driver}\n"
            f"  连接地址: {db.get('host', '?')}:{db.get('port', '?')}\n"
            f"  用户: {db.get('user', '?')}\n"
            f"  数据库: {db.get('database', '?')}\n"
            f"  错误详情: {e}\n"
            f"请检查 .env 文件或 config.yaml 中的数据库配置是否正确，并确认数据库服务已启动。"
        ) from e


def _format_db_info(cfg: dict, driver: str) -> str:
    """格式化数据库连接信息用于日志输出（不包含密码等敏感信息）"""
    db = cfg.get("database") or {}
    return (
        f"数据库类型={driver}, "
        f"主机={db.get('host', '')}, "
        f"端口={db.get('port', '')}, "
        f"用户={db.get('user', '')}, "
        f"数据库={db.get('database', '')}"
    )


def _get_columns_from_description(description) -> List[str]:
    """从cursor.description提取列名并转小写"""
    if not description:
        return []
    columns: List[str] = []
    for col_desc in description:
        if isinstance(col_desc, str):
            columns.append(col_desc.lower())
        else:
            # 元组格式: (name, type_code, ...)
            columns.append(col_desc[0].lower())
    return columns


def _execute_query(
    cfg: dict, driver: str, sql: str, max_rows: int = 50
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    执行查询并返回结果

    Returns:
        (rows, truncated) - 行列表和是否截断标志
    """
    driver = driver.lower()
    conn = _get_db_connection(cfg, driver)

    try:
        if driver == "mysql":
            import pymysql
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = list(cur.fetchmany(max_rows))
                truncated = cur.fetchone() is not None
                return rows, truncated

        elif driver in ("postgresql", "postgres", "pg"):
            import psycopg2
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = [dict(r) for r in cur.fetchmany(max_rows)]
                truncated = cur.fetchone() is not None
                return rows, truncated

        elif driver in ("oracle", "cx_oracle"):
            import cx_Oracle
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = _get_columns_from_description(cur.description)
                batch = cur.fetchmany(max_rows)
                rows = [dict(zip(columns, row)) for row in batch]
                truncated = cur.fetchone() is not None
                return rows, truncated

        elif driver in ("dm", "dmdb", "dameng"):
            import dmPython
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = _get_columns_from_description(cur.description)
                batch = cur.fetchmany(max_rows)
                rows = [dict(zip(columns, row)) for row in batch]
                truncated = cur.fetchone() is not None
                return rows, truncated

        elif driver in ("mssql", "sqlserver", "sql_server"):
            import pymssql
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = _get_columns_from_description(cur.description)
                batch = cur.fetchmany(max_rows)
                rows = [dict(zip(columns, row)) for row in batch]
                truncated = cur.fetchone() is not None
                return rows, truncated

        else:
            raise ValueError(f"Unsupported driver: {driver}")
    finally:
        conn.close()


def _run_oracle_explain_plan(cfg: dict, stmt: str) -> List[Dict[str, Any]]:
    """Run EXPLAIN PLAN FOR and return DBMS_XPLAN rows when possible."""
    import cx_Oracle

    s = stmt.strip()
    if not s.upper().startswith("EXPLAIN PLAN FOR"):
        s = "EXPLAIN PLAN FOR " + s

    conn = _get_db_connection(cfg, "oracle")
    try:
        with conn.cursor() as cur:
            cur.execute(s)
            try:
                cur.execute(
                    "SELECT PLAN_TABLE_OUTPUT FROM TABLE(DBMS_XPLAN.DISPLAY())"
                )
                cols = [c[0].lower() for c in cur.description]
                rows = cur.fetchmany(_EXPLAIN_MAX_ROWS)
                return [dict(zip(cols, r)) for r in rows]
            except Exception:
                return [
                    {
                        "plan_table_note": (
                            "EXPLAIN PLAN FOR executed; DBMS_XPLAN.DISPLAY "
                            "unavailable or failed"
                        )
                    }
                ]
    finally:
        conn.close()


def _enrich_mysql_explain_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """If FORMAT=JSON returned a string column, parse JSON for readable output."""
    import json

    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and v.strip().startswith("{"):
                try:
                    d[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    pass
        out.append(d)
    return out


# ============================================================
# SQL 文件校验
# ============================================================


@dataclass
class ValidationResult:
    """SQL 校验结果"""
    ok: bool = True
    kind: str = ""
    skipped: bool = False
    skip_reason: Optional[str] = None
    executed_sql: Optional[str] = None
    mode: Optional[str] = None
    rows: List[Dict[str, Any]] = field(default_factory=list)
    rows_truncated: bool = False
    error: Optional[str] = None
    execution_plan_validated: bool = False
    sample_execution: Optional[Dict[str, Any]] = None
    validation_stage: Optional[str] = None
    index: Optional[int] = None


def _validate_one_statement(
    cfg: dict,
    driver: str,
    stmt: str,
    index: int,
    max_data_rows: int,
    explain_default: bool,
    execute_sample: bool,
) -> ValidationResult:
    """校验单个 SQL 语句"""
    kind = _classify_statement(stmt)

    result = ValidationResult(
        index=index,
        kind=kind,
        executed_sql=truncate_sql(stmt),
    )

    # 空语句
    if kind == "empty":
        result.ok = True
        result.skipped = True
        result.skip_reason = "empty_statement"
        return result

    # DDL - 跳过
    if kind == "ddl":
        result.ok = True
        result.skipped = True
        result.skip_reason = "ddl_not_executed"
        return result

    # 会话语句 - 跳过
    if kind == "session":
        result.ok = True
        result.skipped = True
        result.skip_reason = "session_use_set_skipped"
        return result

    # 存储过程 - 跳过
    if kind == "proc":
        result.ok = True
        result.skipped = True
        result.skip_reason = "procedure_call_skipped"
        return result

    # 确定执行模式和 SQL
    sql_run: Optional[str] = None
    mode: str = "execute"

    if kind == "explain":
        if driver in ("oracle", "cx_oracle"):
            sql_run = _oracle_explain_stmt_to_plan_sql(stmt)
            mode = "explain"
        elif driver in ("dm", "dmdb", "dameng"):
            sql_run = _dm_explain_stmt_to_plan_sql(stmt)
            mode = "explain"
        else:
            sql_run = stmt.strip()
            mode = "explain"

    elif kind == "dml":
        sql_run = (
            stmt.strip()
            if _already_explain(driver, stmt)
            else _wrap_explain_sql(cfg, driver, stmt)
        )
        mode = "explain"

    elif kind == "show":
        sql_run = stmt.strip()
        mode = "execute"

    elif kind == "select":
        if explain_default:
            sql_run = (
                stmt.strip()
                if _already_explain(driver, stmt)
                else _wrap_explain_sql(cfg, driver, stmt)
            )
            mode = "explain"
        else:
            sql_run = stmt.strip()
            mode = "execute"

    else:
        if explain_default:
            sql_run = (
                stmt.strip()
                if _already_explain(driver, stmt)
                else _wrap_explain_sql(cfg, driver, stmt)
            )
            mode = "explain"
        else:
            sql_run = stmt.strip()
            mode = "execute"

    if sql_run is None:
        result.ok = False
        result.error = "Failed to prepare SQL for execution"
        return result

    try:
        _ensure_db_driver(driver)

        # Oracle EXPLAIN
        if driver in ("oracle", "cx_oracle") and mode == "explain":
            rows = _run_oracle_explain_plan(cfg, sql_run)
            result.ok = True
            result.executed_sql = truncate_sql(sql_run)
            result.mode = mode
            result.rows = rows
            result.execution_plan_validated = True

        # 达梦 EXPLAIN
        elif driver in ("dm", "dmdb", "dameng") and mode == "explain":
            rows = _run_dm_explain_plan(cfg, sql_run)
            result.ok = True
            result.executed_sql = truncate_sql(sql_run)
            result.mode = mode
            result.rows = rows
            result.execution_plan_validated = True

        # SQL Server EXPLAIN
        elif driver in ("mssql", "sqlserver", "sql_server") and mode == "explain":
            rows = _run_mssql_explain_plan(cfg, stmt.strip())
            result.ok = True
            result.executed_sql = truncate_sql(stmt.strip())
            result.mode = mode
            result.rows = rows
            result.execution_plan_validated = True

        # 直接执行
        elif mode == "execute":
            rows, truncated = _execute_query(cfg, driver, sql_run, max_data_rows)
            result.ok = True
            result.executed_sql = truncate_sql(sql_run)
            result.mode = mode
            result.rows = rows
            result.rows_truncated = truncated
            result.execution_plan_validated = False

        # EXPLAIN 执行
        else:
            rows, truncated = _execute_query(cfg, driver, sql_run, _EXPLAIN_MAX_ROWS)
            if driver == "mysql" and "FORMAT=JSON" in sql_run.upper():
                rows = _enrich_mysql_explain_rows(rows)
            result.ok = True
            result.executed_sql = truncate_sql(sql_run)
            result.mode = mode
            result.rows = rows[:_EXPLAIN_MAX_ROWS]
            result.rows_truncated = len(rows) > _EXPLAIN_MAX_ROWS
            result.execution_plan_validated = True

        # 示例执行（EXPLAIN 成功后）
        if result.ok and not result.skipped and explain_default and execute_sample and mode == "explain" and kind == "select":
            try:
                srows, strunc = _execute_query(cfg, driver, stmt.strip(), max_data_rows)
                result.sample_execution = {
                    "sql": truncate_sql(stmt.strip()),
                    "rows": srows,
                    "rows_truncated": strunc,
                }
                result.validation_stage = "execution_plan_then_sample"
            except Exception as e:
                result.ok = False
                result.error = f"Execution plan OK but sample run failed: {e}"
                result.sample_execution = None

    except Exception as e:
        result.ok = False
        result.error = str(e)

    return result


def _oracle_explain_stmt_to_plan_sql(stmt: str) -> str:
    """Normalize MySQL-style EXPLAIN ... or plain SQL to EXPLAIN PLAN FOR ... (Oracle)."""
    s = stmt.strip()
    if s.upper().startswith("EXPLAIN PLAN FOR"):
        return s
    if s.upper().startswith("EXPLAIN"):
        inner = re.sub(r"^\s*EXPLAIN\s+", "", s, count=1, flags=re.I)
        return "EXPLAIN PLAN FOR " + inner.strip()
    return "EXPLAIN PLAN FOR " + s


def _dm_explain_stmt_to_plan_sql(stmt: str) -> str:
    """Normalize SQL to EXPLAIN PLAN FOR ... (达梦数据库，类似Oracle)."""
    s = stmt.strip()
    if s.upper().startswith("EXPLAIN PLAN FOR"):
        return s
    if s.upper().startswith("EXPLAIN"):
        inner = re.sub(r"^\s*EXPLAIN\s+", "", s, count=1, flags=re.I)
        return "EXPLAIN PLAN FOR " + inner.strip()
    return "EXPLAIN PLAN FOR " + s


def _run_dm_explain_plan(cfg: dict, stmt: str) -> List[Dict[str, Any]]:
    """Run EXPLAIN PLAN FOR for 达梦数据库."""
    import dmPython

    s = stmt.strip()
    if not s.upper().startswith("EXPLAIN PLAN FOR"):
        s = "EXPLAIN PLAN FOR " + s

    conn = _get_db_connection(cfg, "dm")
    try:
        with conn.cursor() as cur:
            cur.execute(s)
            # 达梦使用V$MYSTATS等视图获取计划，或返回说明信息
            try:
                cur.execute("SELECT * FROM TABLE(DBMS_XPLAN.BUILD_PLAN_TABLE('PLAN_TABLE'))")
                if cur.description:
                    columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in cur.description]
                    rows = cur.fetchmany(_EXPLAIN_MAX_ROWS)
                    return [dict(zip(columns, r)) for r in rows]
            except Exception:
                pass
            return [{"plan_note": "EXPLAIN PLAN FOR executed for 达梦数据库"}]
    finally:
        conn.close()


def _run_mssql_explain_plan(cfg: dict, sql: str) -> List[Dict[str, Any]]:
    """Run SET SHOWPLAN_XML ON for SQL Server to get execution plan."""
    import pymssql

    conn = _get_db_connection(cfg, "mssql")
    try:
        with conn.cursor() as cur:
            # 开启显示计划
            cur.execute("SET SHOWPLAN_XML ON")
            conn.commit()
            try:
                # 执行SQL但不实际运行
                cur.execute(sql)
                conn.commit()
                # 获取XML格式的执行计划
                if cur.description:
                    columns = [col[0].lower() for col in cur.description]
                    rows = cur.fetchmany(_EXPLAIN_MAX_ROWS)
                    result = [dict(zip(columns, r)) for r in rows]
                else:
                    result = [{"plan_note": "执行计划已生成"}]
            finally:
                # 关闭显示计划
                try:
                    cur.execute("SET SHOWPLAN_XML OFF")
                    conn.commit()
                except Exception:
                    pass
            return result
    finally:
        conn.close()


def _run_report_sql_file(
    cfg: dict,
    driver: str,
    path: Path,
    max_rows: int,
    explain_default: bool,
    execute_sample: bool,
) -> Dict[str, Any]:
    """运行报表 SQL 文件校验"""
    text = path.read_text(encoding="utf-8")
    parts = _split_statements_sql(text)
    if not parts:
        raise ValueError(f"No SQL statements found in {path}")

    results: List[Dict[str, Any]] = []
    for idx, stmt in enumerate(parts):
        result = _validate_one_statement(
            cfg, driver, stmt, idx, max_rows, explain_default, execute_sample
        )
        results.append(vars(result))

    success = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
    failed = sum(1 for r in results if not r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))

    # 兼容旧格式
    legacy_sql: Optional[str] = None
    legacy_rows: Optional[List[Dict[str, Any]]] = None
    for r in results:
        if r.get("skipped") or not r.get("ok"):
            continue
        rows = r.get("rows")
        if rows is not None and r.get("executed_sql"):
            legacy_sql = r["executed_sql"]
            legacy_rows = rows
            break

    out: Dict[str, Any] = {
        "validation": "report_sql_file",
        "source_file": str(path.resolve()),
        "explain": explain_default,
        "execute_sample_after_plan": execute_sample,
        "statements": results,
        "summary": {
            "statement_count": len(parts),
            "success": success,
            "failed": failed,
            "skipped": skipped,
        },
        "max_data_rows": max_rows,
    }
    if legacy_sql is not None and legacy_rows is not None:
        out["sql"] = legacy_sql
        out["rows"] = legacy_rows
        out["row_count"] = len(legacy_rows)

    return out


# ============================================================
# 命名查询
# ============================================================


def _default_elastic_sql(schema: str, virtual_table: str, ytenant_id: str) -> str:
    """生成特征字段检查的默认 SQL"""
    # 验证标识符只包含合法字符，防止SQL注入
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', schema):
        raise ValueError(f"Invalid schema name: {schema} (only letters, digits, and underscores allowed)")
    if not re.match(r'^[a-zA-Z0-9_]+$', virtual_table):
        raise ValueError(f"Invalid virtual_table name: {virtual_table} (only letters, digits, and underscores allowed)")
    if not re.match(r'^[a-zA-Z0-9_-]+$', ytenant_id):
        raise ValueError(f"Invalid ytenant_id: {ytenant_id} (only letters, digits, underscores, and hyphens allowed)")

    return f"""SELECT
    field.real_table AS real_table,
    field.real_column AS real_column,
    field.field_name AS field_name,
    field.comment AS field_comment,
    field.ytenant_id AS ytenant_id
FROM {schema}.elastic_object obj
LEFT JOIN {schema}.elastic_field field ON obj.id = field.object_id
WHERE obj.table_name = '{virtual_table}'
  AND field.ytenant_id = '{ytenant_id}'
"""


def _run_named_query(cfg: dict, driver: str, query_key: str) -> Dict[str, Any]:
    """运行数据库.queries 中定义的命名查询"""
    db = cfg.get("database") or {}
    queries = db.get("queries") or {}
    qdef = queries.get(query_key) or {}

    if not qdef.get("enabled", True):
        raise ValueError(f"Query {query_key} is disabled.")

    sql = (qdef.get("sql") or "").strip()
    if not sql:
        sql = _default_elastic_sql(
            str(qdef.get("schema", "uorders")),
            str(qdef.get("virtual_table_name", "orders_character_define")),
            str(qdef.get("ytenant_id", "0")),
        )

    _ensure_db_driver(driver)
    rows, _ = _execute_query(cfg, driver, sql, 1000)

    return {"sql": sql, "rows": rows, "query_key": query_key}


# ============================================================
# 主入口
# ============================================================


def main() -> int:
    require_python_version()

    configure_stdio_utf8()
    setup_logging("db_query")

    ap = argparse.ArgumentParser(
        description="Run configured DB queries from iuap-c-report_sql_gen skill."
    )
    ap.add_argument(
        "--config",
        default=str(_skill_dir() / "config.yaml"),
        help="Path to config.yaml",
    )
    ap.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file (default: <config_dir>/.env)",
    )
    ap.add_argument(
        "--query",
        default=None,
        help="Key under database.queries (default elastic_field_check when --sql-file omitted)",
    )
    ap.add_argument(
        "--sql-file",
        default=None,
        help="Path to user deliverable .sql; splits all statements (sqlparse), validates each",
    )
    ap.add_argument(
        "--report-sql-max-rows",
        type=int,
        default=None,
        help="Max rows for --sql-file (default: database.report_sql_max_rows or 50)",
    )
    ap.add_argument(
        "--explain",
        action="store_true",
        help="Use EXPLAIN for SELECT/WITH (plan only) instead of executing",
    )
    ap.add_argument(
        "--execute-only",
        action="store_true",
        help="For --sql-file: run SELECT/WITH directly (no EXPLAIN first)",
    )
    ap.add_argument(
        "--no-execute-sample",
        action="store_true",
        help="For --sql-file: do not run a limited sample execute after EXPLAIN",
    )
    ap.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Output detailed logs",
    )

    args = ap.parse_args()

    # 设置详细日志
    if args.verbose:
        import logging
        logging.getLogger("db_query").setLevel(logging.DEBUG)

    # 加载配置
    cfg_path = Path(args.config).expanduser().resolve()
    if not cfg_path.exists():
        print(f"错误: 配置文件不存在: {cfg_path}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR

    # 显式加载 .env 文件
    if args.env_file:
        env_path = Path(args.env_file).expanduser().resolve()
    else:
        env_path = cfg_path.parent / ".env"
    load_dotenv(env_path)
    if env_path.exists():
        logger.info(f"已加载环境配置: {env_path}")
    else:
        logger.warning(f"未找到 .env 文件: {env_path}，请确认文件路径是否正确")

    try:
        cfg = resolve_config(cfg_path)
    except Exception as e:
        print(f"错误: 配置加载失败: {e}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR

    db = cfg.get("database") or {}
    if not str_to_bool(db.get("enabled")):
        logger.info("database.enabled is false; nothing to run.")
        return ExitCode.SUCCESS

    # 验证数据库配置
    errors = validate_database_config(cfg)
    if errors:
        logger.error("数据库配置验证失败:")
        for err in errors:
            logger.error(f"  - {err}")
        return ExitCode.CONFIG_ERROR

    # 确保 sqlparse 可用
    if args.sql_file:
        try:
            _ensure_sqlparse()
        except ImportError as e:
            print(str(e), file=sys.stderr)
            return ExitCode.CONFIG_ERROR

    driver = (db.get("driver") or "mysql").lower()

    query_key = args.query
    if args.sql_file is None and query_key is None:
        query_key = "elastic_field_check"

    max_rows = args.report_sql_max_rows
    if max_rows is None:
        max_rows = int(db.get("report_sql_max_rows") or 50)

    explain_default = (not args.execute_only) and (
        bool(args.explain) or bool(db.get("report_sql_use_explain", True))
    )
    execute_sample = (not args.no_execute_sample) and bool(
        db.get("report_sql_execute_sample", True)
    )

    # 打印数据库连接信息
    db_info_str = _format_db_info(cfg, driver)
    logger.info(f"数据库连接信息: {db_info_str}")
    print(f"数据库连接信息: {db_info_str}", file=sys.stderr)

    combined: Dict[str, Any] = {}
    combined["database_info"] = {
        "driver": driver,
        "host": db.get("host", ""),
        "port": str(db.get("port", "")),
        "user": db.get("user", ""),
        "database": db.get("database", ""),
    }

    # 执行 SQL 文件校验
    if args.sql_file:
        raw_path = Path(args.sql_file).expanduser()
        sql_path = raw_path if raw_path.is_absolute() else (Path.cwd() / raw_path).resolve()
        if not sql_path.is_file():
            print(f"SQL file not found: {args.sql_file}", file=sys.stderr)
            return ExitCode.FILE_ERROR
        try:
            logger.info(f"校验 SQL 文件: {sql_path}")
            combined["report_sql_file"] = _run_report_sql_file(
                cfg, driver, sql_path, max_rows, explain_default, execute_sample
            )
        except Exception as e:
            logger.error(f"SQL 文件校验失败: {e}")
            return ExitCode.VALIDATION_ERROR

    # 执行命名查询
    if query_key:
        try:
            logger.info(f"执行命名查询: {query_key}")
            nq = _run_named_query(cfg, driver, query_key)
            combined[query_key] = {"sql": nq["sql"], "rows": nq["rows"]}
        except Exception as e:
            logger.error(f"命名查询执行失败: {e}")
            return ExitCode.VALIDATION_ERROR

    if not combined:
        print("Nothing to run (no --sql-file and no --query).", file=sys.stderr)
        return ExitCode.SUCCESS

    # 输出结果
    if len(combined) == 1:
        only = next(iter(combined.values()))
        if args.sql_file and not query_key:
            print(json.dumps(only, ensure_ascii=False, indent=2, default=_json_default))
        else:
            print(json.dumps({"sql": only["sql"], "rows": only["rows"]}, ensure_ascii=False, indent=2, default=_json_default))
        return ExitCode.SUCCESS

    print(json.dumps(combined, ensure_ascii=False, indent=2, default=_json_default))
    return ExitCode.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
