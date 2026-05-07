#!/usr/bin/env python3
import os
import re
import yaml
import pymysql

# Load .env file
skill_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(skill_dir)  # Go up 1 level: scripts -> iuap-c-report-sqlgen
env_path = os.path.join(skill_dir, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if not k:
                continue
            if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
                v = v[1:-1]
            if k not in os.environ:
                def replace_ref(m):
                    return os.environ.get(m.group(1), "")
                v = re.sub(r"\$\{([^}:]+)(?::-([^}]*))?\}", replace_ref, v)
                os.environ[k] = v


def _resolve_env_vars(value):
    """解析环境变量引用 ${VAR} 或 ${VAR:-default}"""
    if not isinstance(value, str):
        return value
    def replacer(m):
        var_name = m.group(1)
        default = m.group(2) if m.group(2) is not None else ""
        return os.environ.get(var_name, default)
    return re.sub(r"\$\{([^}:]+)(?::-([^}]*))?\}", replacer, value)


def _walk_vars(obj):
    """递归解析对象中的环境变量"""
    if isinstance(obj, dict):
        return {k: _walk_vars(_resolve_env_vars(v)) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_walk_vars(item) for item in obj]
    elif isinstance(obj, str):
        return _resolve_env_vars(obj)
    return obj


# Load config
config_path = os.path.join(skill_dir, "config.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    cfg = _walk_vars(yaml.safe_load(f))

db_cfg = cfg["database"]
sql = db_cfg["queries"]["moneytype_field_check"]["sql"]

print(f"Executing SQL:\n{sql}\n")

try:
    # Connect and execute
    conn = pymysql.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        charset=db_cfg.get("charset", "utf8mb4")
    )

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    print(f"Result ({len(rows)} rows):")
    print("-" * 80)
    for row in rows:
        print(row)

    cur.close()
    conn.close()
    print("\nSQL validation PASSED!")
except Exception as e:
    print(f"Error: {e}")
    exit(1)
