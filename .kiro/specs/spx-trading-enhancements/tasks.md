# Implementation Plan

- [x] 1. Fix state serialization for Option objects

  - Implement serialize_option() and deserialize_option() methods for proper Option object handling
  - Implement serialize_iron_fly() and deserialize_iron_fly() methods for IronFly objects
  - Add comprehensive error handling and logging for serialization failures
  - Test complete state serialization cycle with Option objects to ensure no JSON errors
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Add min and max net PnL tracking to state management

  - Add min_net_pnl and max_net_pnl fields to StrategyState dataclass
  - Implement update_pnl_extremes() function to track PnL minimums and maximums
  - Add initialization logic for existing state files without min/max fields
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3. Fix duplicate field serialization bug in save_state() method

  - Remove duplicate min_net_pnl and max_net_pnl entries in state_dict that cause JSON syntax errors
  - Test state serialization to ensure clean JSON output without duplicate keys
  - _Requirements: 1.1, 2.4_

- [x] 4. Update Flask template references from strategy.html to SPX_9IF_0DTE.html

  - Update Flask route in flask_app.py to reference SPX_9IF_0DTE.html instead of strategy.html
  - Verify template rendering works correctly with new template name
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 5. Integrate PnL extremes tracking into compute_strategy_status()

  - Modify compute_strategy_status() to calculate net PnL including realized and unrealized
  - Update PnL calculation to call update_pnl_extremes() with current net PnL
  - Ensure min/max values are properly updated during strategy monitoring
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 6. Implement functional chart data preparation

  - Create prepare_spx_data() function to parse spx.csv and extract time/mark price data
  - Create prepare_pnl_data() function to parse pnl.csv and organize by fly body
  - Implement get_current_pnl() function to extract latest total PnL including realized losses
  - Create format_spx_trace() function to structure SPX data for Plotly
  - Create format_fly_traces() function to structure individual fly PnL data with color coding
  - Add data validation and error handling for missing or malformed CSV files
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 7. Update chart rendering and display logic

  - Modify strategy route in flask_app.py to use new data preparation functions
  - Update chart configuration to properly display SPX on primary y-axis
  - Configure secondary y-axis for PnL data with proper scaling
  - Implement color palette for 9 fly positions with distinct colors
  - Add current PnL display in top-right corner of chart
  - Update chart to respond to date selection changes
  - Test chart rendering with various data scenarios and edge cases
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 8. Implement file download system

  - Create download route in flask_app.py with date and file_type parameters
  - Implement file path validation and security checks for download requests
  - Add error handling for missing files with appropriate HTTP status codes
  - Create generate_download_url() helper function for template use
  - Update template to replace raw data display with download buttons
  - Add download button for pnl.csv with date-specific file serving
  - Add download button for quotes.csv with date-specific file serving
  - Test download functionality with various dates and handle missing file scenarios
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 9. Integration testing and validation

  - Test chart functionality with real market data from multiple dates
  - Validate file download system with various date selections
  - Test error scenarios including missing files, corrupted data, and invalid dates
  - Verify system restart safety with enhanced state management
  - Test complete state serialization/deserialization cycle with Option objects

  - Validate min/max PnL tracking works correctly during strategy execution
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
