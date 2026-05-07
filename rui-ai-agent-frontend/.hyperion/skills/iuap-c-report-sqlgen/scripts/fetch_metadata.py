#!/usr/bin/env python3
"""
拉取 BIP 业务对象元数据 - 对齐 ReportSQLGenTool / BusinessObjectToolUtil
支持并行处理、URI 缓存、进度显示、配置验证

Database helpers: run scripts/db_query.py separately, or use --run-db-check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# 确保 scripts 目录在 sys.path 中（支持直接执行脚本）
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# 添加common目录到sys.path，导入共享模块
_skills_dir = _scripts_dir.parent.parent
_common_dir = _skills_dir / "common"
if str(_common_dir) not in sys.path:
    sys.path.insert(0, str(_common_dir))

from utils import (
    ConfigValidationError,
    ExitCode,
    _text,
    _first_non_empty,
    get_progress_bar,
    load_dotenv,
    load_yaml,
    parse_doc_fields,
    resolve_config,
    safe_filename,
    validate_api_config,
)
from logging_config import get_logger, setup_logging

import bip_auth
from console_utf8 import configure_stdio_utf8
from metadata_parse import AttributeInfo, BizTableGroup, parse
from paths_util import (
    SKILL_DIR,
    resolve_skill_path,
    resolve_workspace_path,
    workspace_base,
)

# 全局日志记录器（须在快速查找 try 之前，避免 ImportError 分支引用未定义 logger）
logger = get_logger("fetch_metadata")

# 尝试导入快速查找模块
try:
    from metadata_fast_lookup import get_fast_lookup
    _FAST_LOOKUP_ENABLED = True
except ImportError:
    _FAST_LOOKUP_ENABLED = False
    logger.debug("快速查找模块未加载")

# 批量查询默认上限（可被 config.performance 覆盖）
MAX_CONCURRENT_REQUESTS_DEFAULT = 16  # queryByUri 并行度默认
MAX_BATCH_SIZE = 80  # 单批 URI 数量（仅分批，不降低并发）
MAX_REFERENCE_FIELDS_DEFAULT = 30  # 参照展开条数上限默认


def _perf(cfg: dict) -> dict:
    return cfg.get("performance") or {}


def _max_concurrent_uri(cfg: dict) -> int:
    return max(
        1, int(_perf(cfg).get("max_concurrent_query_by_uri", MAX_CONCURRENT_REQUESTS_DEFAULT))
    )


def _max_concurrent_bills(cfg: dict) -> int:
    return max(1, int(_perf(cfg).get("max_concurrent_bills", 6)))


def _max_concurrent_entities(cfg: dict) -> int:
    return max(1, int(_perf(cfg).get("max_concurrent_entities", 8)))


def _max_reference_fields(cfg: dict) -> int:
    v = _perf(cfg).get("max_reference_fields_expand")
    if v is None:
        return MAX_REFERENCE_FIELDS_DEFAULT
    return max(1, int(v))


# 全局 URI 缓存：避免重复请求相同的 URI
_uri_cache: Dict[str, str] = {}
_cache_lock = threading.Lock()


def http_get_json(
    cfg: dict, path: str, extra_params: Optional[Dict[str, str]] = None
) -> Any:
    """见 bip_auth.http_get_json：先取 token（缓存+过期刷新），再带 access_token 请求。"""
    return bip_auth.http_get_json(cfg, path, extra_params)


def _get_cached_uri(uri: str) -> Optional[str]:
    """从缓存获取 URI 对应的数据"""
    with _cache_lock:
        return _uri_cache.get(uri)


def _set_cached_uri(uri: str, data: str) -> None:
    """缓存 URI 对应的数据"""
    with _cache_lock:
        _uri_cache[uri] = data


def _query_by_uri_cached(cfg: dict, uri: str) -> str:
    """
    queryByUri 统一入口：进程内 URI 缓存，避免主实体解析、参照批量、特征/平行表重复请求同一 URI。
    HTTP 层超时由 api.http_timeout_seconds 控制（见 bip_auth）。
    """
    cached = _get_cached_uri(uri)
    if cached:
        logger.debug(f"Cache hit: {uri}")
        return cached
    api = cfg.get("api") or {}
    meta_uri_path = api.get("metadata_uri", "")
    j = http_get_json(cfg, meta_uri_path, {"uri": uri})
    s = json.dumps(j, ensure_ascii=False)
    _set_cached_uri(uri, s)
    logger.debug(f"Cache miss, fetched: {uri}")
    return s


def fetch_entity_db_info_with_timeout(cfg: dict, uri: str) -> Optional[str]:
    """批量路径使用的 queryByUri（失败返回 None）；超时由 api.http_timeout_seconds 控制。"""
    try:
        return _query_by_uri_cached(cfg, uri)
    except Exception as e:
        logger.error(f"获取实体信息失败 [uri={uri}]: {e}")
        return None


def fetch_entity_db_info_batch(
    cfg: dict, uris: Set[str]
) -> Dict[str, str]:
    """
    批量获取实体数据库信息（限流并行查询）

    优化策略：
    - 限制最大并发请求数，避免过多请求同时发起导致超时
    - 分批处理大量 URI，每批不超过 MAX_BATCH_SIZE
    - 使用线程池控制并发
    """
    if not uris:
        return {}

    result: Dict[str, str] = {}
    uri_list = list(uris)
    total_count = len(uri_list)

    # 如果 URI 数量过多，记录警告日志
    if total_count > MAX_BATCH_SIZE:
        logger.warning(
            f"批量查询 URI 数量过多({total_count})，将分批处理，每批最多{MAX_BATCH_SIZE}个"
        )

    # 分批处理
    success_count = 0
    fail_count = 0

    with get_progress_bar(total=total_count, desc="拉取元数据") as pbar:
        for i in range(0, total_count, MAX_BATCH_SIZE):
            batch = uri_list[i : i + MAX_BATCH_SIZE]
            batch_success, batch_fail = _fetch_batch_with_limit(cfg, batch, result)
            success_count += batch_success
            fail_count += batch_fail
            pbar.update(len(batch))

    logger.info(f"批量查询完成: 成功={success_count}, 失败={fail_count}, 总计={total_count}")
    return result


def _fetch_batch_with_limit(
    cfg: dict, uris: List[str], result: Dict[str, str]
) -> Tuple[int, int]:
    """使用线程池限制并发数，批量获取实体信息"""
    success_count = 0
    fail_count = 0
    workers = _max_concurrent_uri(cfg)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_uri = {
            executor.submit(fetch_entity_db_info_with_timeout, cfg, uri): uri
            for uri in uris
        }

        for future in as_completed(future_to_uri):
            uri = future_to_uri[future]
            try:
                data = future.result()
                if data:
                    result[uri] = data
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"获取实体信息失败 [uri={uri}]: {e}")
                fail_count += 1

    return success_count, fail_count


@dataclass
class CodeNameResult:
    """业务对象编码和名称解析结果"""
    code: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None
    available_names: Optional[List[str]] = None
    available_items: Optional[List[Dict[str, Optional[str]]]] = None

    def needs_selection(self) -> bool:
        return bool(self.available_items and len(self.available_items) > 1)


def parse_business_object_code_name(result: Any, billname: str) -> Optional[CodeNameResult]:
    """解析业务对象响应，提取编码和名称"""
    if not isinstance(result, dict):
        return None
    code_val = _text(result, "code") or _text(result, "resultCode")
    if code_val != "200":
        return None
    data_node = result.get("data")
    if not isinstance(data_node, dict):
        return None
    target_nodes: List[dict] = []
    inner_data_array = data_node.get("data")
    if isinstance(inner_data_array, list):
        for item in inner_data_array:
            if isinstance(item, dict):
                target_nodes.append(item)
    nodes_with_parent: List[Tuple[dict, Optional[str]]] = []
    if not target_nodes:
        bo_array = data_node.get("METACLASS")
        if isinstance(bo_array, list):
            for bo in bo_array:
                if not isinstance(bo, dict):
                    continue
                parent_code = _text(bo, "code")
                children = bo.get("children")
                if isinstance(children, list):
                    for child in children:
                        if isinstance(child, dict):
                            nodes_with_parent.append((child, parent_code))
    search_name = (billname or "").strip()

    def _dedupe_by_code(
        items: List[Dict[str, Optional[str]]]
    ) -> List[Dict[str, Optional[str]]]:
        seen: Set[str] = set()
        out: List[Dict[str, Optional[str]]] = []
        for it in items:
            c = (it.get("code") or "").strip()
            if not c or c in seen:
                continue
            seen.add(c)
            out.append(it)
        return out

    exact_tn: List[Dict[str, Optional[str]]] = []
    for node in target_nodes:
        name = _text(node, "name")
        if name == search_name:
            code = _text(node, "code")
            id_ = _text(node, "id")
            if code and code != "null":
                exact_tn.append({"code": code, "name": name, "id": id_})
    exact_tn = _dedupe_by_code(exact_tn)
    if len(exact_tn) == 1:
        o = exact_tn[0]
        return CodeNameResult(code=o["code"], name=o["name"], id=o.get("id"))
    if len(exact_tn) > 1:
        names = [f"{x.get('name') or ''}（{x.get('code') or ''}）" for x in exact_tn]
        return CodeNameResult(available_names=names, available_items=exact_tn)

    exact_wp: List[Dict[str, Optional[str]]] = []
    for node, parent_code in nodes_with_parent:
        name = _text(node, "name")
        if name == search_name and parent_code and parent_code != "null":
            exact_wp.append(
                {"code": parent_code, "name": name, "id": _text(node, "id")}
            )
    exact_wp = _dedupe_by_code(exact_wp)
    if len(exact_wp) == 1:
        o = exact_wp[0]
        return CodeNameResult(code=o["code"], name=o["name"], id=o.get("id"))
    if len(exact_wp) > 1:
        names = [f"{x.get('name') or ''}（{x.get('code') or ''}）" for x in exact_wp]
        return CodeNameResult(available_names=names, available_items=exact_wp)

    sub_tn: List[Dict[str, Optional[str]]] = []
    for node in target_nodes:
        name = _text(node, "name")
        if name and search_name in name:
            code = _text(node, "code")
            id_ = _text(node, "id")
            if code and code != "null":
                sub_tn.append({"code": code, "name": name, "id": id_})
    sub_tn = _dedupe_by_code(sub_tn)
    if len(sub_tn) == 1:
        o = sub_tn[0]
        return CodeNameResult(code=o["code"], name=o["name"], id=o.get("id"))
    if len(sub_tn) > 1:
        names = [f"{x.get('name') or ''}（{x.get('code') or ''}）" for x in sub_tn]
        return CodeNameResult(available_names=names, available_items=sub_tn)

    sub_wp: List[Dict[str, Optional[str]]] = []
    for node, parent_code in nodes_with_parent:
        name = _text(node, "name")
        if name and search_name in name and parent_code and parent_code != "null":
            sub_wp.append(
                {"code": parent_code, "name": name, "id": _text(node, "id")}
            )
    sub_wp = _dedupe_by_code(sub_wp)
    if len(sub_wp) == 1:
        o = sub_wp[0]
        return CodeNameResult(code=o["code"], name=o["name"], id=o.get("id"))
    if len(sub_wp) > 1:
        names = [f"{x.get('name') or ''}（{x.get('code') or ''}）" for x in sub_wp]
        return CodeNameResult(available_names=names, available_items=sub_wp)

    # 收集所有候选业务对象及其完整信息（code、name、id）
    all_items: List[Dict[str, Optional[str]]] = []
    seen_codes: Set[str] = set()
    for node in target_nodes:
        name = _text(node, "name")
        code = _text(node, "code")
        if name and code and code != "null" and code not in seen_codes:
            all_items.append({"code": code, "name": name, "id": _text(node, "id")})
            seen_codes.add(code)
    for node, parent_code in nodes_with_parent:
        name = _text(node, "name")
        if name and parent_code and parent_code != "null" and parent_code not in seen_codes:
            all_items.append({"code": parent_code, "name": name, "id": _text(node, "id")})
            seen_codes.add(parent_code)

    if len(all_items) == 1:
        # 只有一个候选，直接使用
        item = all_items[0]
        return CodeNameResult(code=item["code"], name=item["name"], id=item["id"])
    elif len(all_items) > 1:
        # 多个候选，返回完整信息供选择
        all_names = [item["name"] for item in all_items]
        return CodeNameResult(available_names=all_names, available_items=all_items)
    return None


def collect_entity_details(result: Any) -> List[Dict[str, Optional[str]]]:
    """从业务对象响应中收集实体详情列表"""
    if not isinstance(result, dict):
        return []
    code_val = _text(result, "code") or _text(result, "resultCode")
    if code_val != "200":
        return []
    data_node = result.get("data")
    if not isinstance(data_node, dict):
        return []
    entities_node = data_node.get("entities")
    if not isinstance(entities_node, list):
        inner = data_node.get("data")
        if isinstance(inner, dict):
            entities_node = inner.get("entities")
    if not isinstance(entities_node, list):
        return []

    out: List[Dict[str, Optional[str]]] = []

    def walk(arr: List[Any]) -> None:
        for entity in arr:
            if not isinstance(entity, dict):
                continue
            eid = _text(entity, "id")
            if eid == "null":
                eid = None
            out.append(
                {
                    "entityId": eid,
                    "uri": _text(entity, "uri"),
                    "boId": _text(entity, "businessObjectId"),
                    "businessObjectCode": _text(entity, "businessObjectCode"),
                }
            )
            ch = entity.get("children")
            if isinstance(ch, list):
                walk(ch)

    walk(entities_node)
    return out


def parse_entity_model_for_ai(result: Any) -> Optional[Dict[str, Any]]:
    """解析实体模型供 AI 使用"""
    if not isinstance(result, dict):
        return None
    code_val = _text(result, "code") or _text(result, "resultCode")
    if code_val != "200":
        return None
    data_node = result.get("data")
    if not isinstance(data_node, dict):
        return None
    inner = data_node.get("data")
    if isinstance(inner, dict):
        data_node = inner
    domain = _text(data_node, "domain")
    schema = _text(data_node, "schema")
    if (not schema or not str(schema).strip()) and domain and domain.startswith("c-"):
        schema = domain.replace("-", "_") + "_db"
    model: Dict[str, Any] = {
        "uri": _text(data_node, "uri"),
        "tableName": _text(data_node, "tableName"),
        "businessObjectCode": _text(data_node, "businessObjectCode"),
        "domain": domain,
        "schema": schema,
        "businessProperties": [],
    }
    bp_array = data_node.get("businessProperties")
    if isinstance(bp_array, list):
        for bp in bp_array:
            if not isinstance(bp, dict):
                continue
            all_tables = bp.get("allTables")
            tbl = None
            if isinstance(all_tables, list) and all_tables:
                t0 = all_tables[0]
                if isinstance(t0, str):
                    tbl = t0
            summary = {
                "name": _text(bp, "name"),
                "displayName": _text(bp, "displayName"),
                "uri": _text(bp, "uri"),
                "tableName": tbl,
            }
            model["businessProperties"].append(summary)
            cfs = bp.get("characterFields")
            if isinstance(cfs, list):
                for cf in cfs:
                    if not isinstance(cf, dict):
                        continue
                    c_all = cf.get("allTables")
                    ctbl = None
                    if isinstance(c_all, list) and c_all and isinstance(c_all[0], str):
                        ctbl = c_all[0]
                    model["businessProperties"].append(
                        {
                            "name": _text(cf, "name"),
                            "displayName": _text(cf, "displayName"),
                            "uri": _text(cf, "uri"),
                            "tableName": ctbl,
                        }
                    )
    return model


def parse_foreign_keys_util(
    entity_db: Any, _entity_uri: Optional[str]
) -> List[Dict[str, Any]]:
    """解析外键关联"""
    if not isinstance(entity_db, dict):
        return []
    code_val = _text(entity_db, "code") or _text(entity_db, "resultCode")
    if code_val != "200":
        return []
    data_node = entity_db.get("data")
    if not isinstance(data_node, dict):
        return []
    inner = data_node.get("data")
    if isinstance(inner, dict):
        data_node = inner
    assoc = data_node.get("associationAttributes")
    if not isinstance(assoc, list):
        return []
    fks: List[Dict[str, Any]] = []
    for attr in assoc:
        if not isinstance(attr, dict):
            continue
        biztype = str(attr.get("biztype", "")).replace('"', "")
        if biztype != "quote":
            continue
        col = attr.get("columnName")
        type_uri = attr.get("typeUri")
        col_s = str(col).replace('"', "") if col is not None else None
        uri_s = str(type_uri).replace('"', "") if type_uri is not None else None
        if col_s and uri_s:
            fks.append({"columnName": col_s, "refUri": uri_s})
    return fks


def load_scheme_map(path: Path) -> List[Dict[str, Any]]:
    """加载领域 schema 映射表"""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def scheme_by_domain(
    scheme_list: List[Dict[str, Any]], domain: Optional[str]
) -> Optional[str]:
    """根据领域获取对应的 schema"""
    if not domain or not str(domain).strip():
        return None
    target_key = "mdd_schema." + domain.strip()
    for scheme in scheme_list:
        if not isinstance(scheme, dict):
            continue
        key = scheme.get("key")
        if key == target_key:
            ex = scheme.get("exclusiveValue")
            if ex and str(ex).strip():
                return str(ex).strip()
            val = scheme.get("value")
            return str(val).strip() if val else None
    return None


def attr_to_map(attr: AttributeInfo) -> Dict[str, Any]:
    """将 AttributeInfo 转换为字典"""
    m: Dict[str, Any] = {
        "displayName": attr.display_name,
        "dbColumnName": attr.db_column_name,
        "type": attr.type,
        "name": attr.name,
        "tableName": attr.table_name,
    }
    if attr.uri:
        m["uri"] = attr.uri
    if attr.enums:
        m["enums"] = [{"code": e.code, "name": e.name} for e in attr.enums]
    return m


def biz_table_group_to_entity_map(
    group: BizTableGroup,
    entity_result: Dict[str, Optional[str]],
    entity_model: Optional[Dict[str, Any]],
    foreign_keys: List[Dict[str, Any]],
    doc_fields: List[str],
    is_sql_y: bool,
    table_template: Optional[str],
    fetch_uri_json: Callable[[str], str],
    scheme_list: List[Dict[str, Any]],
    cfg: dict,
) -> Optional[Dict[str, Any]]:
    """将 BizTableGroup 转换为实体映射字典"""
    max_ref = _max_reference_fields(cfg)
    schema_val = entity_model.get("schema") if entity_model else None
    m: Dict[str, Any] = {
        "tableName": group.table_name,
        "billName": group.bill_name,
        "domain": group.domain,
        "uri": entity_result.get("uri"),
        "businessObjectCode": entity_result.get("businessObjectCode"),
        "schema": schema_val,
    }
    if foreign_keys:
        m["foreignKeys"] = foreign_keys
    prop_map: Dict[str, str] = {}
    if entity_model:
        for bp in entity_model.get("businessProperties") or []:
            if not isinstance(bp, dict):
                continue
            tn = bp.get("tableName")
            if not tn:
                continue
            n = bp.get("name")
            dn = bp.get("displayName")
            if n:
                prop_map[str(n)] = str(tn)
            if dn:
                prop_map[str(dn)] = str(tn)

    uris: Set[str] = set()
    if is_sql_y and group.attributes:
        for attr in group.attributes:
            if doc_fields:
                dn = attr.display_name or ""
                if dn not in doc_fields:
                    continue
            if attr.uri:
                uris.add(attr.uri)

    # 引用字段数量限制（防止过多引用字段导致超时）
    skipped_uris: Set[str] = set()
    if len(uris) > max_ref:
        logger.warning(
            f"引用字段数量过多({len(uris)})，将超过限制的 {max_ref} 个进行分批处理"
        )
        uri_list = list(uris)
        uris = set(uri_list[:max_ref])
        skipped_uris = set(uri_list[max_ref:])

    # 使用限流的批量查询
    uri_to_json: Dict[str, str] = (
        fetch_entity_db_info_batch(cfg, uris) if uris else {}
    )

    attrs_out: List[Dict[str, Any]] = []
    for attr in group.attributes or []:
        if doc_fields:
            dn = attr.display_name or ""
            if dn not in doc_fields:
                continue
        am = attr_to_map(attr)
        tn = prop_map.get(attr.name or "") or prop_map.get(attr.display_name or "")
        if not tn:
            tn = group.table_name
        am["tableName"] = tn
        attr_uri = attr.uri
        if attr_uri and is_sql_y:
            # 检查该 URI 是否被跳过（因数量过多）
            if attr_uri in skipped_uris:
                am["referenceSkipped"] = True
                am["referenceSkipReason"] = (
                    f"引用字段数量超过限制({max_ref})，"
                    f"如需展开此引用请在docFields中指定该字段"
                )
            else:
                ref_json = uri_to_json.get(attr_uri)
                if ref_json:
                    try:
                        ref_groups = parse(json.loads(ref_json), fetch_uri_json)
                        if ref_groups:
                            ref_group = ref_groups[0]
                            ref_attrs: List[Dict[str, Any]] = []
                            for ra in ref_group.attributes or []:
                                an = ra.name
                                dn = ra.display_name or ""
                                if an in ("name", "code") or (
                                    table_template and dn and dn in str(table_template)
                                ):
                                    ref_attrs.append(
                                        {
                                            "dbColumnName": ra.db_column_name,
                                            "displayName": ra.display_name,
                                            "primarykey": "id",
                                        }
                                    )
                            domain = ref_group.domain
                            ref_structure: Dict[str, Any] = {
                                "billName": ref_group.bill_name,
                                "domain": domain,
                                "tableName": ref_group.table_name,
                                "attributes": ref_attrs,
                            }
                            sch = scheme_by_domain(scheme_list, domain) or "scheme"
                            if (
                                not sch or sch == "scheme"
                            ) and domain and domain.startswith("c-"):
                                sch = domain.replace("-", "_") + "_db"
                            ref_structure["scheme"] = sch
                            am["referenceStructure"] = ref_structure
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.warning(f"解析引用 {attr_uri} 失败: {e}")
        attrs_out.append(am)
    m["attributes"] = attrs_out
    return m


def filter_strip_attribute_names(root: Dict[str, Any]) -> Dict[str, Any]:
    """移除 attributes 中的 name 字段（对齐 ReportSQLGenTool）"""
    entities = root.get("entities")
    if not isinstance(entities, list):
        return root
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        attributes = ent.get("attributes")
        if not isinstance(attributes, list):
            continue
        for attr in attributes:
            if isinstance(attr, dict) and "name" in attr:
                del attr["name"]
    return root


def _count_unique_uris_in_fast(fast_results: list) -> int:
    seen: Set[str] = set()
    for f in fast_results:
        u = (getattr(f, "uri", None) or "").strip()
        if u:
            seen.add(u)
    return len(seen)


def _build_fast_uri_selection(billname_trim: str, fast_results: list) -> Dict[str, Any]:
    """
    同一 bizName 命中 metadata_lookup 中多条不同 uri 时，与 searchByName 多义一样返回 selection 结构。
    main() 在 source=fast_lookup_uri 分支会将选中项写回 request.queryUri 并重跑。
    """
    seen: Set[str] = set()
    items: List[Dict[str, Any]] = []
    names: List[str] = []
    candidates: List[Dict[str, Any]] = []
    for fr in fast_results:
        u = (getattr(fr, "uri", None) or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        md = (getattr(fr, "metadata_name", None) or "") or ""
        bz = (getattr(fr, "biz_name", None) or "") or ""
        dom = (getattr(fr, "domain", None) or "") or ""
        tn = (getattr(fr, "table_name", None) or "") or ""
        label = f"{md or bz} | {u} | domain={dom} | table={tn}"
        candidates.append(
            {
                "uri": u,
                "metadataName": md,
                "bizName": bz,
                "domain": dom,
                "tableName": tn,
            }
        )
        items.append(
            {
                "uri": u,
                "code": None,
                "id": None,
                "name": label,
            }
        )
        names.append(label)
    return {
        "type": "selection",
        "source": "fast_lookup_uri",
        "items": items,
        "names": names,
        "candidates": candidates,
        "billname": billname_trim,
    }


def _should_interactive_selection_prompt() -> bool:
    """与插件 / Agent 非 TTY 环境：不阻塞 input，仅输出可解析的 stdout（见 Chat 侧栏多 URI 选择器）。"""
    if not sys.stdin.isatty():
        return False
    v = (os.environ.get("HYPERION_NON_INTERACTIVE") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return False
    return True


def _format_fast_lookup_multi_uri_stdout(selection_info: Dict[str, Any]) -> str:
    """
    与 iuap-c-metadata-info / metadata_core._format_fast_lookup_ambiguous 对齐，
    以便侧栏「元数据实体 URI 选择器」与 mcpRunner 暂停逻辑识别（须含固定短语）。
    """
    billname = selection_info.get("billname", "")
    intro = "\n业务对象属性信息如下:\n"
    parts: List[str] = [
        intro,
        "\n",
        f"停止：{billname!r} 在本地元数据索引中命中多条不同 URI，必须选定其一，否则结果会混单出错。\n"
        f"请用户或 Agent 在下次查询的 request 中设置 queryUri 为下面某一条 uri，亦可保留 allbillname 作展示用。\n",
        "\n候选：\n",
    ]
    candidates = selection_info.get("candidates") or []
    n = 0
    seen: Set[str] = set()
    for c in candidates:
        if not isinstance(c, dict):
            continue
        u = (c.get("uri") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        n += 1
        md = c.get("metadataName") or ""
        bz = c.get("bizName") or ""
        dom = c.get("domain") or ""
        tn = c.get("tableName") or ""
        parts.append(
            f"  {n}) uri: {u}\n     metadataName: {md}  "
            f"bizName: {bz}  domain: {dom}  tableName: {tn}\n"
        )
    parts.append('\n（再次调用示例：request 中传 "queryUri": "<所选 uri>" ）\n')
    return "".join(parts)


def _format_byname_bo_selection_stdout(selection_info: Dict[str, Any]) -> str:
    """与 Chat.parseBillNameChoiceFromStdout 一致（searchByName 多业务对象）。"""
    names = selection_info.get("names") or []
    return "停止继续往下走，请从以下单据名称中选择：" + "、".join(str(x) for x in names if x)


def _format_selection_stdout_for_ui(selection_info: Dict[str, Any]) -> str:
    src = selection_info.get("source") or "byname"
    if src == "fast_lookup_uri":
        return _format_fast_lookup_multi_uri_stdout(selection_info)
    return _format_byname_bo_selection_stdout(selection_info)


def _process_fast_results(
    cfg: dict,
    billname_trim: str,
    fast_results: list,
    scheme_list: List[Dict[str, Any]],
    doc_fields: List[str],
    is_sql_y: bool,
    table_template: Optional[str],
    is_include_sub: bool,
    relax_billname_filter: bool = False,
) -> List[Dict[str, Any]]:
    """
    处理快速查找结果 - 直接使用预计算的URI和元数据信息
    跳过byname和byboid API调用，只调用queryByUri获取详细结构
    同 uri 多行索引只处理一次。relax_billname_filter 为 True 时不过滤 billName 与入参的匹配（queryUri 直查用）。
    """
    entities_list: List[Dict[str, Any]] = []

    def fetch_uri(u: str) -> str:
        return _query_by_uri_cached(cfg, u)

    fr_by_uri: Dict[str, Any] = {}
    for fr in fast_results:
        uri = (getattr(fr, "uri", None) or "").strip()
        if uri and uri not in fr_by_uri:
            fr_by_uri[uri] = fr

    for fr in fr_by_uri.values():
        uri = (getattr(fr, "uri", None) or "").strip()
        if not uri:
            continue

        logger.info(
            f"快速处理: {getattr(fr, 'biz_name', None) or getattr(fr, 'metadata_name', None)} (uri={uri})"
        )

        db_json_str = fetch_uri(uri)
        if not db_json_str:
            logger.warning(f"获取URI数据失败: {uri}")
            continue

        try:
            db_obj = json.loads(db_json_str)
            groups = parse(db_obj, fetch_uri_json=fetch_uri)
            fkeys = parse_foreign_keys_util(db_obj, uri)

            ent = {
                "entityId": None,
                "uri": uri,
                "boId": None,
                "businessObjectCode": None,
            }

            for group in groups:
                if not is_include_sub:
                    gb = group.bill_name or ""
                    if not gb:
                        continue
                    if not relax_billname_filter and not (
                        gb == billname_trim
                        or billname_trim in gb
                        or gb in billname_trim
                    ):
                        continue

                if getattr(fr, "domain", None) and not group.domain:
                    group.domain = fr.domain

                entity_model: Dict[str, Any] = {
                    "schema": getattr(fr, "schema", None),
                    "domain": getattr(fr, "domain", None),
                    "tableName": getattr(fr, "table_name", None),
                }

                if uri:
                    entity_model["businessProperties"] = [
                        {"uri": uri, "tableName": getattr(fr, "table_name", None)}
                    ]

                emap = biz_table_group_to_entity_map(
                    group,
                    ent,
                    entity_model,
                    fkeys,
                    doc_fields,
                    is_sql_y,
                    str(table_template) if table_template is not None else None,
                    fetch_uri,
                    scheme_list,
                    cfg,
                )
                if emap:
                    if getattr(fr, "schema", None):
                        emap["schema"] = fr.schema
                    if getattr(fr, "domain", None):
                        emap["domain"] = fr.domain
                    entities_list.append(emap)

        except json.JSONDecodeError as e:
            logger.error(f"解析JSON失败 [{uri}]: {e}")

    logger.info(f"快速处理完成，共获取 {len(entities_list)} 个实体")
    return entities_list


def build_entities_for_bill(
    cfg: dict, billname_trim: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """为单个单据构建实体列表"""
    api = cfg.get("api") or {}
    scheme_path = resolve_skill_path(
        (cfg.get("paths") or {}).get("scheme_info_json", "reference/scheme-info.json")
    )
    scheme_list = load_scheme_map(scheme_path)
    req = cfg.get("request") or {}
    doc_fields = parse_doc_fields(req.get("docFields"))
    if str(req.get("isDescField", "Y")).upper() == "N":
        doc_fields = []
    is_sql_y = str(req.get("isSQL", "N")).upper() == "Y"
    table_template = req.get("tableTemplate")
    is_include_sub = (
        bool(req.get("isIncludeSub"))
        and str(req.get("isIncludeSub", "")).strip().upper() != "N"
    )

    logger.info(f"正在拉取单据: {billname_trim}")

    pre_query_uri = (req.get("queryUri") or req.get("query_uri") or "").strip()

    # 含子表时必须走 byname → byboid → entityId → queryByUri（与 Java 一致），
    # 由 byboid 扁平化主实体与子实体 URI；快速查找 / queryUri 直查只会请求单一 URI，子表元数据会丢。
    fast_lookup = None
    fast_results: list = []
    if not is_include_sub:
        if pre_query_uri:
            if _FAST_LOOKUP_ENABLED:
                fast_lookup = get_fast_lookup(cfg)
            frq = None
            if fast_lookup and fast_lookup.is_loaded:
                frq = fast_lookup.get_by_uri(pre_query_uri)
            if frq is None:
                from types import SimpleNamespace

                frq = SimpleNamespace(
                    uri=pre_query_uri,
                    domain=None,
                    schema=None,
                    metadata_name=None,
                    biz_name=None,
                    table_name=None,
                )
            fast_results = [frq]
        elif _FAST_LOOKUP_ENABLED:
            fast_lookup = get_fast_lookup(cfg)
            if fast_lookup and fast_lookup.is_loaded:
                fast_results = fast_lookup.lookup(billname_trim)
                if fast_results:
                    logger.info(
                        f"快速查找命中: {billname_trim}，找到 {len(fast_results)} 个匹配"
                    )
    elif pre_query_uri or _FAST_LOOKUP_ENABLED:
        logger.info(
            "isIncludeSub=Y：跳过本地快速查找与 queryUri 直查，使用 byname/byboid 全量实体列表"
        )

    pre_selected_code = req.get("_selected_bo_code")
    pre_selected_id = req.get("_selected_bo_id")

    if fast_results and not pre_selected_code:
        if not pre_query_uri and _count_unique_uris_in_fast(fast_results) > 1:
            return [], _build_fast_uri_selection(billname_trim, fast_results)

        logger.info("使用快速查找结果，跳过 byname API 调用")
        relax = bool(pre_query_uri)
        entities_list = _process_fast_results(
            cfg,
            billname_trim,
            fast_results,
            scheme_list,
            doc_fields,
            is_sql_y,
            table_template,
            is_include_sub,
            relax_billname_filter=relax,
        )
        return entities_list, None

    # 原始流程
    cn = None
    byname_path = api.get("metadata_byname", "")
    raw = http_get_json(cfg, byname_path, {"key": billname_trim})

    if pre_selected_code:
        cn = CodeNameResult(code=pre_selected_code, id=pre_selected_id or "", name=req.get("_selected_bo_name"))
        logger.info(f"使用预先选择的业务对象: code={pre_selected_code}, id={pre_selected_id}")
    else:
        cn = parse_business_object_code_name(raw, billname_trim)
        if cn is None:
            return [], f"错误: 无法解析单据 [{billname_trim}] 的编码和名称"
        if cn.needs_selection():
            items = cn.available_items or []
            names = cn.available_names or []
            return [], {
                "type": "selection",
                "source": "search_by_name",
                "items": items,
                "names": names,
                "billname": billname_trim,
            }

    byboid_path = api.get("metadata_byboid", "")
    raw_bo = http_get_json(
        cfg,
        byboid_path,
        {"boId": cn.id or "", "businessObjectCode": cn.code or ""},
    )
    details = collect_entity_details(raw_bo)
    entities_list: List[Dict[str, Any]] = []

    def fetch_uri(u: str) -> str:
        return _query_by_uri_cached(cfg, u)

    # 并行处理多个实体，提高性能
    def process_entity(ent: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
        """处理单个实体，返回实体映射列表"""
        entity_id = ent.get("entityId")
        uri = ent.get("uri")
        if not uri:
            return []

        entity_model: Optional[Dict[str, Any]] = None
        if entity_id:
            ent_path = api.get("metadata_entityid", "")
            raw_ent = http_get_json(
                cfg,
                ent_path,
                {
                    "entityId": entity_id,
                    "uri": uri or "",
                    "boId": ent.get("boId") or "",
                    "businessObjectCode": ent.get("businessObjectCode") or "",
                },
            )
            entity_model = parse_entity_model_for_ai(raw_ent)

        db_json_str = fetch_uri(uri)
        db_obj = json.loads(db_json_str)
        groups = parse(db_obj, fetch_uri_json=fetch_uri)
        fkeys = parse_foreign_keys_util(db_obj, uri)

        results: List[Dict[str, Any]] = []
        for group in groups:
            if not is_include_sub:
                gb = group.bill_name or ""
                if not (gb == billname_trim or billname_trim in gb or gb in billname_trim):
                    continue
            emap = biz_table_group_to_entity_map(
                group,
                ent,
                entity_model,
                fkeys,
                doc_fields,
                is_sql_y,
                str(table_template) if table_template is not None else None,
                fetch_uri,
                scheme_list,
                cfg,
            )
            if emap:
                results.append(emap)
        return results

    # 使用线程池并行处理实体（限制并发数避免过载）
    if len(details) > 1:
        ew = min(_max_concurrent_entities(cfg), len(details))
        logger.info(f"使用 {ew} 个线程并行处理 {len(details)} 个实体")
        with ThreadPoolExecutor(max_workers=ew) as executor:
            future_to_ent = {
                executor.submit(process_entity, ent): ent for ent in details
            }
            for future in as_completed(future_to_ent):
                try:
                    results = future.result()
                    entities_list.extend(results)
                except Exception as e:
                    ent = future_to_ent[future]
                    logger.error(f"处理实体失败 [uri={ent.get('uri')}]: {e}")
    else:
        # 单个实体时直接处理，避免线程池开销
        for ent in details:
            entities_list.extend(process_entity(ent))

    logger.info(f"单据 {billname_trim} 完成，共获取 {len(entities_list)} 个实体")
    return entities_list, None


def run_all_bills(cfg: dict) -> Tuple[Dict[str, Any], Optional[str]]:
    """运行所有单据的元数据拉取"""
    req = cfg.get("request") or {}
    quri = (req.get("queryUri") or req.get("query_uri") or "").strip()
    allbill = str(req.get("allbillname", "")).strip()
    if not allbill and quri:
        allbill = "metadata"
    if not allbill:
        return (
            {"entities": []},
            "错误: 缺少必需的参数 'allbillname'（单据名称），或提供 queryUri 以仅按元数据 uri 直查",
        )
    parts = [p.strip() for p in allbill.split(",") if p.strip()]
    if not parts:
        return (
            {"entities": []},
            "错误: 缺少必需的参数 'allbillname'（单据名称），或提供 queryUri 以仅按元数据 uri 直查",
        )

    logger.info(f"开始拉取 {len(parts)} 个单据: {', '.join(parts)}")

    if len(parts) == 1:
        ents, err = build_entities_for_bill(cfg, parts[0])
        if err:
            # 检查是否是选择类型的错误
            if isinstance(err, dict) and err.get("type") == "selection":
                return {"entities": [], "selection": err}, None
            return {"entities": []}, err
        return {"entities": ents}, None

    max_b = _max_concurrent_bills(cfg)
    bill_results: Dict[str, Tuple[List[Dict[str, Any]], Optional[str]]] = {}

    with ThreadPoolExecutor(max_workers=min(max_b, len(parts))) as executor:
        future_to_part = {
            executor.submit(build_entities_for_bill, cfg, p): p for p in parts
        }
        for future in as_completed(future_to_part):
            part = future_to_part[future]
            try:
                ents, err = future.result()
                # 检查是否是选择类型的错误
                if isinstance(err, dict) and err.get("type") == "selection":
                    return {"entities": [], "selection": err}, None
                bill_results[part] = (ents, err)
            except Exception as e:
                logger.error(f"拉取单据失败 [{part}]: {e}")
                return {"entities": []}, f"拉取单据失败 [{part}]: {e}"

    merged: List[Dict[str, Any]] = []
    for p in parts:
        ents, err = bill_results[p]
        if err:
            return {"entities": []}, err
        merged.extend(ents)

    logger.info(f"全部单据拉取完成，共获取 {len(merged)} 个实体")
    return {"entities": merged}, None


def _get_tenant_id(cfg: dict) -> Optional[str]:
    """从配置或环境变量获取租户ID"""
    # 优先从环境变量获取
    tenant_id = os.environ.get("YONBIP_TENANT_ID", "").strip()
    if tenant_id:
        return tenant_id
    # 从配置中获取
    db = cfg.get("database") or {}
    queries = db.get("queries") or {}
    elastic = queries.get("elastic_field_check") or {}
    tenant_id = str(elastic.get("ytenant_id", "")).strip()
    if tenant_id:
        return tenant_id
    return None


def write_outputs(cfg: dict, payload: Dict[str, Any]) -> None:
    """将元数据写入输出文件"""
    out_cfg = cfg.get("output") or {}
    paths = cfg.get("paths") or {}
    ws_base = workspace_base(cfg)
    logger.info(f"Workspace (outputs): {ws_base}")

    out_dir = resolve_workspace_path(paths.get("output_dir", "output"), cfg)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = dict(payload)
    if out_cfg.get("strip_attribute_names", True):
        data = filter_strip_attribute_names(data)

    if out_cfg.get("write_entities_json", True):
        p = out_dir / str(out_cfg.get("entities_json_filename", "entities.json"))
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"写入: {p}")

    if out_cfg.get("write_bundle_md", True):
        guide = resolve_skill_path(
            paths.get("sql_guide_md", "reference/旗舰版通用_后端_报表_SQL生成.md")
        )
        body = ""
        if guide.exists():
            body = guide.read_text(encoding="utf-8")
        p = out_dir / str(out_cfg.get("bundle_md_filename", "report_sql_context.md"))
        header = "业务对象属性信息如下:\n\n```json\n"
        footer = (
            "\n```\n\n实体模型字段说明: schema为schema，tableName 为表名，"
            "billName 为单据名称，domain 为领域；attributes 为属性列表，"
            "每项含 displayName(显示名)、dbColumnName(数据库列名)、type(数据类型)、"
            "enums(枚举值列表)。referenceStructure 为属性字段的引用元数据结构信息,,"
            "referenceStructure中primarykey是引用的主键\n"
        )
        # 租户信息（仅提供租户ID供参考，不强制要求添加到WHERE条件
        tenant_id = _get_tenant_id(cfg)
        tenant_section = ""
        if tenant_id:
            tenant_section = (
                f"\n## 租户信息\n\n"
                f"当前租户ID (ytenant_id): `{tenant_id}`\n\n"
                f"> **说明**: 此租户ID仅供参考，**仅当用户明确要求按租户过滤时**才需要在WHERE条件中使用。\n"
                f"> 禁止猜测添加此租户ID过滤条件。\n\n"
            )
        # 数据库校验环境信息
        db_cfg_out = cfg.get("database") or {}
        db_section = ""
        if str(db_cfg_out.get("enabled", "false")).lower() in ("true", "1", "yes"):
            db_driver = db_cfg_out.get("driver", "mysql")
            db_host = db_cfg_out.get("host", "")
            db_port = db_cfg_out.get("port", "")
            db_name = db_cfg_out.get("database", "")
            db_section = (
                f"\n## 数据库校验环境\n\n"
                f"- 数据库类型: `{db_driver}`\n"
                f"- 主机: `{db_host}`\n"
                f"- 端口: `{db_port}`\n"
                f"- 数据库名: `{db_name}`\n\n"
                f"> 生成的SQL将在此数据库上执行校验，请确保SQL语法兼容。\n\n"
            )
        # Windows 记事本等默认用 ANSI 打开无 BOM 的 UTF-8 易误判为系统编码
        md_enc = "utf-8-sig" if sys.platform == "win32" else "utf-8"
        p.write_text(
            header + json.dumps(data, ensure_ascii=False, indent=2) + footer + tenant_section + db_section + body,
            encoding=md_enc,
        )
        logger.info(f"写入: {p}")


def _apply_workspace_cli_overrides(cfg: dict, args: argparse.Namespace) -> None:
    """应用命令行的工作空间覆盖"""
    wr = getattr(args, "workspace_root", None)
    if wr is not None and str(wr).strip():
        cfg.setdefault("paths", {})["workspace_root"] = str(wr).strip()


def _apply_request_cli_overrides(cfg: dict, args: argparse.Namespace) -> None:
    """将命令行显式传入的项合并进 cfg['request']，覆盖 config.yaml 同名字段。"""
    req = cfg.setdefault("request", {})
    if getattr(args, "allbillname", None) is not None:
        req["allbillname"] = args.allbillname
    if getattr(args, "is_include_sub", None) is not None:
        req["isIncludeSub"] = args.is_include_sub
    if getattr(args, "doc_fields", None) is not None:
        req["docFields"] = args.doc_fields
    if getattr(args, "is_sql", None) is not None:
        req["isSQL"] = args.is_sql
    if getattr(args, "is_desc_field", None) is not None:
        req["isDescField"] = args.is_desc_field
    if getattr(args, "table_template", None) is not None:
        req["tableTemplate"] = args.table_template
    if getattr(args, "selected_bo_code", None) is not None:
        req["_selected_bo_code"] = args.selected_bo_code
    if getattr(args, "selected_bo_id", None) is not None:
        req["_selected_bo_id"] = args.selected_bo_id
    if getattr(args, "query_uri", None) is not None:
        req["queryUri"] = args.query_uri


def main() -> int:
    configure_stdio_utf8()
    setup_logging("fetch_metadata")

    ap = argparse.ArgumentParser(
        description="拉取旗舰版业务对象元数据；request.* 可由话术解析后通过下列参数注入（覆盖 config.yaml）。"
    )
    ap.add_argument("--config", default=str(SKILL_DIR / "config.yaml"))
    ap.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file (default: <config_dir>/.env)",
    )
    ap.add_argument(
        "--workspace-root",
        default=None,
        metavar="DIR",
        help="覆盖 paths.workspace_root：元数据输出 output_dir 相对此目录（默认自动推断项目根）",
    )
    ap.add_argument(
        "--run-db-check",
        action="store_true",
        help="拉取完成后运行 database.queries.elastic_field_check",
    )
    ap.add_argument(
        "--validate",
        action="store_true",
        help="仅验证配置，不拉取数据",
    )
    ap.add_argument(
        "--allbillname",
        default=None,
        help="覆盖 request.allbillname（多个单据用英文逗号分隔）",
    )
    ap.add_argument(
        "--is-include-sub",
        dest="is_include_sub",
        default=None,
        metavar="Y|N",
        help="覆盖 request.isIncludeSub：含子实体为 Y，仅主表匹配为 N",
    )
    ap.add_argument(
        "--doc-fields",
        dest="doc_fields",
        default=None,
        metavar="CSV",
        help="覆盖 request.docFields：仅保留这些 displayName，逗号分隔；空字符串表示不过滤",
    )
    ap.add_argument(
        "--is-sql",
        dest="is_sql",
        default=None,
        metavar="Y|N",
        help="覆盖 request.isSQL：需要参照 referenceStructure 时为 Y",
    )
    ap.add_argument(
        "--is-desc-field",
        dest="is_desc_field",
        default=None,
        metavar="Y|N",
        help="覆盖 request.isDescField：为 N 时忽略 docFields",
    )
    ap.add_argument(
        "--table-template",
        dest="table_template",
        default=None,
        metavar="STR",
        help="覆盖 request.tableTemplate：参照属性额外保留的 displayName 匹配子串",
    )
    ap.add_argument(
        "--selected-bo-code",
        dest="selected_bo_code",
        default=None,
        metavar="CODE",
        help="指定已选择的业务对象编码（用于交互式选择后继续执行）",
    )
    ap.add_argument(
        "--selected-bo-id",
        dest="selected_bo_id",
        default=None,
        metavar="ID",
        help="指定已选择的业务对象ID（用于交互式选择后继续执行）",
    )
    ap.add_argument(
        "--query-uri",
        dest="query_uri",
        default=None,
        metavar="URI",
        help="覆盖 request.queryUri：本地快速索引多义时选定元数据实体 uri；也可单独与空 allbillname 搭配直查",
    )
    ap.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出详细日志",
    )

    args = ap.parse_args()

    # 设置详细日志
    if args.verbose:
        import logging
        logging.getLogger("fetch_metadata").setLevel(logging.DEBUG)

    # 加载配置（支持环境变量）
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

    # 先合并命令行覆盖再校验（与 ultimate_metadata_query 一致，避免仅依赖 --allbillname 仍报 yaml 空值）
    _apply_workspace_cli_overrides(cfg, args)
    _apply_request_cli_overrides(cfg, args)

    errors = validate_api_config(cfg)
    if errors:
        print("配置验证失败:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        if not args.validate:
            return ExitCode.CONFIG_ERROR

    if args.validate:
        print("配置验证通过", file=sys.stderr)
        return ExitCode.SUCCESS

    payload, err = run_all_bills(cfg)
    if err:
        print(err, file=sys.stderr)
        print(json.dumps({"error": err}, ensure_ascii=False))
        return ExitCode.NETWORK_ERROR

    # 处理选择：插件 / Agent 下 stdin 非 TTY，只输出可解析的 stdout，由侧栏点选后带 queryUri 重试
    selection_info = payload.get("selection")
    if selection_info:
        items = selection_info.get("items", [])
        names = selection_info.get("names", [])
        billname = selection_info.get("billname", "")
        if not items or not names:
            return ExitCode.CONFIG_ERROR

        src = selection_info.get("source") or "byname"
        ui_text = _format_selection_stdout_for_ui(selection_info)
        if not _should_interactive_selection_prompt():
            # searchByName 多对象的提示须独占 stdout 末尾，不可再拼接 JSON，否则 Chat 侧栏
            # parseBillNameChoiceFromStdout 会误把 JSON 并入选项。
            # fast_lookup 多 URI 的解析基于「n) uri:」行，可与 JSON 同出。
            print(ui_text, end="")
            if src == "fast_lookup_uri":
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return ExitCode.SUCCESS

        print(ui_text, end="", file=sys.stdout)
        if src == "fast_lookup_uri":
            print(
                f"\n本地 metadata 快速索引中 [{billname}] 对应多条不同 uri，请选一条：",
                file=sys.stderr,
            )
        else:
            print(
                f"\n找到多个业务对象，请在终端为 [{billname}] 选择对应序号：",
                file=sys.stderr,
            )

        while True:
            for i, name in enumerate(names):
                print(f"  [{i+1}] {name}", file=sys.stderr)
            try:
                choice = input("\n请输入序号 (1-" + str(len(names)) + ") 或 q 退出: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n已退出", file=sys.stderr)
                return ExitCode.USER_CANCEL

            if choice.lower() == "q":
                print("已退出", file=sys.stderr)
                return ExitCode.USER_CANCEL

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    selected = items[idx]
                    req = cfg.setdefault("request", {})
                    if src == "fast_lookup_uri":
                        u = (selected.get("uri") or "").strip()
                        if u:
                            req["queryUri"] = u
                        logger.info(f"已选择元数据 uri: {u}")
                    else:
                        req["_selected_bo_code"] = selected.get("code")
                        req["_selected_bo_id"] = selected.get("id")
                        req["_selected_bo_name"] = selected.get("name")
                        logger.info(
                            f"已选择: {selected.get('name')} (code={selected.get('code')})"
                        )
                    break
                else:
                    print(f"无效的选择，请输入 1-{len(names)} 之间的数字", file=sys.stderr)
            except ValueError:
                print("无效的输入，请输入数字或 q 退出", file=sys.stderr)

        # 重新运行，使用选中的业务对象
        payload, err = run_all_bills(cfg)
        if err:
            print(err, file=sys.stderr)
            print(json.dumps({"error": err}, ensure_ascii=False))
            return ExitCode.NETWORK_ERROR

    write_outputs(cfg, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.run_db_check:
        import subprocess

        db = cfg.get("database") or {}
        if db.get("enabled"):
            logger.info("运行数据库校验...")
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent / "db_query.py"),
                    "--config",
                    args.config,
                ],
                check=False,
            )

    return ExitCode.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
