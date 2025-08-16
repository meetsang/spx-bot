#!/usr/bin/env python3
"""
Final test to verify that task 3 has been completed successfully:
- Remove duplicate min_net_pnl and max_net_pnl entries in state_dict that cause JSON syntax errors
- Test state serialization to ensure clean JSON output without duplicate keys
"""

import json
import os
from SPX_9IF_0DTE_v2 import SPXIFStrategy, Config

def test_task_completion():
    """Test that task 3 requirements have been met"""
    print("🔍 Testing Task 3 Completion: Fix duplicate field serialization bug")
    print("=" * 70)
    
    # Test 1: Verify no duplicate field serialization in code
    print("\n1. Checking for duplicate field serialization in code...")
    
    with open('SPX_9IF_0DTE_v2.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count direct field serializations (should only be in helper method)
    min_pnl_count = content.count('"min_net_pnl": float(self.state.min_net_pnl)')
    max_pnl_count = content.count('"max_net_pnl": float(self.state.max_net_pnl)')
    
    print(f"   Direct min_net_pnl serializations: {min_pnl_count}")
    print(f"   Direct max_net_pnl serializations: {max_pnl_count}")
    
    # Should only be 1 occurrence each (in the helper method)
    if min_pnl_count == 1 and max_pnl_count == 1:
        print("   ✅ Field serialization properly centralized in helper method")
    else:
        print("   ❌ Duplicate field serialization still exists")
        return False
    
    # Test 2: Verify helper method exists
    print("\n2. Checking for _create_base_state_dict helper method...")
    
    if '_create_base_state_dict' in content:
        print("   ✅ Helper method _create_base_state_dict exists")
    else:
        print("   ❌ Helper method _create_base_state_dict not found")
        return False
    
    # Test 3: Test actual state serialization produces clean JSON
    print("\n3. Testing state serialization produces clean JSON...")
    
    cfg = Config()
    cfg.simulate_only = True
    strategy = SPXIFStrategy(cfg)
    
    # Set test data including min/max PnL fields
    strategy.state.entered_today = True
    strategy.state.expiry = "2025-08-15"
    strategy.state.total_pnl = -2.5
    strategy.state.realized_pnl = -1.0
    strategy.state.min_net_pnl = -3.0
    strategy.state.max_net_pnl = 1.5
    strategy.state.per_if_pnl = {5900.0: -0.5, 5905.0: -1.0}
    
    # Save state
    strategy.save_state()
    
    # Read and verify the JSON
    state_path = os.path.join(strategy.strategy_folder, "state.json")
    with open(state_path, 'r', encoding='utf-8') as f:
        json_content = f.read()
    
    print(f"   JSON content length: {len(json_content)} characters")
    
    # Test 4: Verify JSON is valid (no syntax errors)
    print("\n4. Testing JSON parsing (no syntax errors)...")
    
    try:
        data = json.loads(json_content)
        print("   ✅ JSON parsing successful - no syntax errors")
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON parsing failed: {e}")
        return False
    
    # Test 5: Verify no duplicate keys in JSON
    print("\n5. Testing for duplicate keys in JSON...")
    
    # Count field occurrences in raw JSON
    min_pnl_json_count = json_content.count('"min_net_pnl":')
    max_pnl_json_count = json_content.count('"max_net_pnl":')
    
    print(f"   min_net_pnl occurrences in JSON: {min_pnl_json_count}")
    print(f"   max_net_pnl occurrences in JSON: {max_pnl_json_count}")
    
    if min_pnl_json_count == 1 and max_pnl_json_count == 1:
        print("   ✅ No duplicate keys in JSON output")
    else:
        print("   ❌ Duplicate keys found in JSON output")
        return False
    
    # Test 6: Verify field values are correct
    print("\n6. Testing field values are correct...")
    
    if (data['min_net_pnl'] == -3.0 and 
        data['max_net_pnl'] == 1.5 and
        data['total_pnl'] == -2.5 and
        data['realized_pnl'] == -1.0):
        print("   ✅ All field values are correct")
    else:
        print("   ❌ Field values are incorrect")
        print(f"      Expected: min_net_pnl=-3.0, max_net_pnl=1.5, total_pnl=-2.5, realized_pnl=-1.0")
        print(f"      Got: min_net_pnl={data.get('min_net_pnl')}, max_net_pnl={data.get('max_net_pnl')}, total_pnl={data.get('total_pnl')}, realized_pnl={data.get('realized_pnl')}")
        return False
    
    return True

def main():
    """Run the task completion test"""
    success = test_task_completion()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 TASK 3 COMPLETED SUCCESSFULLY!")
        print("✅ Duplicate field serialization bug has been fixed")
        print("✅ State serialization produces clean JSON without duplicate keys")
        print("✅ Code has been refactored to eliminate duplication")
        print("✅ All requirements have been met")
    else:
        print("💥 TASK 3 INCOMPLETE!")
        print("❌ Some requirements have not been met")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)