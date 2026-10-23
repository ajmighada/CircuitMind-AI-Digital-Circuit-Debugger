"""Deterministic digital waveform checks (not a physical circuit simulator)."""
from __future__ import annotations
from typing import Any
import pandas as pd


def _validate(frame: pd.DataFrame, signals: list[str]) -> pd.DataFrame:
    needed = ["time_ns", *signals]
    missing = [name for name in needed if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    result = frame[needed].copy()
    if len(result) < 3:
        raise ValueError("At least 3 timestamped samples are required.")
    for name in needed:
        result[name] = pd.to_numeric(result[name], errors="raise")
        if result[name].isna().any():
            raise ValueError(f"Column {name} contains blank values.")
    if not result["time_ns"].is_monotonic_increasing or (result["time_ns"].diff().iloc[1:] <= 0).any():
        raise ValueError("time_ns values must be strictly increasing.")
    for signal in signals:
        if not result[signal].isin([0, 1]).all():
            raise ValueError(f"{signal} must contain only digital values 0 or 1.")
        result[signal] = result[signal].astype(int)
    return result.reset_index(drop=True)


def analyze_xor(frame: pd.DataFrame, max_glitch_ns: float = 2.0) -> dict[str, Any]:
    if max_glitch_ns <= 0:
        raise ValueError("max_glitch_ns must be positive.")
    data = _validate(frame, ["A", "B", "Y"])
    data["expected_Y"] = data["A"] ^ data["B"]
    data["mismatch"] = data["Y"] != data["expected_Y"]
    mismatch_count = int(data["mismatch"].sum())
    findings: list[dict[str, Any]] = []
    if mismatch_count:
        bad_times = data.loc[data["mismatch"], "time_ns"].tolist()
        findings.append({
            "severity": "HIGH", "type": "Logic mismatch", "time_ns": float(bad_times[0]),
            "details": f"Observed Y differs from A XOR B at {mismatch_count} sample(s); first at {bad_times[0]} ns.",
        })
    # A one-sample pulse, with both inputs stable across the pulse, can be a glitch.
    # Sampling cannot reveal what happened between measurements.
    for i in range(1, len(data) - 1):
        before, here, after = (data.iloc[i - 1], data.iloc[i], data.iloc[i + 1])
        if (before["Y"] == after["Y"] != here["Y"]
                and before["A"] == here["A"] == after["A"]
                and before["B"] == here["B"] == after["B"]):
            pulse_ns = float(after["time_ns"] - here["time_ns"])
            if pulse_ns <= max_glitch_ns:
                findings.append({
                    "severity": "MEDIUM", "type": "Possible output glitch",
                    "time_ns": float(here["time_ns"]),
                    "details": f"One-sample Y pulse while A and B remain unchanged (observed width about {pulse_ns:g} ns).",
                })
    return {
        "data": data, "findings": findings,
        "metrics": {"Samples": len(data), "Logic mismatches": mismatch_count, "Findings": len(findings)},
        "signals": ["A", "B", "Y"],
    }


def analyze_dff(frame: pd.DataFrame, setup_ns: float = 2.0, hold_ns: float = 1.0) -> dict[str, Any]:
    if setup_ns < 0 or hold_ns < 0:
        raise ValueError("Setup/hold intervals must be nonnegative.")
    data = _validate(frame, ["CLK", "D", "Q"])
    rising_indices = [i for i in range(1, len(data))
                      if data.at[i - 1, "CLK"] == 0 and data.at[i, "CLK"] == 1]
    d_changes = [i for i in range(1, len(data)) if data.at[i - 1, "D"] != data.at[i, "D"]]
    findings: list[dict[str, Any]] = []
    checks = []
    for edge_index in rising_indices:
        edge_ns = float(data.at[edge_index, "time_ns"])
        prior_changes = [i for i in d_changes if i <= edge_index]
        next_changes = [i for i in d_changes if i > edge_index]
        preceding_delta = edge_ns - float(data.at[prior_changes[-1], "time_ns"]) if prior_changes else None
        following_delta = float(data.at[next_changes[0], "time_ns"]) - edge_ns if next_changes else None
        if preceding_delta is not None and preceding_delta < setup_ns:
            findings.append({
                "severity": "HIGH", "type": "Potential setup-time violation", "time_ns": edge_ns,
                "details": f"D changed {preceding_delta:g} ns before CLK rising edge; required minimum {setup_ns:g} ns.",
            })
        if following_delta is not None and following_delta < hold_ns:
            findings.append({
                "severity": "HIGH", "type": "Potential hold-time violation", "time_ns": edge_ns,
                "details": f"D changed {following_delta:g} ns after CLK rising edge; required minimum {hold_ns:g} ns.",
            })
        # Simplifying assumption: Q settles by the following sampled timestamp.
        # If setup or hold is violated, ideal D-sampling no longer predicts real behavior reliably.
        observed_q = int(data.at[edge_index + 1, "Q"]) if edge_index + 1 < len(data) else None
        expected_q = int(data.at[edge_index, "D"])
        if observed_q is not None and observed_q != expected_q:
            findings.append({
                "severity": "MEDIUM", "type": "Q differs from ideal D-FF model", "time_ns": edge_ns,
                "details": f"At the next sample, Q={observed_q} but ideal rising-edge sampling predicts {expected_q}. "
                           "This may be affected by setup/hold timing or propagation delay assumptions.",
            })
        checks.append({"clock_edge_ns": edge_ns, "D_at_edge": expected_q,
                       "Q_next_sample": observed_q,
                       "setup_margin_ns": preceding_delta,
                       "hold_margin_ns": following_delta})
    if not rising_indices:
        findings.append({"severity": "INFO", "type": "No rising clock edge", "time_ns": None,
                         "details": "No 0→1 transition of CLK was captured; flip-flop sampling cannot be checked."})
    return {
        "data": data, "findings": findings,
        "metrics": {"Samples": len(data), "Rising clock edges": len(rising_indices), "Findings": len(findings)},
        "signals": ["CLK", "D", "Q"],
        "edge_checks": pd.DataFrame(checks),
    }
