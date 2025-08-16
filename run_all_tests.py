#!/usr/bin/env python3
"""
Master test runner for all SPX Trading Enhancement tests

This script runs all test suites to validate the complete implementation:
- State serialization tests
- Task completion tests  
- Comprehensive serialization tests
- Integration validation tests
"""

import subprocess
import sys
import os
from datetime import datetime

def run_test_script(script_name, description):
    """Run a test script and return success status"""
    print(f"\n{'='*80}")
    print(f"🧪 Running {description}")
    print(f"📄 Script: {script_name}")
    print('='*80)
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True, 
                              timeout=300)  # 5 minute timeout
        
        success = result.returncode == 0
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status}: {description}")
        return success
        
    except subprocess.TimeoutExpired:
        print(f"\n⏰ TIMEOUT: {description} took too long to complete")
        return False
    except Exception as e:
        print(f"\n💥 ERROR: Failed to run {description}: {e}")
        return False

def main():
    """Run all test suites"""
    print("🚀 SPX Trading Enhancements - Master Test Suite")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Define test suites
    test_suites = [
        ("test_state_serialization.py", "State Serialization Tests"),
        ("test_comprehensive_serialization.py", "Comprehensive Serialization Tests"),
        ("test_task_completion.py", "Task Completion Tests"),
        ("test_integration_validation.py", "Integration Validation Tests"),
    ]
    
    # Check that all test files exist
    missing_files = []
    for script, _ in test_suites:
        if not os.path.exists(script):
            missing_files.append(script)
    
    if missing_files:
        print(f"❌ Missing test files: {', '.join(missing_files)}")
        return False
    
    # Run all test suites
    results = []
    for script, description in test_suites:
        success = run_test_script(script, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "="*80)
    print("📊 MASTER TEST SUITE SUMMARY")
    print("="*80)
    
    passed_count = 0
    total_count = len(results)
    
    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {description}")
        if success:
            passed_count += 1
    
    print(f"\n🎯 OVERALL RESULT: {passed_count}/{total_count} test suites passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TEST SUITES PASSED!")
        print("✅ State serialization working correctly")
        print("✅ Option object handling implemented")
        print("✅ Min/max PnL tracking functional")
        print("✅ Duplicate field serialization bug fixed")
        print("✅ Chart functionality validated")
        print("✅ File download system working")
        print("✅ Error scenarios handled gracefully")
        print("✅ System restart safety verified")
        print("✅ Template references updated")
        print("\n🏆 SPX Trading Enhancements implementation is COMPLETE and VALIDATED!")
        return True
    else:
        print(f"\n💥 {total_count - passed_count} TEST SUITE(S) FAILED!")
        print("❌ Some functionality may not be working correctly")
        failed_suites = [desc for desc, success in results if not success]
        print(f"❌ Failed suites: {', '.join(failed_suites)}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Master test suite failed: {e}")
        sys.exit(1)