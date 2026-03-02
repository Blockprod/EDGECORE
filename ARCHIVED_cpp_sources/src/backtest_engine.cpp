#include "backtest_engine.h"
#include <iostream>
#include <cmath>
#include <algorithm>
#include <numeric>

BacktestEngine::BacktestEngine(double initial_equity) 
    : equity_(initial_equity) {}

void BacktestEngine::log_debug(const std::string& msg) const {
    #ifdef DEBUG_BACKTEST
    std::cout << "[BacktestEngine] " << msg << std::endl;
    #endif
}

py::dict BacktestEngine::run(
    const std::vector<std::vector<double>>& prices,
    const std::vector<std::string>& symbols,
    py::object strategy_callback,
    py::object risk_callback,
    int lookback
) {
    if (prices.empty()) {
        throw std::runtime_error("Empty price data");
    }
    
    if (symbols.empty() || prices[0].size() != symbols.size()) {
        throw std::runtime_error("Symbol/price data mismatch");
    }
    
    log_debug("Starting backtest with " + std::to_string(prices.size()) + " days");
    
    double old_equity = equity_;
    
    // Main backtesting loop
    for (size_t day = 0; day < prices.size(); day++) {
        try {
            // Generate signals from Python strategy
            py::object signals_obj = strategy_callback(
                py::cast(prices[day]),
                day
            );
            
            // Convert signals to vector of Order structs
            std::vector<Order> signals;
            try {
                signals = signals_obj.cast<std::vector<Order>>();
            } catch (const std::exception&) {
                // If conversion fails, skip this day
                log_debug("Failed to convert signals on day " + std::to_string(day));
                signals.clear();
            }
            
            // Process each signal
            for (const auto& signal : signals) {
                try {
                    // Risk check via Python callback
                    bool can_trade = risk_callback(
                        py::cast(signal.symbol),
                        py::cast(signal.side > 0 ? signal.size : -signal.size),
                        py::cast(signal.price),
                        py::cast(equity_)
                    ).cast<bool>();
                    
                    if (can_trade) {
                        executeOrder(signal, signal.price);
                    }
                } catch (const std::exception& e) {
                    log_debug(std::string("Risk check failed: ") + e.what());
                }
            }
            
            // Update equity based on current prices
            updateEquity(prices[day], symbols, day);
            
            // Calculate daily return
            double daily_pnl = equity_ - old_equity;
            double daily_return = (old_equity > 0) ? (daily_pnl / old_equity) : 0.0;
            daily_returns_.push_back(daily_return);
            
            old_equity = equity_;
            
        } catch (const std::exception& e) {
            log_debug(std::string("Error on day ") + std::to_string(day) + ": " + e.what());
            // Continue with next day on error
        }
    }
    
    log_debug("Backtest complete. Final equity: " + std::to_string(equity_));
    
    // Build and return Python dict
    py::dict result;
    result["equity"] = equity_;
    result["daily_returns"] = daily_returns_;
    
    // Create positions dict
    py::dict positions_dict;
    for (const auto& [symbol, position] : positions_) {
        py::dict pos;
        pos["symbol"] = position.symbol;
        pos["shares"] = position.shares;
        pos["entry_price"] = position.entry_price;
        positions_dict[py::cast(symbol)] = pos;
    }
    result["positions"] = positions_dict;
    
    return result;
}

void BacktestEngine::executeOrder(const Order& order, double price) {
    if (price <= 0) {
        throw std::runtime_error("Invalid price for order execution");
    }
    
    double cost = order.size * price;
    
    if (order.side > 0) {  // BUY
        if (cost > equity_) {
            log_debug("Insufficient funds for buy order");
            return;  // Skip order if insufficient funds
        }
        positions_[order.symbol] = Position{
            order.symbol,
            order.size,
            price
        };
        equity_ -= cost;
    } else if (order.side < 0) {  // SELL
        if (positions_.find(order.symbol) == positions_.end()) {
            log_debug("Position not found for sell order");
            return;  // Skip if no position
        }
        equity_ += cost;
        positions_.erase(order.symbol);
    }
}

void BacktestEngine::updateEquity(
    const std::vector<double>& prices,
    const std::vector<std::string>& symbols,
    int price_idx
) {
    // Update unrealized P&L for all open positions
    for (auto& [sym, position] : positions_) {
        // Find symbol index in prices array
        auto it = std::find(symbols.begin(), symbols.end(), sym);
        if (it != symbols.end()) {
            size_t idx = std::distance(symbols.begin(), it);
            if (idx < prices.size()) {
                double current_price = prices[idx];
                double pnl = (current_price - position.entry_price) * position.shares;
                equity_ += pnl;
                position.entry_price = current_price;
            }
        }
    }
}

double BacktestEngine::getEquity() const {
    return equity_;
}

std::vector<double> BacktestEngine::getDailyReturns() const {
    return daily_returns_;
}

// Pybind11 module definition
PYBIND11_MODULE(backtest_engine_cpp, m) {
    m.doc() = "EDGECORE Backtest Engine (C++)";
    
    py::class_<Order>(m, "Order")
        .def(py::init<>())
        .def_readwrite("symbol", &Order::symbol)
        .def_readwrite("side", &Order::side)
        .def_readwrite("size", &Order::size)
        .def_readwrite("price", &Order::price);
    
    py::class_<Position>(m, "Position")
        .def(py::init<>())
        .def_readwrite("symbol", &Position::symbol)
        .def_readwrite("shares", &Position::shares)
        .def_readwrite("entry_price", &Position::entry_price);
    
    py::class_<BacktestEngine>(m, "BacktestEngine")
        .def(py::init<double>(),
            py::arg("initial_equity"),
            "Initialize backtest engine with initial equity")
        .def("run", &BacktestEngine::run,
            py::arg("prices"),
            py::arg("symbols"),
            py::arg("strategy_callback"),
            py::arg("risk_callback"),
            py::arg("lookback") = 20,
            "Run backtest with given data and callbacks")
        .def("get_equity", &BacktestEngine::getEquity,
            "Get current equity")
        .def("get_daily_returns", &BacktestEngine::getDailyReturns,
            "Get daily returns array");
}
