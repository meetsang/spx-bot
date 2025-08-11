#!/usr/bin/env python3
"""
XSP Iron Condor Trader - Based on your SPX trader patterns
XSP is mini SPX (1/10 size) with lower margin requirements
"""

import json
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from tastytrade import Session, Account, DXLinkStreamer
from tastytrade.dxfeed import Quote
from tastytrade.instruments import get_option_chain
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType


class XSPIronCondorTrader:
    def __init__(self, secrets_file='secrets.json'):
        """Initialize using your proven pattern"""
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
                print(f"Getting quotes for {len(option_symbols)} XSP options...")
                
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
                
                print(f"Collected {quotes_collected}/{target_quotes} XSP option quotes")
                
        except Exception as e:
            print(f"Error getting XSP option prices: {e}")
        
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

    async def place_xsp_iron_condor(self, current_xsp_price, days_out=7, spread_width=1,
                                   call_otm=5, put_otm=5, quantity=1, dry_run=True):
        """
        Place XSP Iron Condor with $1 width spreads
        XSP has lower margin requirements than SPX
        """
        try:
            # Get XSP option chain
            chain = get_option_chain(self.session, 'XSP')
            target_date = datetime.now().date() + timedelta(days=days_out)
            exp_date = min(chain.keys(), key=lambda d: abs((d - target_date).days))
            options = chain[exp_date]
            
            print(f"Using XSP expiration: {exp_date}")
            
            # Separate calls and puts
            calls = [opt for opt in options if opt.option_type == 'C']
            puts = [opt for opt in options if opt.option_type == 'P']
            
            call_strikes = sorted([float(c.strike_price) for c in calls])
            put_strikes = sorted([float(p.strike_price) for p in puts], reverse=True)
            
            print(f"XSP call strikes available: {len(call_strikes)} total")
            print(f"XSP put strikes available: {len(put_strikes)} total")
            
            # Find iron condor strikes for $1 width spreads
            short_call_strike = min(call_strikes, key=lambda x: abs(x - (current_xsp_price + call_otm)))
            long_call_strike = min(call_strikes, key=lambda x: abs(x - (short_call_strike + spread_width)))
            
            short_put_strike = min(put_strikes, key=lambda x: abs(x - (current_xsp_price - put_otm)))
            long_put_strike = min(put_strikes, key=lambda x: abs(x - (short_put_strike - spread_width)))
            
            print(f"XSP Iron Condor strikes ($1 width):")
            print(f"  Put side: {long_put_strike}/{short_put_strike}")
            print(f"  Call side: {short_call_strike}/{long_call_strike}")
            
            # Find option objects
            short_call = next(c for c in calls if float(c.strike_price) == short_call_strike)
            long_call = next(c for c in calls if float(c.strike_price) == long_call_strike)
            short_put = next(p for p in puts if float(p.strike_price) == short_put_strike)
            long_put = next(p for p in puts if float(p.strike_price) == long_put_strike)
            
            # Calculate total credit from market prices
            print("Calculating XSP iron condor credit from current market prices...")
            call_credit = await self.calculate_spread_credit(short_call, long_call)
            put_credit = await self.calculate_spread_credit(short_put, long_put)
            
            if call_credit is None or put_credit is None:
                print("Could not get all XSP option prices, using fallback")
                total_credit = spread_width * 0.20  # Fallback for $1 spreads
            else:
                total_credit = call_credit + put_credit
            
            total_credit = self.round_to_nickel_explicit(total_credit)
            
            print(f"XSP Call Credit: ${call_credit:.2f}")
            print(f"XSP Put Credit: ${put_credit:.2f}")
            print(f"Total XSP Iron Condor Credit: ${total_credit:.2f}")
            
            # Create 4-leg XSP iron condor order
            legs = [
                short_call.build_leg(Decimal(str(quantity)), OrderAction.SELL_TO_OPEN),
                long_call.build_leg(Decimal(str(quantity)), OrderAction.BUY_TO_OPEN),
                short_put.build_leg(Decimal(str(quantity)), OrderAction.SELL_TO_OPEN),
                long_put.build_leg(Decimal(str(quantity)), OrderAction.BUY_TO_OPEN)
            ]
            
            # Single order with all 4 legs
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=legs,
                price=Decimal(str(total_credit))
            )
            
            response = self.account.place_order(self.session, order, dry_run=dry_run)
            
            print(f"✅ XSP Iron Condor {'(DRY RUN) ' if dry_run else ''}placed!")
            print(f"Short Call: {short_call.symbol}")
            print(f"Long Call: {long_call.symbol}")
            print(f"Short Put: {short_put.symbol}")
            print(f"Long Put: {long_put.symbol}")
            print(f"Total Credit Target: ${total_credit:.2f}")
            print(f"Max Risk: ${spread_width * 100}")  # XSP multiplier is 100
            
            return response
            
        except Exception as e:
            print(f"❌ Error placing XSP Iron Condor: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def place_xsp_call_credit_spread(self, current_xsp_price, days_out=7, spread_width=1,
                                          otm_distance=5, quantity=1, dry_run=True):
        """Place XSP call credit spread with $1 width"""
        try:
            chain = get_option_chain(self.session, 'XSP')
            target_date = datetime.now().date() + timedelta(days=days_out)
            exp_date = min(chain.keys(), key=lambda d: abs((d - target_date).days))
            options = chain[exp_date]
            
            calls = [opt for opt in options if opt.option_type == 'C']
            call_strikes = sorted([float(c.strike_price) for c in calls])
            
            short_strike = min(call_strikes, key=lambda x: abs(x - (current_xsp_price + otm_distance)))
            long_strike = min(call_strikes, key=lambda x: abs(x - (short_strike + spread_width)))
            
            short_call = next(c for c in calls if float(c.strike_price) == short_strike)
            long_call = next(c for c in calls if float(c.strike_price) == long_strike)
            
            calculated_credit = await self.calculate_spread_credit(short_call, long_call)
            if calculated_credit is None:
                calculated_credit = spread_width * 0.25
            
            credit_target = self.round_to_nickel_explicit(calculated_credit)
            
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
            
            response = self.account.place_order(self.session, order, dry_run=dry_run)
            
            print(f"✅ XSP Call Credit Spread placed! Credit: ${credit_target:.2f}")
            return response
            
        except Exception as e:
            print(f"❌ Error placing XSP call spread: {e}")
            return None

    async def place_xsp_put_credit_spread(self, current_xsp_price, days_out=7, spread_width=1,
                                         otm_distance=5, quantity=1, dry_run=True):
        """Place XSP put credit spread with $1 width"""
        try:
            chain = get_option_chain(self.session, 'XSP')
            target_date = datetime.now().date() + timedelta(days=days_out)
            exp_date = min(chain.keys(), key=lambda d: abs((d - target_date).days))
            options = chain[exp_date]
            
            puts = [opt for opt in options if opt.option_type == 'P']
            put_strikes = sorted([float(p.strike_price) for p in puts], reverse=True)
            
            short_strike = min(put_strikes, key=lambda x: abs(x - (current_xsp_price - otm_distance)))
            long_strike = min(put_strikes, key=lambda x: abs(x - (short_strike - spread_width)))
            
            short_put = next(p for p in puts if float(p.strike_price) == short_strike)
            long_put = next(p for p in puts if float(p.strike_price) == long_strike)
            
            calculated_credit = await self.calculate_spread_credit(short_put, long_put)
            if calculated_credit is None:
                calculated_credit = spread_width * 0.25
            
            credit_target = self.round_to_nickel_explicit(calculated_credit)
            
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
            
            response = self.account.place_order(self.session, order, dry_run=dry_run)
            
            print(f"✅ XSP Put Credit Spread placed! Credit: ${credit_target:.2f}")
            return response
            
        except Exception as e:
            print(f"❌ Error placing XSP put spread: {e}")
            return None


async def main():
    """Test XSP Iron Condor with $1 width spreads"""
    print("🚀 XSP Iron Condor Trader - $1 Width Spreads")
    print("=" * 55)
    
    trader = XSPIronCondorTrader('secrets.json')
    
    # XSP price is roughly 1/10 of SPX price
    current_xsp = 639  # Approximately SPX 6390 / 10
    
    print(f"Current XSP Price: ${current_xsp}")
    
    # Test XSP Iron Condor with $1 width spreads
    print("\n🔷 XSP Iron Condor ($1 Width, Lower Margin):")
    await trader.place_xsp_iron_condor(
        current_xsp_price=current_xsp,
        days_out=7,
        spread_width=1,    # $1 wide spreads
        call_otm=5,        # $5 OTM call side  
        put_otm=5,         # $5 OTM put side
        quantity=1,
        dry_run=True       # Set to False for live trading
    )
    
    # # Optional: Test individual spreads
    # print("\n📉 XSP Call Credit Spread ($1 Width):")
    # await trader.place_xsp_call_credit_spread(
    #     current_xsp_price=current_xsp,
    #     days_out=7,
    #     spread_width=1,
    #     otm_distance=5,
    #     dry_run=True
    # )
    
    # print("\n📈 XSP Put Credit Spread ($1 Width):")
    # await trader.place_xsp_put_credit_spread(
    #     current_xsp_price=current_xsp,
    #     days_out=7,
    #     spread_width=1,
    #     otm_distance=5,
    #     dry_run=True
    # )


if __name__ == "__main__":
    asyncio.run(main())
