# Cython Optimization for python-redux

This document details the Cython optimization implemented for `python-redux` to improve dispatch throughput and reduce CPU usage.

## Overview

We utilize a **Cython hybrid approach** to optimize critical "hot paths" while maintaining the flexibility of Python for complex logic.

-   **Optimized Components (Cython):**
    -   `Store.dispatch()` loop
    -   Action and Event processing queues (`FastActionQueue`)
    -   Listener notification (`call_listeners_fast`)
    -   Middleware application
-   **Python Components (Unchanged):**
    -   `Autorun` and reactivity logic
    -   `combine_reducers`
    -   `python-immutable` data structures

This approach ensures strict backward compatibility. If the Cython extension cannot be built or imported, the library automatically falls back to the pure Python implementation.

## Benchmark Results

Performance comparison between the pure Python implementation and the Cython-optimized version:

| Test Case | Baseline (Python) | Optimized (Cython) | Improvement |
|-----------|-------------------|--------------------|-------------|
| **Simple Dispatch** (1000 actions) | 3.83 ms | 2.52 ms | **~34% faster** |
| **Dispatch with Payload** | 3.21 ms | 2.68 ms | **~17% faster** |
| **Batch Dispatch** (1000 actions) | 1.85 ms | 1.56 ms | **~16% faster** |
| **Dispatch with subscribers** | 4.56 ms | 3.70 ms | **~19% faster** |
| **Dispatch with event handlers** | 1.59 ms | 0.98 ms | **~38% faster** |

*Benchmarks run on Apple M2, Python 3.11.*

## Files Changed

### New Files
-   `setup.py`: Build configuration for compiling the Cython extension.
-   `redux/_store_core.pyx`: The Cython implementation containing the optimized `FastActionQueue`, `run_dispatch_loop`, and `call_listeners_fast`.
-   `benchmarks/bench_dispatch.py`: Comparison benchmark suite.

### Modified Files
-   `redux/main.py`: Updated to import optimized functions from `_store_core` with a graceful fallback to pure Python.
-   `pyproject.toml`: Added `cython` and `pytest-benchmark` to development dependencies.

## Build Instructions

To build the Cython extension locally:

1.  **Install build dependencies:**
    ```bash
    pip install cython
    ```

2.  **Compile the extension:**
    ```bash
    # Build in-place (useful for development)
    python setup.py build_ext --inplace
    ```

    This will generate a shared object file (e.g., `redux/_store_core.cpython-311-darwin.so`) in the `redux/` directory.

3.  **Verify installation:**
    You can verify the optimization is active by running the benchmarks:
    ```bash
    pytest benchmarks/ -v
    ```

## Development

If you modify `redux/_store_core.pyx`, you must rebuild the extension for changes to take effect:

```bash
python setup.py build_ext --inplace
```

To run tests ensuring both Cython and Python fallback work correctly and match behavior:

```bash
pytest tests/
```
