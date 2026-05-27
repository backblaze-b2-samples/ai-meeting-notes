"""Structural tests that enforce layering rules and code quality invariants."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).parent.parent / "app"

# Layer ordering: lower layers must not import from higher layers
LAYER_ORDER = ["types", "config", "repo", "service", "runtime"]

# Map of layer -> set of layers it must NOT import from
FORBIDDEN_IMPORTS: dict[str, set[str]] = {}
for i, layer in enumerate(LAYER_ORDER):
    FORBIDDEN_IMPORTS[layer] = set(LAYER_ORDER[i + 1 :])


# External SDK clients allowed only inside `repo/`. AssemblyAI / OpenAI /
# Anthropic clients are wrapped exactly like boto3 — service-layer callers
# get provider-neutral dicts, never SDK objects.
SDK_PACKAGES = {"boto3", "botocore", "assemblyai", "openai", "anthropic"}


def _get_python_files(directory: Path) -> list[Path]:
    """Get all .py files in a directory recursively."""
    return list(directory.rglob("*.py"))


def _get_imports(filepath: Path) -> list[str]:
    """Extract all import module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _layer_of_import(module: str) -> str | None:
    """Return the layer name if the import is from app.<layer>, else None."""
    if not module.startswith("app."):
        return None
    parts = module.split(".")
    if len(parts) >= 2:
        return parts[1]
    return None


def _is_sdk_import(imp: str) -> str | None:
    """Return the SDK package name if the import is from one, else None."""
    root = imp.split(".", 1)[0]
    return root if root in SDK_PACKAGES else None


def test_no_backward_imports():
    """Verify no layer imports from a higher layer."""
    violations = []
    for layer in LAYER_ORDER:
        layer_dir = APP_ROOT / layer
        if not layer_dir.exists():
            continue
        for pyfile in _get_python_files(layer_dir):
            for imp in _get_imports(pyfile):
                imported_layer = _layer_of_import(imp)
                if imported_layer and imported_layer in FORBIDDEN_IMPORTS[layer]:
                    rel = pyfile.relative_to(APP_ROOT.parent)
                    violations.append(
                        f"{rel}: {layer}/ imports from {imported_layer}/ ({imp})"
                    )
    assert violations == [], "Backward import violations:\n" + "\n".join(violations)


def test_boto3_only_in_repo():
    """Verify boto3 is only imported in app/repo/."""
    violations = []
    for layer in LAYER_ORDER:
        if layer == "repo":
            continue
        layer_dir = APP_ROOT / layer
        if not layer_dir.exists():
            continue
        for pyfile in _get_python_files(layer_dir):
            for imp in _get_imports(pyfile):
                if (
                    imp == "boto3"
                    or imp.startswith("boto3.")
                    or imp == "botocore"
                    or imp.startswith("botocore.")
                ):
                    rel = pyfile.relative_to(APP_ROOT.parent)
                    violations.append(f"{rel}: boto3/botocore imported outside repo/")
    assert violations == [], "boto3 boundary violations:\n" + "\n".join(violations)


def test_external_sdks_only_in_repo():
    """Verify AssemblyAI / OpenAI / Anthropic SDKs are only imported in app/repo/.

    The transcription + LLM adapters live in `repo/` exactly like boto3 —
    service-layer code consumes provider-neutral dicts, never SDK types.
    """
    violations = []
    for layer in LAYER_ORDER:
        if layer == "repo":
            continue
        layer_dir = APP_ROOT / layer
        if not layer_dir.exists():
            continue
        for pyfile in _get_python_files(layer_dir):
            for imp in _get_imports(pyfile):
                sdk = _is_sdk_import(imp)
                if sdk and sdk != "boto3" and sdk != "botocore":
                    rel = pyfile.relative_to(APP_ROOT.parent)
                    violations.append(
                        f"{rel}: {sdk} imported outside repo/ (import: {imp})"
                    )
    assert violations == [], "External SDK boundary violations:\n" + "\n".join(
        violations
    )


def test_file_size_limits():
    """Verify no Python file exceeds 300 lines."""
    violations = []
    for pyfile in _get_python_files(APP_ROOT):
        line_count = len(pyfile.read_text().splitlines())
        if line_count > 300:
            rel = pyfile.relative_to(APP_ROOT.parent)
            violations.append(f"{rel}: {line_count} lines (max 300)")
    assert violations == [], "File size violations:\n" + "\n".join(violations)


def test_all_layers_exist():
    """Verify all expected layer directories exist."""
    for layer in LAYER_ORDER:
        layer_dir = APP_ROOT / layer
        assert layer_dir.exists(), f"Missing layer directory: app/{layer}/"
        init_file = layer_dir / "__init__.py"
        assert init_file.exists(), f"Missing __init__.py in app/{layer}/"


def test_required_meeting_modules_exist():
    """Verify the meetings sample has its load-bearing modules in place."""
    required = [
        APP_ROOT / "types" / "meeting.py",
        APP_ROOT / "types" / "search.py",
        APP_ROOT / "repo" / "meetings_store.py",
        APP_ROOT / "repo" / "transcription.py",
        APP_ROOT / "repo" / "llm.py",
        APP_ROOT / "service" / "meeting.py",
        APP_ROOT / "service" / "pipeline.py",
        APP_ROOT / "service" / "search.py",
        APP_ROOT / "runtime" / "meetings.py",
        APP_ROOT / "runtime" / "search.py",
    ]
    missing = [str(p.relative_to(APP_ROOT.parent)) for p in required if not p.exists()]
    assert missing == [], "Missing meeting-pipeline modules:\n" + "\n".join(missing)
