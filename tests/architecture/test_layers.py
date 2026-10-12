"""TC-A01〜A03：利用規則（01 §1.6）と依存の決まり（DD-01）を、ソースの import から検査する。

構成要素ごとにパッケージを作り、`<層>/<構成要素>/__init__.py` に契約、同じパッケージの別モジュールに実装を置く。
- 契約（パッケージ）は、規則で呼んでよい層からだけ import できる。
- 実装（パッケージの中のモジュール）は、同じ構成要素の中と composition からだけ import できる（TC-A02）。
- domain は値の型だけを持ち、どの層からも import できる。
"""

import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src" / "fukugyononuko_social"
NAME = "fukugyononuko_social"
LAYERS = {"domain", "utilities", "engines", "access", "managers", "clients", "composition"}

# 契約を import してよい層（規則 1〜6）。同じ層の別の構成要素の契約は、utilities を除いて import できない
INTERFACES = {
    "domain": set(),
    "utilities": {"utilities"},
    "engines": {"utilities", "access"},
    "access": {"utilities"},
    "managers": {"utilities", "engines", "access"},
    "clients": {"utilities", "managers"},
    "composition": LAYERS - {"composition"},
}


@dataclass(frozen=True)
class Module:
    layer: str
    component: str | None  # domain・composition は None
    is_implementation: bool  # 構成要素のパッケージの中のモジュール


def describe(parts: tuple[str, ...]) -> Module | None:
    """`fukugyononuko_social` より下のモジュール名の並びを、層・構成要素・実装かどうかに分ける。"""
    if not parts or parts[0] not in LAYERS:
        return None
    layer = parts[0]
    if layer in {"domain", "composition"}:
        return Module(layer, None, False)
    component = parts[1] if len(parts) > 1 else None
    return Module(layer, component, len(parts) > 2)


def module_of(path: Path) -> Module | None:
    rel = path.relative_to(PKG).with_suffix("")
    parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
    return describe(tuple(parts))


def imports_of(path: Path) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.startswith(NAME + "."):
            found.append(tuple(node.module.split(".")[1:]))
        elif isinstance(node, ast.Import):
            found += [tuple(a.name.split(".")[1:]) for a in node.names if a.name.startswith(NAME + ".")]
    return found


def sources() -> list[Path]:
    return sorted(PKG.rglob("*.py"))


def violations() -> list[str]:
    problems = []
    for path in sources():
        src = module_of(path)
        if src is None:
            continue
        for parts in imports_of(path):
            dst = describe(parts)
            if dst is None:
                problems.append(f"{path.relative_to(ROOT)}：層に属さないモジュール {'.'.join(parts)}")
                continue
            if dst.layer == "domain":
                continue
            same_component = (src.layer, src.component) == (dst.layer, dst.component)
            if dst.is_implementation:
                if not same_component and src.layer != "composition":
                    problems.append(f"{path.relative_to(ROOT)}：実装 {'.'.join(parts)} を import している（TC-A02）")
            elif not same_component and dst.layer not in INTERFACES[src.layer]:
                problems.append(
                    f"{path.relative_to(ROOT)}：{src.layer} から {dst.layer} の契約 {'.'.join(parts)} を import している"
                )
    return problems


def test_a01_a02_imports_follow_layer_rules() -> None:
    assert violations() == []


def test_a01_detects_planted_violations() -> None:
    """検査そのものが違反を見つけられることを確かめる。"""
    planted = PKG / "engines" / "cost" / "zz_planted.py"
    planted.write_text(
        "from fukugyononuko_social.engines.aggregation import AggregationEngine\n"
        "from fukugyononuko_social.access.ledger.sqlite import X\n"
        "from fukugyononuko_social.managers.measurement import M\n",
        encoding="utf-8",
    )
    try:
        found = violations()
    finally:
        planted.unlink()
    assert len([p for p in found if "zz_planted" in p]) == 3


def test_a03_runtime_dependencies_are_stdlib_only() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []
    problems = []
    for path in sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for n in names:
                root = n.split(".")[0]
                if root != NAME and root not in sys.stdlib_module_names:
                    problems.append(f"{path.relative_to(ROOT)}：標準ライブラリ以外の {n}")
    assert problems == []
