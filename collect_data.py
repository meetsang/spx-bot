import asyncio
import aiofiles
from tastytrade import DXLinkStreamer, Session
from tastytrade.dxfeed import Quote, Greeks
from tastytrade.instruments import get_option_chain
from datetime import date, datetime
import logging
import math
import json
import time
import re
#from datetime import datetime
from pytz import timezone

market_tz = timezone("US/Central")

from shared_queues import data_queue, subscription_queue

def establish_connection():
    with open('secrets.json', 'r') as file:
        secrets = json.load(file)
    session = Session(secrets['username'], secrets['password'])
    account_num = secrets['AccountNumber']
    return session, account_num

async def write_to_csv(filepath, row):
    async with aiofiles.open(filepath, mode='a') as f:
        await f.write(','.join(map(str, row)) + '\n')

def is_option_symbol(symbol):
    """Check if symbol is an option based on common option symbol patterns"""
    # Common option patterns: .SPXW250527C5910, AAPL250117C150, etc.
    option_patterns = [
        r'^\.[A-Z]+\d{6}[CP]\d+$',  # .SPXW250527C5910
        r'^[A-Z]+\d{6}[CP]\d+$',    # AAPL250117C150
        r'^[A-Z]+_\d{6}[CP]\d+$',   # Some brokers use underscores
    ]
    
    for pattern in option_patterns:
        if re.match(pattern, symbol):
            return True
    return False

def get_underlying_ticker(symbol):
    """Extract underlying ticker from option symbol"""
    if symbol.startswith('.'):
        # For symbols like .SPXW250527C5910, extract base ticker
        match = re.match(r'^\.([A-Z]+)', symbol)
        if match:
            base = match.group(1)
            # Handle special cases like SPXW -> SPX
            if base.endswith('W'):
                return base[:-1]  # Remove 'W' suffix
            return base
    else:
        # For symbols like AAPL250117C150
        match = re.match(r'^([A-Z]+)\d{6}[CP]\d+$', symbol)
        if match:
            return match.group(1)
    
    return symbol  # Fallback

def categorize_symbols(symbols):
    """Categorize symbols into regular tickers and options with their underlying"""
    regular_tickers = []
    options = []
    
    for symbol in symbols:
        if is_option_symbol(symbol):
            underlying = get_underlying_ticker(symbol)
            options.append({
                'symbol': symbol,
                'underlying': underlying,
                'filename': f"{underlying.lower()}_options.csv"
            })
        else:
            regular_tickers.append({
                'symbol': symbol,
                'filename': f"{symbol.lower()}.csv"
            })
    
    return regular_tickers, options

async def initialize_csv_files(folder_path, regular_tickers, options):
    """Initialize CSV files with appropriate headers"""
    
    # Header for regular tickers
    ticker_header = ['Time', 'Symbol', 'Bid Price', 'Ask Price', 'Bid Size', 'Ask Size']
    
    # Header for options (includes Greeks)
    option_header = [
        'Time', 'Symbol', 'Bid Price', 'Ask Price', 'Bid Size', 'Ask Size',
        'Greeks Price', 'Volatility', 'Delta', 'Gamma', 'Theta', 'Rho', 'Vega'
    ]
    
    # Initialize regular ticker files
    for ticker_info in regular_tickers:
        full_file_path = folder_path + ticker_info['filename']
        try:
            async with aiofiles.open(full_file_path, mode='r') as f:
                pass  # File exists, skip header
        except FileNotFoundError:
            await write_to_csv(full_file_path, ticker_header)
            print(f"Created new file: {ticker_info['filename']}")
    
    # Initialize option files (group by underlying)
    option_files_created = set()
    for option_info in options:
        if option_info['filename'] not in option_files_created:
            full_file_path = folder_path + option_info['filename']
            try:
                async with aiofiles.open(full_file_path, mode='r') as f:
                    pass  # File exists, skip header
            except FileNotFoundError:
                await write_to_csv(full_file_path, option_header)
                print(f"Created new options file: {option_info['filename']}")
                option_files_created.add(option_info['filename'])

def clean_row(row):
    return [
        "" if (x is None or (isinstance(x, float) and math.isnan(x))) else x
        for x in row
    ]

async def stream_and_write(session, initial_tickers, folder_path, max_retries=5, retry_delay=5):
    """Enhanced streaming function to handle both regular tickers and options with Greeks"""
    
    # Categorize symbols
    regular_tickers, options = categorize_symbols(initial_tickers)
    
    print(f"Regular tickers: {[t['symbol'] for t in regular_tickers]}")
    print(f"Options: {[o['symbol'] for o in options]}")
    
    # Initialize CSV files
    await initialize_csv_files(folder_path, regular_tickers, options)
    
    # Combine all symbols for subscription
    all_symbols = [t['symbol'] for t in regular_tickers] + [o['symbol'] for o in options]
    option_symbols = [o['symbol'] for o in options]
    
    # Create lookup dictionaries for quick file path resolution
    symbol_to_filepath = {}
    for ticker_info in regular_tickers:
        symbol_to_filepath[ticker_info['symbol']] = folder_path + ticker_info['filename']
    
    for option_info in options:
        symbol_to_filepath[option_info['symbol']] = folder_path + option_info['filename']
    
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"Establishing connection (attempt {retry_count + 1}/{max_retries})")
            
            async with DXLinkStreamer(session) as streamer:
                # Subscribe to quotes for all symbols
                await streamer.subscribe(Quote, all_symbols)
                print(f"Successfully subscribed to quotes for {len(all_symbols)} symbols")
                
                # Subscribe to Greeks for options only
                greeks_available = False
                if option_symbols:
                    try:
                        await streamer.subscribe(Greeks, option_symbols)
                        print(f"Successfully subscribed to Greeks for {len(option_symbols)} option symbols")
                        greeks_available = True
                    except Exception as e:
                        print(f"Warning: Greeks subscription failed: {e}")
                        print("Continuing without Greeks data...")
                
                # Reset retry count on successful connection
                retry_count = 0
                last_data_time = time.time()
                connection_timeout = 20
                
                # Storage for Greeks data - keyed by symbol
                greeks_data = {}
                
                while True:
                    try:
                        # Try to get Quote events
                        try:
                            quote = await asyncio.wait_for(
                                streamer.get_event(Quote), 
                                timeout=connection_timeout
                            )
                            
                            # Update last data time
                            last_data_time = time.time()
                            
                            current_time = datetime.now(market_tz).isoformat()
                            
                            # Check if this is an option or regular ticker
                            if quote.event_symbol in option_symbols:
                                # This is an option - prepare row with Greeks placeholders
                                greeks_info = greeks_data.get(quote.event_symbol, {})
                                
                                row = [
                                    current_time,
                                    quote.event_symbol,
                                    quote.bid_price,
                                    quote.ask_price,
                                    quote.bid_size,
                                    quote.ask_size,
                                    greeks_info.get('price'),
                                    greeks_info.get('volatility'),
                                    greeks_info.get('delta'),
                                    greeks_info.get('gamma'),
                                    greeks_info.get('theta'),
                                    greeks_info.get('rho'),
                                    greeks_info.get('vega')
                                ]
                            else:
                                # This is a regular ticker
                                row = [
                                    current_time,
                                    quote.event_symbol,
                                    quote.bid_price,
                                    quote.ask_price,
                                    quote.bid_size,
                                    quote.ask_size
                                ]
                            
                            # Write to appropriate file
                            file_path = symbol_to_filepath.get(quote.event_symbol)
                            if file_path:
                                cleaned_row = clean_row(row)
                                # Only put quotes in data_queue (for backward compatibility)
                                if quote.event_symbol not in option_symbols:
                                    await data_queue.put(cleaned_row)
                                await write_to_csv(file_path, cleaned_row)
                            
                        except asyncio.TimeoutError:
                            # Try to get Greeks events if available
                            if greeks_available:
                                try:
                                    greeks = await asyncio.wait_for(
                                        streamer.get_event(Greeks), 
                                        timeout=1.0  # Shorter timeout for Greeks
                                    )
                                    
                                    # Update Greeks data storage
                                    if greeks.event_symbol in option_symbols:
                                        greeks_data[greeks.event_symbol] = {
                                            'price': greeks.price,
                                            'volatility': greeks.volatility,
                                            'delta': greeks.delta,
                                            'gamma': greeks.gamma,
                                            'theta': greeks.theta,
                                            'rho': greeks.rho,
                                            'vega': greeks.vega
                                        }
                                        
                                        # Print periodic update
                                        if int(time.time()) % 30 == 0:  # Every 30 seconds
                                            print(f"Updated Greeks for {greeks.event_symbol}")
                                    
                                except asyncio.TimeoutError:
                                    # Check if connection is really dead
                                    if time.time() - last_data_time > connection_timeout:
                                        print(f"No data received for {connection_timeout} seconds, assuming connection is dead")
                                        break
                            else:
                                # No Greeks subscription, just check connection timeout
                                if time.time() - last_data_time > connection_timeout:
                                    print(f"No data received for {connection_timeout} seconds, assuming connection is dead")
                                    break
                    
                    except Exception as e:
                        print(f"Error during streaming: {e}")
                        print(f"Exception type: {type(e).__name__}")
                        break  # Break to trigger reconnection
                        
        except Exception as e:
            retry_count += 1
            print(f"Connection failed: {e}")
            print(f"Exception type: {type(e).__name__}")
            
            if retry_count >= max_retries:
                print(f"Max retries ({max_retries}) reached. Giving up.")
                raise
            
            print(f"Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            
            # Exponential backoff: double the delay each time, up to 60 seconds
            retry_delay = min(retry_delay * 2, 60)
            
            # Re-establish session in case it's stale
            try:
                session, _ = establish_connection()
                print("Re-established session")
            except Exception as session_error:
                print(f"Failed to re-establish session: {session_error}")
                
        # Reset retry delay after a successful connection period
        retry_delay = 5
        print("Connection lost, attempting to reconnect...")

async def collect_data(folder_path, tickers=None):
    """
    Main data collection function
    
    Args:
        folder_path (str): Path where CSV files will be saved
        tickers (list): List of tickers/options to stream. If None, defaults to ['SPX']
    """
    if tickers is None:
        tickers = ['SPX']
    
    session, _ = establish_connection()
    logging.getLogger("tastytrade").setLevel(logging.WARNING)
    
    print(f"Starting data collection for: {tickers}")
    print(f"Files will be saved to: {folder_path}")
    
    # Run with high retry count for continuous operation
    await stream_and_write(session, tickers, folder_path, max_retries=999999)

if __name__ == "__main__":
    # Example usage with multiple tickers including options
    example_tickers = [
        'SPX',                    # Regular SPX ticker -> spx.csv
        '.SPXW250527C5910',      # SPX option -> spx_options.csv
        'AAPL',                  # Regular AAPL ticker -> aapl.csv
        # 'AAPL250117C150'       # AAPL option -> aapl_options.csv (uncomment to test)
    ]
    
    # Run with example tickers
    asyncio.run(collect_data("./", example_tickers))
    
    # Or run with default SPX only
    # asyncio.run(collect_data("./"))
