#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <vector>

struct Stats {
    double mean;
    double variance;
    double stddev;
};


Stats stable_stats(
    const std::vector<double>& values
) {

    if (values.size() < 2) {
        throw std::invalid_argument(
            "need >= 2 observations"
        );
    }

    // Welford's one-pass algorithm.
    double mean = 0.0;
    double m2 = 0.0;

    std::size_t n = 0;

    for (double value : values) {

        ++n;

        const double delta =
            value - mean;

        mean +=
            delta /
            static_cast<double>(n);

        const double delta2 =
            value - mean;

        m2 +=
            delta * delta2;
    }

    const double variance =
        m2 /
        static_cast<double>(
            n - 1
        );

    return {
        mean,
        variance,
        std::sqrt(variance)
    };
}