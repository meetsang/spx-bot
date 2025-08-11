#!/usr/bin/env python3
"""
Below is a detailed, structured documentation of your SPX Iron Fly (IF) Strategy as implemented in the current first version of the code. It summarizes what the strategy does end-to-end, clarifies where and how SPX price is derived, explains entry/exit logic and rolling, describes streaming and PnL computation, and documents file outputs, configuration, and operational flow. No code changes are proposed; this is purely documentation for the current implementation.

Overview
- Strategy: SPX Iron Fly (IF) ladder that opens 9 iron flies around the ATM body at the scheduled time and manages risk via per-IF and portfolio-level stops, with rolling on individual stops.
- Underlying: SPX (cash-settled index options; 5-point strike grid).
- DTE preference: Choose 0 DTE if available; otherwise use the nearest positive DTE (1 DTE expected).
- Entry structure:
  - 9 IFs by default, 60-wide.
  - Bodies spaced by 5 points: ATM plus 4 bodies above and 4 bodies below.
  - All prices used for order placement are rounded to $0.05 and formatted to 2 decimals.
- Exit structure:
  - Per-IF stop loss (default $500 loss).
  - Portfolio stop loss (default $4,000 loss) across all open IFs.
  - When a per-IF stop triggers and the portfolio stop is not breached, that IF is closed and rolled to the far edge (one more step beyond the current ladder extremity).
- Streaming and mark-to-market:
  - Option legs’ Quote and Greeks are streamed internally via dxFeed (no external collector required).
  - Mids are computed from current bid/ask and rounded to $0.05.
  - Per-IF PnL and total strategy PnL are recomputed on every streaming cycle and written to CSVs.

SPX Price Derivation for ATM Body
- Purpose: The strategy needs an “ATM body” strike to center the ladder.
- Source:
  1) Primary: dxFeed Trade event price for SPX (treated as “Mark Price” similar to your collect_data.py pattern).
  2) Fallback: dxFeed Quote mid for SPX (i.e., (bid + ask)/2).
  3) Final fallback (when market is closed and neither Trade nor Quote yields usable data): pick the strike closest to the median of available strikes for the selected expiration.
- Rounding to strike grid:
  - Whatever spot is obtained (Trade price or Quote mid), it is rounded to the nearest 5 to conform to SPX’s 5-point strike grid.
  - This rounded value is the ATM body for the central IF.

Entry Logic
- Schedule:
  - Entry evaluated against a configurable local time window: defaults to 8:33 AM.
  - The function evaluate_entry_window() returns true when current local time is at or after the configured entry time and the strategy hasn’t entered yet for the day.
- Expiration selection:
  - pick_0_or_1_dte(chain)
    - If an expiration is available for the current date (0 DTE), select it.
    - Otherwise select the nearest future expiration (1 DTE expected).
- Ladder construction (construct_ladder):
  - Determine the ATM body (rounded to nearest 5 as described above).
  - Build a list of 9 bodies by default:
    - Center at ATM body.
    - n_below bodies spaced below by step points (default 4 bodies, step=5).
    - n_above bodies spaced above by step points (default 4 bodies, step=5).
  - For each body b:
    - Short call at strike b.
    - Long call at strike b + width (default 60).
    - Short put at strike b.
    - Long put at strike b − width.
  - Option objects are sourced directly from the tastytrade option chain (get_option_chain). Legs are built from these objects (no Option.get by string).
- Pricing for entry orders:
  - For each IF:
    - Stream Quote and (when available) Greeks for its four legs via DXLinkStreamer using each leg’s streamer_symbol.
    - Compute each leg’s mid = (bid + ask) / 2 when both are available.
    - IF entry credit = (short call mid + short put mid) − (long call mid + long put mid).
    - Round the credit to $0.05 using Decimal-based rounding to eliminate float artifacts.
  - Place a single 4-leg LIMIT order per IF at the computed credit (dry_run defaults to True).
- Execution notes:
  - All prices used in orders are rounded to valid $0.05 increments.
  - Credits/debits are formatted and logged to 2 decimals.

Exit Logic
- Continuous monitoring loop:
  - After entry, the strategy continuously streams leg quotes, recomputes each IF’s current mid credit, and evaluates exits.
- PnL computation (compute_strategy_status):
  - For an open IF:
    - Current “debit to close” approximation is the current mid credit of the IF.
    - PnL ≈ entry_credit − current_mid.
    - Per-IF PnL and total strategy PnL are maintained in state and written to CSVs.
- Per-IF stop:
  - If an IF’s PnL is less than or equal to −per_if_stop (default −$500), that IF is closed (reverse the original legs with appropriate BTC/STC actions).
  - After a successful close, and if portfolio stop is not hit, the strategy “rolls”:
    - It opens a replacement IF one more step beyond the far side of the current ladder:
      - If the losing IF was at the lowest body, open a new IF at highest body + step.
      - If the losing IF was at the highest body, open a new IF at lowest body − step.
- Portfolio stop:
  - If total strategy loss (i.e., −total_pnl) reaches or exceeds portfolio_stop (default $4,000), close all open IFs and stop adding new ones.

Streaming and Pricing Details
- Instruments:
  - Quotes and Greeks are streamed for all open IF leg symbols using dxFeed (DXLinkStreamer).
- Data captured:
  - Quote: bid, ask, and mid where both bid and ask exist. Mid is rounded to $0.05.
  - Greeks (if available): delta, gamma, theta, vega.
- Robustness:
  - Streaming uses short timeouts and iterates for a bounded number of cycles to collect events.
  - Greeks subscription is attempted but optional; absence of Greeks does not block operation.
- Internal use of objects:
  - Orders and legs are built using Option objects returned by get_option_chain, avoiding symbol lookup issues.
  - Streaming always uses streamer_symbol from each Option object (as in your greeks_gex.py pattern).

Data Output
- Base folder:
  - Data// where  = SPX_9IF_0DTE.
  - The folder is refreshed daily to handle date rollovers.
- Files:
  - quotes.csv
    - Columns: ts, symbol, bid, ask, mid, delta, gamma, theta, vega
    - All numeric fields are formatted to 2 decimals for readability.
  - pnl.csv (per-IF PnL)
    - Columns: ts, body, pnl, total_pnl
    - body: IF label (the short strike), e.g., 6390.00
    - pnl: per-IF PnL rounded to cents.
    - total_pnl: strategy total PnL at the time of row creation.
  - pnl_strategy.csv (overall strategy PnL)
    - Columns: ts, strategy_total_pnl
    - Contains one row per mark-to-market cycle reflecting the total strategy PnL.
- When files are first written for the day, the header row is included automatically.

Configuration (Config)
- secrets_file: path to tastytrade credentials JSON.
- entry_hour, entry_minute: entry schedule (local time).
- n_above, n_below: how many IF bodies above and below ATM to open (default 4 each → 9 total with center).
- step: distance between successive IF bodies (default 5).
- width: wing width for each IF (default 60).
- symbol: underlying symbol, default “SPX”.
- dry_run: if True, place DRY RUN orders; set False to place live orders.
- tif: time-in-force for orders (default DAY).
- per_if_stop: per-IF stop loss in dollars (default 500.0).
- portfolio_stop: portfolio-level stop loss in dollars (default 4000.0).
- max_quote_timeouts and quote_wait_timeout: streaming cadence and patience for collecting quote/greeks events.
- data_base_dir: base folder for outputs (default “Data”).
- strategy_name: subfolder inside the date folder (default “SPX_9IF_0DTE”).
- quotes_csv, pnl_if_csv, pnl_strategy_csv: filenames for output CSVs in the strategy folder.

Operational Flow
1) Initialize:
   - Authenticate to tastytrade with secrets.json.
   - Ensure output folder Data//SPX_9IF_0DTE exists, and set file paths.
2) Select expiration:
   - 0 DTE if available, otherwise nearest future expiration.
3) Determine ATM:
   - Try SPX Trade.price (“Mark Price”).
   - Else use SPX Quote mid.
   - If neither available (market closed and no snapshot), select the strike closest to the median of available strikes for the chosen expiration.
   - Round to nearest 5.
4) Entry at scheduled time:
   - Construct 9 IFs centered on ATM with 5-point spacing and 60-point wings.
   - Price each IF via streamed mids and round to $0.05.
   - Place 4-leg LIMIT orders (dry run by default).
5) Continuous monitoring:
   - Stream quotes (and Greeks if available) for all open legs.
   - Recompute mids → per-IF and total PnL.
   - Write quotes.csv, pnl.csv, pnl_strategy.csv updates.
6) Exit management:
   - If total loss ≥ portfolio_stop: close all IFs.
   - Else if any IF loss ≥ per_if_stop: close that IF and roll to far edge.
7) Rollover handling:
   - Output folder re-evaluated periodically; if date changes, switch paths to new date folder.

Conventions and Rounding
- All order prices (credits/debits) are rounded to $0.05 increments per SPX minimum price increment rules.
- All formatted outputs (logs and CSV) show two decimal places.
- PnL computations are rounded to the nearest cent for reporting.

Assumptions and Notes
- SPX strikes are in 5-point increments; the ATM body is rounded to that grid.
- Credit strategy PnL approximation uses current mid credit as the “debit to close.” This is a practical proxy; exact executable close prices would depend on current bid/ask and slippage.
- Dry run is enabled by default; no live orders are sent unless explicitly configured.
- Greeks are optional and not required for pricing or PnL; the streaming attempts to capture them but proceeds regardless.

Summary
- The strategy is a rules-driven, time-based entry system that builds a 9-IF ladder around a robustly derived ATM body, with internal streaming for price discovery, consistent rounding for SPX, CSV logging for audit and analysis, and straightforward risk controls via per-IF and portfolio-level stops plus a directional rolling mechanism. It is designed to run self-contained without external data collectors, aligned with your greeks_gex streaming pattern, and organized so you can later refactor entry/exit/status evaluators into a multi-strategy rules engine.
"""

import asyncio
import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional

from tastytrade import Session, Account, DXLinkStreamer
from tastytrade.dxfeed import Quote, Greeks, Trade
from tastytrade.instruments import get_option_chain
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType


# =========================
# Configuration
# =========================
@dataclass
class Config:
    secrets_file: str = "secrets.json"

    # Entry schedule (local time)
    entry_hour: int = 8
    entry_minute: int = 33

    # Ladder structure
    n_above: int = 4         # number of IFs above ATM
    n_below: int = 4         # number of IFs below ATM
    step: int = 5            # distance between successive IF bodies
    width: int = 60          # wings (distance from body)

    # Underlying
    symbol: str = "SPX"

    # Order params
    dry_run: bool = True
    tif: OrderTimeInForce = OrderTimeInForce.DAY

    # Exit rules
    per_if_stop: float = 500.0        # loss per IF to stop/roll
    portfolio_stop: float = 4000.0    # total loss to close all IFs

    # Streaming cadence
    max_quote_timeouts: int = 12      # loop timeouts
    quote_wait_timeout: float = 2.5   # seconds

    # Data folder base
    data_base_dir: str = "Data"       # CSVs under Data/<YYYY-MM-DD>/<Strategy>/
    strategy_name: str = "SPX_9IF_0DTE"  # subfolder name under date folder

    # Filenames (within the strategy folder)
    quotes_csv: str = "quotes.csv"
    pnl_if_csv: str = "pnl.csv"
    pnl_strategy_csv: str = "pnl_strategy.csv"


# =========================
# Helpers
# =========================
def round_to_nickel(value: float) -> float:
    # round to nearest 0.05, using Decimal to avoid float artifacts
    d = Decimal(str(value))
    nickel = Decimal("0.05")
    return float((d / nickel).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * nickel)

def fmt2(value: float) -> str:
    return f"{value:.2f}"

def now_local() -> datetime:
    return datetime.now()

def is_time_to_enter(cfg: Config) -> bool:
    target = time(hour=cfg.entry_hour, minute=cfg.entry_minute)
    return now_local().time() >= target

def nearest(items: List[float], target: float) -> float:
    return min(items, key=lambda x: abs(x - target))

def ensure_strategy_folder(cfg: Config) -> str:
    date_str = now_local().strftime("%Y-%m-%d")
    folder = os.path.join(cfg.data_base_dir, date_str, cfg.strategy_name)
    os.makedirs(folder, exist_ok=True)
    return folder

def write_csv_row(filepath: str, fieldnames: List[str], row: Dict, write_header_if_missing: bool = True):
    write_header = write_header_if_missing and (not os.path.exists(filepath) or os.path.getsize(filepath) == 0)
    with open(filepath, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow(row)


# =========================
# Data structures
# =========================
@dataclass
class IronFly:
    body: float
    width: int
    qty: int
    call_short_opt: any
    call_long_opt: any
    put_short_opt: any
    put_long_opt: any
    entry_credit: float = 0.0
    open: bool = True

    def streamer_symbols(self) -> List[str]:
        return [
            self.call_short_opt.streamer_symbol,
            self.call_long_opt.streamer_symbol,
            self.put_short_opt.streamer_symbol,
            self.put_long_opt.streamer_symbol,
        ]


@dataclass
class StrategyState:
    entered_today: bool = False
    active_flies: Dict[float, IronFly] = field(default_factory=dict)  # keyed by body
    closed_flies: Dict[float, IronFly] = field(default_factory=dict)
    per_if_pnl: Dict[float, float] = field(default_factory=dict)
    total_pnl: float = 0.0


# =========================
# Strategy class
# =========================
class SPXIFStrategy:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        with open(cfg.secrets_file, "r") as f:
            sec = json.load(f)
        self.session = Session(sec["username"], sec["password"])
        self.account = Account.get(self.session, sec["AccountNumber"])
        self.state = StrategyState()
        self.strategy_folder = ensure_strategy_folder(cfg)
        # Prepare full paths
        self.quotes_path = os.path.join(self.strategy_folder, self.cfg.quotes_csv)
        self.pnl_if_path = os.path.join(self.strategy_folder, self.cfg.pnl_if_csv)
        self.pnl_strategy_path = os.path.join(self.strategy_folder, self.cfg.pnl_strategy_csv)

    # ---------- Entry evaluation ----------
    def evaluate_entry_window(self) -> bool:
        return is_time_to_enter(self.cfg) and not self.state.entered_today

    # ---------- Exit evaluation ----------
    def evaluate_exit_rules(self) -> Tuple[List[float], bool]:
        """
        Returns:
          - list of IF bodies to close/roll due to per-IF stop
          - True if portfolio stop is hit (close everything)
        """
        to_close = []
        portfolio_loss = -self.state.total_pnl
        portfolio_stop_hit = portfolio_loss >= self.cfg.portfolio_stop
        if portfolio_stop_hit:
            return list(self.state.active_flies.keys()), True

        for body, pnl in self.state.per_if_pnl.items():
            if -pnl >= self.cfg.per_if_stop:
                to_close.append(body)

        return to_close, False

    # ---------- Status computation ----------
    def compute_strategy_status(self, fly_mids: Dict[float, float]) -> None:
        """
        PnL per IF ≈ entry_credit − current_mid (debit to close).
        """
        per_if_pnl = {}
        total = 0.0
        for body, fly in self.state.active_flies.items():
            if not fly.open:
                continue
            current_mid = fly_mids.get(body)
            if current_mid is None:
                continue
            pnl = float(fly.entry_credit) - float(current_mid)
            pnl = float(Decimal(pnl).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            per_if_pnl[body] = pnl
            total += pnl
        total = float(Decimal(total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        self.state.per_if_pnl = per_if_pnl
        self.state.total_pnl = total

    # ---------- Chain and construction ----------
    def get_chain(self):
        return get_option_chain(self.session, self.cfg.symbol)

    def pick_0_or_1_dte(self, chain) -> datetime.date:
        today = now_local().date()
        exps = sorted(chain.keys())
        same_day = [d for d in exps if d == today]
        if same_day:
            return same_day[0]
        future = [d for d in exps if d > today]
        return future[0] if future else exps[0]

    async def get_underlying_spot_mark_rounded5(self) -> Optional[float]:
        """
        Read underlying mark price similar to collect_data.py:
        - Subscribe to Quote and Trade.
        - Prefer Trade.price (mark), else fallback to Quote mid.
        Then round to nearest 5 to define ATM for IF ladder.
        """
        try:
            async with DXLinkStreamer(self.session) as s:
                await s.subscribe(Quote, [self.cfg.symbol])
                await s.subscribe(Trade, [self.cfg.symbol])
                mark = None
                mid = None
                for _ in range(6):
                    try:
                        t = await asyncio.wait_for(s.get_event(Trade), timeout=0.5)
                        if t.event_symbol == self.cfg.symbol and t.price is not None:
                            mark = float(t.price)
                    except asyncio.TimeoutError:
                        pass
                    try:
                        q = await asyncio.wait_for(s.get_event(Quote), timeout=0.5)
                        if q.event_symbol == self.cfg.symbol and q.bid_price and q.ask_price:
                            mid = float((q.bid_price + q.ask_price) / 2)
                    except asyncio.TimeoutError:
                        pass
                    if mark is not None:
                        break
                spot = mark if mark is not None else mid
                if spot is None:
                    return None
                rounded_body = round(spot / 5) * 5
                return float(rounded_body)
        except Exception:
            return None

    def build_if_options(self, options, body: float, width: int):
        calls = [o for o in options if o.option_type == "C"]
        puts  = [o for o in options if o.option_type == "P"]
        call_body = next(c for c in calls if float(c.strike_price) == body)
        put_body  = next(p for p in puts  if float(p.strike_price) == body)
        call_wing = next(c for c in calls if float(c.strike_price) == body + width)
        put_wing  = next(p for p in puts  if float(p.strike_price) == body - width)
        return call_body, call_wing, put_body, put_wing

    async def mids_for_symbols(self, syms: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Returns {symbol: {'bid','ask','mid','delta','gamma','theta','vega', flags...}}
        Mirrors greeks_gex.py approach.
        """
        out: Dict[str, Dict[str, float]] = {
            s: {'bid': None, 'ask': None, 'mid': None,
                'delta': None, 'gamma': None, 'theta': None, 'vega': None,
                'has_quote': False, 'has_greeks': False} for s in syms
        }
        try:
            async with DXLinkStreamer(self.session) as s:
                await s.subscribe(Quote, syms)
                greeks_available = True
                try:
                    await s.subscribe(Greeks, syms)
                except Exception:
                    greeks_available = False

                quotes_collected = 0
                greeks_collected = 0
                target_quotes = len(syms)
                target_greeks = len(syms) if greeks_available else 0

                timeouts = 0
                while (quotes_collected < target_quotes or greeks_collected < target_greeks) and timeouts < self.cfg.max_quote_timeouts:
                    got_event = False
                    try:
                        q = await asyncio.wait_for(s.get_event(Quote), timeout=self.cfg.quote_wait_timeout)
                        if q.event_symbol in out and not out[q.event_symbol]['has_quote']:
                            if q.bid_price is not None or q.ask_price is not None:
                                out[q.event_symbol]['bid'] = float(q.bid_price) if q.bid_price is not None else None
                                out[q.event_symbol]['ask'] = float(q.ask_price) if q.ask_price is not None else None
                                if out[q.event_symbol]['bid'] is not None and out[q.event_symbol]['ask'] is not None:
                                    mid_val = (out[q.event_symbol]['bid'] + out[q.event_symbol]['ask']) / 2
                                    out[q.event_symbol]['mid'] = float(round_to_nickel(mid_val))
                                out[q.event_symbol]['has_quote'] = True
                                quotes_collected += 1
                                got_event = True
                    except asyncio.TimeoutError:
                        pass

                    if greeks_available:
                        try:
                            g = await asyncio.wait_for(s.get_event(Greeks), timeout=0.05)
                            if g.event_symbol in out and not out[g.event_symbol]['has_greeks']:
                                out[g.event_symbol]['delta'] = float(g.delta) if g.delta is not None else None
                                out[g.event_symbol]['gamma'] = float(g.gamma) if g.gamma is not None else None
                                out[g.event_symbol]['theta'] = float(g.theta) if g.theta is not None else None
                                out[g.event_symbol]['vega']  = float(g.vega)  if g.vega  is not None else None
                                out[g.event_symbol]['has_greeks'] = True
                                greeks_collected += 1
                                got_event = True
                        except asyncio.TimeoutError:
                            pass

                    if not got_event:
                        timeouts += 1
                    else:
                        timeouts = 0
        except Exception:
            pass
        return out

    async def if_mid_credit(self, fly: IronFly) -> Optional[float]:
        syms = fly.streamer_symbols()
        data = await self.mids_for_symbols(syms)
        try:
            cs = data[fly.call_short_opt.streamer_symbol]["mid"]
            cl = data[fly.call_long_opt.streamer_symbol]["mid"]
            ps = data[fly.put_short_opt.streamer_symbol]["mid"]
            pl = data[fly.put_long_opt.streamer_symbol]["mid"]
            if None in (cs, cl, ps, pl):
                return None
            credit = (cs + ps) - (cl + pl)
            return float(round_to_nickel(credit))
        except Exception:
            return None

    # ---------- Order placement ----------
    def _build_leg_from_option(self, opt_obj, qty: int, action: OrderAction):
        return opt_obj.build_leg(Decimal(str(qty)), action)

    async def open_if(self, fly: IronFly, dry_run: Optional[bool] = None) -> bool:
        dry = self.cfg.dry_run if dry_run is None else dry_run
        credit = await self.if_mid_credit(fly)
        if credit is None:
            print(f"Could not price IF {fmt2(fly.body)}")
            return False

        legs = [
            self._build_leg_from_option(fly.call_short_opt, fly.qty, OrderAction.SELL_TO_OPEN),
            self._build_leg_from_option(fly.call_long_opt,  fly.qty, OrderAction.BUY_TO_OPEN),
            self._build_leg_from_option(fly.put_short_opt,  fly.qty, OrderAction.SELL_TO_OPEN),
            self._build_leg_from_option(fly.put_long_opt,   fly.qty, OrderAction.BUY_TO_OPEN),
        ]

        order = NewOrder(
            time_in_force=self.cfg.tif,
            order_type=OrderType.LIMIT,
            legs=legs,
            price=Decimal(str(credit))
        )
        try:
            self.account.place_order(self.session, order, dry_run=dry)
            fly.entry_credit = credit
            fly.open = True
            print(f"Opened IF {fmt2(fly.body)} for credit ${fmt2(credit)} dry={dry}")
            return True
        except Exception as e:
            print(f"Open IF {fmt2(fly.body)} failed: {e}")
            return False

    async def close_if(self, fly: IronFly, dry_run: Optional[bool] = None) -> bool:
        dry = self.cfg.dry_run if dry_run is None else dry_run
        syms = fly.streamer_symbols()
        data = await self.mids_for_symbols(syms)
        try:
            cs = data[fly.call_short_opt.streamer_symbol]["mid"]
            cl = data[fly.call_long_opt.streamer_symbol]["mid"]
            ps = data[fly.put_short_opt.streamer_symbol]["mid"]
            pl = data[fly.put_long_opt.streamer_symbol]["mid"]
            if None in (cs, cl, ps, pl):
                print(f"Could not price close for IF {fmt2(fly.body)} (missing mids)")
                return False
            debit = (cs + ps) - (cl + pl)
            debit = float(round_to_nickel(debit))
        except Exception as e:
            print(f"Could not price close for IF {fmt2(fly.body)}: {e}")
            return False

        legs = [
            self._build_leg_from_option(fly.call_short_opt, fly.qty, OrderAction.BUY_TO_CLOSE),
            self._build_leg_from_option(fly.call_long_opt,  fly.qty, OrderAction.SELL_TO_CLOSE),
            self._build_leg_from_option(fly.put_short_opt,  fly.qty, OrderAction.BUY_TO_CLOSE),
            self._build_leg_from_option(fly.put_long_opt,   fly.qty, OrderAction.SELL_TO_CLOSE),
        ]

        order = NewOrder(
            time_in_force=self.cfg.tif,
            order_type=OrderType.LIMIT,
            legs=legs,
            price=Decimal(str(debit))
        )
        try:
            self.account.place_order(self.session, order, dry_run=dry)
            fly.open = False
            print(f"Closed IF {fmt2(fly.body)} for debit ${fmt2(debit)} dry={dry}")
            return True
        except Exception as e:
            print(f"Close IF {fmt2(fly.body)} failed: {e}")
            return False

    # ---------- CSV writers ----------
    def write_quotes_csv(self, rows: List[Dict]):
        if not rows:
            return
        fieldnames = ["ts", "symbol", "bid", "ask", "mid", "delta", "gamma", "theta", "vega"]
        # format values to 2 decimals
        for r in rows:
            for k in ["bid", "ask", "mid", "delta", "gamma", "theta", "vega"]:
                if r.get(k) is not None:
                    r[k] = fmt2(float(r[k]))
        write_csv_row(self.quotes_path, fieldnames, rows[0])  # ensures header
        with open(self.quotes_path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            for r in rows:
                w.writerow(r)

    def write_pnl_if_csv(self):
        # per-IF pnl rows; also append overall strategy PnL row
        fieldnames = ["ts", "body", "pnl", "total_pnl"]
        ts = now_local().isoformat()
        self.write_pnl_strategy_row(ts, self.state.total_pnl)
        for body, pnl in sorted(self.state.per_if_pnl.items()):
            row = {
                "ts": ts,
                "body": fmt2(body),
                "pnl": fmt2(pnl),
                "total_pnl": fmt2(self.state.total_pnl),
            }
            write_csv_row(self.pnl_if_path, fieldnames, row)

    def write_pnl_strategy_row(self, ts: str, total_pnl: float):
        fieldnames = ["ts", "strategy_total_pnl"]
        row = {"ts": ts, "strategy_total_pnl": fmt2(total_pnl)}
        write_csv_row(self.pnl_strategy_path, fieldnames, row)

    # ---------- Streaming and mark-to-market ----------
    async def stream_and_mark(self):
        """
        Streams all active leg symbols, writes quotes.csv, recomputes PnL and writes pnl.csv files.
        """
        if not self.state.active_flies:
            return
        syms = sorted(set(
            s for fly in self.state.active_flies.values() if fly.open
            for s in fly.streamer_symbols()
        ))
        data = await self.mids_for_symbols(syms)

        # quotes.csv
        rows = []
        ts = now_local().isoformat()
        for s, d in data.items():
            rows.append({
                "ts": ts,
                "symbol": s,
                "bid": d.get("bid"),
                "ask": d.get("ask"),
                "mid": d.get("mid"),
                "delta": d.get("delta"),
                "gamma": d.get("gamma"),
                "theta": d.get("theta"),
                "vega": d.get("vega"),
            })
        self.write_quotes_csv(rows)

        # compute mids per IF (credit to open now)
        fly_mids: Dict[float, float] = {}
        for body, fly in self.state.active_flies.items():
            try:
                cs = data[fly.call_short_opt.streamer_symbol]["mid"]
                cl = data[fly.call_long_opt.streamer_symbol]["mid"]
                ps = data[fly.put_short_opt.streamer_symbol]["mid"]
                pl = data[fly.put_long_opt.streamer_symbol]["mid"]
                if None in (cs, cl, ps, pl):
                    continue
                mid_credit = (cs + ps) - (cl + pl)
                fly_mids[body] = float(round_to_nickel(mid_credit))
            except Exception:
                continue

        self.compute_strategy_status(fly_mids)
        self.write_pnl_if_csv()

    # ---------- Ladder construction ----------
    def construct_ladder(self, options, atm_body: float) -> List[IronFly]:
        bodies = [atm_body]
        for i in range(1, self.cfg.n_below + 1):
            bodies.append(atm_body - i * self.cfg.step)
        for i in range(1, self.cfg.n_above + 1):
            bodies.append(atm_body + i * self.cfg.step)
        bodies = sorted(bodies)

        flies: List[IronFly] = []
        for b in bodies:
            cs_opt, cl_opt, ps_opt, pl_opt = self.build_if_options(options, b, self.cfg.width)
            flies.append(IronFly(
                body=b, width=self.cfg.width, qty=1,
                call_short_opt=cs_opt, call_long_opt=cl_opt,
                put_short_opt=ps_opt,  put_long_opt=pl_opt
            ))
        return flies

    # ---------- Roll logic ----------
    async def roll_replacement(self, options, hit_body: float):
        """
        Close the losing far-side IF and open a new one on the opposite end by one more step.
        """
        if not self.state.active_flies:
            return

        active_bodies = sorted(self.state.active_flies.keys())
        lowest, highest = active_bodies[0], active_bodies[-1]

        if hit_body == lowest:
            new_body = highest + self.cfg.step
        elif hit_body == highest:
            new_body = lowest - self.cfg.step
        else:
            if abs(hit_body - lowest) < abs(hit_body - highest):
                new_body = highest + self.cfg.step
            else:
                new_body = lowest - self.cfg.step

        cs_opt, cl_opt, ps_opt, pl_opt = self.build_if_options(options, new_body, self.cfg.width)
        new_fly = IronFly(
            body=new_body, width=self.cfg.width, qty=1,
            call_short_opt=cs_opt, call_long_opt=cl_opt,
            put_short_opt=ps_opt,  put_long_opt=pl_opt
        )
        ok = await self.open_if(new_fly)
        if ok:
            self.state.active_flies[new_body] = new_fly
            print(f"Rolled in new IF at body {fmt2(new_body)}")

    # ---------- Strategy loop ----------
    async def run(self):
        # Ensure today's strategy folder exists (in case of date rollover)
        self.strategy_folder = ensure_strategy_folder(self.cfg)
        self.quotes_path = os.path.join(self.strategy_folder, self.cfg.quotes_csv)
        self.pnl_if_path = os.path.join(self.strategy_folder, self.cfg.pnl_if_csv)
        self.pnl_strategy_path = os.path.join(self.strategy_folder, self.cfg.pnl_strategy_csv)

        chain = self.get_chain()
        expiry = self.pick_0_or_1_dte(chain)
        options = chain[expiry]

        # Underlying rounded body from Mark Price (or Quote mid), rounded to nearest 5
        atm_body = await self.get_underlying_spot_mark_rounded5()
        if atm_body is None:
            # fallback to closest strike to median of available strikes
            strikes = sorted(list({float(o.strike_price) for o in options}))
            approx = strikes[len(strikes)//2]
            atm_body = nearest(strikes, approx)

        while True:
            # Refresh folder daily (handles date change)
            current_folder = ensure_strategy_folder(self.cfg)
            if current_folder != self.strategy_folder:
                self.strategy_folder = current_folder
                self.quotes_path = os.path.join(self.strategy_folder, self.cfg.quotes_csv)
                self.pnl_if_path = os.path.join(self.strategy_folder, self.cfg.pnl_if_csv)
                self.pnl_strategy_path = os.path.join(self.strategy_folder, self.cfg.pnl_strategy_csv)

            # Entry
            if self.evaluate_entry_window():
                ladder = self.construct_ladder(options, atm_body)
                for fly in ladder:
                    ok = await self.open_if(fly, dry_run=self.cfg.dry_run)
                    if ok:
                        self.state.active_flies[fly.body] = fly
                self.state.entered_today = True
                print(f"Opened {len(self.state.active_flies)} IFs at expiry {expiry}")

            # Stream quotes/greeks and mark-to-market
            await self.stream_and_mark()

            # Exit checks
            to_close, portfolio_stop = self.evaluate_exit_rules()
            if portfolio_stop and self.state.active_flies:
                print("Portfolio stop hit; closing all IFs")
                for fly in list(self.state.active_flies.values()):
                    await self.close_if(fly, dry_run=self.cfg.dry_run)
                    self.state.closed_flies[fly.body] = fly
                    self.state.active_flies.pop(fly.body, None)
            elif to_close:
                for body in to_close:
                    fly = self.state.active_flies.get(body)
                    if not fly or not fly.open:
                        continue
                    ok = await self.close_if(fly, dry_run=self.cfg.dry_run)
                    if ok:
                        self.state.closed_flies[body] = fly
                        self.state.active_flies.pop(body, None)
                        # Roll to far side
                        await self.roll_replacement(options, body)

            await asyncio.sleep(2.0)


# =========================
# Main
# =========================
async def main():
    cfg = Config(
        secrets_file="secrets.json",
        entry_hour=8,
        entry_minute=33,
        n_above=4,
        n_below=4,
        step=5,
        width=60,
        symbol="SPX",
        dry_run=True,
        per_if_stop=500.0,
        portfolio_stop=4000.0,
        data_base_dir="Data",
        strategy_name="SPX_9IF_0DTE"
    )
    strat = SPXIFStrategy(cfg)
    print("SPX IF strategy starting...")
    await strat.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
