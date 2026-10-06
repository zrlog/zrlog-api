#!/usr/bin/env python3
"""Generate the contract catalog and synchronize consumer snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
CONSUMERS = {
    "zrlog-client-java": ("src/main/resources/openapi", None),
    "zrlog-www": ("src/main/resources/api-docs", None),
    "zrlog-admin-web": ("docs/api", "admin-web"),
    "zrlog-blog-web-parent": ("docs/api", "blog-web"),
}


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError(f"OpenAPI keys must be unique strings: {key!r}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def check_refs(value, root):
    if isinstance(value, dict):
        if "$ref" in value:
            ref = value["$ref"]
            if not ref.startswith("#/"):
                raise ValueError(f"Contract must be self-contained: {ref}")
            target = root
            for part in unquote(ref[2:]).split("/"):
                key = part.replace("~1", "/").replace("~0", "~")
                target = target[int(key)] if isinstance(target, list) else target[key]
        for child in value.values():
            check_refs(child, root)
    elif isinstance(value, list):
        for child in value:
            check_refs(child, root)


def catalog():
    sources = []
    ids = set()
    for path in sorted(ROOT.glob("*.yaml")):
        data = path.read_bytes()
        spec = yaml.load(data, Loader=UniqueLoader)
        source_id = spec["x-zrlog-id"]
        if source_id in ids or path.name != source_id + ".yaml":
            raise ValueError(f"Duplicate or mismatched source id: {source_id}")
        ids.add(source_id)
        if not str(spec["openapi"]).startswith("3.1."):
            raise ValueError(f"Expected OpenAPI 3.1: {path}")
        check_refs(spec, spec)
        operations, operation_ids = [], set()
        for api_path, item in spec["paths"].items():
            for method, operation in item.items():
                if method not in METHODS:
                    continue
                operation_id = operation["operationId"]
                if operation_id in operation_ids or not operation_id or not api_path.startswith("/"):
                    raise ValueError(f"Invalid/duplicate operation: {source_id}/{operation_id}")
                operation_ids.add(operation_id)
                if not operation.get("responses"):
                    raise ValueError(f"Missing responses: {operation_id}")
                operations.append({"operationId": operation_id, "method": method.upper(),
                                   "path": api_path, "summary": operation.get("summary", "")})
        if not operations:
            raise ValueError(f"No operations: {source_id}")
        sources.append({"id": source_id, "file": path.name, "title": spec["info"]["title"],
                        "version": spec["info"]["version"], "sha256": hashlib.sha256(data).hexdigest(),
                        "operations": operations})
    if not sources:
        raise ValueError("No contracts found")
    return (json.dumps({"schemaVersion": 1, "sources": sources}, ensure_ascii=False, indent=2) + "\n").encode()


def write_or_check(path, data, check):
    if check:
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"Stale generated file: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("index", "sync"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--workspace", type=Path, default=ROOT.parent)
    parser.add_argument("--consumer", choices=CONSUMERS, action="append")
    args = parser.parse_args()
    index = catalog()
    write_or_check(ROOT / "index.json", index, args.check or args.command == "sync")
    if args.command == "sync":
        for name in args.consumer or CONSUMERS:
            repository = args.workspace / name
            if not repository.is_dir():
                if args.consumer:
                    raise ValueError(f"Missing consumer: {repository}")
                continue
            directory, source_id = CONSUMERS[name]
            destination = repository / directory
            if source_id is None:
                write_or_check(destination / "index.json", index, args.check)
            for source in json.loads(index)["sources"]:
                if source_id is None or source["id"] == source_id:
                    filename = source["file"] if source_id is None else "openapi.yaml"
                    write_or_check(destination / filename, (ROOT / source["file"]).read_bytes(), args.check)
            print(f"{'Checked' if args.check else 'Synced'} {name}")
    else:
        print(f"{'Checked' if args.check else 'Generated'} index.json")


if __name__ == "__main__":
    main()
