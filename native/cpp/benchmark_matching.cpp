#include <chrono>
#include <cstddef>
#include <iostream>
#include <vector>

struct Order {
    double price;
    double quantity;
};


double match_volume(
    const std::vector<Order>& orders,
    double requested
) {

    double filled = 0.0;

    for (const auto& order : orders) {

        if (filled >= requested) {
            break;
        }

        const double remaining =
            requested - filled;

        filled +=
            order.quantity < remaining
            ? order.quantity
            : remaining;
    }

    return filled;
}


int main() {

    constexpr std::size_t N =
        1'000'000;

    std::vector<Order> orders;

    orders.reserve(N);

    for (std::size_t i = 0; i < N; ++i) {

        orders.push_back(
            {
                100.0,
                1.0
            }
        );
    }

    const auto start =
        std::chrono::steady_clock::now();

    volatile double result =
        match_volume(
            orders,
            500'000.0
        );

    const auto end =
        std::chrono::steady_clock::now();

    const auto ns =
        std::chrono::duration_cast<
            std::chrono::nanoseconds
        >(end - start).count();

    std::cout
        << "result="
        << result
        << "\n";

    std::cout
        << "nanoseconds="
        << ns
        << "\n";
}