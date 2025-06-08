import asyncio
# from collections import deque
# import time

# Approach 1: Custom Queue Class with Symbol Tracking
class SymbolOverwriteQueue:
    def __init__(self, maxsize=0):
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._symbol_map = {}  # Maps event_symbol to the actual row data
        self._lock = asyncio.Lock()
    
    async def put(self, row):
        """
        Put a row in the queue. If event_symbol exists and new bid/ask prices are non-zero,
        replace the existing entry. Otherwise, add new entry.
        """
        current_time, event_symbol, bid_price, ask_price, bid_size, ask_size = row
        
        async with self._lock:
            # Check if we should overwrite (bid_price and ask_price are non-zero)
            # should_overwrite = bid_price != 0 and ask_price != 0
            
            if event_symbol in self._symbol_map:
                # Update existing entry in place
                self._symbol_map[event_symbol] = row
            else:
                # Add new entry
                self._symbol_map[event_symbol] = row
                await self._queue.put(row)

    async def get(self, symbol=None):
        """
        Get item from the queue.
        If symbol is specified, get the latest value for that symbol.
        If symbol is None, get the next item from the queue.
        """
        if symbol is not None:
            # Get latest value for specific symbol
            async with self._lock:
                if symbol in self._symbol_map:
                    return self._symbol_map[symbol]
                else:
                    raise KeyError(f"Symbol '{symbol}' not found in queue")
        else:
            # Get next item from queue (original behavior)
            row = await self._queue.get()
            event_symbol = row[1]
            
            async with self._lock:
                # Return the most current version of this symbol's data
                current_row = self._symbol_map.get(event_symbol, row)
                # Remove from tracking once consumed
                if event_symbol in self._symbol_map:
                    del self._symbol_map[event_symbol]
                
                return current_row
    
    def task_done(self):
        """Mark a formerly enqueued task as done"""
        self._queue.task_done()
    
    def get_latest(self, symbol):
        """
        Get the latest value for a specific symbol without removing it from tracking.
        This is a synchronous method that doesn't affect the queue.
        Returns None if symbol not found.
        """
        return self._symbol_map.get(symbol)
    
    async def get_latest_async(self, symbol):
        """
        Async version of get_latest with proper locking.
        Get the latest value for a specific symbol without removing it from tracking.
        Returns None if symbol not found.
        """
        async with self._lock:
            return self._symbol_map.get(symbol)
    
    def has_symbol(self, symbol):
        """Check if a symbol exists in the current tracking"""
        return symbol in self._symbol_map
    
    def get_all_symbols(self):
        """Get list of all currently tracked symbols"""
        return list(self._symbol_map.keys())
    


# Queue for latest price data (SPX and options)
data_queue = SymbolOverwriteQueue()

# Queue for new ticker subscriptions (from trading logic)
subscription_queue = asyncio.Queue()
