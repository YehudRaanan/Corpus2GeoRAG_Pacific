"""Separate preparation and decisions without loading model dependencies."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("step", "expected", "excluded"),
    [
        ("prepare_candidates", "--mentions", "--checkpoint"),
        ("resolve_entities", "--checkpoint", "--mentions"),
    ],
)
def test_matching_steps_have_separate_lazy_entry_points(step, expected, excluded):
    module = f"GG_Data.entity_resolution.hundred_page_pilot.{step}"
    code = (
        "import importlib, sys; "
        f"step = importlib.import_module({module!r}); "
        "assert 'torch' not in sys.modules; "
        "assert 'GG_Data.entity_resolution.decision_model.model' not in sys.modules; "
        "sys.argv = [step.__name__, '--help']; step.main()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
    assert excluded not in result.stdout
