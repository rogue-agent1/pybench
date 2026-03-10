#!/usr/bin/env python3
"""pybench — lightweight Python benchmark runner with history tracking.

Zero dependencies. Runs commands/scripts multiple times, computes stats,
stores results in JSONL for trend analysis.

Usage:
    pybench.py run "python3 script.py" [-n 5] [--name test1] [--warmup 1]
    pybench.py compare "cmd1" "cmd2" [-n 10]
    pybench.py history [--name test1] [--last 10]
    pybench.py trend [--name test1]
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

HISTORY_FILE = Path.home() / ".openclaw" / "data" / "pybench-history.jsonl"


def run_command(cmd: str, capture: bool = True) -> tuple[float, int, str, str]:
    """Run a command, return (elapsed_seconds, returncode, stdout, stderr)."""
    start = time.perf_counter()
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True
    )
    elapsed = time.perf_counter() - start
    return elapsed, result.returncode, result.stdout or "", result.stderr or ""


def stats(times: list[float]) -> dict:
    """Compute mean, median, stddev, min, max from a list of floats."""
    n = len(times)
    if n == 0:
        return {}
    sorted_t = sorted(times)
    mean = sum(times) / n
    median = sorted_t[n // 2] if n % 2 else (sorted_t[n // 2 - 1] + sorted_t[n // 2]) / 2
    variance = sum((t - mean) ** 2 for t in times) / n if n > 1 else 0
    return {
        "mean": round(mean, 6),
        "median": round(median, 6),
        "stddev": round(math.sqrt(variance), 6),
        "min": round(min(times), 6),
        "max": round(max(times), 6),
        "runs": n,
    }


def format_time(seconds: float) -> str:
    """Human-readable time."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.3f}s"


def save_result(name: str, cmd: str, s: dict):
    """Append result to history."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "name": name,
        "command": cmd,
        **s,
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def cmd_run(args):
    cmd = args.command
    name = args.name or cmd[:40]
    n = args.n
    warmup = args.warmup

    # Warmup runs
    if warmup > 0:
        print(f"⏳ Warming up ({warmup} run{'s' if warmup > 1 else ''})...")
        for _ in range(warmup):
            run_command(cmd)

    # Benchmark runs
    times = []
    errors = 0
    print(f"🏃 Running {n} iterations: {cmd}")
    for i in range(n):
        elapsed, rc, _, _ = run_command(cmd)
        times.append(elapsed)
        if rc != 0:
            errors += 1
        marker = "✓" if rc == 0 else "✗"
        print(f"  [{i+1}/{n}] {marker} {format_time(elapsed)}")

    s = stats(times)
    s["errors"] = errors
    save_result(name, cmd, s)

    print(f"\n📊 Results for: {name}")
    print(f"  Mean:   {format_time(s['mean'])}")
    print(f"  Median: {format_time(s['median'])}")
    print(f"  StdDev: {format_time(s['stddev'])}")
    print(f"  Min:    {format_time(s['min'])}")
    print(f"  Max:    {format_time(s['max'])}")
    print(f"  Runs:   {s['runs']} ({errors} errors)")


def cmd_compare(args):
    commands = args.commands
    n = args.n
    warmup = args.warmup

    results = []
    for cmd in commands:
        if warmup > 0:
            for _ in range(warmup):
                run_command(cmd)
        times = []
        print(f"🏃 Benchmarking: {cmd}")
        for i in range(n):
            elapsed, rc, _, _ = run_command(cmd)
            times.append(elapsed)
            marker = "✓" if rc == 0 else "✗"
            print(f"  [{i+1}/{n}] {marker} {format_time(elapsed)}")
        s = stats(times)
        results.append((cmd, s))
        print()

    # Compare
    print("📊 Comparison:")
    print(f"  {'Command':<40} {'Mean':>10} {'Median':>10} {'StdDev':>10}")
    print(f"  {'─' * 40} {'─' * 10} {'─' * 10} {'─' * 10}")

    baseline = results[0][1]["mean"] if results else 1
    for cmd, s in results:
        label = cmd[:40]
        ratio = s["mean"] / baseline if baseline > 0 else 0
        suffix = "" if ratio == 1 else f" ({ratio:.2f}x)"
        print(f"  {label:<40} {format_time(s['mean']):>10} {format_time(s['median']):>10} {format_time(s['stddev']):>10}{suffix}")

    if len(results) >= 2:
        faster = results[0] if results[0][1]["mean"] < results[1][1]["mean"] else results[1]
        slower = results[1] if faster == results[0] else results[0]
        speedup = slower[1]["mean"] / faster[1]["mean"] if faster[1]["mean"] > 0 else 0
        print(f"\n  🏆 Winner: {faster[0][:40]} ({speedup:.2f}x faster)")


def cmd_history(args):
    if not HISTORY_FILE.exists():
        print("No history yet.")
        return

    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            entry = json.loads(line.strip())
            if args.name and entry.get("name") != args.name:
                continue
            entries.append(entry)

    entries = entries[-args.last:]

    if not entries:
        print("No matching entries.")
        return

    print(f"📜 History (last {len(entries)}):")
    print(f"  {'Timestamp':<22} {'Name':<25} {'Mean':>10} {'Runs':>5}")
    print(f"  {'─' * 22} {'─' * 25} {'─' * 10} {'─' * 5}")
    for e in entries:
        ts = e.get("timestamp", "?")[:19]
        name = e.get("name", "?")[:25]
        mean = format_time(e.get("mean", 0))
        runs = e.get("runs", 0)
        print(f"  {ts:<22} {name:<25} {mean:>10} {runs:>5}")


def cmd_trend(args):
    if not HISTORY_FILE.exists():
        print("No history yet.")
        return

    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            entry = json.loads(line.strip())
            if args.name and entry.get("name") != args.name:
                continue
            entries.append(entry)

    if len(entries) < 2:
        print("Need at least 2 data points for trend.")
        return

    means = [e["mean"] for e in entries]
    first, last = means[0], means[-1]
    change = ((last - first) / first) * 100 if first > 0 else 0
    direction = "📈 slower" if change > 0 else "📉 faster"

    name = args.name or entries[0].get("name", "?")
    print(f"📊 Trend for: {name}")
    print(f"  First: {format_time(first)} → Last: {format_time(last)}")
    print(f"  Change: {abs(change):.1f}% {direction}")

    # Sparkline
    min_m, max_m = min(means), max(means)
    bars = "▁▂▃▄▅▆▇█"
    span = max_m - min_m if max_m != min_m else 1
    spark = "".join(bars[min(int((m - min_m) / span * 7), 7)] for m in means[-20:])
    print(f"  Trend:  {spark}")


def main():
    parser = argparse.ArgumentParser(description="pybench — lightweight benchmark runner")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Benchmark a command")
    p_run.add_argument("command", help="Command to benchmark")
    p_run.add_argument("-n", type=int, default=5, help="Number of iterations")
    p_run.add_argument("--name", help="Benchmark name for history")
    p_run.add_argument("--warmup", type=int, default=1, help="Warmup runs")

    p_cmp = sub.add_parser("compare", help="Compare two+ commands")
    p_cmp.add_argument("commands", nargs="+", help="Commands to compare")
    p_cmp.add_argument("-n", type=int, default=5, help="Iterations per command")
    p_cmp.add_argument("--warmup", type=int, default=1, help="Warmup runs")

    p_hist = sub.add_parser("history", help="View benchmark history")
    p_hist.add_argument("--name", help="Filter by name")
    p_hist.add_argument("--last", type=int, default=10, help="Show last N entries")

    p_trend = sub.add_parser("trend", help="Show performance trend")
    p_trend.add_argument("--name", help="Filter by name")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    {"run": cmd_run, "compare": cmd_compare, "history": cmd_history, "trend": cmd_trend}[args.cmd](args)


if __name__ == "__main__":
    main()
