#!/usr/bin/env python
"""
simulator_bp.py

This blueprint integrates the dynamic hedging/gamma scalping simulation engine
with a web dashboard. Users can input simulation parameters (collateral, position size,
entry price, liquidation price, rebalance threshold, hedging cost, simulation duration,
time step, drift, volatility, position side, etc.) via interactive controls and view live‑updated
charts comparing simulated results with historical data pulled from the database via DataLocker.
"""

from flask import Blueprint, render_template, request, current_app, url_for, jsonify
import logging
from datetime import datetime, timedelta
from simulator.simulation import PositionSimulator
from data.data_locker import DataLocker

simulator_bp = Blueprint('simulator', __name__, template_folder='templates')
logger = logging.getLogger("SimulatorBP")

def generate_simulated_position(sim_results):
    """
    Generates a simulated position summary from the simulation log.
    This summary uses the final step to compute a dollar value ("size") of the holding.
    """
    if sim_results.get("simulation_log"):
        final_step = sim_results["simulation_log"][-1]
        # Compute the dollar value of the holding.
        # Here, position_size is assumed to be the number of units,
        # so value = price * units.
        value = final_step.get("price", 0.0) * sim_results.get("position_size", 1.0)
        # Leverage is computed as value divided by collateral.
        leverage = value / sim_results.get("collateral", 1000.0)
        simulated_position = {
            "asset_type": "BTC",  # Adjust as needed or derive from input.
            "position_type": "Long" if sim_results["position_side"] == "long" else "Short",
            "pnl_after_fees_usd": final_step.get("cumulative_profit", 0.0),
            "collateral": sim_results.get("collateral", 1000.0),
            "value": value,
            "size": value,  # Now 'size' represents the dollar value of the holding.
            "leverage": leverage,
            "current_travel_percent": final_step.get("travel_percent", 0.0),
            "heat_index": 0.0,  # Insert logic to compute heat index if needed.
            "liquidation_distance": sim_results.get("liquidation_price", 8000.0),
            "wallet_image": "default_wallet.png"
        }
        return simulated_position
    return {}


@simulator_bp.route('/simulation', methods=['GET', 'POST'])
def simulator_dashboard():
    """
    Interactive simulation endpoint.
    On GET: Renders simulator_dashboard.html (if needed for testing).
    On POST: Expects JSON simulation parameters, runs the simulation, and returns results as JSON.
    """
    if request.method == "POST":
        try:
            data = request.get_json() or {}
            entry_price = float(data.get("entry_price", 10000))
            liquidation_price = float(data.get("liquidation_price", 8000))
            position_size = float(data.get("position_size", 1.0))
            collateral = float(data.get("collateral", 1000.0))
            rebalance_threshold = float(data.get("rebalance_threshold", -25))
            hedging_cost_pct = float(data.get("hedging_cost_pct", 0.001))
            simulation_duration = float(data.get("simulation_duration", 60))
            dt_minutes = float(data.get("dt_minutes", 1))
            drift = float(data.get("drift", 0.05))
            volatility = float(data.get("volatility", 0.8))
            position_side = data.get("position_side", "long").lower()
        except Exception as e:
            logger.error("Error parsing simulation parameters: %s", e)
            return jsonify(error=str(e)), 400

        simulator = PositionSimulator(
            entry_price=entry_price,
            liquidation_price=liquidation_price,
            position_size=position_size,
            collateral=collateral,
            rebalance_threshold=rebalance_threshold,
            hedging_cost_pct=hedging_cost_pct,
            position_side=position_side
        )
        results = simulator.run_simulation(
            simulation_duration=simulation_duration,
            dt_minutes=dt_minutes,
            drift=drift,
            volatility=volatility
        )
        # Compute leverage as (effective_entry_price * position_size) / collateral.
        leverage = (simulator.effective_entry_price * position_size) / collateral

        # Prepare chart data from the simulation log.
        chart_data = []
        for log_entry in results["simulation_log"]:
            chart_data.append({
                "step": log_entry["step"],
                "cumulative_profit": log_entry["cumulative_profit"],
                "travel_percent": log_entry["travel_percent"],
                "price": log_entry["price"],
                "unrealized_pnl": log_entry["unrealized_pnl"]
            })

        response_data = {
            "params": {
                "entry_price": entry_price,
                "liquidation_price": liquidation_price,
                "position_size": position_size,
                "collateral": collateral,
                "rebalance_threshold": rebalance_threshold,
                "hedging_cost_pct": hedging_cost_pct,
                "simulation_duration": simulation_duration,
                "dt_minutes": dt_minutes,
                "drift": drift,
                "volatility": volatility,
                "position_side": position_side
            },
            "results": results,
            "chart_data": chart_data,
            "leverage": leverage
        }
        return jsonify(response_data)
    else:
        # For GET, render a basic dashboard page (could be used for testing).
        params = {
            "entry_price": 10000,
            "liquidation_price": 8000,
            "position_size": 1.0,
            "collateral": 1000.0,
            "rebalance_threshold": -25.0,
            "hedging_cost_pct": 0.001,
            "simulation_duration": 60,
            "dt_minutes": 1,
            "drift": 0.05,
            "volatility": 0.8,
            "position_side": "long"
        }
        return render_template("simulator_dashboard.html", params=params)

@simulator_bp.route('/load_current_positions', methods=['GET'])
def load_current_positions():
    try:
        dl = DataLocker.get_instance()
        positions = dl.get_positions()
        return jsonify({"positions": positions})
    except Exception as e:
        logger.error("Error loading current positions: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

@simulator_bp.route('/compare', methods=['GET', 'POST'])
def compare_simulation():
    """
    Merged comparison endpoint that displays interactive simulation controls along with
    historical data from the database. It runs both a baseline and a tweaked simulation,
    then connects to DataLocker to retrieve historical positions and portfolio snapshots.
    The final data is passed to compare.html for a side-by-side comparison.
    """
    # Default baseline simulation parameters.
    baseline_params = {
        "entry_price": 10000.0,
        "liquidation_price": 8000.0,
        "position_size": 1.0,
        "collateral": 1000.0,
        "rebalance_threshold": -25.0,
        "hedging_cost_pct": 0.001,
        "simulation_duration": 60,  # minutes
        "dt_minutes": 1,
        "drift": 0.05,
        "volatility": 0.8,
        "position_side": "long"
    }

    # Override defaults with POSTed form data, if available.
    if request.method == "POST":
        try:
            baseline_params["entry_price"] = float(request.form.get("entry_price", baseline_params["entry_price"]))
            baseline_params["liquidation_price"] = float(request.form.get("liquidation_price", baseline_params["liquidation_price"]))
            baseline_params["position_size"] = float(request.form.get("position_size", baseline_params["position_size"]))
            baseline_params["collateral"] = float(request.form.get("collateral", baseline_params["collateral"]))
            baseline_params["rebalance_threshold"] = float(request.form.get("rebalance_threshold", baseline_params["rebalance_threshold"]))
            baseline_params["hedging_cost_pct"] = float(request.form.get("hedging_cost_pct", baseline_params["hedging_cost_pct"]))
            baseline_params["simulation_duration"] = float(request.form.get("simulation_duration", baseline_params["simulation_duration"]))
            baseline_params["dt_minutes"] = float(request.form.get("dt_minutes", baseline_params["dt_minutes"]))
            baseline_params["drift"] = float(request.form.get("drift", baseline_params["drift"]))
            baseline_params["volatility"] = float(request.form.get("volatility", baseline_params["volatility"]))
            baseline_params["position_side"] = request.form.get("position_side", baseline_params["position_side"]).lower()
        except Exception as e:
            logger.error("Error parsing simulation parameters: %s", e)

    # Create tweaked parameters (e.g., increase collateral by 10%).
    tweaked_params = baseline_params.copy()
    tweaked_params["collateral"] = baseline_params["collateral"] * 1.10

    # Run baseline simulation.
    baseline_simulator = PositionSimulator(
        entry_price=baseline_params["entry_price"],
        liquidation_price=baseline_params["liquidation_price"],
        position_size=baseline_params["position_size"],
        collateral=baseline_params["collateral"],
        rebalance_threshold=baseline_params["rebalance_threshold"],
        hedging_cost_pct=baseline_params["hedging_cost_pct"],
        position_side=baseline_params["position_side"]
    )
    baseline_results = baseline_simulator.run_simulation(
        simulation_duration=baseline_params["simulation_duration"],
        dt_minutes=baseline_params["dt_minutes"],
        drift=baseline_params["drift"],
        volatility=baseline_params["volatility"]
    )

    # Run tweaked simulation.
    tweaked_simulator = PositionSimulator(
        entry_price=tweaked_params["entry_price"],
        liquidation_price=tweaked_params["liquidation_price"],
        position_size=tweaked_params["position_size"],
        collateral=tweaked_params["collateral"],
        rebalance_threshold=tweaked_params["rebalance_threshold"],
        hedging_cost_pct=tweaked_params["hedging_cost_pct"],
        position_side=tweaked_params["position_side"]
    )
    tweaked_results = tweaked_simulator.run_simulation(
        simulation_duration=tweaked_params["simulation_duration"],
        dt_minutes=tweaked_params["dt_minutes"],
        drift=tweaked_params["drift"],
        volatility=tweaked_params["volatility"]
    )

    # Prepare simulation chart data (using step vs cumulative_profit).
    baseline_chart = [[entry["step"], entry["cumulative_profit"]] for entry in baseline_results["simulation_log"]]
    tweaked_chart = [[entry["step"], entry["cumulative_profit"]] for entry in tweaked_results["simulation_log"]]
    chart_data = {
        "simulated": baseline_chart,
        "real": tweaked_chart  # Placeholder; will be overridden if historical data is available.
    }

    # Connect to the database to retrieve historical positions and portfolio snapshots.
    data_locker = DataLocker.get_instance()
    historical_positions = data_locker.get_positions()

    portfolio_history = data_locker.get_portfolio_history()
    historical_chart = []
    for entry in portfolio_history:
        try:
            dt_obj = datetime.fromisoformat(entry["snapshot_time"])
            timestamp = int(dt_obj.timestamp() * 1000)
            historical_chart.append([timestamp, entry.get("total_value", 0.0)])
        except Exception as e:
            logger.error("Error processing portfolio snapshot: %s", e)
    if historical_chart:
        chart_data["real"] = historical_chart

    # Generate simulated position summary from baseline simulation.
    simulated_position = generate_simulated_position(baseline_results)
    simulated_positions = [simulated_position]

    return render_template(
        "compare.html",
        chart_data=chart_data,
        baseline_compare=baseline_chart,
        tweaked_compare=tweaked_chart,
        simulated_positions=simulated_positions,
        real_positions=historical_positions,
        timeframe=24,  # Example timeframe; adjust as needed.
        now=datetime.now()
    )
