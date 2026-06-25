import re
from pathlib import Path

import main as api_main
from app.config.settings import (
    B2_PLACEHOLDER_VALUES,
    B2_REGION_PATTERN,
    B2_REQUIRED_SETTINGS,
    B2_ROLLING_MIGRATION_HELP,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _extract_js_strings(source: str, name: str) -> set[str]:
    match = re.search(
        rf"export const {name} = (?:new Set\()?\[(.*?)\]\)?;",
        source,
        re.DOTALL,
    )
    assert match, f"Could not find {name} in doctor env module"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _extract_js_regex(source: str, name: str) -> str:
    match = re.search(rf"export const {name} = /(.*)/;", source)
    assert match, f"Could not find {name} in doctor env module"
    return match.group(1)


def _extract_js_joined_strings(source: str, name: str) -> str:
    match = re.search(
        rf"export const {name} = \[(.*?)\]\.join\(\" \"\);",
        source,
        re.DOTALL,
    )
    assert match, f"Could not find {name} in doctor env module"
    return " ".join(re.findall(r'"([^"]+)"', match.group(1)))


def test_b2_env_contract_has_drift_guard():
    doctor_source = (REPO_ROOT / "scripts/doctor.mjs").read_text()
    doctor_env_source = (REPO_ROOT / "scripts/doctor-env.mjs").read_text()
    env_example_source = (REPO_ROOT / ".env.example").read_text()
    required_env_names = {env_name for _, env_name in B2_REQUIRED_SETTINGS}

    env_example_values = {}
    for raw in env_example_source.splitlines():
        line = raw.strip()
        if not line.startswith("B2_") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in required_env_names:
            env_example_values[key] = value

    assert api_main.B2_REQUIRED_SETTINGS == B2_REQUIRED_SETTINGS
    assert api_main.B2_PLACEHOLDER_VALUES == B2_PLACEHOLDER_VALUES
    assert api_main.B2_ROLLING_MIGRATION_HELP == B2_ROLLING_MIGRATION_HELP
    assert 'from "./doctor-env.mjs"' in doctor_source
    assert _extract_js_strings(doctor_env_source, "REQUIRED_B2_VARS") == required_env_names
    assert _extract_js_strings(doctor_env_source, "PLACEHOLDERS") == set(B2_PLACEHOLDER_VALUES)
    assert _extract_js_regex(doctor_env_source, "B2_REGION_PATTERN") == B2_REGION_PATTERN
    assert (
        _extract_js_joined_strings(doctor_env_source, "B2_ROLLING_MIGRATION_FIX")
        == B2_ROLLING_MIGRATION_HELP
    )
    assert set(env_example_values) == required_env_names
    assert set(env_example_values.values()) == set(B2_PLACEHOLDER_VALUES)

    example_region = re.search(r"^# B2_REGION=(\S+)$", env_example_source, re.MULTILINE)
    assert example_region
    assert re.fullmatch(B2_REGION_PATTERN, example_region.group(1))
