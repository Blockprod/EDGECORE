#include "cointegration_engine.h"
#include <omp.h>
#include <cmath>
#include <iostream>
#include <algorithm>
#include <numeric>

void CointegrationEngine::log_debug(const std::string& msg) const {
    #ifdef DEBUG_COINTEGRATION
    std::cout << "[CointegrationEngine] " << msg << std::endl;
    #endif
}

std::vector<CointegrationResult> CointegrationEngine::findCointegrationParallel(
    const std::vector<std::string>& symbols,
    const py::array_t<double>& price_matrix,
    int max_half_life,
    double min_correlation,
    double pvalue_threshold
) {
    auto buf = price_matrix.request();
    double* ptr = static_cast<double*>(buf.ptr);
    
    if (buf.ndim != 2) {
        throw std::runtime_error("price_matrix must be 2D");
    }
    
    size_t rows = buf.shape[0];
    size_t cols = buf.shape[1];
    
    if (cols == 0 || cols != symbols.size()) {
        throw std::runtime_error("Symbol/price column mismatch");
    }
    
    std::vector<std::pair<size_t, size_t>> pairs_to_test;
    
    // Generate all pairs
    for (size_t i = 0; i < symbols.size(); i++) {
        for (size_t j = i + 1; j < symbols.size(); j++) {
            pairs_to_test.push_back({i, j});
        }
    }
    
    std::vector<CointegrationResult> results;
    size_t num_pairs = pairs_to_test.size();
    std::vector<CointegrationResult> thread_results(num_pairs);
    
    log_debug("Testing " + std::to_string(num_pairs) + " pairs");
    
    // Parallel testing with OpenMP
    #pragma omp parallel for schedule(dynamic) collapse(1) if(num_pairs > 100)
    for (size_t p = 0; p < num_pairs; p++) {
        size_t i = pairs_to_test[p].first;
        size_t j = pairs_to_test[p].second;
        
        // Extract series (direct memory access)
        std::vector<double> series1(rows), series2(rows);
        for (size_t r = 0; r < rows; r++) {
            series1[r] = ptr[r * cols + i];
            series2[r] = ptr[r * cols + j];
        }
        
        // Test cointegration
        thread_results[p] = testPairCointegration(
            symbols[i],
            symbols[j],
            series1,
            series2,
            max_half_life,
            min_correlation,
            pvalue_threshold
        );
    }
    
    // Collect non-empty results
    for (const auto& res : thread_results) {
        if (!res.sym1.empty()) {
            results.push_back(res);
        }
    }
    
    log_debug("Found " + std::to_string(results.size()) + " cointegrated pairs");
    
    return results;
}

CointegrationResult CointegrationEngine::testPairCointegration(
    const std::string& sym1,
    const std::string& sym2,
    const std::vector<double>& series1,
    const std::vector<double>& series2,
    int max_half_life,
    double min_correlation,
    double pvalue_threshold
) {
    // Correlation check (fast filter)
    double corr = calculateCorrelation(series1, series2);
    if (std::isnan(corr) || std::abs(corr) < min_correlation) {
        return {"", "", 0.0, 0.0};  // No cointegration
    }
    
    // Calculate residuals via OLS
    std::vector<double> residuals = calculateResiduals(series1, series2);
    
    // ADF test
    double adf_pvalue = performSimpleADFTest(residuals);
    
    // Check cointegration significance
    if (adf_pvalue > pvalue_threshold) {
        return {"", "", 0.0, 0.0};  // Not cointegrated
    }
    
    // Calculate half-life
    double half_life = calculateHalfLife(residuals);
    
    if (half_life < 0 || half_life > max_half_life) {
        return {"", "", 0.0, 0.0};
    }
    
    return {sym1, sym2, adf_pvalue, half_life};
}

double CointegrationEngine::calculateCorrelation(const std::vector<double>& x, const std::vector<double>& y) {
    if (x.size() == 0 || y.size() == 0) {
        return 0.0;
    }
    
    double mean_x = std::accumulate(x.begin(), x.end(), 0.0) / x.size();
    double mean_y = std::accumulate(y.begin(), y.end(), 0.0) / y.size();
    
    double numerator = 0.0, denom_x = 0.0, denom_y = 0.0;
    
    for (size_t i = 0; i < x.size(); i++) {
        double dx = x[i] - mean_x;
        double dy = y[i] - mean_y;
        numerator += dx * dy;
        denom_x += dx * dx;
        denom_y += dy * dy;
    }
    
    if (denom_x == 0 || denom_y == 0) {
        return 0.0;
    }
    
    return numerator / std::sqrt(denom_x * denom_y);
}

std::vector<double> CointegrationEngine::calculateResiduals(const std::vector<double>& y, const std::vector<double>& x) {
    // Simple OLS: y = beta_0 + beta_1 * x + residual
    
    int n = y.size();
    if (n < 2) {
        return std::vector<double>(n, 0.0);
    }
    
    double mean_x = std::accumulate(x.begin(), x.end(), 0.0) / n;
    double mean_y = std::accumulate(y.begin(), y.end(), 0.0) / n;
    
    double beta_1 = 0.0, ss_x = 0.0;
    for (int i = 0; i < n; i++) {
        double dx = x[i] - mean_x;
        beta_1 += (y[i] - mean_y) * dx;
        ss_x += dx * dx;
    }
    
    if (ss_x == 0) {
        return std::vector<double>(n, 0.0);
    }
    
    beta_1 /= ss_x;
    double beta_0 = mean_y - beta_1 * mean_x;
    
    // Calculate residuals
    std::vector<double> residuals(n);
    for (int i = 0; i < n; i++) {
        residuals[i] = y[i] - (beta_0 + beta_1 * x[i]);
    }
    
    return residuals;
}

double CointegrationEngine::calculateHalfLife(const std::vector<double>& residuals) {
    // AR(1) model: residuals_t = rho * residuals_{t-1} + eps
    
    int n = residuals.size();
    if (n < 2) return -1.0;
    
    // Calculate rho via OLS
    double numerator = 0.0, denominator = 0.0;
    
    for (int i = 1; i < n; i++) {
        numerator += residuals[i] * residuals[i - 1];
        denominator += residuals[i - 1] * residuals[i - 1];
    }
    
    if (denominator == 0 || std::isnan(denominator)) return -1.0;
    
    double rho = numerator / denominator;
    
    // Validate rho
    if (rho <= 0.0 || rho >= 1.0) return -1.0;
    if (std::isnan(rho) || std::isinf(rho)) return -1.0;
    
    // Half-life = -ln(2) / ln(rho)
    double log_rho = std::log(rho);
    if (log_rho >= 0 || std::isnan(log_rho) || std::isinf(log_rho)) {
        return -1.0;
    }
    
    double half_life = -std::log(2.0) / log_rho;
    
    if (std::isnan(half_life) || std::isinf(half_life) || half_life < 0) {
        return -1.0;
    }
    
    return half_life;
}

double CointegrationEngine::performSimpleADFTest(const std::vector<double>& series) {
    // Simplified ADF test based on autocorrelation
    
    if (series.size() < 2) return 1.0;
    
    double mean = std::accumulate(series.begin(), series.end(), 0.0) / series.size();
    double var_sum = 0.0;
    for (double val : series) {
        var_sum += (val - mean) * (val - mean);
    }
    double var = var_sum / series.size();
    
    if (var < 1e-10) {
        return 1.0;  // Constant series, not stationary
    }
    
    // Autocorrelation at lag 1
    double auto_cov = 0.0;
    for (size_t i = 1; i < series.size(); i++) {
        auto_cov += (series[i] - mean) * (series[i-1] - mean);
    }
    auto_cov /= series.size();
    
    double auto_corr = auto_cov / var;
    
    // Heuristic: if |autocorr| is high, likely mean-reverting
    if (auto_corr < 0.7) {
        return 0.01;  // Likely stationary (p-value ~ 0.01)
    } else {
        return 0.5;   // Likely non-stationary
    }
}

// Pybind11 module definition
PYBIND11_MODULE(cointegration_cpp, m) {
    m.doc() = "EDGECORE Cointegration Engine (C++)";
    
    py::class_<CointegrationResult>(m, "CointegrationResult")
        .def(py::init<>())
        .def_readwrite("sym1", &CointegrationResult::sym1)
        .def_readwrite("sym2", &CointegrationResult::sym2)
        .def_readwrite("pvalue", &CointegrationResult::pvalue)
        .def_readwrite("half_life", &CointegrationResult::half_life);
    
    py::class_<CointegrationEngine>(m, "CointegrationEngine")
        .def(py::init<>())
        .def("find_cointegration_parallel",
            &CointegrationEngine::findCointegrationParallel,
            py::arg("symbols"),
            py::arg("price_matrix"),
            py::arg("max_half_life") = 60,
            py::arg("min_correlation") = 0.7,
            py::arg("pvalue_threshold") = 0.05,
            "Find cointegrated pairs with OpenMP parallelization");
}
