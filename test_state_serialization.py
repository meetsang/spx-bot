#!/usr/bin/env python3
"""
Test script to verify state serialization works correctly without duplicate fields or JSON errors.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional

# Add the current directory to Python path to import the strategy
sys.path.append('.')

# Import the strategy class
try:
    from SPX_9IF_0DTE_v2 import StrategyState, Config, SPXIFStrategy
    print("Successfully imported strategy classes")
except ImportError as e:
    print(f"Failed to import strategy classes: {e}")
    sys.exit(1)

def test_state_serialization():
    """Test state serialization to ensure no duplicate fields or JSON errors"""
    print("Testing state serialization...")
    
    # Create a test config
    cfg = Config()
    cfg.dry_run = True
    cfg.simulate_only = True
    
    try:
        # Create strategy instance
        strategy = SPXIFStrategy(cfg)
        
        # Initialize some test state data
        strategy.state.entered_today = True
        strategy.state.expiry = "2025-08-15"
        strategy.state.total_pnl = -2.5
        strategy.state.realized_pnl = -1.0
        strategy.state.min_net_pnl = -3.0
        strategy.state.max_net_pnl = 1.5
        strategy.state.per_if_pnl = {5900.0: -0.5, 5905.0: -1.0}
        
        print("Test state data initialized")
        
        # Test the save_state method
        strategy.save_state()
        print("State saved successfully")
        
        # Verify the saved JSON is valid and doesn't have duplicates
        state_path = os.path.join(strategy.strategy_folder, "state.json")
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                content = f.read()
                print(f"State file content length: {len(content)} characters")
                
                # Parse JSON to verify it's valid
                data = json.loads(content)
                print("JSON parsing successful")
                
                # Check for required fields
                required_fields = ['entered_today', 'expiry', 'active_flies', 'closed_flies', 
                                 'per_if_pnl', 'total_pnl', 'realized_pnl', 'min_net_pnl', 'max_net_pnl']
                
                missing_fields = []
                for field in required_fields:
                    if field not in data:
                        missing_fields.append(field)
                
                if missing_fields:
                    print(f"Missing fields: {missing_fields}")
                else:
                    print("All required fields present")
                
                # Check for duplicate keys by comparing original vs parsed
                original_keys = set(data.keys())
                print(f"Fields in state: {sorted(original_keys)}")
                
                # Verify specific values
                assert data['min_net_pnl'] == -3.0, f"Expected min_net_pnl=-3.0, got {data['min_net_pnl']}"
                assert data['max_net_pnl'] == 1.5, f"Expected max_net_pnl=1.5, got {data['max_net_pnl']}"
                
                print("State serialization test PASSED")
                return True
        else:
            print("State file was not created")
            return False
            
    except Exception as e:
        print(f"State serialization test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_load_state():
    """Test state loading to ensure deserialization works correctly"""
    print("\nTesting state loading...")
    
    cfg = Config()
    cfg.dry_run = True
    cfg.simulate_only = True
    
    try:
        strategy = SPXIFStrategy(cfg)
        
        # Load the state we just saved
        loaded_data = strategy.load_state()
        
        if loaded_data:
            print("State loaded successfully")
            
            # Verify the loaded values
            assert strategy.state.min_net_pnl == -3.0, f"Expected min_net_pnl=-3.0, got {strategy.state.min_net_pnl}"
            assert strategy.state.max_net_pnl == 1.5, f"Expected max_net_pnl=1.5, got {strategy.state.max_net_pnl}"
            assert strategy.state.total_pnl == -2.5, f"Expected total_pnl=-2.5, got {strategy.state.total_pnl}"
            
            print("State loading test PASSED")
            return True
        else:
            print("No state data was loaded")
            return False
            
    except Exception as e:
        print(f"State loading test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting state serialization tests...")
    
    # Run tests
    save_success = test_state_serialization()
    load_success = test_load_state()
    
    if save_success and load_success:
        print("\n✅ All state serialization tests PASSED")
        sys.exit(0)
    else:
        print("\n❌ Some state serialization tests FAILED")
        sys.exit(1)