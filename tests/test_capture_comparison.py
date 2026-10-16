"""Tests for project-relative MATLAB capture comparison."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.io import savemat

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.domain.capture_comparison import compare_capture_files


SIGNAL_NAME = "Plant.VehicleMovement.Velocities.Vehicle.Linear.v_Total_Vehicle[km|h]"


def _write_capture(
    working_root: Path,
    file_name: str,
    values: tuple[float, ...],
    times: tuple[float, ...] | None = None,
) -> None:
    measurements = working_root / "Pool" / "Simulation" / "Measurements"
    measurements.mkdir(parents=True, exist_ok=True)
    time_values = np.arange(len(values), dtype=float) if times is None else np.asarray(times, dtype=float)
    savemat(
        measurements / file_name,
        {
            Path(file_name).stem: {
                "X": {"Data": time_values},
                "Y": {
                    "Name": SIGNAL_NAME,
                    "Unit": "km|h",
                    "Path": SIGNAL_NAME,
                    "Data": np.asarray(values, dtype=float),
                },
            }
        },
    )


def test_compare_capture_files_uses_each_projects_working_root(tmp_path: Path) -> None:
    first_project = tmp_path / "first-project"
    second_project = tmp_path / "second-project"
    _write_capture(first_project, "a.mat", (0.0, 1.0, 2.0))
    _write_capture(first_project, "b.mat", (0.0, 1.5, 2.5))
    _write_capture(second_project, "a.mat", (0.0, 10.0, 20.0))
    _write_capture(second_project, "b.mat", (0.0, 15.0, 25.0))

    first = compare_capture_files(first_project, "a.mat", "b.mat", "[]", '{"maximumAbsoluteError": 1.0}')
    second = compare_capture_files(second_project, "a.mat", "b.mat", "[]", '{"maximumAbsoluteError": 1.0}')

    assert first["signalSet"] == {"commonCount": 1, "onlyReferenceCount": 0, "onlyCandidateCount": 0}
    assert first["comparisons"][0]["metrics"]["maximumAbsoluteError"] == pytest.approx(0.5)
    assert first["verdict"] == "passed"
    assert second["comparisons"][0]["metrics"]["maximumAbsoluteError"] == pytest.approx(5.0)
    assert second["verdict"] == "failed"


def test_compare_capture_files_rejects_paths_outside_project_measurements(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="file name"):
        compare_capture_files(tmp_path, "..\\a.mat", "b.mat", "[]", "{}")


def test_compare_capture_files_does_not_pass_one_sample_overlap(tmp_path: Path) -> None:
    _write_capture(tmp_path, "a.mat", (0.0,))
    _write_capture(tmp_path, "b.mat", (0.0, 10.0, 20.0))

    result = compare_capture_files(tmp_path, "a.mat", "b.mat", "[]", '{"maximumAbsoluteError": 0.0}')

    assert result["comparisons"][0]["sampleCount"] == 1
    assert result["comparisons"][0]["status"] == "insufficientOverlap"
    assert result["comparisons"][0]["withinTolerance"] is None
    assert result["verdict"] == "notEvaluated"


def test_compare_capture_files_interpolates_candidate_time_raster(tmp_path: Path) -> None:
    _write_capture(tmp_path, "a.mat", (0.0, 2.0, 4.0), (0.0, 1.0, 2.0))
    _write_capture(tmp_path, "b.mat", (0.0, 1.0, 2.0, 3.0, 4.0), (0.0, 0.5, 1.0, 1.5, 2.0))

    result = compare_capture_files(tmp_path, "a.mat", "b.mat", "[]", '{"rootMeanSquaredError": 0.0}')

    comparison = result["comparisons"][0]
    assert comparison["alignment"] == "candidateInterpolatedToReference"
    assert comparison["sampleCount"] == 3
    assert comparison["metrics"]["rootMeanSquaredError"] == pytest.approx(0.0)
    assert comparison["withinTolerance"] is True
    assert result["verdict"] == "passed"


def test_compare_capture_files_paginates_comparisons_without_changing_verdict(tmp_path: Path) -> None:
    _write_capture(tmp_path, "a.mat", (0.0, 1.0, 2.0))
    _write_capture(tmp_path, "b.mat", (0.0, 1.5, 2.5))
    signal_specs = f'["{SIGNAL_NAME}","{SIGNAL_NAME}"]'

    first_page = compare_capture_files(tmp_path, "a.mat", "b.mat", signal_specs, "{}", offset=0, limit=1)
    second_page = compare_capture_files(tmp_path, "a.mat", "b.mat", signal_specs, "{}", offset=1, limit=1)

    assert first_page["comparisonCount"] == 2
    assert len(first_page["comparisons"]) == 1
    assert first_page["nextOffset"] == 1
    assert len(second_page["comparisons"]) == 1
    assert second_page["nextOffset"] is None
    assert first_page["verdict"] == second_page["verdict"] == "notEvaluated"


def test_compare_capture_files_rejects_nonfinite_metrics_from_finite_samples(tmp_path: Path) -> None:
    _write_capture(tmp_path, "reference.mat", (-1e308, 0.0))
    _write_capture(tmp_path, "candidate.mat", (1e308, 0.0))

    with pytest.raises(ValueError, match="finite|overflow|represent"):
        compare_capture_files(tmp_path, "reference.mat", "candidate.mat", "[]", '{"maximumAbsoluteError":1e308}')


def test_gateway_uses_active_projects_working_root(tmp_path: Path) -> None:
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    application = SimpleNamespace(ActiveProject=SimpleNamespace(WorkingRoot=str(tmp_path)))
    received: list[object] = []
    gateway._execute_com = lambda _, callback: callback(application)  # type: ignore[attr-defined, method-assign]
    gateway._compare_capture_files = lambda *arguments: received.extend(arguments) or {"verdict": "passed"}  # type: ignore[attr-defined]

    result = gateway.compare_captures("a.mat", "b.mat", "[]", "{}")

    assert result == {"verdict": "passed"}
    assert received == [str(tmp_path), "a.mat", "b.mat", "[]", "{}", 0, 100]
