#!/usr/bin/env python3
"""
Enhanced SPX Trader with Mid Price Reading and $0.05 Rounding - Based on your greeks_gex.py patterns
"""

import json
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from tastytrade import Session, Account, DXLinkStreamer
from tastytrade.dxfeed import Quote
from tastytrade.instruments import get_option_chain
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType


class EnhancedSPXTrader:
    def __init__(self, secrets_file='secrets.json'):
        """Initialize using your exact pattern from greeks_gex.py"""
        with open(secrets_file, 'r') as f:
            creds = json.load(f)
        
        self.session = Session(creds['username'], creds['password'])
        self.account = Account.get(self.session, creds['AccountNumber'])
    
    def round_to_nickel_explicit(self, price):
        """Round price to nearest $0.05 increment (nickel rounding)"""
        return round(price / 0.05) * 0.05
    
    async def get_option_mid_prices(self, option_symbols):
        """Get mid prices for options using your exact pattern from greeks_gex.py"""
        option_prices = {}
        
        try:
            async with DXLinkStreamer(self.session) as streamer:
                await streamer.subscribe(Quote, option_symbols)
                print(f"Getting quotes for {len(option_symbols)} options...")
                
                quotes_collected = 0
                target_quotes = len(option_symbols)
                timeout_counter = 0
                
                while quotes_collected < target_quotes and timeout_counter < 10:
                    try:
                        quote = await asyncio.wait_for(streamer.get_event(Quote), timeout=3.0)
                        if quote.event_symbol in option_symbols:
                            if quote.bid_price and quote.ask_price:
                                mid_price = (quote.bid_price + quote.ask_price) / 2
                                option_prices[quote.event_symbol] = {
                                    'bid': quote.bid_price,
                                    'ask': quote.ask_price,
                                    'mid': mid_price
                                }
                                quotes_collected += 1
                    except asyncio.TimeoutError:
                        timeout_counter += 1
                
                print(f"Collected {quotes_collected}/{target_quotes} option quotes")
                
        except Exception as e:
            print(f"Error getting option prices: {e}")
        
        return option_prices
    
    async def calculate_spread_credit(self, short_option, long_option):
        """Calculate actual spread credit based on current mid prices"""
        symbols = [short_option.streamer_symbol, long_option.streamer_symbol]
        prices = await self.get_option_mid_prices(symbols)
        
        if len(prices) == 2:
            short_mid = prices[short_option.streamer_symbol]['mid']
            long_mid = prices[long_option.streamer_symbol]['mid']
            
            # Credit spread = premium received - premium paid
            spread_credit = short_mid - long_mid
            
            print(f"Short option mid: ${short_mid:.2f}")
            print(f"Long option mid: ${long_mid:.2f}")
            print(f"Calculated spread credit: ${spread_credit:.2f}")
            
            return float(spread_credit)
        
        return None
    
    async def place_call_credit_spread(self, current_spx_price, days_out=7, spread_width=50,
                                      otm_distance=100, quantity=1, dry_run=True):
        """
        Place SPX call credit spread with automatic mid price calculation and $0.05 rounding
        """
        try:
            # Get option chain
            chain = get_option_chain(self.session, 'SPX')
            
            # Find target expiration
            target_date = datetime.now().date() + timedelta(days=days_out)
            exp_date = min(chain.keys(), key=lambda d: abs((d - target_date).days))
            
            print(f"Using expiration: {exp_date}")
            
            # Get all options for this expiration
            options = chain[exp_date]
            
            # Filter calls and get all strikes
            calls = [opt for opt in options if opt.option_type == 'C']
            call_strikes = sorted([float(c.strike_price) for c in calls])
            
            print(f"Available call strikes: {len(call_strikes)} total")
            
            # Calculate target strikes
            target_short = current_spx_price + otm_distance
            target_long = target_short + spread_width
            
            # Find closest actual strikes
            short_strike = min(call_strikes, key=lambda x: abs(x - target_short))
            long_strike = min(call_strikes, key=lambda x: abs(x - target_long))
            
            print(f"Selected strikes: Short ${short_strike}, Long ${long_strike}")
            
            # Find the option objects
            short_call = next(c for c in calls if float(c.strike_price) == short_strike)
            long_call = next(c for c in calls if float(c.strike_price) == long_strike)
            
            # Calculate realistic credit target based on current mid prices
            print("Calculating spread credit from current market prices...")
            calculated_credit = await self.calculate_spread_credit(short_call, long_call)
            
            if calculated_credit is None:
                print("Could not get current market prices, using default credit")
                calculated_credit = spread_width * 0.10  # Fallback
            
            # Use 100% of calculated credit
            credit_target_raw = calculated_credit * 1
            credit_target = self.round_to_nickel_explicit(credit_target_raw)
            
            print(f"Market credit available: ${calculated_credit:.2f}")
            print(f"Order credit target: ${credit_target_raw:.2f} → ${credit_target:.2f} (rounded to $0.05)")
            
            # Build order
            legs = [
                short_call.build_leg(Decimal(str(quantity)), OrderAction.SELL_TO_OPEN),
                long_call.build_leg(Decimal(str(quantity)), OrderAction.BUY_TO_OPEN)
            ]
            
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=legs,
                price=Decimal(str(credit_target))
            )
            
            # Place order
            response = self.account.place_order(self.session, order, dry_run=dry_run)
            
            print(f"✅ Call credit spread {'(DRY RUN) ' if dry_run else ''}placed!")
            print(f"Short Call: {short_call.symbol}")
            print(f"Long Call: {long_call.symbol}")
            print(f"Credit Target: ${credit_target:.2f} (Market: ${calculated_credit:.2f})")
            
            return response
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def place_put_credit_spread(self, current_spx_price, days_out=7, spread_width=50,
                                     otm_distance=50, quantity=1, dry_run=True):
        """
        Place SPX put credit spread with automatic mid price calculation and $0.05 rounding
        """
        try:
            # Get option chain
            chain = get_option_chain(self.session, 'SPX')
            
            # Find target expiration
            target_date = datetime.now().date() + timedelta(days=days_out)
            exp_date = min(chain.keys(), key=lambda d: abs((d - target_date).days))
            
            print(f"Using expiration: {exp_date}")
            
            # Get all options for this expiration
            options = chain[exp_date]
            
            # Filter puts and get all strikes
            puts = [opt for opt in options if opt.option_type == 'P']
            put_strikes = sorted([float(p.strike_price) for p in puts], reverse=True)
            
            print(f"Available put strikes: {len(put_strikes)} total")
            
            # Calculate target strikes
            target_short = current_spx_price - otm_distance
            target_long = target_short - spread_width
            
            # Find closest actual strikes
            short_strike = min(put_strikes, key=lambda x: abs(x - target_short))
            long_strike = min(put_strikes, key=lambda x: abs(x - target_long))
            
            print(f"Selected strikes: Short ${short_strike}, Long ${long_strike}")
            
            # Find the option objects
            short_put = next(p for p in puts if float(p.strike_price) == short_strike)
            long_put = next(p for p in puts if float(p.strike_price) == long_strike)
            
            # Calculate realistic credit target
            print("Calculating spread credit from current market prices...")
            calculated_credit = await self.calculate_spread_credit(short_put, long_put)
            
            if calculated_credit is None:
                print("Could not get current market prices, using default credit")
                calculated_credit = spread_width * 0.08  # Fallback for puts
            
            # Use 100% of calculated credit
            credit_target_raw = calculated_credit * 1
            credit_target = self.round_to_nickel_explicit(credit_target_raw)
            
            print(f"Market credit available: ${calculated_credit:.2f}")
            print(f"Order credit target: ${credit_target_raw:.2f} → ${credit_target:.2f} (rounded to $0.05)")
            
            # Build order
            legs = [
                short_put.build_leg(Decimal(str(quantity)), OrderAction.SELL_TO_OPEN),
                long_put.build_leg(Decimal(str(quantity)), OrderAction.BUY_TO_OPEN)
            ]
            
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=legs,
                price=Decimal(str(credit_target))
            )
            
            # Place order
            response = self.account.place_order(self.session, order, dry_run=dry_run)
            
            print(f"✅ Put credit spread {'(DRY RUN) ' if dry_run else ''}placed!")
            print(f"Short Put: {short_put.symbol}")
            print(f"Long Put: {long_put.symbol}")
            print(f"Credit Target: ${credit_target:.2f} (Market: ${calculated_credit:.2f})")
            
            return response
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def place_iron_condor(self, current_spx_price, days_out=7, spread_width=5,
                               call_otm=10, put_otm=10, quantity=1, dry_run=True):
        """
        Place SPX Iron Condor using tastyware's multi-leg order capability
        Simple 4-leg order that handles margin correctly
        """
        try:
            # Get option chain - your proven pattern
            chain = get_option_chain(self.session, 'SPX')
            target_date = datetime.now().date() + timedelta(days=days_out)
            exp_date = min(chain.keys(), key=lambda d: abs((d - target_date).days))
            options = chain[exp_date]
            
            print(f"Using expiration: {exp_date}")
            
            # Separate calls and puts
            calls = [opt for opt in options if opt.option_type == 'C']
            puts = [opt for opt in options if opt.option_type == 'P']
            
            call_strikes = sorted([float(c.strike_price) for c in calls])
            put_strikes = sorted([float(p.strike_price) for p in puts], reverse=True)
            
            # Find iron condor strikes
            short_call_strike = min(call_strikes, key=lambda x: abs(x - (current_spx_price + call_otm)))
            long_call_strike = min(call_strikes, key=lambda x: abs(x - (short_call_strike + spread_width)))
            
            short_put_strike = min(put_strikes, key=lambda x: abs(x - (current_spx_price - put_otm)))
            long_put_strike = min(put_strikes, key=lambda x: abs(x - (short_put_strike - spread_width)))
            
            print(f"Iron Condor strikes:")
            print(f"  Put side: {long_put_strike}/{short_put_strike}")
            print(f"  Call side: {short_call_strike}/{long_call_strike}")
            
            # Find option objects
            short_call = next(c for c in calls if float(c.strike_price) == short_call_strike)
            long_call = next(c for c in calls if float(c.strike_price) == long_call_strike)
            short_put = next(p for p in puts if float(p.strike_price) == short_put_strike)
            long_put = next(p for p in puts if float(p.strike_price) == long_put_strike)
            
            # Calculate total credit
            print("Calculating iron condor credit from current market prices...")
            call_credit = await self.calculate_spread_credit(short_call, long_call)
            put_credit = await self.calculate_spread_credit(short_put, long_put)
            
            if call_credit is None or put_credit is None:
                print("Could not get all option prices, using fallback")
                total_credit = spread_width * 0.15  # Fallback
            else:
                total_credit = call_credit + put_credit
            
            total_credit = self.round_to_nickel_explicit(total_credit)
            
            print(f"Call Credit: ${call_credit:.2f}")
            print(f"Put Credit: ${put_credit:.2f}")
            print(f"Total Iron Condor Credit: ${total_credit:.2f}")
            
            # Create 4-leg iron condor order - tastyware handles the rest!
            legs = [
                short_call.build_leg(Decimal(str(quantity)), OrderAction.SELL_TO_OPEN),
                long_call.build_leg(Decimal(str(quantity)), OrderAction.BUY_TO_OPEN),
                short_put.build_leg(Decimal(str(quantity)), OrderAction.SELL_TO_OPEN),
                long_put.build_leg(Decimal(str(quantity)), OrderAction.BUY_TO_OPEN)
            ]
            
            # Single order with all 4 legs - proper margin calculation
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=legs,
                price=Decimal(str(total_credit))
            )
            
            response = self.account.place_order(self.session, order, dry_run=dry_run)
            
            print(f"✅ Iron Condor {'(DRY RUN) ' if dry_run else ''}placed!")
            print(f"Short Call: {short_call.symbol}")
            print(f"Long Call: {long_call.symbol}")
            print(f"Short Put: {short_put.symbol}")
            print(f"Long Put: {long_put.symbol}")
            print(f"Total Credit Target: ${total_credit:.2f}")
            
            return response
            
        except Exception as e:
            print(f"❌ Error placing Iron Condor: {e}")
            import traceback
            traceback.print_exc()
            return None


async def main():
    """Test the enhanced trader with Iron Condor functionality"""
    print("🚀 Enhanced SPX Trader with Iron Condor")
    print("=" * 50)
    
    trader = EnhancedSPXTrader('secrets.json')
    current_spx = 6390
    
    print(f"Current SPX Price: ${current_spx}")
    
    # # Test call credit spread with automatic credit calculation
    # print("\n📉 Call Credit Spread with Auto Credit Calculation:")
    # await trader.place_call_credit_spread(
    #     current_spx_price=current_spx,
    #     days_out=7,
    #     spread_width=5,
    #     otm_distance=10,
    #     dry_run=False
    # )
    
    # # Test put credit spread
    # print("\n📈 Put Credit Spread with Auto Credit Calculation:")
    # await trader.place_put_credit_spread(
    #     current_spx_price=current_spx,
    #     days_out=7,
    #     spread_width=5,
    #     otm_distance=10,
    #     dry_run=False
    # )
    
    # Test Iron Condor - single 4-leg order with proper margin handling
    print("\n🔷 Iron Condor with Auto Credit Calculation:")
    await trader.place_iron_condor(
        current_spx_price=current_spx,
        days_out=7,
        spread_width=5,
        call_otm=10,
        put_otm=10,
        quantity=1,
        dry_run=False  # Set to False for live trading
    )


if __name__ == "__main__":
    asyncio.run(main())
    # Add this at the start of place_iron_condor method:

