#!/usr/bin/env python
import subprocess
import sys

# Test the 6 fixed tests
tests = [
    "tests/test_distributed_tracing.py::TestTraceCollector::test_collector_get_statistics",
    "tests/test_distributed_tracing.py::TestDistributedTracer::test_nested_spans",
    "tests/test_ml_impact.py::TestNeuralNetworkModel::test_forward_pass",
    "tests/test_ml_impact.py::TestNeuralNetworkModel::test_predict",
    "tests/test_ml_impact.py::TestMLImpactPredictor::test_predict_with_model",
    "tests/test_integration.py::TestEndToEndPipeline::test_risk_engine_integration",
]

for test in tests:
    print(f"\n{'='*60}")
    print(f"Running: {test}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test, "-xvs"],
        timeout=30
    )
    if result.returncode != 0:
        print(f"FAILED: {test}")
        sys.exit(1)
    print(f"PASSED: {test}")

print(f"\n{'='*60}")
print("ALL 6 TESTS PASSED!")
print(f"{'='*60}")
