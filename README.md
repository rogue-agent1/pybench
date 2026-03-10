# pybench

Lightweight Python benchmark runner with history tracking. Zero dependencies.

## Usage

```bash
# Benchmark a command (5 runs + 1 warmup)
python3 pybench.py run "python3 script.py" -n 5

# Compare two commands
python3 pybench.py compare "python3 v1.py" "python3 v2.py" -n 10

# View history
python3 pybench.py history --name "my-test" --last 20

# Show performance trend with sparkline
python3 pybench.py trend --name "my-test"
```

## Features

- **Warmup runs** — skip cold-start outliers
- **Stats** — mean, median, stddev, min, max
- **Comparison** — side-by-side with speedup ratio
- **History** — JSONL tracking for regression detection  
- **Trends** — sparkline visualization of performance over time
- **Zero deps** — single file, stdlib only

## Philosophy

One file. Zero deps. Does one thing well.
