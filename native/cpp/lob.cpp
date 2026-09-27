// lob.cpp — limit order book, price-time priority (C ABI).
// Integer ticks/lots (no fp in matching path). O(log L) level lookup +
// O(1) FIFO within level. Resting price prints. Deterministic sequences.
#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <vector>

namespace {

struct Node {
    uint64_t id;
    int64_t price;
    int64_t qty;
    uint64_t seq;
};

struct Fill {
    uint64_t buy_id;
    uint64_t sell_id;
    int64_t price;
    int64_t qty;
};

struct Book {
    // bids: descending; asks: ascending
    std::map<int64_t, std::deque<Node>, std::greater<int64_t>> bids;
    std::map<int64_t, std::deque<Node>, std::less<int64_t>> asks;
    uint64_t seq = 0;
};

void sweep_buy(Book* b, Node& in, std::vector<Fill>& out) {
    while (in.qty > 0) {
        auto it = b->asks.begin();
        while (it != b->asks.end() && (it->second.empty() || it->first > in.price)) {
            if (it->second.empty()) { auto e = it++; b->asks.erase(e); }
            else ++it;
        }
        if (it == b->asks.end()) {
            b->bids[in.price].push_back(in);
            break;
        }
        Node& r = it->second.front();
        int64_t q = in.qty < r.qty ? in.qty : r.qty;
        out.push_back(Fill{in.id, r.id, r.price, q});
        in.qty -= q;
        r.qty -= q;
        if (r.qty <= 0) {
            it->second.pop_front();
            if (it->second.empty()) b->asks.erase(it);
        }
    }
}

void sweep_sell(Book* b, Node& in, std::vector<Fill>& out) {
    while (in.qty > 0) {
        auto it = b->bids.begin();
        while (it != b->bids.end() && (it->second.empty() || it->first < in.price)) {
            if (it->second.empty()) { auto e = it++; b->bids.erase(e); }
            else ++it;
        }
        if (it == b->bids.end()) {
            b->asks[in.price].push_back(in);
            break;
        }
        Node& r = it->second.front();
        int64_t q = in.qty < r.qty ? in.qty : r.qty;
        out.push_back(Fill{r.id, in.id, r.price, q});
        in.qty -= q;
        r.qty -= q;
        if (r.qty <= 0) {
            it->second.pop_front();
            if (it->second.empty()) b->bids.erase(it);
        }
    }
}

bool cancel_in(auto& levels, uint64_t id) {
    for (auto it = levels.begin(); it != levels.end();) {
        auto& dq = it->second;
        for (auto n = dq.begin(); n != dq.end(); ++n) {
            if (n->id == id) {
                dq.erase(n);
                if (dq.empty()) levels.erase(it);
                return true;
            }
        }
        ++it;
    }
    return false;
}

}  // namespace

extern "C" {

void* delta_lob_create() { return new Book(); }
void delta_lob_destroy(void* book) { delete static_cast<Book*>(book); }

// Scatter helper: writes up to cap fills to caller arrays.
void scatter(const std::vector<Fill>& v,
             uint64_t* f_buy, uint64_t* f_sell, int64_t* f_price, int64_t* f_qty,
             size_t cap, size_t& stored) {
    for (size_t i = 0; i < v.size() && stored < cap; ++i, ++stored) {
        if (f_buy) f_buy[stored] = v[i].buy_id;
        if (f_sell) f_sell[stored] = v[i].sell_id;
        if (f_price) f_price[stored] = v[i].price;
        if (f_qty) f_qty[stored] = v[i].qty;
    }
}

// side: 0=buy, 1=sell. Returns total fills (only first cap stored).
size_t delta_lob_add(void* book, uint64_t id, int side, int64_t price, int64_t qty,
                     uint64_t* f_buy, uint64_t* f_sell, int64_t* f_price, int64_t* f_qty,
                     size_t cap) {
    if (!book || price <= 0 || qty <= 0 || (side != 0 && side != 1)) return 0;
    Book* b = static_cast<Book*>(book);
    Node in{id, price, qty, ++b->seq};
    std::vector<Fill> v;
    v.reserve(8);
    if (side == 0) sweep_buy(b, in, v);
    else sweep_sell(b, in, v);
    size_t stored = 0;
    scatter(v, f_buy, f_sell, f_price, f_qty, cap, stored);
    return v.size();
}

int delta_lob_cancel(void* book, uint64_t id) {
    if (!book) return 0;
    Book* b = static_cast<Book*>(book);
    return cancel_in(b->bids, id) || cancel_in(b->asks, id) ? 1 : 0;
}

// Batch submit: amortizes FFI to one crossing per order. Returns total fills
// across the batch; only the first cap are stored. counts[k] = fills produced
// by order k (always written when counts != null). Invalid orders
// (price/qty<=0, bad side) are skipped without aborting the batch.
size_t delta_lob_add_batch(void* book, const uint64_t* ids, const int* sides,
                           const int64_t* prices, const int64_t* qtys, size_t n,
                           uint64_t* f_buy, uint64_t* f_sell, int64_t* f_price,
                           int64_t* f_qty, size_t cap, size_t* counts) {
    if (!book || !ids || !sides || !prices || !qtys) return 0;
    Book* b = static_cast<Book*>(book);
    size_t total = 0;   // all fills produced
    size_t stored = 0;  // fills written to caller arrays
    std::vector<Fill> v;
    v.reserve(8);
    for (size_t k = 0; k < n; ++k) {
        size_t produced = 0;
        if (prices[k] > 0 && qtys[k] > 0 && (sides[k] == 0 || sides[k] == 1)) {
            Node in{ids[k], prices[k], qtys[k], ++b->seq};
            v.clear();
            if (sides[k] == 0) sweep_buy(b, in, v);
            else sweep_sell(b, in, v);
            produced = v.size();
            total += produced;
            scatter(v, f_buy, f_sell, f_price, f_qty, cap, stored);
        }
        if (counts) counts[k] = produced;
    }
    return total;
}

// Replace = cancel + add with fresh sequence (price-time priority forfeited, documented).
size_t delta_lob_replace(void* book, uint64_t id, int side, int64_t price, int64_t qty,
                         uint64_t* f_buy, uint64_t* f_sell, int64_t* f_price, int64_t* f_qty,
                         size_t cap) {
    if (!book) return 0;
    delta_lob_cancel(book, id);
    return delta_lob_add(book, id, side, price, qty, f_buy, f_sell, f_price, f_qty, cap);
}

int delta_lob_top(void* book, int64_t* bid_px, int64_t* bid_q, int64_t* ask_px, int64_t* ask_q) {
    if (!book) return 0;
    Book* b = static_cast<Book*>(book);
    auto bi = b->bids.begin();
    while (bi != b->bids.end() && bi->second.empty()) { auto e = bi++; b->bids.erase(e); }
    auto ai = b->asks.begin();
    while (ai != b->asks.end() && ai->second.empty()) { auto e = ai++; b->asks.erase(e); }
    int found = 0;
    if (bi != b->bids.end()) {
        int64_t q = 0;
        for (auto& o : bi->second) q += o.qty;
        if (bid_px) *bid_px = bi->first;
        if (bid_q) *bid_q = q;
        found |= 1;
    }
    if (ai != b->asks.end()) {
        int64_t q = 0;
        for (auto& o : ai->second) q += o.qty;
        if (ask_px) *ask_px = ai->first;
        if (ask_q) *ask_q = q;
        found |= 2;
    }
    return found;
}

}  // extern "C"
