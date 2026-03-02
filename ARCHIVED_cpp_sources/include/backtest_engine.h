#pragma once

#include <vector>
#include <string>
#include <unordered_map>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

// Simple implementation without Eigen for Windows compatibility

struct Order {
    std::string symbol;
    int side;  // 1 = BUY, -1 = SELL
    double size;
    double price;
};

struct Position {
    std::string symbol;
    double shares;
    double entry_price;
};

class BacktestEngine {
private:
    double equity_;
    std::vector<double> daily_returns_;
    std::unordered_map<std::string, Position> positions_;
    
public:
    BacktestEngine(double initial_equity);
    
    py::dict run(
        const std::vector<std::vector<double>>& prices,
        const std::vector<std::string>& symbols,
        py::object strategy_callback,
        py::object risk_callback,
        int lookback = 20
    );
    
    double getEquity() const;
    std::vector<double> getDailyReturns() const;
    
private:
    void executeOrder(const Order& order, double price);
    void updateEquity(const std::vector<double>& prices, 
                      const std::vector<std::string>& symbols,
                      int price_idx);
    void log_debug(const std::string& msg) const;
};
