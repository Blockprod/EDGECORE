#pragma once

#include <vector>
#include <string>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <cmath>
#include <numeric>

namespace py = pybind11;

// Simple implementation for Windows compatibility

struct CointegrationResult {
    std::string sym1;
    std::string sym2;
    double pvalue;
    double half_life;
};

class CointegrationEngine {
public:
    std::vector<CointegrationResult> findCointegrationParallel(
        const std::vector<std::string>& symbols,
        const py::array_t<double>& price_matrix,
        int max_half_life = 60,
        double min_correlation = 0.7,
        double pvalue_threshold = 0.05
    );
    
private:
    CointegrationResult testPairCointegration(
        const std::string& sym1,
        const std::string& sym2,
        const std::vector<double>& series1,
        const std::vector<double>& series2,
        int max_half_life,
        double min_correlation,
        double pvalue_threshold
    );
    
    double calculateCorrelation(const std::vector<double>& x, const std::vector<double>& y);
    std::vector<double> calculateResiduals(const std::vector<double>& y, const std::vector<double>& x);
    double calculateHalfLife(const std::vector<double>& residuals);
    double performSimpleADFTest(const std::vector<double>& series);
    void log_debug(const std::string& msg) const;
};
