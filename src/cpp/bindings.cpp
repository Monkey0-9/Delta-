#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "order_book.h"
#include "matching_engine.h"

namespace py = pybind11;

PYBIND11_MODULE(delta_cpp, m) {
    m.doc() = "DELTA C++ high-performance components";
    
    // OrderSide enum
    py::enum_<delta::OrderSide>(m, "OrderSide")
        .value("BUY", delta::OrderSide::BUY)
        .value("SELL", delta::OrderSide::SELL)
        .export_values();
    
    // OrderType enum
    py::enum_<delta::OrderType>(m, "OrderType")
        .value("LIMIT", delta::OrderType::LIMIT)
        .value("MARKET", delta::OrderType::MARKET)
        .value("IOC", delta::OrderType::IOC)
        .value("FOK", delta::OrderType::FOK)
        .export_values();
    
    // OrderStatus enum
    py::enum_<delta::OrderStatus>(m, "OrderStatus")
        .value("NEW", delta::OrderStatus::NEW)
        .value("PARTIALLY_FILLED", delta::OrderStatus::PARTIALLY_FILLED)
        .value("FILLED", delta::OrderStatus::FILLED)
        .value("CANCELLED", delta::OrderStatus::CANCELLED)
        .value("REJECTED", delta::OrderStatus::REJECTED)
        .value("EXPIRED", delta::OrderStatus::EXPIRED)
        .export_values();
    
    // OrderBookLevel struct
    py::class_<delta::OrderBookLevel>(m, "OrderBookLevel")
        .def(py::init<double, double, uint32_t>())
        .def_readwrite("price", &delta::OrderBookLevel::price)
        .def_readwrite("total_quantity", &delta::OrderBookLevel::total_quantity)
        .def_readwrite("num_orders", &delta::OrderBookLevel::num_orders);
    
    // Order struct
    py::class_<delta::Order>(m, "Order")
        .def(py::init<uint64_t, delta::OrderSide, double, double, uint64_t, const std::string&>())
        .def_readwrite("order_id", &delta::Order::order_id)
        .def_readwrite("side", &delta::Order::side)
        .def_readwrite("price", &delta::Order::price)
        .def_readwrite("quantity", &delta::Order::quantity)
        .def_readwrite("timestamp_ns", &delta::Order::timestamp_ns)
        .def_readwrite("participant", &delta::Order::participant);
    
    // Fill struct
    py::class_<delta::Fill>(m, "Fill")
        .def(py::init<uint64_t, uint64_t, delta::OrderSide, double, double, uint64_t>())
        .def_readwrite("fill_id", &delta::Fill::fill_id)
        .def_readwrite("order_id", &delta::Fill::order_id)
        .def_readwrite("side", &delta::Fill::side)
        .def_readwrite("price", &delta::Fill::price)
        .def_readwrite("quantity", &delta::Fill::quantity)
        .def_readwrite("timestamp_ns", &delta::Fill::timestamp_ns)
        .def_readwrite("venue", &delta::Fill::venue)
        .def_readwrite("liquidity_indicator", &delta::Fill::liquidity_indicator)
        .def_property("notional", [](const delta::Fill& f) { return f.price * f.quantity; })
        .def_property("total_cost", [](const delta::Fill& f) { return f.price * f.quantity; });
    
    // ExecutionResult struct
    py::class_<delta::ExecutionResult>(m, "ExecutionResult")
        .def(py::init<>())
        .def_readwrite("order_id", &delta::ExecutionResult::order_id)
        .def_readwrite("status", &delta::ExecutionResult::status)
        .def_readwrite("filled_quantity", &delta::ExecutionResult::filled_quantity)
        .def_readwrite("average_price", &delta::ExecutionResult::average_price)
        .def_readwrite("fills", &delta::ExecutionResult::fills)
        .def_readwrite("remaining_quantity", &delta::ExecutionResult::remaining_quantity)
        .def_readwrite("timestamp_ns", &delta::ExecutionResult::timestamp_ns);
    
    // OrderBook class
    py::class_<delta::OrderBook, std::shared_ptr<delta::OrderBook>>(m, "OrderBook")
        .def(py::init<const std::string&>())
        .def("add_limit_order", &delta::OrderBook::add_limit_order)
        .def("cancel_order", &delta::OrderBook::cancel_order)
        .def("get_best_bid", &delta::OrderBook::get_best_bid, py::return_value_policy::reference)
        .def("get_best_ask", &delta::OrderBook::get_best_ask, py::return_value_policy::reference)
        .def("get_bids", &delta::OrderBook::get_bids)
        .def("get_asks", &delta::OrderBook::get_asks)
        .def("get_spread", &delta::OrderBook::get_spread)
        .def("get_mid_price", &delta::OrderBook::get_mid_price)
        .def("get_sequence_number", &delta::OrderBook::get_sequence_number)
        .def("get_symbol", &delta::OrderBook::get_symbol)
        .def("lock", &delta::OrderBook::lock)
        .def("unlock", &delta::OrderBook::unlock);
    
    // MatchingEngine class
    py::class_<delta::MatchingEngine>(m, "MatchingEngine")
        .def(py::init<std::shared_ptr<delta::OrderBook>>())
        .def("submit_limit_order", &delta::MatchingEngine::submit_limit_order)
        .def("submit_market_order", &delta::MatchingEngine::submit_market_order)
        .def("cancel_order", &delta::MatchingEngine::cancel_order)
        .def("get_fill_count", &delta::MatchingEngine::get_fill_count)
        .def("set_fill_callback", &delta::MatchingEngine::set_fill_callback);
}