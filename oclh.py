import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import os

VERBOSE = False  # Only essential updates shown

# Try to import talib, fallback to pandas if not available
try:
    import talib
    USE_TALIB = True
except ImportError:
    USE_TALIB = False
    if VERBOSE:
        print("Warning: TA-Lib not available, using pandas implementations")

OCLH_FILES = {
    1: "OCLH1.csv",
    2: "OCLH2.csv", 
    3: "OCLH3.csv",
    5: "OCLH5.csv",
    10: "OCLH10.csv"
}

MARKET_OPEN_TIME = time(8, 30)  # 8:30 AM
BUFFER_SECONDS = 30  # Wait 30 seconds after minute boundary

def calculate_mid_price(bid, ask):
    """Calculate mid price from bid and ask"""
    return round((bid + ask) / 2, 2)

def hull_moving_average(series, window):
    """Custom implementation of Hull Moving Average (HMA)"""
    if len(series) < window:
        return pd.Series([np.nan] * len(series), index=series.index)
    
    wma_half = series.rolling(window=window//2, min_periods=1).mean()
    wma_full = series.rolling(window=window, min_periods=1).mean()
    raw_hma = (2 * wma_half) - wma_full
    sqrt_window = int(np.sqrt(window))
    hma = raw_hma.rolling(window=sqrt_window, min_periods=1).mean()
    return hma

def rsi_custom(series, window=14):
    """Custom implementation of RSI"""
    if len(series) < window + 1:
        return pd.Series([np.nan] * len(series), index=series.index)
    
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window, min_periods=1).mean()
    
    # Avoid division by zero
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

async def get_last_oclh_time(file_path):
    """Get the last processed time from existing OCLH file"""
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            if not df.empty and 'Time_End' in df.columns:
                last_time = pd.to_datetime(df['Time_End'].iloc[-1])
                last_time = last_time.tz_localize(None)          # ensure naïve
                return last_time
        except Exception as e:
            if VERBOSE:
                print(f"Error reading {file_path}: {e}")
    return None

def create_ohlc_bars(df, interval_minutes, market_start_time, first_available_price):
    """
    Create OHLC bars according to your specification:
    1. Open: First price in the time interval (use first_available_price for gaps)
    2. Close: Last price in the time interval
    3. High/Low: Max/Min price in the time interval
    4. Fill gaps from market open with first_available_price
    """
    if df.empty:
        return pd.DataFrame(columns=['Time_Start', 'Time_End', 'Open', 'High', 'Low', 'Close'])
    
    # Sort by time to ensure proper ordering
    df = df.sort_values('Time').reset_index(drop=True)
    
    # Get the time range we need to cover
    first_data_time = df['Time'].min()
    last_data_time = df['Time'].max()
    
    # Create time intervals starting from market open
    start_time = min(market_start_time, first_data_time.floor(f'{interval_minutes}min'))
    end_time = last_data_time.ceil(f'{interval_minutes}min')
    
    # Generate all time intervals
    time_intervals = pd.date_range(start=start_time, end=end_time, freq=f'{interval_minutes}min')
    
    ohlc_bars = []
    
    for i in range(len(time_intervals) - 1):
        interval_start = time_intervals[i]
        interval_end = time_intervals[i + 1]
        
        # Get data for this interval
        interval_data = df[(df['Time'] >= interval_start) & (df['Time'] < interval_end)]
        
        if interval_data.empty:
            # No data for this interval - fill with first_available_price if before first data
            if interval_end <= first_data_time:
                ohlc_bars.append({
                    'Time_Start': interval_start,
                    'Time_End': interval_end,
                    'Open': first_available_price,
                    'High': first_available_price,
                    'Low': first_available_price,
                    'Close': first_available_price
                })
            # Skip intervals with no data after first data appears
            continue
        
        # Calculate OHLC for this interval
        # Open: First price in interval
        open_price = interval_data['Mid_Price'].iloc[0]
        
        # Close: Last price in interval  
        close_price = interval_data['Mid_Price'].iloc[-1]
        
        # High: Maximum price in interval
        high_price = interval_data['Mid_Price'].max()
        
        # Low: Minimum price in interval
        low_price = interval_data['Mid_Price'].min()
        
        ohlc_bars.append({
            'Time_Start': interval_start,
            'Time_End': interval_end,
            'Open': open_price,
            'High': high_price,
            'Low': low_price,
            'Close': close_price
        })
    
    # Convert to DataFrame
    ohlc_df = pd.DataFrame(ohlc_bars)
    
    return ohlc_df

def calculate_technical_indicators(df):
    """Calculate all technical indicators"""
    if df.empty or len(df) < 2:
        return df
    
    close_prices = df['Close'].astype(float)
    
    # Simple Moving Averages
    df['SMA10'] = close_prices.rolling(window=10, min_periods=1).mean().round(2)
    df['SMA20'] = close_prices.rolling(window=20, min_periods=1).mean().round(2)
    df['SMA50'] = close_prices.rolling(window=50, min_periods=1).mean().round(2)
    df['SMA100'] = close_prices.rolling(window=100, min_periods=1).mean().round(2)
    df['SMA200'] = close_prices.rolling(window=200, min_periods=1).mean().round(2)
    
    # Exponential Moving Averages
    df['EMA8'] = close_prices.ewm(span=8, adjust=False).mean().round(2)
    df['EMA13'] = close_prices.ewm(span=13, adjust=False).mean().round(2)
    df['EMA21'] = close_prices.ewm(span=21, adjust=False).mean().round(2)
    df['EMA34'] = close_prices.ewm(span=34, adjust=False).mean().round(2)
    
    # Hull Moving Average
    df['HMA'] = hull_moving_average(close_prices, window=9).round(2)
    
    # RSI
    df['RSI14'] = rsi_custom(close_prices, window=14).round(2)
    
    # MACD
    if USE_TALIB and len(close_prices) >= 26:
        try:
            macd, macdsignal, macdhist = talib.MACD(close_prices.values, 
                                                   fastperiod=12, slowperiod=26, signalperiod=9)
            df['MACD'] = macd
            df['MACD_Signal'] = macdsignal
            df['MACD_Histogram'] = macdhist
        except Exception:
            # Fallback to pandas implementation
            ema12 = close_prices.ewm(span=12, adjust=False).mean().round(2)
            ema26 = close_prices.ewm(span=26, adjust=False).mean().round(2)
            df['MACD'] = round(ema12 - ema26, 2)
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean().round(2)
            df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    else:
        # Pandas implementation
        ema12 = close_prices.ewm(span=12, adjust=False).mean().round(2)
        ema26 = close_prices.ewm(span=26, adjust=False).mean().round(2)
        df['MACD'] = round(ema12 - ema26, 2)
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean().round(2)
        df['MACD_Histogram'] = round(df['MACD'] - df['MACD_Signal'], 2)
    
    # Bollinger Bands
    if USE_TALIB and len(close_prices) >= 20:
        try:
            upper, middle, lower = talib.BBANDS(close_prices.values, 
                                              timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
            df['BB_Upper'] = upper
            df['BB_Middle'] = middle
            df['BB_Lower'] = lower
        except Exception:
            # Fallback to pandas implementation
            rolling_mean = close_prices.rolling(window=20, min_periods=1).mean().round(2)
            rolling_std = close_prices.rolling(window=20, min_periods=1).std().round(2)
            df['BB_Middle'] = rolling_mean
            df['BB_Upper'] = round(rolling_mean + (2 * rolling_std), 2)
            df['BB_Lower'] = round(rolling_mean - (2 * rolling_std), 2)
    else:
        # Pandas implementation
        rolling_mean = close_prices.rolling(window=20, min_periods=1).mean().round(2)
        rolling_std = close_prices.rolling(window=20, min_periods=1).std().round(2)
        df['BB_Middle'] = rolling_mean
        df['BB_Upper'] = round(rolling_mean + (2 * rolling_std), 2)
        df['BB_Lower'] = round(rolling_mean - (2 * rolling_std), 2)
    
    return df

async def calculate_write_oclh_and_indicators(interval_minutes, folder_path, spx_file_with_path):
    """Main processing function for each interval"""
    oclh_file = OCLH_FILES[interval_minutes]
    if VERBOSE:
        print(f"Starting {interval_minutes}-minute OCLH processor...")
    
    # Get market start time for today
    today = datetime.now().date()
    market_start_time = datetime.combine(today, MARKET_OPEN_TIME)
    
    first_run = True
    first_available_price = None
    
    # Process immediately on first run, then wait for updates
    process_immediately = True
    
    while True:
        try:
            if not process_immediately:
                # Wait until buffer time after the minute boundary
                now = datetime.now()
                next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
                wait_time = (next_minute - now).total_seconds() + BUFFER_SECONDS
                
                if VERBOSE:
                    print(f"[{interval_minutes}min] Waiting {wait_time:.1f} seconds until next check...")
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            else:
                process_immediately = False
            
            if VERBOSE:
                print(f"[{interval_minutes}min] Checking for new data...")
            
            # Read current SPX data
            if not os.path.exists(spx_file_with_path):
                if VERBOSE:
                    print(f"[{interval_minutes}min] {spx_file_with_path} not found, waiting...")
                await asyncio.sleep(60)
                continue
                
            try:
                df = pd.read_csv(spx_file_with_path)
            except Exception as e:
                if VERBOSE:
                    print(f"[{interval_minutes}min] Error reading {spx_file_with_path}: {e}")
                await asyncio.sleep(60)
                continue
                
            if df.empty:
                if VERBOSE:
                    print(f"[{interval_minutes}min] {spx_file_with_path} is empty, waiting...")
                await asyncio.sleep(60)
                continue
            
            if VERBOSE:
                print(f"[{interval_minutes}min] Found {len(df)} total records in {spx_file_with_path}")
                
            # Parse time and calculate mid price
            try:
                df['Time'] = pd.to_datetime(df['Time'])
                df['Time'] = df['Time'].dt.tz_localize(None)     # make all values offset-naive
                df['Mid_Price'] = calculate_mid_price(df['Bid Price'], df['Ask Price'])
                df = df.sort_values('Time').reset_index(drop=True)
                if VERBOSE:
                    print(f"[{interval_minutes}min] Data time range: {df['Time'].min()} to {df['Time'].max()}")
            except Exception as e:
                print(f"[{interval_minutes}min] Error processing data: {e}")
                
            
            # Store first available price for gap filling
            if first_available_price is None:
                first_available_price = df['Mid_Price'].iloc[0]
                if VERBOSE:
                    print(f"[{interval_minutes}min] First available price: {first_available_price}")
            
            # Get last processed time
            last_processed_time = await get_last_oclh_time(oclh_file)
            if last_processed_time:
                if VERBOSE:
                    print(f"[{interval_minutes}min] Last processed time: {last_processed_time}")
                # Filter for new data only
                original_count = len(df)
                df = df[df['Time'] > last_processed_time]
                if VERBOSE:
                    print(f"[{interval_minutes}min] Records after filtering: {len(df)} (from {original_count})")
            else:
                if VERBOSE:
                    print(f"[{interval_minutes}min] No previous data found, processing from beginning")
            
            if df.empty and not first_run:
                if VERBOSE:
                    print(f"[{interval_minutes}min] No new data to process")
                continue
            
            if VERBOSE:
                print(f"[{interval_minutes}min] Processing {len(df)} records...")
            
            # Create OHLC bars using the new logic
            if first_run:
                # For first run, process all available data
                all_df = pd.read_csv(spx_file_with_path)
                all_df['Time'] = pd.to_datetime(all_df['Time'])
                all_df['Time'] = all_df['Time'].dt.tz_localize(None)  
                all_df['Mid_Price'] = calculate_mid_price(all_df['Bid Price'], all_df['Ask Price'])
                new_ohlc = create_ohlc_bars(all_df, interval_minutes, market_start_time, first_available_price)
                first_run = False
            else:
                # For subsequent runs, only process new data
                new_ohlc = create_ohlc_bars(df, interval_minutes, market_start_time, first_available_price)
            
            if VERBOSE:
                print(f"[{interval_minutes}min] Generated {len(new_ohlc)} OHLC bars")
            
            if new_ohlc.empty:
                if VERBOSE:
                    print(f"[{interval_minutes}min] No complete bars generated")
                continue
            
            # Load existing data if available
            if os.path.exists(oclh_file) and last_processed_time is not None:
                if VERBOSE:
                    print(f"[{interval_minutes}min] Loading existing data from {oclh_file}")
                existing_df = pd.read_csv(oclh_file)
                existing_df['Time_Start'] = pd.to_datetime(existing_df['Time_Start'])
                existing_df['Time_End'] = pd.to_datetime(existing_df['Time_End'])
                
                # Combine with new data, avoiding duplicates
                combined_df = pd.concat([existing_df, new_ohlc]).drop_duplicates(
                    subset=['Time_Start'], keep='last').sort_values('Time_Start').reset_index(drop=True)
                if VERBOSE:
                    print(f"[{interval_minutes}min] Combined: {len(existing_df)} existing + {len(new_ohlc)} new = {len(combined_df)} total")
            else:
                combined_df = new_ohlc.copy()
                if VERBOSE:
                    print(f"[{interval_minutes}min] Creating new file with {len(combined_df)} bars")
            
            if combined_df.empty:
                if VERBOSE:
                    print(f"[{interval_minutes}min] No data to process after combining")
                continue
            
            # Calculate technical indicators
            if VERBOSE:
                print(f"[{interval_minutes}min] Calculating technical indicators...")
            combined_df = calculate_technical_indicators(combined_df)
            
            # Save to file
            if VERBOSE:
                print(f"[{interval_minutes}min] Saving to {oclh_file}...")
            combined_df.to_csv(folder_path + oclh_file, index=False)
            
            if VERBOSE:
                print(f"[{interval_minutes}min] ✓ Updated {oclh_file} - Total bars: {len(combined_df)}")
            
            # Show latest data
            if len(combined_df) > 0:
                latest = combined_df.iloc[-1]
                if VERBOSE:
                    print(f"[{interval_minutes}min] Latest bar: {latest['Time_Start']} | O:{latest['Open']:.2f} H:{latest['High']:.2f} L:{latest['Low']:.2f} C:{latest['Close']:.2f}")
                if not pd.isna(latest['SMA10']) and not pd.isna(latest['RSI14']):
                    if VERBOSE:
                        print(f"[{interval_minutes}min] Latest indicators: SMA10:{latest['SMA10']:.2f} RSI14:{latest['RSI14']:.1f}")
            
        except Exception as e:
            print(f"[{interval_minutes}min] ERROR: {e}")
            if VERBOSE:
                import traceback
                traceback.print_exc()
            await asyncio.sleep(60)  # Wait before retrying

async def oclh(folder_path):
    """Main function to run all processors concurrently"""
    if VERBOSE:
        print("Starting SPX OCLH processors...")
        print(f"Market open time: {MARKET_OPEN_TIME}")
        print(f"Buffer time: {BUFFER_SECONDS} seconds")
        print(f"Processing intervals: {list(OCLH_FILES.keys())} minutes")
    
    # Create tasks for all intervals
    tasks = [
        asyncio.create_task(calculate_write_oclh_and_indicators(interval, folder_path, folder_path+"spx.csv"))
        for interval in OCLH_FILES.keys()
    ]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(oclh(r"C:\Users\meets\OneDrive\tasty2025\tasty101\Data\2025-05-27\\"))

# Go through this to get day level data: 
# https://github.com/tastyware/tastytrade/blob/61e832ef66f7628efce9077dabddff11d309084c/docs/market-data.rst#L16