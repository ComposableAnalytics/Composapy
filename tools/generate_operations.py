from pathlib import Path
import re
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _const import COMPOSABLE_PROD_DIR

_SERVICE = re.compile(
    r"^\s*\[ServiceContract\b[^\]]*\](?:\s*\[[^\]]*\])*\s*public\s+interface\s+(\w+)[^{]*\{",
    re.M,
)
_OPERATION = re.compile(
    r"(?P<attrs>(?:\s*\[[^\]]*\])+)\s*(?P<ret>[\w<>\[\],.?\s]+?)\s+(?P<name>\w+)\s*\((?P<params>[^;]*?)\)\s*;",
)
_ATTRIBUTE = re.compile(r"\[\s*(\w+)\s*(?:\((.*?)\))?\s*\]", re.S)
_KNOWN_OP_ATTRS = {"OperationContract", "OperationCancellable", "WebGet", "WebInvoke"}


def generate_ops(interface_dir=None, out=None):
    dir_path = (
        Path(interface_dir)
        if interface_dir
        else COMPOSABLE_PROD_DIR / "CompAnalytics.IServices"
    )
    services = dict()

    problems = []
    for item in sorted(dir_path.glob("I*.cs")):
        text = _strip_comments(item.read_text(encoding="utf-8-sig"))
        m = _SERVICE.search(text)
        if m is not None:
            try:
                text = _trim_body(
                    text, m.end() - 1
                )  # the end of it will be the opening {
                ops = parse(text)
                expected = len(re.findall(r"\[OperationContract", text))
                services[m.group(1)[1:]] = ops
                if len(ops) != expected:
                    problems.append(
                        (
                            item.name,
                            f"parsed {len(ops)} of {expected} [OperationContract]",
                        )
                    )
            except Exception as e:
                problems.append((item.name, str(e)))
                continue

    if problems:
        for p in problems:
            print("  ", p)
        raise SystemExit(f"{len(problems)} problem(s); operations.json not written.")

    out = (
        out
        or Path(__file__).resolve().parent.parent
        / "composapy"
        / "_wire"
        / "operations.json"
    )
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(services, f, indent=2)
        f.write("\n")


def _strip_comments(text):
    text = re.sub(
        r"/\*.*?\*/", "", text, flags=re.S
    )  # block comments, including /// doc blocks
    return re.sub(r"//[^\n]*", "", text)  # line comments, including ///


def parse(text):
    ops = []
    for m in _OPERATION.finditer(text):
        attrs = {}
        for a in _ATTRIBUTE.finditer(m.group("attrs")):
            attrs[a.group(1)] = a.group(2) or ""
        unknown = set(attrs) - _KNOWN_OP_ATTRS
        if unknown:
            raise ValueError(f"Unknown attribute(s) {unknown} on {m.group('name')}")
        if "OperationContract" in attrs:
            params = [_parse_param(p) for p in _split_params(m.group("params"))]

            verb = "POST"
            if "WebInvoke" in attrs:
                mm = re.search(r'Method\s*=\s*"(\w+)"', attrs["WebInvoke"])
                if mm:
                    verb = mm.group(1)
            elif "WebGet" in attrs:
                verb = "GET"

            uri = None
            for a in ("WebGet", "WebInvoke"):
                if a in attrs:
                    um = re.search(r'UriTemplate\s*=\s*"([^"]*)"', attrs[a])
                    uri = um.group(1) if um else None

            ops.append(
                {
                    "name": m.group("name"),
                    "params": [n for n, _ in params],
                    "verb": verb,
                    "uri": uri,
                    "request": (
                        "raw"
                        if len(params) == 1 and params[0][1] == "Stream"
                        else "json"
                    ),
                    "response": "raw" if m.group("ret").strip() == "Stream" else "json",
                }
            )
    return ops


def _trim_body(text, beginning_idx):
    depth = 0
    for i in range(beginning_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[beginning_idx:i]
    raise ValueError("Unbalanced braces")


def _split_params(params):
    out, depth, current = [], 0, ""
    for ch in params:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        out.append(current)
    return out


def _parse_param(p):
    p = p.split("=")[0].strip()
    type_, _, name = p.rpartition(" ")
    return name, " ".join(type_.split())


if __name__ == "__main__":
    generate_ops()
