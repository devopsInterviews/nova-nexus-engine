#!/usr/bin/env python3
"""
Derive schema/table hierarchy + lineage from a dbt manifest.json (v12).

Outputs:
- Database → Schema → Relation tree
- Each relation shows its DEPTH (distance from roots) and its immediate upstream physical parents
- Optional lineage print for any unique_id

Usage
  python dbt_lineage_tree.py manifest.json
  python dbt_lineage_tree.py manifest.json --no-sources
  python dbt_lineage_tree.py manifest.json --lineage model.pkg.my_model
  python dbt_lineage_tree.py manifest.json --json > lineage.json
"""

import argparse
import json
from collections import defaultdict
from functools import lru_cache
from typing import Dict, Any, List, Set, Tuple, Optional

PHYSICAL_NODE_TYPES = {"model", "seed", "snapshot"}  # sources handled separately

def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------- helpers for node identity / display ----------

def is_ephemeral(node: Dict[str, Any]) -> bool:
    return (
        node.get("resource_type") == "model"
        and (node.get("config") or {}).get("materialized") == "ephemeral"
    )

def is_disabled(node: Dict[str, Any]) -> bool:
    cfg = node.get("config") or {}
    return cfg.get("enabled") is False

def node_kind(node: Dict[str, Any]) -> str:
    """Returns 'model', 'seed', 'snapshot', etc."""
    return str(node.get("resource_type"))

def node_materialization(node: Dict[str, Any]) -> Optional[str]:
    if node_kind(node) == "model":
        return (node.get("config") or {}).get("materialized")
    return None

def node_identifier(node: Dict[str, Any]) -> str:
    """
    For models/seeds/snapshots: alias (if set) else name.
    For sources (handled elsewhere): identifier (fallback name).
    """
    return str(node.get("alias") or node.get("name") or "<unnamed>")

def node_db(node: Dict[str, Any]) -> str:
    return str(node.get("database") or "<default_db>")

def node_schema(node: Dict[str, Any]) -> str:
    return str(node.get("schema") or "<default_schema>")

def source_identifier(src: Dict[str, Any]) -> str:
    return str(src.get("identifier") or src.get("name") or "<unnamed>")

# ---------- main extraction ----------

class PhysicalInfo:
    def __init__(self, unique_id: str, database: str, schema: str,
                 identifier: str, kind: str, materialization: Optional[str]):
        self.unique_id = unique_id
        self.database = database
        self.schema = schema
        self.identifier = identifier
        self.kind = kind  # 'model' | 'seed' | 'snapshot' | 'source'
        self.materialization = materialization  # for models
    @property
    def label(self) -> str:
        km = f"{self.kind}:{self.materialization}" if (self.kind == "model" and self.materialization) else self.kind
        return f"{self.identifier} [{km}]"
    @property
    def fqn(self) -> str:
        return f"{self.database}.{self.schema}.{self.identifier}"

def build_physical_maps(
    manifest: Dict[str, Any],
    include_sources: bool = True,
    include_seeds: bool = True,
    include_snapshots: bool = True,
    include_models: bool = True,
    include_disabled: bool = False,
) -> Tuple[Dict[str, PhysicalInfo], Dict[str, Dict[str, List[str]]]]:
    """
    Returns:
      physical_info_by_uid: unique_id -> PhysicalInfo
      tree: { db: { schema: [unique_id, ...] } }   (values are UIDs, sorted later)
    """
    nodes = manifest.get("nodes") or {}
    sources = manifest.get("sources") or {}
    physical_info_by_uid: Dict[str, PhysicalInfo] = {}
    tree: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    # nodes (models/seeds/snapshots)
    for uid, node in nodes.items():
        rtype = node_kind(node)
        if include_disabled is False and is_disabled(node):
            continue
        if rtype == "model" and not include_models:
            continue
        if rtype == "seed" and not include_seeds:
            continue
        if rtype == "snapshot" and not include_snapshots:
            continue
        if rtype not in PHYSICAL_NODE_TYPES:
            continue
        if is_ephemeral(node):
            continue  # no physical relation

        pi = PhysicalInfo(
            unique_id=uid,
            database=node_db(node),
            schema=node_schema(node),
            identifier=node_identifier(node),
            kind=rtype,
            materialization=node_materialization(node),
        )
        physical_info_by_uid[uid] = pi
        tree[pi.database][pi.schema].append(uid)

    # sources
    if include_sources:
        for uid, src in sources.items():
            pi = PhysicalInfo(
                unique_id=uid,
                database=str(src.get("database") or "<default_db>"),
                schema=str(src.get("schema") or "<default_schema>"),
                identifier=source_identifier(src),
                kind="source",
                materialization=None,
            )
            physical_info_by_uid[uid] = pi
            tree[pi.database][pi.schema].append(uid)

    # stable sorting by schema then identifier
    for db in tree:
        for sch in tree[db]:
            tree[db][sch].sort(key=lambda u: (physical_info_by_uid[u].kind, physical_info_by_uid[u].identifier))
    return physical_info_by_uid, tree

# ---------- lineage from depends_on (with ephemeral collapse) ----------

def resource_prefix(unique_id: str) -> str:
    return unique_id.split(".", 1)[0] if "." in unique_id else unique_id

def _depends_on_uids(node: Dict[str, Any]) -> List[str]:
    dep = node.get("depends_on") or {}
    return list(dep.get("nodes") or [])  # ignore macros for physical lineage

def build_parent_map_physical(manifest: Dict[str, Any],
                              physical_info_by_uid: Dict[str, PhysicalInfo]) -> Dict[str, Set[str]]:
    """
    For each PHYSICAL uid, compute immediate PHYSICAL parents by reading depends_on
    and collapsing ephemerals.
    """
    nodes = manifest.get("nodes") or {}
    sources = manifest.get("sources") or {}

    @lru_cache(maxsize=None)
    def expand_to_physical(uid: str) -> Set[str]:
        """
        Returns the set of PHYSICAL uids represented by 'uid'.
        - If uid is a source or a physical node -> {uid}
        - If uid is an ephemeral model -> recurse through its depends_on nodes
        - If uid is a non-physical/test/analysis/etc -> empty set
        """
        pref = resource_prefix(uid)
        if uid in physical_info_by_uid:
            return {uid}
        if pref == "source":
            # included only if user opted to include sources and thus it's in physical_info_by_uid
            return {uid} if uid in physical_info_by_uid else set()
        if pref == "model":
            n = nodes.get(uid)
            if n is None:
                return set()
            if is_ephemeral(n):
                ups = set()
                for p in _depends_on_uids(n):
                    ups |= expand_to_physical(p)
                return ups
            # non-ephemeral models we didn't include (e.g., disabled)
            return {uid} if uid in physical_info_by_uid else set()
        # ignore tests/macros/analyses/etc
        return set()

    parent_map: Dict[str, Set[str]] = {uid: set() for uid in physical_info_by_uid.keys()}

    # go over every physical node that came from "nodes"
    for uid, pi in physical_info_by_uid.items():
        # sources have no depends_on in manifest (they're roots)
        if resource_prefix(uid) == "source":
            parent_map[uid] = set()
            continue

        # read raw depends_on for the underlying manifest node
        node = nodes.get(uid)
        raw_parents = _depends_on_uids(node) if node else []
        collapsed: Set[str] = set()
        for p in raw_parents:
            collapsed |= expand_to_physical(p)
        # never include self
        collapsed.discard(uid)
        parent_map[uid] = collapsed

    return parent_map

# ---------- depth computation ----------

def compute_depths(parent_map: Dict[str, Set[str]]) -> Dict[str, int]:
    """
    depth(uid) = 0 if no parents (roots like sources/seeds with no parents)
               = 1 + max(depth(parent))
    """
    @lru_cache(maxsize=None)
    def _depth(u: str) -> int:
        parents = parent_map.get(u) or set()
        if not parents:
            return 0
        return 1 + max(_depth(p) for p in parents)
    return {u: _depth(u) for u in parent_map.keys()}

# ---------- rendering ----------

def print_ascii_tree(tree: Dict[str, Dict[str, List[str]]],
                     info: Dict[str, PhysicalInfo],
                     parent_map: Dict[str, Set[str]],
                     depth_map: Dict[str, int]) -> None:
    def branch(prefix: str, is_last: bool) -> str:
        return f"{prefix}{'└── ' if is_last else '├── '}"
    def indent(prefix: str, is_last: bool) -> str:
        return f"{prefix}{'    ' if is_last else '│   '}"

    db_names = sorted(tree)
    for i, db in enumerate(db_names):
        is_last_db = (i == len(db_names) - 1)
        print(db)
        schemas = sorted(tree[db])
        for j, sch in enumerate(schemas):
            is_last_sch = (j == len(schemas) - 1)
            print(branch("", is_last_sch) + sch)

            # sort relations by depth DESC (latest first), then by name
            uids = tree[db][sch]
            uids_sorted = sorted(uids, key=lambda u: (-depth_map.get(u, 0), info[u].identifier, info[u].kind))

            for k, u in enumerate(uids_sorted):
                is_last_rel = (k == len(uids_sorted) - 1)
                pi = info[u]
                d = depth_map.get(u, 0)
                print(branch(indent("", is_last_sch), is_last_rel) + f"{pi.label}  (depth={d})")

                # show immediate upstream parents (physical only)
                parents = sorted(parent_map.get(u) or set(), key=lambda x: (info[x].database, info[x].schema, info[x].identifier))
                if parents:
                    parent_lines_prefix = indent(indent("", is_last_sch), is_last_rel)
                    for p in parents:
                        pp = info[p]
                        print(parent_lines_prefix + f"↑ from {pp.fqn} [{pp.kind}]")

def print_lineage(manifest: Dict[str, Any],
                  root_uid: str,
                  info: Dict[str, PhysicalInfo],
                  parent_map: Dict[str, Set[str]],
                  depth_map: Dict[str, int],
                  max_depth: int = 50) -> None:
    """
    Print upstream lineage recursively from a uid (physical-only, ephemerals collapsed).
    """
    seen: Set[str] = set()

    def _recurse(uid: str, prefix: str, is_last: bool, depth: int):
        if uid in seen:
            print(f"{prefix}{'└── ' if is_last else '├── '}{info[uid].fqn} [{info[uid].kind}] (depth={depth_map[uid]}) [cycle?]")
            return
        seen.add(uid)

        pi = info[uid]
        print(f"{prefix}{'└── ' if is_last else '├── '}{pi.fqn} [{pi.kind}] (depth={depth_map[uid]})")
        if depth >= max_depth:
            return
        parents = sorted(parent_map.get(uid) or set(), key=lambda x: (info[x].database, info[x].schema, info[x].identifier))
        for i, p in enumerate(parents):
            last = (i == len(parents) - 1)
            _recurse(p, prefix + ('    ' if is_last else '│   '), last, depth + 1)

    root = info.get(root_uid)
    if not root:
        print(f"{root_uid}: not found or not a physical node")
        return
    print(f"{root.fqn} [{root.kind}] (depth={depth_map[root_uid]})")
    parents = sorted(parent_map.get(root_uid) or set(), key=lambda x: (info[x].database, info[x].schema, info[x].identifier))
    for i, p in enumerate(parents):
        _recurse(p, "", i == len(parents) - 1, 1)

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help="Path to dbt manifest.json (v12)")
    ap.add_argument("--no-sources", action="store_true", help="Exclude sources (show only dbt-created relations)")
    ap.add_argument("--include-disabled", action="store_true", help="Include disabled nodes if present in manifest")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of ASCII tree")
    ap.add_argument("--lineage", metavar="UNIQUE_ID", help="Print upstream lineage (physical-only) for a given unique_id")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)

    info, tree = build_physical_maps(
        manifest,
        include_sources=not args.no_sources,
        include_seeds=True,
        include_snapshots=True,
        include_models=True,
        include_disabled=args.include_disabled,
    )
    parent_map = build_parent_map_physical(manifest, info)
    depth_map = compute_depths(parent_map)

    if args.lineage:
        print_lineage(manifest, args.lineage, info, parent_map, depth_map)
        return

    if args.json:
        # emit a machine-friendly structure
        out = {
            "relations": [
                {
                    "unique_id": uid,
                    "database": pi.database,
                    "schema": pi.schema,
                    "identifier": pi.identifier,
                    "kind": pi.kind,
                    "materialization": pi.materialization,
                    "depth": depth_map.get(uid, 0),
                    "upstream_uids": sorted(list(parent_map.get(uid) or [])),
                }
                for uid, pi in sorted(info.items(), key=lambda kv: (kv[1].database, kv[1].schema, kv[1].identifier))
            ]
        }
        print(json.dumps(out, indent=2))
    else:
        print_ascii_tree(tree, info, parent_map, depth_map)

if __name__ == "__main__":
    main()
