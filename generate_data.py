"""Reproducible synthetic digital-circuit waveform datasets (1 ns sampling)."""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"


def make_xor_data(glitch: bool = False) -> pd.DataFrame:
    rows = []
    for t in range(41):
        a = int(8 <= t < 20 or t >= 32)
        b = int(14 <= t < 26)
        y = a ^ b
        if glitch and t == 17:
            y ^= 1  # One deliberately corrupted sample (simulated short pulse)
        rows.append({"time_ns": t, "A": a, "B": b, "Y": y})
    return pd.DataFrame(rows)


def make_dff_data() -> pd.DataFrame:
    rows = []
    q = 0
    previous_clk = 0
    for t in range(41):
        clk = int(t % 10 >= 5)
        d = int(14 <= t < 28)
        if clk == 1 and previous_clk == 0:
            # Simulate an incorrect D-FF outcome at t=15, near a D input transition.
            if t != 15:
                q = d
        rows.append({"time_ns": t, "CLK": clk, "D": d, "Q": q})
        previous_clk = clk
    return pd.DataFrame(rows)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    samples = {
        "xor_normal.csv": make_xor_data(False),
        "xor_glitch.csv": make_xor_data(True),
        "dff_timing.csv": make_dff_data(),
    }
    for filename, data in samples.items():
        data.to_csv(DATA_DIR / filename, index=False)
        print(f"Created data/{filename} ({len(data)} rows)")


if __name__ == "__main__":
    main()
