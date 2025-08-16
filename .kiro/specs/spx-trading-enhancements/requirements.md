# Requirements Document

## Introduction

This feature addresses multiple enhancements to the SPX 9IF 0DTE trading system, including fixing state serialization issues, adding PnL tracking capabilities, renaming strategy components, implementing functional charting, and improving file download functionality. These improvements will enhance the system's reliability, data visualization, and user experience.

## Requirements

### Requirement 1

**User Story:** As a trader, I want the system to properly save state data, so that my trading session information is preserved without serialization errors.

#### Acceptance Criteria

1. WHEN the system attempts to save state THEN it SHALL serialize all data types including Option objects without errors
2. WHEN state contains complex objects THEN the system SHALL convert them to JSON-serializable formats before saving
3. WHEN state is saved successfully THEN the system SHALL confirm the operation completed without exceptions

### Requirement 2

**User Story:** As a trader, I want to track minimum and maximum net PnL values in the state, so that I can monitor my trading performance extremes.

#### Acceptance Criteria

1. WHEN calculating net PnL THEN the system SHALL include both realized and unrealized PnL
2. WHEN net PnL is calculated THEN the system SHALL update min_net_pnl if current value is lower than stored minimum
3. WHEN net PnL is calculated THEN the system SHALL update max_net_pnl if current value is higher than stored maximum
4. WHEN state is saved THEN it SHALL include min_net_pnl and max_net_pnl fields in the JSON output

### Requirement 3

**User Story:** As a system maintainer, I want the strategy template renamed to reflect the SPX_9IF_0DTE strategy, so that the naming is consistent across the application.

#### Acceptance Criteria

1. WHEN the HTML template is accessed THEN it SHALL be named SPX_9IF_0DTE.html instead of strategy.html
2. WHEN Flask routes reference the template THEN they SHALL use the new template name
3. WHEN any code references the old template name THEN it SHALL be updated to use SPX_9IF_0DTE.html
4. WHEN the application runs THEN all template references SHALL work without errors

### Requirement 4

**User Story:** As a trader, I want to see a functional chart displaying SPX prices and active fly positions, so that I can visualize market data and my trading positions in real-time.

#### Acceptance Criteria

1. WHEN the chart loads THEN it SHALL display SPX price data from Data/<Date>/spx.csv with time on x-axis and mark prices on y-axis
2. WHEN the chart displays SPX data THEN it SHALL superimpose active fly prices from Data/<Date>/pnl.csv
3. WHEN displaying fly data THEN the system SHALL use color coding to distinguish between all 9 flies
4. WHEN the chart is rendered THEN it SHALL show current PnL including realized losses in the top right corner
5. WHEN the date selection changes THEN the chart SHALL update to display data for the selected date

### Requirement 5

**User Story:** As a trader, I want to download PnL and quotes data files, so that I can analyze trading data offline or in external tools.

#### Acceptance Criteria

1. WHEN viewing the strategy page THEN it SHALL provide a downloadable link for pnl.csv instead of displaying the raw data
2. WHEN a date is selected THEN the download link SHALL correspond to the pnl.csv file for that specific date
3. WHEN the download button is clicked THEN it SHALL serve the correct Data/<Date>/pnl.csv file
4. WHEN viewing the strategy page THEN it SHALL provide a download button for quotes.csv
5. WHEN the quotes download button is clicked THEN it SHALL serve the Data/<Date>/quotes.csv file for the selected date
6. WHEN either download fails THEN the system SHALL provide appropriate error messaging to the user