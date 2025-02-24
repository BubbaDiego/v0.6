#!/usr/bin/env python
"""
simulator.py

A simulation engine for dynamic hedging/gamma scalping of a single trading position.
It simulates a price path using geometric Brownian motion and applies discrete rebalancing
rules. When the simulated "travel percent" (the percentage change from the effective entry price,
normalized by the range from entry to liquidation) falls below a threshold, a hedging trade is
executed—resetting the effective entry price and incurring a cost.

This version uses minute-based time steps.
"""

import numpy as np
import math
import datetime
import logging
import csv
from utils.calc_services import CalcServices  # Import our helper

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PositionSimulator")

MINUTES_IN_YEAR = 525600  # For a 24/7 market

class PositionSimulator:
    def __init__(self,
                 entry_price: float,
                 liquidation_price: float,
                 position_size: float = 1.0,
                 collateral: float = 1000.0,
                 rebalance_threshold: float = -25.0,  # threshold in percent
                 hedging_cost_pct: float = 0.001,      # hedging cost as a fraction (0.1%)
                 position_side: str = "long"           # "long" or "short"
                 ):
        """
        Initialize the simulator.

        :param entry_price: The price at which the position is entered.
        :param liquidation_price: The price at which the position would be liquidated.
        :param position_size: The size of the position.
        :param collateral: The collateral amount used to compute leverage.
        :param rebalance_threshold: The threshold (in percent) at which to trigger a hedge.
        :param hedging_cost_pct: The cost (as a fraction) incurred on each hedge.
        :param position_side: "long" or "short" indicating the position side.
        """
        self.entry_price = entry_price
        self.liquidation_price = liquidation_price
        self.position_size = position_size
        self.collateral = collateral
        self.rebalance_threshold = rebalance_threshold
        self.hedging_cost_pct = hedging_cost_pct
        self.position_side = position_side.lower()
        self.original_entry_price = entry_price  # For static travel percent calculation

        self.effective_entry_price = entry_price  # This resets with each hedge.
        self.cumulative_profit = 0.0
        self.total_hedging_cost = 0.0
        self.rebalance_count = 0
        self.simulation_log = []

    def generate_simulated_position(sim_results):
        # Use the final simulation log entry as a summary of the simulated position.
        if sim_results.get("simulation_log"):
            final_step = sim_results["simulation_log"][-1]
            simulated_position = {
                "asset_type": "BTC",  # You can adjust this based on your input
                "position_type": "Long" if sim_results["position_side"] == "long" else "Short",
                "pnl_after_fees_usd": final_step.get("cumulative_profit", 0.0),
                "collateral": sim_results.get("collateral", 1000.0),
                "value": final_step.get("price", 0.0) * sim_results.get("position_size", 1.0),
                "size": sim_results.get("position_size", 1.0),
                "leverage": (final_step.get("price", 0.0) * sim_results.get("position_size", 1.0)) / sim_results.get(
                    "collateral", 1000.0),
                "current_travel_percent": final_step.get("travel_percent", 0.0),
                "heat_index": 0.0,  # Insert computation if needed
                "liquidation_distance": sim_results.get("liquidation_price", 8000),
                "wallet_image": "default_wallet.png"
            }
            return simulated_position
        return {}

    def _simulate_price_path(self, current_price: float, drift: float, volatility: float, dt: float) -> float:
        """
        Generate the next price using geometric Brownian motion.
        """
        epsilon = np.random.normal()
        factor = (drift - 0.5 * volatility ** 2) * dt + volatility * np.sqrt(dt) * epsilon
        return current_price * math.exp(factor)

    def _calculate_travel_percent(self, current_price: float) -> float:
        """
        Calculate dynamic travel percent relative to the effective entry price.
        """
        if self.position_side == "long":
            denominator = self.effective_entry_price - self.liquidation_price
            if denominator == 0:
                return 0.0
            return ((current_price - self.effective_entry_price) / denominator) * 100
        else:
            denominator = self.liquidation_price - self.effective_entry_price
            if denominator == 0:
                return 0.0
            return ((self.effective_entry_price - current_price) / denominator) * 100

    def _execute_rebalance(self, current_price: float):
        """
        Simulate a hedge by resetting the effective entry price and logging profit/loss.
        """
        if self.position_side == "long":
            trade_profit = (current_price - self.effective_entry_price) * self.position_size
        else:
            trade_profit = (self.effective_entry_price - current_price) * self.position_size
        hedging_cost = abs(current_price * self.position_size) * self.hedging_cost_pct
        net_profit = trade_profit - hedging_cost
        logger.debug(
            f"Rebalancing at {current_price:.2f}: profit {trade_profit:.2f}, cost {hedging_cost:.2f}, net {net_profit:.2f}")
        self.cumulative_profit += net_profit
        self.total_hedging_cost += hedging_cost
        self.rebalance_count += 1
        self.effective_entry_price = current_price
        return {
            "trade_profit": trade_profit,
            "hedging_cost": hedging_cost,
            "net_profit": net_profit
        }

    def run_simulation(self,
                       simulation_duration: float = 60,  # in minutes
                       dt_minutes: float = 1,            # time step in minutes
                       drift: float = 0.05,
                       volatility: float = 0.8):
        """
        Run the simulation over a specified duration.
        """
        dt = dt_minutes / MINUTES_IN_YEAR  # Convert minutes to fraction of a year
        num_steps = int(simulation_duration / dt_minutes)
        current_price = self.entry_price
        calc = CalcServices()  # to compute static travel percent
        logger.info(f"Running simulation for {num_steps} steps over {simulation_duration} minutes")

        for step in range(num_steps):
            sim_time = datetime.datetime.now() + datetime.timedelta(minutes=step * dt_minutes)
            next_price = self._simulate_price_path(current_price, drift, volatility, dt)
            dynamic_travel_pct = self._calculate_travel_percent(next_price)
            # Compute static travel percent using the original entry price
            static_travel_pct = calc.calculate_travel_percent_no_profit(self.position_side.upper(),
                                                                        self.original_entry_price,
                                                                        next_price,
                                                                        self.liquidation_price)
            action = "NONE"
            hedge_details = None
            if dynamic_travel_pct <= self.rebalance_threshold:
                action = "REBALANCE"
                hedge_details = self._execute_rebalance(next_price)
            if self.position_side == "long":
                unrealized_pnl = (next_price - self.effective_entry_price) * self.position_size
            else:
                unrealized_pnl = (self.effective_entry_price - next_price) * self.position_size
            step_log = {
                "step": step + 1,
                "timestamp": sim_time.isoformat(),
                "price": next_price,
                "travel_percent": dynamic_travel_pct,
                "static_travel_percent": static_travel_pct,
                "action": action,
                "unrealized_pnl": unrealized_pnl,
                "cumulative_profit": self.cumulative_profit
            }
            if hedge_details:
                step_log.update(hedge_details)
            self.simulation_log.append(step_log)
            logger.debug(
                f"Step {step + 1}: Price={next_price:.2f}, Dynamic Travel%={dynamic_travel_pct:.2f}, Static Travel%={static_travel_pct:.2f}, Action={action}, Unrealized PnL={unrealized_pnl:.2f}, Cumulative Profit={self.cumulative_profit:.2f}")
            current_price = next_price

        if self.position_side == "long":
            final_unrealized = (current_price - self.effective_entry_price) * self.position_size
        else:
            final_unrealized = (self.effective_entry_price - current_price) * self.position_size
        total_profit = self.cumulative_profit + final_unrealized
        computed_leverage = (self.position_size * current_price) / self.collateral if self.collateral != 0 else None
        logger.info(
            f"Simulation complete: Final Price {current_price:.2f}, Rebalances {self.rebalance_count}, Total Profit {total_profit:.2f}")
        return {
            "simulation_log": self.simulation_log,
            "final_price": current_price,
            "final_unrealized_pnl": final_unrealized,
            "cumulative_profit": self.cumulative_profit,
            "total_profit": total_profit,
            "rebalance_count": self.rebalance_count,
            "total_hedging_cost": self.total_hedging_cost,
            "leverage": computed_leverage,
            "collateral": self.collateral,
            "position_size": self.position_size,
            "position_side": self.position_side
        }

    def export_log_to_csv(self, filename: str):
        if not self.simulation_log:
            logger.warning("No simulation log data to export.")
            return
        keys = self.simulation_log[0].keys()
        with open(filename, 'w', newline='') as csvfile:
            dict_writer = csv.DictWriter(csvfile, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(self.simulation_log)
        logger.info(f"Simulation log exported to {filename}")


if __name__ == "__main__":
    # Example usage with side parameter.
    simulator = PositionSimulator(entry_price=10000,
                                  liquidation_price=8000,
                                  position_size=1.0,
                                  collateral=1000.0,
                                  rebalance_threshold=-25.0,
                                  hedging_cost_pct=0.001,
                                  position_side="long")  # Change to "short" to simulate a short position.
    results = simulator.run_simulation(simulation_duration=60, dt_minutes=1, drift=0.05, volatility=0.8)
    simulator.export_log_to_csv("simulation_log.csv")
    print("Simulation Summary:")
    print(f"Final Price: {results['final_price']:.2f}")
    print(f"Rebalances Executed: {results['rebalance_count']}")
    print(f"Cumulative Profit from Rebalances: {results['cumulative_profit']:.2f}")
    print(f"Final Total Profit (including current unrealized PnL): {results['total_profit']:.2f}")
    print(f"Leverage: {results['leverage']:.2f}")
    print(f"Collateral: {results['collateral']:.2f}")
    print(f"Position Size: {results['position_size']:.2f}")
    print(f"Position Side: {results['position_side']}")
