#!/usr/bin/env python
"""Verify Phase 4.5 tests can be imported and run."""

import sys
import traceback

def verify_imports():
    """Verify all Phase 4.5 modules can be imported."""
    try:
        print("Checking imports...")
        from execution.monte_carlo import MonteCarloOrderBookSimulator
        print("  ✓ execution.monte_carlo")
        
        from execution.venue_models import get_venue_model
        print("  ✓ execution.venue_models")
        
        from monitoring.tracing import DistributedTracer
        print("  ✓ monitoring.tracing")
        
        from execution.ml_impact import MLImpactPredictor
        print("  ✓ execution.ml_impact")
        
        from monitoring.latency import LatencyMonitor
        print("  ✓ monitoring.latency")
        
        print("\n✓ All Phase 4.5 modules imported successfully!")
        return True
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        traceback.print_exc()
        return False

def verify_model_creation():
    """Verify ML model can be created."""
    try:
        print("\nVerifying model creation...")
        from execution.ml_impact import NeuralNetworkModel
        import numpy as np
        
        model = NeuralNetworkModel(input_size=8, hidden_size_1=64, hidden_size_2=32)
        assert model.W1 is not None
        assert model.feature_mean is not None
        print(f"  ✓ NeuralNetworkModel created")
        print(f"    - Input size: {model.input_size}")
        print(f"    - W1 shape: {model.W1.shape}")
        print(f"    - Feature mean shape: {model.feature_mean.shape}")
        return True
    except Exception as e:
        print(f"\n✗ Model creation failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    imports_ok = verify_imports()
    model_ok = verify_model_creation()
    
    if imports_ok and model_ok:
        print("\n" + "="*50)
        print("✓ All Phase 4.5 verifications PASSED!")
        print("="*50)
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("✗ Some verifications FAILED!")
        print("="*50)
        sys.exit(1)
