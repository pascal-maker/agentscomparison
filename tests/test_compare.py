import subprocess
import sys


def test_compare_runner_outputs_deterministic_adapter_rows() -> None:
    result = subprocess.run(
        [sys.executable, "compare.py", "--scenario", "appliance_savings"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Scenario: Appliance off-peak savings" in result.stdout
    assert "harness" in result.stdout
    assert "tinyagi" in result.stdout
    assert "LUM-1002" in result.stdout
    assert "standby devices" in result.stdout
