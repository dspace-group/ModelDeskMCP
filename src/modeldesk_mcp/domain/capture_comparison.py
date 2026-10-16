"""Read and compare ModelDesk MATLAB captures within an active project.

Comparisons use finite samples and must reject arithmetic whose returned metrics
cannot be represented as finite doubles; this module never edits capture files.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat


MEASUREMENTS_RELATIVE_PATH = Path("Pool") / "Simulation" / "Measurements"
MAX_CAPTURE_FILE_SIZE_BYTES = 512 * 1024 * 1024
MAX_COMPARISON_PAGE_SIZE = 500
TOLERANCE_KEYS = ("meanAbsoluteError", "rootMeanSquaredError", "maximumAbsoluteError")


def compare_capture_files(
    working_root: str | Path,
    reference_capture: str,
    candidate_capture: str,
    signal_specs_json: str,
    tolerances_json: str,
    offset: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """Compare two project-local captures and return finite metrics or ``ValueError``.

Both names must resolve to bounded MAT files beneath the measurements directory;
signal and tolerance JSON is validated before a result is returned. This function
performs read-only filesystem access and never writes captures or project state.
"""

    if offset < 0:
        raise ValueError("Comparison offset must not be negative.")
    if limit < 1 or limit > MAX_COMPARISON_PAGE_SIZE:
        raise ValueError(f"Comparison limit must be between 1 and {MAX_COMPARISON_PAGE_SIZE}.")
    measurements_directory = Path(working_root).resolve() / MEASUREMENTS_RELATIVE_PATH
    reference = _load_capture(_resolve_capture_path(measurements_directory, reference_capture))
    candidate = _load_capture(_resolve_capture_path(measurements_directory, candidate_capture))
    signal_pairs = _parse_signal_specs(signal_specs_json, reference["signals"], candidate["signals"])
    tolerances = _parse_tolerances(tolerances_json)
    all_comparisons = tuple(
        _compare_signal(reference, candidate, reference_name, candidate_name, tolerances)
        for reference_name, candidate_name in signal_pairs
    )
    evaluated = tuple(item["withinTolerance"] for item in all_comparisons if item["withinTolerance"] is not None)
    verdict = "notEvaluated" if not evaluated else "passed" if all(evaluated) else "failed"
    reference_names = set(reference["signals"])
    candidate_names = set(candidate["signals"])
    end_offset = min(len(all_comparisons), offset + limit)
    return {
        "referenceCapture": _capture_summary(reference_capture, reference),
        "candidateCapture": _capture_summary(candidate_capture, candidate),
        "signalSet": {
            "commonCount": len(reference_names & candidate_names),
            "onlyReferenceCount": len(reference_names - candidate_names),
            "onlyCandidateCount": len(candidate_names - reference_names),
        },
        "comparisons": all_comparisons[offset:end_offset],
        "comparisonCount": len(all_comparisons),
        "nextOffset": end_offset if end_offset < len(all_comparisons) else None,
        "verdict": verdict,
    }


def _resolve_capture_path(measurements_directory: Path, capture_name: str) -> Path:
    normalized = capture_name.strip()
    if normalized == "":
        raise ValueError("Capture file name must not be empty.")
    if "/" in normalized or "\\" in normalized or Path(normalized).name != normalized:
        raise ValueError("Capture must be a file name without directory components.")
    if Path(normalized).suffix.lower() != ".mat":
        raise ValueError("Capture file name must use the .mat extension.")
    measurements_root = measurements_directory.resolve()
    capture_path = (measurements_root / normalized).resolve()
    if capture_path.parent != measurements_root:
        raise ValueError("Capture must resolve inside the active project's measurements directory.")
    if not capture_path.is_file():
        raise ValueError(f"Capture '{normalized}' was not found in the active project's measurements directory.")
    if capture_path.stat().st_size > MAX_CAPTURE_FILE_SIZE_BYTES:
        raise ValueError(f"Capture '{normalized}' exceeds the supported 512 MiB size limit.")
    return capture_path


def _load_capture(path: Path) -> dict[str, Any]:
    try:
        document = loadmat(path, squeeze_me=True, struct_as_record=False)
    except Exception as exception:
        raise ValueError(f"Capture '{path.name}' is not a readable MATLAB 5 file: {exception}") from exception
    variable_names = tuple(name for name in document if not name.startswith("__"))
    preferred_name = path.stem if path.stem in variable_names else None
    if preferred_name is None and len(variable_names) != 1:
        raise ValueError(f"Capture '{path.name}' must contain one root measurement structure.")
    root = document[preferred_name or variable_names[0]]
    try:
        times = _numeric_array(root.X.Data, "time axis")
        raw_signals = root.Y if isinstance(root.Y, np.ndarray) else np.asarray([root.Y], dtype=object)
    except (AttributeError, TypeError, ValueError) as exception:
        raise ValueError(f"Capture '{path.name}' does not contain the expected ModelDesk X/Y measurement structure.") from exception
    if not np.all(np.isfinite(times)):
        raise ValueError(f"Capture '{path.name}' time axis must contain only finite values.")
    signals: dict[str, dict[str, Any]] = {}
    for raw_signal in raw_signals.reshape(-1):
        try:
            signal_name = str(raw_signal.Name)
            signal_values = _numeric_array(raw_signal.Data, f"signal '{signal_name}'")
            signal_unit = str(raw_signal.Unit)
        except (AttributeError, TypeError, ValueError) as exception:
            raise ValueError(f"Capture '{path.name}' contains an invalid signal structure.") from exception
        if signal_name in signals:
            raise ValueError(f"Capture '{path.name}' contains duplicate signal '{signal_name}'.")
        if signal_values.size != times.size:
            raise ValueError(
                f"Capture '{path.name}' signal '{signal_name}' has {signal_values.size} values for {times.size} timestamps."
            )
        signals[signal_name] = {"unit": signal_unit, "values": signal_values}
    if not signals:
        raise ValueError(f"Capture '{path.name}' does not contain any signals.")
    return {"times": times, "signals": signals, "sizeBytes": path.stat().st_size}


def _numeric_array(value: Any, label: str) -> np.ndarray[Any, np.dtype[np.float64]]:
    try:
        values = np.asarray(value, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exception:
        raise ValueError(f"Capture {label} must contain numeric values.") from exception
    if values.size == 0:
        raise ValueError(f"Capture {label} must not be empty.")
    return values


def _parse_signal_specs(
    json_text: str,
    reference_signals: dict[str, Any],
    candidate_signals: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    try:
        data = json.loads(json_text) if json_text.strip() else []
    except json.JSONDecodeError as exception:
        raise ValueError(f"Signal specifications must be a JSON array: {exception.msg}") from exception
    if not isinstance(data, list):
        raise ValueError("Signal specifications must be a JSON array.")
    if len(data) > 500:
        raise ValueError("At most 500 signal specifications are supported.")
    if not data:
        common = sorted(set(reference_signals) & set(candidate_signals))
        if not common:
            raise ValueError("The captures do not contain common signals.")
        return tuple((name, name) for name in common)
    pairs: list[tuple[str, str]] = []
    for index, item in enumerate(data):
        if isinstance(item, str):
            reference_name = candidate_name = item
        elif isinstance(item, dict):
            reference_name = item.get("reference") or item.get("name")
            candidate_name = item.get("candidate") or reference_name
        else:
            raise ValueError(f"Signal specification {index} must be a string or object.")
        if not isinstance(reference_name, str) or not isinstance(candidate_name, str):
            raise ValueError(f"Signal specification {index} requires string signal names.")
        if reference_name not in reference_signals:
            raise ValueError(f"Reference signal '{reference_name}' was not found.")
        if candidate_name not in candidate_signals:
            raise ValueError(f"Candidate signal '{candidate_name}' was not found.")
        pairs.append((reference_name, candidate_name))
    return tuple(pairs)


def _parse_tolerances(json_text: str) -> dict[str, Any]:
    try:
        data = json.loads(json_text) if json_text.strip() else {}
    except json.JSONDecodeError as exception:
        raise ValueError(f"Tolerances must be a JSON object: {exception.msg}") from exception
    if not isinstance(data, dict):
        raise ValueError("Tolerances must be a JSON object.")
    parsed = {key: _nonnegative_number(data[key], key) for key in TOLERANCE_KEYS if key in data}
    signal_values = data.get("signals", {})
    if not isinstance(signal_values, dict):
        raise ValueError("Tolerance 'signals' must be an object keyed by reference signal name.")
    parsed_signals: dict[str, dict[str, float]] = {}
    for signal_name, signal_tolerances in signal_values.items():
        if not isinstance(signal_name, str) or not isinstance(signal_tolerances, dict):
            raise ValueError("Each signal tolerance must be an object keyed by a signal name.")
        parsed_signals[signal_name] = {
            key: _nonnegative_number(signal_tolerances[key], f"signals.{signal_name}.{key}")
            for key in TOLERANCE_KEYS
            if key in signal_tolerances
        }
    parsed["signals"] = parsed_signals
    return parsed


def _nonnegative_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Tolerance '{label}' must be a non-negative finite number.")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Tolerance '{label}' must be a non-negative finite number.")
    return number


def _compare_signal(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    reference_name: str,
    candidate_name: str,
    tolerances: dict[str, Any],
) -> dict[str, Any]:
    reference_times = reference["times"]
    candidate_times = candidate["times"]
    reference_values = reference["signals"][reference_name]["values"]
    candidate_values = candidate["signals"][candidate_name]["values"]
    if np.array_equal(reference_times, candidate_times):
        aligned_times = reference_times
        aligned_reference = reference_values
        aligned_candidate = candidate_values
        alignment = "exact"
    elif reference_times.size >= 2 and candidate_times.size >= 2:
        if np.any(np.diff(reference_times) <= 0) or np.any(np.diff(candidate_times) <= 0):
            raise ValueError("Capture time axes must be strictly increasing for interpolation.")
        overlap_start = max(float(reference_times[0]), float(candidate_times[0]))
        overlap_end = min(float(reference_times[-1]), float(candidate_times[-1]))
        overlap_mask = (reference_times >= overlap_start) & (reference_times <= overlap_end)
        aligned_times = reference_times[overlap_mask]
        aligned_reference = reference_values[overlap_mask]
        aligned_candidate = np.interp(aligned_times, candidate_times, candidate_values)
        alignment = "candidateInterpolatedToReference"
    else:
        aligned_times, reference_indices, candidate_indices = np.intersect1d(
            reference_times, candidate_times, return_indices=True
        )
        aligned_reference = reference_values[reference_indices]
        aligned_candidate = candidate_values[candidate_indices]
        alignment = "exactCommonTimestamps"
    finite_mask = np.isfinite(aligned_reference) & np.isfinite(aligned_candidate)
    if not np.any(finite_mask):
        raise ValueError(f"Signals '{reference_name}' and '{candidate_name}' have no finite overlapping samples.")
    compared_times = aligned_times[finite_mask]
    with np.errstate(over="ignore", invalid="ignore"):
        differences = aligned_candidate[finite_mask] - aligned_reference[finite_mask]
        if not np.all(np.isfinite(differences)):
            raise ValueError("Signal differences cannot be represented as finite values.")
        metrics = {
            "meanDifference": float(np.mean(differences)),
            "meanAbsoluteError": float(np.mean(np.abs(differences))),
            "rootMeanSquaredError": float(np.sqrt(np.mean(np.square(differences)))),
            "maximumAbsoluteError": float(np.max(np.abs(differences))),
        }
    if not all(math.isfinite(value) for value in metrics.values()):
        raise ValueError("Signal comparison metrics cannot be represented as finite values.")
    applied_tolerances = {key: tolerances[key] for key in TOLERANCE_KEYS if key in tolerances}
    applied_tolerances.update(tolerances["signals"].get(reference_name, {}))
    has_sufficient_overlap = compared_times.size >= 2
    within_tolerance = (
        all(metrics[key] <= threshold for key, threshold in applied_tolerances.items())
        if applied_tolerances and has_sufficient_overlap
        else None
    )
    return {
        "referenceSignal": reference_name,
        "candidateSignal": candidate_name,
        "referenceUnit": reference["signals"][reference_name]["unit"],
        "candidateUnit": candidate["signals"][candidate_name]["unit"],
        "alignment": alignment,
        "status": "compared" if has_sufficient_overlap else "insufficientOverlap",
        "sampleCount": int(compared_times.size),
        "timeStart": float(compared_times[0]),
        "timeEnd": float(compared_times[-1]),
        "metrics": metrics,
        "tolerances": applied_tolerances,
        "withinTolerance": within_tolerance,
    }


def _capture_summary(name: str, capture: dict[str, Any]) -> dict[str, Any]:
    times = capture["times"]
    return {
        "name": name,
        "sizeBytes": capture["sizeBytes"],
        "sampleCount": int(times.size),
        "signalCount": len(capture["signals"]),
        "timeStart": float(times[0]),
        "timeEnd": float(times[-1]),
        "duration": float(times[-1] - times[0]),
    }
