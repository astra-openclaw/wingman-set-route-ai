"""Static privacy/import gate. SRA_PRIVATE_WORDS is a JSON array or newline list."""
import argparse
import ast
import json
import os
import re
from pathlib import Path
import sys

def private_words():
    raw = os.environ.get("SRA_PRIVATE_WORDS", "")
    if not raw.strip():
        raise ValueError("SRA_PRIVATE_WORDS must be supplied; scan was not performed.")
    try:
        words = json.loads(raw)
    except json.JSONDecodeError:
        words = raw.splitlines()
    if not isinstance(words, list) or not words or any(not isinstance(w,str) or not w for w in words):
        raise ValueError("SRA_PRIVATE_WORDS must contain nonempty strings.")
    return words


def scan(root, words):
    errors = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(p in {".git","__pycache__",".venv","dist"} for p in rel.parts) or not path.is_file():
            continue
        content = path.read_bytes().decode("utf-8", errors="replace").casefold()
        for i, word in enumerate(words):
            # Word edges avoid flagging a private short name inside an unrelated
            # public game name; paths and punctuation-only tokens remain literal.
            pattern = (r"(?<![a-z0-9])" if word[0].isalnum() else "") + re.escape(word.casefold()) + (r"(?![a-z0-9])" if word[-1].isalnum() else "")
            if re.search(pattern, content) or re.search(pattern, str(rel).casefold()):
                # Do not echo private terms themselves into logs.
                errors.append(f"{rel}: forbidden term #{i+1}")
        if path.suffix == ".py":
            tree = ast.parse(path.read_text(encoding="utf-8"),feature_version=(3,11))
            if rel.parts[0] == "set_route_ai":
                for node in ast.walk(tree):
                    if isinstance(node,ast.ImportFrom) and (node.module or "").startswith("services"):
                        errors.append(f"{rel}: direct runtime-service import")
                    if isinstance(node,ast.Import):
                        if any(n.name.startswith(("services.","requests","urllib")) for n in node.names):
                            errors.append(f"{rel}: runtime-service/network import")
    return errors


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    try:
        errors=scan(args.root,private_words())
    except ValueError as exc:
        print(str(exc));return 2
    for error in errors:print(error)
    if not errors:print("Static check OK: privacy terms absent; runtime imports and Python syntax checked.")
    return bool(errors)

if __name__=="__main__":
    raise SystemExit(main())
