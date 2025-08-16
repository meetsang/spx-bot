#!/usr/bin/env python3
"""
Test to check for duplicate keys in state serialization that would cause JSON syntax errors.
"""

import json
import tempfile
import os
from SPX_9IF_0DTE_v2 import SPXIFStrategy, Config

def test_for_duplicate_keys():
    """Test that state serialization doesn't create duplicate keys"""
    print("Testing for duplicate keys in state serialization...")
    
    # Create a temporary strategy instance
    cfg = Config()
    cfg.simulate_only = True
    
    try:
        strategy = SPXIFStrategy(cfg)
        
        # Set some test data
        strategy.state.entered_today = True
        strategy.state.expiry = "2025-08-15"
        strategy.state.total_pnl = -2.5
        strategy.state.realized_pnl = -1.0
        strategy.state.min_net_pnl = -3.0
        strategy.state.max_net_pnl = 1.5
        strategy.state.per_if_pnl = {5900.0: -0.5, 5905.0: -1.0}
        
        # Try to save state
        strategy.save_state()
        
        # Read the saved state file and check for duplicate keys
        state_path = os.path.join(strategy.strategy_folder, "state.json")
        
        with open(state_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"State file content:\n{content}")
        
        # Parse JSON - this will fail if there are duplicate keys
        try:
            data = json.loads(content)
            print("✅ JSON parsing successful - no duplicate keys found")
            
            # Check that all expected fields are present exactly once
            expected_fields = ['entered_today', 'expiry', 'active_flies', 'closed_flies', 
                             'per_if_pnl', 'total_pnl', 'realized_pnl', 'min_net_pnl', 'max_net_pnl']
            
            for field in expected_fields:
                if field not in data:
                    print(f"❌ Missing field: {field}")
                    return False
                    
            # Count occurrences of each field in the raw content
            for field in ['min_net_pnl', 'max_net_pnl']:
                count = content.count(f'"{field}":')
                if count > 1:
                    print(f"❌ Duplicate field found: {field} appears {count} times")
                    return False
                elif count == 1:
                    print(f"✅ Field {field} appears exactly once")
                else:
                    print(f"❌ Field {field} not found")
                    return False
            
            print("✅ All tests passed - no duplicate keys detected")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_for_duplicate_keys()
    if success:
        print("\n🎉 No duplicate field serialization bugs found!")
    else:
        print("\n💥 Duplicate field serialization bugs detected!")