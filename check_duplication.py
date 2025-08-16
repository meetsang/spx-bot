#!/usr/bin/env python3
"""
Check that the refactoring eliminated duplicate field serialization
"""

with open('SPX_9IF_0DTE_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Count occurrences of the field serialization patterns
min_pnl_serialization = content.count('"min_net_pnl": float(self.state.min_net_pnl)')
max_pnl_serialization = content.count('"max_net_pnl": float(self.state.max_net_pnl)')

print(f'Occurrences of min_net_pnl field serialization: {min_pnl_serialization}')
print(f'Occurrences of max_net_pnl field serialization: {max_pnl_serialization}')

# Check for the new helper method
has_base_state_method = '_create_base_state_dict' in content
print(f'Has _create_base_state_dict helper method: {has_base_state_method}')

if min_pnl_serialization == 0 and max_pnl_serialization == 0 and has_base_state_method:
    print('✅ Successfully eliminated duplicate field serialization!')
    print('✅ Refactoring completed - code now uses helper method to avoid duplication')
else:
    print('❌ Duplicate field serialization may still exist')