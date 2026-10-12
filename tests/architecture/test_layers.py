"""TC-A01〜A03：利用規則（01 §1.6）と依存の決まり（DD-01）を、ソースの import と型注釈から検査する。"""

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src" / "fukugyononuko_social"
NAME = "fukugyononuko_social"

# 層ごとに import してよい層（DD-01）。同じ層の別の構成要素は import できない（規則 2〜4）
ALLOWED = {
    "contracts": set(),
    "utilities": {"contracts"},
    "engines": {"contracts", "utilities"},
    "access": {"contracts", "utilities"},
    "managers": {"contracts", "utilities"},
    "clients": {"contracts", "utilities", "composition"},
    "composition": {"contracts", "utilities", "engines", "access", "managers", "clients"},
}

# コンストラクタで受け取ってよい契約（規則 2・3）
ENGINE_CONTRACTS = {"AggregationEngine", "DraftPolicyEngine", "CostEngine"}
ACCESS_CONTRACTS = {"SettingsAccess", "LedgerAccess", "MetricsAccess", "DraftAccess", "ReportAccess", "ChannelAccess"}
MANAGER_CONTRACTS = {"MeasurementManager", "PublishingManager"}
UTILITY_CONTRACTS = {"Clock", "Security", "Logging"}
INJECTABLE = {
    "engines": ACCESS_CONTRACTS | UTILITY_CONTRACTS,
    "managers": ENGINE_CONTRACTS | ACCESS_CONTRACTS | UTILITY_CONTRACTS,
    "access": UTILITY_CONTRACTS,
}


def layer_of(path: Path) -> str:
    rel = path.relative_to(PKG)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def component_of(path: Path) -> tuple[str, ...]:
    """同じ構成要素とみなす範囲：層の中の 1 つ目のモジュールかサブパッケージ。"""
    rel = path.relative_to(PKG).with_suffix("")
    return rel.parts[:2]


def internal_imports(tree: ast.AST) -> list[tuple[str, ...]]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(NAME):
            parts = tuple(node.module.split(".")[1:])
            found += [parts + (alias.name,) for alias in node.names] if len(parts) == 1 and parts[0] in ALLOWED else [parts]
        elif isinstance(node, ast.Import):
            found += [tuple(a.name.split(".")[1:]) for a in node.names if a.name.startswith(NAME + ".")]
    return found


def sources() -> list[Path]:
    return [p for p in sorted(PKG.rglob("*.py")) if p.name != "__init__.py" or p.parent != PKG]


def test_a01_imports_follow_layer_rules() -> None:
    problems = []
    for path in sources():
        layer = layer_of(path)
        if layer == "__init__":
            continue
        for target in internal_imports(ast.parse(path.read_text(encoding="utf-8"))):
            if not target:
                continue
            target_layer = target[0]
            if target_layer == layer:
                if target[:2] != component_of(path)[:2] and layer not in {"contracts", "composition"}:
                    problems.append(f"{path.relative_to(ROOT)}：同じ層の別の構成要素 {'.'.join(target)} を import している")
            elif target_layer not in ALLOWED[layer]:
                problems.append(f"{path.relative_to(ROOT)}：{layer} から {'.'.join(target)} を import している")
    assert problems == []


def test_a01_constructors_receive_only_allowed_contracts() -> None:
    known = ENGINE_CONTRACTS | ACCESS_CONTRACTS | MANAGER_CONTRACTS | UTILITY_CONTRACTS
    problems = []
    for path in sources():
        layer = layer_of(path)
        if layer not in INJECTABLE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                for arg in node.args.args[1:] + node.args.kwonlyargs:
                    name = ast.unparse(arg.annotation) if arg.annotation else ""
                    if name in known and name not in INJECTABLE[layer]:
                        problems.append(f"{path.relative_to(ROOT)}：{layer} が {name} を受け取っている")
    assert problems == []


def test_a02_only_composition_imports_implementations() -> None:
    # 具体的な実装（engines・access・managers）を import してよいのは composition だけ
    problems = [
        f"{path.relative_to(ROOT)} → {'.'.join(t)}"
        for path in sources()
        if layer_of(path) != "composition"
        for t in internal_imports(ast.parse(path.read_text(encoding="utf-8")))
        if t and t[0] in {"engines", "access", "managers"} and t[0] != layer_of(path)
    ]
    assert problems == []


def test_a03_runtime_dependencies_are_stdlib_only() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []
    problems = []
    for path in sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for n in names:
                root = n.split(".")[0]
                if root != NAME and root not in sys.stdlib_module_names:
                    problems.append(f"{path.relative_to(ROOT)}：標準ライブラリ以外の {n}")
    assert problems == []
