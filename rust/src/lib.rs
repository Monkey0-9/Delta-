pub mod backpressure;
pub mod connector;
pub mod durable;
pub mod fast;
/// DELTA native kernels (Rust+C++ parity).
///
/// Python boundary: PyO3/maturin `delta_native`.
/// C++ boundary: `rust/cpp/*` via C ABI with identical semantics.
///
/// Parity policy:
/// same workload, rel 1e-9 / abs 1e-12;
/// benchmark metadata + commit hash recorded in `benchmark/` results.
pub mod gateway;
pub mod rate_limiter;
pub mod reconnect;

pub fn checksum_u64(values: &[u64]) -> u64 {
    values
        .iter()
        .fold(0u64, |acc, value| acc.wrapping_add(*value))
}

/// Normalize quotes: drop duplicates (exact repeats).
/// Returns number of values written to `out`.
pub fn normalize_dedup(values: &[i64], out: &mut [i64]) -> usize {
    let mut n = 0usize;
    let mut prev: Option<i64> = None;

    for &v in values {
        if prev == Some(v) {
            continue;
        }

        if n < out.len() {
            out[n] = v;
            n += 1;
        }

        prev = Some(v);
    }

    n
}

/// Feature kernel:
/// out[i] = (p[i+1] - p[i]) / |p[i]|.
///
/// Returns number of values written.
pub fn feature_returns(prices: &[f64], out: &mut [f64]) -> usize {
    if prices.len() < 2 || out.is_empty() {
        return 0;
    }

    let n = (prices.len() - 1).min(out.len());

    for i in 0..n {
        let base = prices[i].abs();

        out[i] = if base == 0.0 {
            0.0
        } else {
            (prices[i + 1] - prices[i]) / base
        };
    }

    n
}

/// Counts out-of-order timestamp pairs.
pub fn replay_inversions(timestamps: &[u64]) -> u64 {
    let mut inv = 0u64;

    for i in 0..timestamps.len() {
        for j in (i + 1)..timestamps.len() {
            if timestamps[i] > timestamps[j] {
                inv += 1;
            }
        }
    }

    inv
}

/// Gross exposure using u64 wrapping arithmetic.
pub fn risk_gross_exposure(quantities: &[u64], prices: &[u64]) -> u64 {
    quantities
        .iter()
        .zip(prices.iter())
        .fold(0u64, |acc, (&q, &p)| acc.wrapping_add(q.wrapping_mul(p)))
}

/// Price-time fill.
///
/// Returns:
/// (filled_quantity, remaining_quantity)
pub fn match_orders(buy_qty: u64, asks: &[u64]) -> (u64, u64) {
    let mut remaining = buy_qty;
    let mut filled = 0u64;

    for &ask in asks {
        if remaining == 0 {
            break;
        }

        let take = remaining.min(ask);

        filled = filled.wrapping_add(take);
        remaining -= take;
    }

    (filled, remaining)
}

#[cfg(feature = "python")]
mod python_bindings {
    use pyo3::prelude::*;
    use pyo3::types::PyModule;
    use serde_json::json;

    use super::*;

    #[pyfunction]
    fn checksum_u64_py(values: Vec<u64>) -> PyResult<u64> {
        Ok(checksum_u64(&values))
    }

    #[pyfunction]
    fn normalize_dedup_py(values: Vec<i64>) -> PyResult<Vec<i64>> {
        let mut out = vec![0i64; values.len()];

        let n = normalize_dedup(&values, &mut out);

        Ok(out[..n].to_vec())
    }

    #[pyfunction]
    fn feature_returns_py(prices: Vec<f64>) -> PyResult<Vec<f64>> {
        if prices.len() < 2 {
            return Ok(vec![]);
        }

        let mut out = vec![0.0f64; prices.len() - 1];

        let n = feature_returns(&prices, &mut out);

        Ok(out[..n].to_vec())
    }

    #[pyfunction]
    fn replay_inversions_py(timestamps: Vec<u64>) -> PyResult<u64> {
        Ok(replay_inversions(&timestamps))
    }

    #[pyfunction]
    fn risk_gross_exposure_py(quantities: Vec<u64>, prices: Vec<u64>) -> PyResult<u64> {
        Ok(risk_gross_exposure(&quantities, &prices))
    }

    #[pyfunction]
    fn match_orders_py(buy_qty: u64, asks: Vec<u64>) -> PyResult<(u64, u64)> {
        Ok(match_orders(buy_qty, &asks))
    }

    #[pyfunction]
    fn normalize_market_events(events: Vec<(f64, f64)>) -> PyResult<Vec<(f64, f64)>> {
        let mut deduped = events.clone();

        deduped.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());

        deduped.dedup_by(|a, b| a.0 == b.0);

        Ok(deduped)
    }

    #[pyfunction]
    fn serialize_event_json(event_data: Vec<(String, String)>) -> PyResult<String> {
        let mut map = std::collections::HashMap::new();

        for (key, value) in event_data {
            map.insert(key, value);
        }

        Ok(json!(map).to_string())
    }

    #[pymodule]
    fn delta_native(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(checksum_u64_py, m)?)?;

        m.add_function(wrap_pyfunction!(normalize_dedup_py, m)?)?;

        m.add_function(wrap_pyfunction!(feature_returns_py, m)?)?;

        m.add_function(wrap_pyfunction!(replay_inversions_py, m)?)?;

        m.add_function(wrap_pyfunction!(risk_gross_exposure_py, m)?)?;

        m.add_function(wrap_pyfunction!(match_orders_py, m)?)?;

        m.add_function(wrap_pyfunction!(normalize_market_events, m)?)?;

        m.add_function(wrap_pyfunction!(serialize_event_json, m)?)?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checksum_is_deterministic() {
        let values = [1, 2, 3, 4, 5];

        assert_eq!(checksum_u64(&values), 15);

        assert_eq!(checksum_u64(&values), 15);
    }

    #[test]
    fn empty_checksum_is_zero() {
        assert_eq!(checksum_u64(&[]), 0);
    }

    #[test]
    fn normalize_drops_repeats() {
        let mut out = [0i64; 8];

        let n = normalize_dedup(&[1, 1, 2, 3, 3, 3, 4], &mut out);

        assert_eq!(n, 4);

        assert_eq!(&out[..n], &[1, 2, 3, 4]);
    }

    #[test]
    fn feature_returns_parity_vector() {
        let mut out = [0.0f64; 3];

        let n = feature_returns(&[100.0, 110.0, 110.0, 55.0], &mut out);

        assert_eq!(n, 3);

        assert!((out[0] - 0.1).abs() < 1e-12);

        assert!((out[1] - 0.0).abs() < 1e-12);

        assert!((out[2] + 0.5).abs() < 1e-12);
    }

    #[test]
    fn replay_inversions_counts() {
        assert_eq!(replay_inversions(&[1, 2, 3]), 0);

        assert_eq!(replay_inversions(&[3, 2, 1]), 3);
    }

    #[test]
    fn risk_gross_exposure_sums() {
        assert_eq!(risk_gross_exposure(&[10, 5], &[100, 200],), 2000);
    }

    #[test]
    fn match_orders_fills_in_order() {
        assert_eq!(match_orders(10, &[4, 4, 4],), (10, 0));

        assert_eq!(match_orders(20, &[4, 4],), (8, 12));
    }
}
