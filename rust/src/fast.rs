//! DELTA fast kernels: single-pass, panic-free, no_std-compatible core.
//! Called from Python via C ABI (cdylib) so no maturin/PyO3 install is needed.

/// Sliding population mean/std, min_periods = w. Invalid prefix = NaN.
pub fn roll_mean_std(x: &[f64], w: usize, mean: &mut [f64], std: &mut [f64]) {
    if w == 0 || x.len() != mean.len() || x.len() != std.len() || x.is_empty() {
        return;
    }
    let mut s = 0.0;
    let mut s2 = 0.0;
    let wf = w as f64;
    for (i, &v) in x.iter().enumerate() {
        s += v;
        s2 += v * v;
        if i >= w {
            let o = x[i - w];
            s -= o;
            s2 -= o * o;
        }
        if i + 1 >= w {
            let mu = s / wf;
            let var = (s2 / wf - mu * mu).max(0.0);
            mean[i] = mu;
            std[i] = var.sqrt();
        } else {
            mean[i] = f64::NAN;
            std[i] = f64::NAN;
        }
    }
}

/// Wilder RSI mapped to [-0.5, +0.5] (matches research/real_loop/features.py).
pub fn rsi_wilder(px: &[f64], w: usize, out: &mut [f64]) {
    if px.len() != out.len() || px.is_empty() || w == 0 {
        return;
    }
    out[0] = 0.0;
    let seed = w.min(px.len().saturating_sub(1));
    let mut gu = 0.0;
    let mut gd = 0.0;
    for i in 1..=seed {
        let d = px[i] - px[i - 1];
        if d > 0.0 {
            gu += d;
        } else {
            gd -= d;
        }
    }
    gu /= w as f64;
    gd /= w as f64;
    let wf = w as f64;
    for (i, o) in out.iter_mut().enumerate().skip(1) {
        let d = px[i] - px[i - 1];
        if i > seed {
            let (u, dn) = if d > 0.0 { (d, 0.0) } else { (0.0, -d) };
            gu = (gu * (wf - 1.0) + u) / wf;
            gd = (gd * (wf - 1.0) + dn) / wf;
        }
        let rs = if gd == 0.0 {
            if gu == 0.0 {
                1.0
            } else {
                1e12
            }
        } else {
            gu / gd
        };
        let mut rsi = 100.0 - 100.0 / (1.0 + rs);
        if i < w {
            rsi = 50.0;
        }
        *o = rsi / 100.0 - 0.5;
    }
}

/// Rank data (average ties) into out[0..n]. O(n log n).
pub fn rank_avg(xs: &[f64], out: &mut [f64]) {
    let n = xs.len();
    if out.len() != n {
        return;
    }
    let mut idx: Vec<usize> = (0..n).collect();
    idx.sort_by(|&a, &b| xs[a].partial_cmp(&xs[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut i = 0;
    while i < n {
        let mut j = i + 1;
        while j < n && xs[idx[j]] == xs[idx[i]] {
            j += 1;
        }
        let avg = (i + j - 1) as f64 / 2.0 + 1.0; // 1-based average rank
        for k in i..j {
            out[idx[k]] = avg;
        }
        i = j;
    }
}

/// Pearson correlation of two equal slices. Returns 0 on degenerate input.
pub fn pearson(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len().min(b.len());
    if n < 3 {
        return 0.0;
    }
    let (mut sa, mut sb) = (0.0, 0.0);
    for i in 0..n {
        sa += a[i];
        sb += b[i];
    }
    let (ma, mb) = (sa / n as f64, sb / n as f64);
    let (mut cov, mut va, mut vb) = (0.0, 0.0, 0.0);
    for i in 0..n {
        let da = a[i] - ma;
        let db = b[i] - mb;
        cov += da * db;
        va += da * da;
        vb += db * db;
    }
    if va <= 0.0 || vb <= 0.0 {
        return 0.0;
    }
    let c = cov / (va.sqrt() * vb.sqrt());
    if c.is_nan() {
        0.0
    } else {
        c.clamp(-1.0, 1.0)
    }
}

/// Spearman rank-IC with scratch buffers (caller-sized n). No allocation.
pub fn spearman_ic(x: &[f64], y: &[f64], rx: &mut [f64], ry: &mut [f64]) -> f64 {
    if x.len() != y.len() || rx.len() != x.len() || ry.len() != x.len() {
        return 0.0;
    }
    rank_avg(x, rx);
    rank_avg(y, ry);
    pearson(rx, ry)
}

/// One ERC (risk-parity) coordinate-descent sweep in place.
/// w *= sqrt(target / rc); returns max |dw|. Caller normalizes.
pub fn erc_sweep(cov: &[f64], n: usize, w: &mut [f64]) -> f64 {
    if cov.len() < n * n || w.len() != n || n == 0 {
        return 0.0;
    }
    // sigma*w
    let mut sw = vec![0.0; n];
    for i in 0..n {
        let mut s = 0.0;
        for j in 0..n {
            s += cov[i * n + j] * w[j];
        }
        sw[i] = s;
    }
    let mut pv = 0.0;
    for i in 0..n {
        pv += w[i] * sw[i];
    }
    let pv = pv.max(1e-18).sqrt();
    let target = pv / n as f64;
    let mut maxd: f64 = 0.0;
    for i in 0..n {
        let rc = (w[i] * sw[i] / pv).max(1e-18);
        let nw = w[i] * (target / rc).sqrt().clamp(1e-3, 1e3);
        maxd = maxd.max((nw - w[i]).abs());
        w[i] = nw;
    }
    maxd
}

/// Project weights onto bounded simplex {w in [0, max_weight]^n : sum(w) = 1}.
/// Uses exact iterative water-filling, eliminating weight re-inflation.
pub fn simplex_cap(w: &mut [f64], max_weight: f64) -> Result<(), &'static str> {
    let n = w.len();
    if n == 0 {
        return Ok(());
    }
    if max_weight <= 0.0 {
        return Err("max_weight must be strictly positive");
    }
    if (n as f64) * max_weight < 1.0 - 1e-9 {
        return Err("Infeasible weight cap: n * max_weight < 1.0");
    }
    for v in w.iter_mut() {
        if *v < 0.0 || v.is_nan() {
            *v = 0.0;
        }
    }
    let total_sum: f64 = w.iter().sum();
    if total_sum <= 0.0 {
        let uniform = 1.0 / n as f64;
        for v in w.iter_mut() {
            *v = uniform;
        }
    } else {
        for v in w.iter_mut() {
            *v /= total_sum;
        }
    }

    let mut fixed = vec![false; n];
    for _ in 0..=n {
        let mut any_violator = false;
        for i in 0..n {
            if !fixed[i] && w[i] > max_weight + 1e-12 {
                fixed[i] = true;
                w[i] = max_weight;
                any_violator = true;
            }
        }
        if !any_violator {
            break;
        }
        let fixed_count = fixed.iter().filter(|&&f| f).count();
        let rem_sum = 1.0 - (fixed_count as f64) * max_weight;
        let free_count = n - fixed_count;
        if free_count > 0 {
            let free_sum: f64 = w
                .iter()
                .enumerate()
                .filter(|(i, _)| !fixed[*i])
                .map(|(_, &v)| v)
                .sum();
            if free_sum > 1e-15 {
                let factor = rem_sum / free_sum;
                for (i, v) in w.iter_mut().enumerate() {
                    if !fixed[i] {
                        *v *= factor;
                    }
                }
            } else {
                let uniform_free = rem_sum / free_count as f64;
                for (i, v) in w.iter_mut().enumerate() {
                    if !fixed[i] {
                        *v = uniform_free;
                    }
                }
            }
        }
    }
    for v in w.iter_mut() {
        *v = v.clamp(0.0, max_weight);
    }
    Ok(())
}

/// Error function polynomial approximation (Abramowitz & Stegun 7.1.26).
/// |error| < 1.5e-7.
fn erf_approx(x: f64) -> f64 {
    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let abs_x = x.abs();
    let p = 0.3275911;
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let t = 1.0 / (1.0 + p * abs_x);
    let poly = (((a5 * t + a4) * t + a3) * t + a2) * t + a1;
    sign * (1.0 - poly * t * (-abs_x * abs_x).exp())
}

/// Standard normal cumulative distribution function.
pub fn norm_cdf(x: f64) -> f64 {
    0.5 * (1.0 + erf_approx(x / std::f64::consts::SQRT_2))
}

/// Standard normal probability density function.
pub fn norm_pdf(x: f64) -> f64 {
    (1.0 / (2.0 * std::f64::consts::PI).sqrt()) * (-0.5 * x * x).exp()
}

/// Black-Scholes European option pricing and analytical Greeks.
/// out: [price, delta, gamma, vega, theta, rho]
pub fn black_scholes_greeks(
    spot: f64,
    strike: f64,
    expiry_years: f64,
    vol: f64,
    risk_free: f64,
    is_call: bool,
    out: &mut [f64],
) -> bool {
    if out.len() < 6 || spot <= 0.0 || strike <= 0.0 || expiry_years <= 0.0 || vol <= 0.0 {
        return false;
    }
    let sqrt_t = expiry_years.sqrt();
    let d1 = ((spot / strike).ln() + (risk_free + 0.5 * vol * vol) * expiry_years) / (vol * sqrt_t);
    let d2 = d1 - vol * sqrt_t;
    let nd1 = norm_cdf(d1);
    let nd2 = norm_cdf(d2);
    let pdf_d1 = norm_pdf(d1);
    let disc = (-risk_free * expiry_years).exp();

    let (price, delta) = if is_call {
        let p = spot * nd1 - strike * disc * nd2;
        (p, nd1)
    } else {
        let n_neg_d1 = norm_cdf(-d1);
        let n_neg_d2 = norm_cdf(-d2);
        let p = strike * disc * n_neg_d2 - spot * n_neg_d1;
        (p, nd1 - 1.0)
    };

    let gamma = pdf_d1 / (spot * vol * sqrt_t);
    let vega = spot * sqrt_t * pdf_d1;
    let theta = if is_call {
        -(spot * pdf_d1 * vol) / (2.0 * sqrt_t) - risk_free * strike * disc * nd2
    } else {
        -(spot * pdf_d1 * vol) / (2.0 * sqrt_t) + risk_free * strike * disc * norm_cdf(-d2)
    } / 365.0; // Per-calendar day theta
    let rho = if is_call {
        strike * expiry_years * disc * nd2 / 100.0
    } else {
        -strike * expiry_years * disc * norm_cdf(-d2) / 100.0
    };

    out[0] = price.max(0.0);
    out[1] = delta;
    out[2] = gamma;
    out[3] = vega / 100.0; // 1% vol shift
    out[4] = theta;
    out[5] = rho;
    true
}

/// Historical VaR and Expected Shortfall (CVaR) at significance alpha (e.g. 0.05).
/// out: [VaR, CVaR] (positive values represent losses).
pub fn var_cvar(returns: &[f64], alpha: f64, out: &mut [f64]) -> bool {
    let n = returns.len();
    if n < 5 || out.len() < 2 || alpha <= 0.0 || alpha >= 0.5 {
        return false;
    }
    let mut sorted = returns.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let cutoff = ((n as f64) * alpha).floor() as usize;
    let cutoff = cutoff.clamp(1, n - 1);
    let var_val = -sorted[cutoff - 1];
    let tail_sum: f64 = sorted[..cutoff].iter().sum();
    let cvar_val = -tail_sum / cutoff as f64;
    out[0] = var_val.max(0.0);
    out[1] = cvar_val.max(out[0]);
    true
}

/// Cumulative Volume-Weighted Average Price (VWAP) and rolling deviation bands.
pub fn vwap_bands(prices: &[f64], volumes: &[f64], out_vwap: &mut [f64], out_std: &mut [f64]) {
    let n = prices.len().min(volumes.len()).min(out_vwap.len()).min(out_std.len());
    if n == 0 {
        return;
    }
    let mut cum_pv = 0.0;
    let mut cum_v = 0.0;
    let mut cum_pv2 = 0.0;
    for i in 0..n {
        let p = prices[i];
        let v = volumes[i].max(0.0);
        cum_pv += p * v;
        cum_v += v;
        cum_pv2 += p * p * v;
        if cum_v > 0.0 {
            let vwap = cum_pv / cum_v;
            let variance = (cum_pv2 / cum_v - vwap * vwap).max(0.0);
            out_vwap[i] = vwap;
            out_std[i] = variance.sqrt();
        } else {
            out_vwap[i] = p;
            out_std[i] = 0.0;
        }
    }
}

/// Single-pass MACD(fast, slow, signal) with histogram.
pub fn macd(
    prices: &[f64],
    fast_p: usize,
    slow_p: usize,
    signal_p: usize,
    out_macd: &mut [f64],
    out_signal: &mut [f64],
    out_hist: &mut [f64],
) {
    let n = prices.len().min(out_macd.len()).min(out_signal.len()).min(out_hist.len());
    if n == 0 || fast_p == 0 || slow_p <= fast_p || signal_p == 0 {
        return;
    }
    let k_fast = 2.0 / (fast_p as f64 + 1.0);
    let k_slow = 2.0 / (slow_p as f64 + 1.0);
    let k_sig = 2.0 / (signal_p as f64 + 1.0);

    let mut ema_fast = prices[0];
    let mut ema_slow = prices[0];
    let mut ema_sig = 0.0;

    for i in 0..n {
        let p = prices[i];
        ema_fast = p * k_fast + ema_fast * (1.0 - k_fast);
        ema_slow = p * k_slow + ema_slow * (1.0 - k_slow);
        let m = ema_fast - ema_slow;
        if i == 0 {
            ema_sig = m;
        } else {
            ema_sig = m * k_sig + ema_sig * (1.0 - k_sig);
        }
        out_macd[i] = m;
        out_signal[i] = ema_sig;
        out_hist[i] = m - ema_sig;
    }
}

// ---- C ABI exports (stable, no_mangle) ----
#[no_mangle]
pub extern "C" fn delta_roll_mean_std(
    x: *const f64,
    n: usize,
    w: usize,
    mean: *mut f64,
    std: *mut f64,
) {
    if x.is_null() || mean.is_null() || std.is_null() || n == 0 {
        return;
    }
    unsafe {
        roll_mean_std(
            std::slice::from_raw_parts(x, n),
            w,
            std::slice::from_raw_parts_mut(mean, n),
            std::slice::from_raw_parts_mut(std, n),
        );
    }
}

#[no_mangle]
pub extern "C" fn delta_rsi_wilder(px: *const f64, n: usize, w: usize, out: *mut f64) {
    if px.is_null() || out.is_null() || n == 0 {
        return;
    }
    unsafe {
        rsi_wilder(
            std::slice::from_raw_parts(px, n),
            w,
            std::slice::from_raw_parts_mut(out, n),
        );
    }
}

#[no_mangle]
pub extern "C" fn delta_spearman_ic(
    x: *const f64,
    y: *const f64,
    n: usize,
    rx: *mut f64,
    ry: *mut f64,
) -> f64 {
    if x.is_null() || y.is_null() || rx.is_null() || ry.is_null() || n == 0 {
        return 0.0;
    }
    unsafe {
        spearman_ic(
            std::slice::from_raw_parts(x, n),
            std::slice::from_raw_parts(y, n),
            std::slice::from_raw_parts_mut(rx, n),
            std::slice::from_raw_parts_mut(ry, n),
        )
    }
}

#[no_mangle]
pub extern "C" fn delta_erc_sweep(cov: *const f64, n: usize, w: *mut f64) -> f64 {
    if cov.is_null() || w.is_null() || n == 0 {
        return 0.0;
    }
    unsafe {
        erc_sweep(
            std::slice::from_raw_parts(cov, n * n),
            n,
            std::slice::from_raw_parts_mut(w, n),
        )
    }
}

#[no_mangle]
pub extern "C" fn delta_simplex_cap(w: *mut f64, n: usize, max_weight: f64) -> i32 {
    if w.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(w, n) };
    match simplex_cap(slice, max_weight) {
        Ok(()) => 0,
        Err(_) => -1,
    }
}

#[no_mangle]
pub extern "C" fn delta_black_scholes_greeks(
    spot: f64,
    strike: f64,
    expiry_years: f64,
    vol: f64,
    risk_free: f64,
    is_call: i32,
    out: *mut f64,
) -> i32 {
    if out.is_null() {
        return 0;
    }
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, 6) };
    if black_scholes_greeks(spot, strike, expiry_years, vol, risk_free, is_call != 0, out_slice) {
        1
    } else {
        0
    }
}

#[no_mangle]
pub extern "C" fn delta_var_cvar(
    returns: *const f64,
    n: usize,
    alpha: f64,
    out: *mut f64,
) -> i32 {
    if returns.is_null() || out.is_null() || n == 0 {
        return 0;
    }
    let rets = unsafe { std::slice::from_raw_parts(returns, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, 2) };
    if var_cvar(rets, alpha, out_slice) {
        1
    } else {
        0
    }
}

#[no_mangle]
pub extern "C" fn delta_vwap_bands(
    prices: *const f64,
    volumes: *const f64,
    n: usize,
    out_vwap: *mut f64,
    out_std: *mut f64,
) {
    if prices.is_null() || volumes.is_null() || out_vwap.is_null() || out_std.is_null() || n == 0 {
        return;
    }
    unsafe {
        vwap_bands(
            std::slice::from_raw_parts(prices, n),
            std::slice::from_raw_parts(volumes, n),
            std::slice::from_raw_parts_mut(out_vwap, n),
            std::slice::from_raw_parts_mut(out_std, n),
        );
    }
}

#[no_mangle]
pub extern "C" fn delta_macd(
    prices: *const f64,
    n: usize,
    fast_p: usize,
    slow_p: usize,
    signal_p: usize,
    out_macd: *mut f64,
    out_signal: *mut f64,
    out_hist: *mut f64,
) {
    if prices.is_null() || out_macd.is_null() || out_signal.is_null() || out_hist.is_null() || n == 0 {
        return;
    }
    unsafe {
        macd(
            std::slice::from_raw_parts(prices, n),
            fast_p,
            slow_p,
            signal_p,
            std::slice::from_raw_parts_mut(out_macd, n),
            std::slice::from_raw_parts_mut(out_signal, n),
            std::slice::from_raw_parts_mut(out_hist, n),
        );
    }
}

/// NCM Cosine Similarity Kernel: computes cosine similarity between a query embedding
/// of length `dim` and `num_concepts` prototype concept embeddings stored row-wise in `matrix`.
pub fn ncm_cosine_similarity(
    query: &[f32],
    matrix: &[f32],
    dim: usize,
    num_concepts: usize,
    out_scores: &mut [f32],
) {
    if dim == 0 || num_concepts == 0 || query.len() < dim || matrix.len() < dim * num_concepts || out_scores.len() < num_concepts {
        return;
    }
    let mut q_norm_sq = 0.0f32;
    for &v in &query[..dim] {
        q_norm_sq += v * v;
    }
    let q_norm = q_norm_sq.sqrt();
    if q_norm < 1e-12 {
        for s in &mut out_scores[..num_concepts] {
            *s = 0.0;
        }
        return;
    }

    for c in 0..num_concepts {
        let row = &matrix[c * dim..(c + 1) * dim];
        let mut dot = 0.0f32;
        let mut r_norm_sq = 0.0f32;
        for i in 0..dim {
            dot += query[i] * row[i];
            r_norm_sq += row[i] * row[i];
        }
        let r_norm = r_norm_sq.sqrt();
        if r_norm < 1e-12 {
            out_scores[c] = 0.0;
        } else {
            out_scores[c] = dot / (q_norm * r_norm);
        }
    }
}

/// NCM Shannon Entropy Kernel: computes -\sum p_i \ln(p_i) for a probability distribution.
pub fn ncm_transition_entropy(probs: &[f64]) -> f64 {
    let mut entropy = 0.0f64;
    for &p in probs {
        if p > 1e-12 {
            entropy -= p * p.ln();
        }
    }
    entropy
}

#[no_mangle]
pub extern "C" fn delta_ncm_similarity(
    query: *const f32,
    matrix: *const f32,
    dim: usize,
    num_concepts: usize,
    out_scores: *mut f32,
) {
    if query.is_null() || matrix.is_null() || out_scores.is_null() || dim == 0 || num_concepts == 0 {
        return;
    }
    unsafe {
        ncm_cosine_similarity(
            std::slice::from_raw_parts(query, dim),
            std::slice::from_raw_parts(matrix, dim * num_concepts),
            dim,
            num_concepts,
            std::slice::from_raw_parts_mut(out_scores, num_concepts),
        );
    }
}

#[no_mangle]
pub extern "C" fn delta_ncm_entropy(probs: *const f64, n: usize) -> f64 {
    if probs.is_null() || n == 0 {
        return 0.0;
    }
    unsafe {
        ncm_transition_entropy(std::slice::from_raw_parts(probs, n))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roll_mean_std_matches_hand_computation() {
        let x = [1.0, 2.0, 3.0, 4.0, 5.0];
        let (mut m, mut s) = ([0.0; 5], [0.0; 5]);
        roll_mean_std(&x, 3, &mut m, &mut s);
        assert!(m[0].is_nan() && m[1].is_nan());
        assert!((m[2] - 2.0).abs() < 1e-12);
        assert!((m[4] - 4.0).abs() < 1e-12);
        // population std of [1,2,3] = sqrt(2/3)
        assert!((s[2] - (2.0f64 / 3.0).sqrt()).abs() < 1e-12);
    }

    #[test]
    fn rsi_stays_in_bounds_and_flags_uptrend() {
        let up: Vec<f64> = (0..30).map(|i| i as f64).collect();
        let mut out = [0.0; 30];
        rsi_wilder(&up, 14, &mut out);
        assert!(out.iter().all(|v| (-0.5..=0.5).contains(v)));
        assert!(out[29] > 0.3, "steady uptrend must read overbought");
        let dn: Vec<f64> = (0..30).map(|i| 30.0 - i as f64).collect();
        rsi_wilder(&dn, 14, &mut out);
        assert!(out[29] < -0.3, "steady downtrend must read oversold");
    }

    #[test]
    fn rank_avg_handles_ties() {
        let (mut r,) = ([0.0; 4],);
        rank_avg(&[3.0, 1.0, 1.0, 2.0], &mut r);
        assert_eq!(r, [4.0, 1.5, 1.5, 3.0]);
    }

    #[test]
    fn spearman_detects_monotone_and_ignores_scale() {
        let x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0];
        let y = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0];
        let (mut rx, mut ry) = ([0.0; 6], [0.0; 6]);
        assert!((spearman_ic(&x, &y, &mut rx, &mut ry) - 1.0).abs() < 1e-12);
        let z = [6.0, 5.0, 4.0, 3.0, 2.0, 1.0];
        assert!((spearman_ic(&x, &z, &mut rx, &mut ry) + 1.0).abs() < 1e-12);
    }

    #[test]
    fn erc_sweep_equalizes_feasible_cov() {
        // 2-asset feasible case: must converge to ~equal RC.
        let cov = [0.04, 0.01, 0.01, 0.01];
        let mut w = [0.5, 0.5];
        for _ in 0..500 {
            erc_sweep(&cov, 2, &mut w);
            let s: f64 = w.iter().sum();
            w[0] /= s;
            w[1] /= s;
        }
        let rc0 = w[0] * (cov[0] * w[0] + cov[1] * w[1]);
        let rc1 = w[1] * (cov[2] * w[0] + cov[3] * w[1]);
        assert!((rc0 - rc1).abs() / (rc0 + rc1) < 0.01, "rc0={rc0} rc1={rc1}");
        assert!((w[0] - 1.0 / 3.0).abs() < 0.02, "w={w:?}");
    }

    #[test]
    fn c_abi_null_inputs_are_safe() {
        let mut out = [0.0; 4];
        delta_roll_mean_std(std::ptr::null(), 4, 2, out.as_mut_ptr(), out.as_mut_ptr());
        assert_eq!(delta_spearman_ic(std::ptr::null(), std::ptr::null(), 0,
                                     std::ptr::null_mut(), std::ptr::null_mut()), 0.0);
        assert_eq!(delta_erc_sweep(std::ptr::null(), 0, std::ptr::null_mut()), 0.0);
        assert_eq!(delta_simplex_cap(std::ptr::null_mut(), 0, 0.2), -1);
        assert_eq!(delta_black_scholes_greeks(100.0, 100.0, 1.0, 0.2, 0.05, 1, std::ptr::null_mut()), 0);
        assert_eq!(delta_var_cvar(std::ptr::null(), 0, 0.05, std::ptr::null_mut()), 0);
    }

    #[test]
    fn simplex_cap_enforces_bounds_and_budget() {
        let mut w = [0.5, 0.3, 0.1, 0.1];
        simplex_cap(&mut w, 0.35).expect("valid cap");
        let sum: f64 = w.iter().sum();
        assert!((sum - 1.0).abs() < 1e-12, "weights must sum to 1, got {sum}");
        for &val in &w {
            assert!(val <= 0.35 + 1e-12, "weight exceeds max: {val}");
            assert!(val >= 0.0, "weight is negative: {val}");
        }
        assert!((w[0] - 0.35).abs() < 1e-12);
        assert!(w[1] > w[2] && w[2] == w[3]);
    }

    #[test]
    fn black_scholes_matches_analytical_benchmark() {
        let mut out = [0.0; 6];
        let ok = black_scholes_greeks(100.0, 100.0, 1.0, 0.2, 0.05, true, &mut out);
        assert!(ok);
        let price = out[0];
        let delta = out[1];
        let gamma = out[2];
        let vega = out[3];
        let theta = out[4];
        let rho = out[5];

        // Standard ATM 1-yr call: price ~ 10.4506, delta ~ 0.6368
        assert!((price - 10.4506).abs() < 0.02, "Call price mismatch: {price}");
        assert!((delta - 0.6368).abs() < 0.01, "Delta mismatch: {delta}");
        assert!(gamma > 0.015 && gamma < 0.025, "Gamma mismatch: {gamma}");
        assert!(vega > 0.35 && vega < 0.40, "Vega mismatch: {vega}");
        assert!(theta < 0.0, "Call theta must be negative: {theta}");
        assert!(rho > 0.0, "Call rho must be positive: {rho}");

        // Put call parity ATM check: C - P = S - K * exp(-rT) = 100 - 100*exp(-0.05) ~ 4.877
        let mut put_out = [0.0; 6];
        black_scholes_greeks(100.0, 100.0, 1.0, 0.2, 0.05, false, &mut put_out);
        let put_price = put_out[0];
        let parity_diff = (price - put_price) - (100.0 - 100.0 * (-0.05f64).exp());
        assert!(parity_diff.abs() < 0.02, "Put-call parity failed: {parity_diff}");
    }

    #[test]
    fn var_cvar_subadditivity_and_ordering() {
        let rets = [-0.05, -0.04, -0.03, -0.02, -0.01, 0.00, 0.01, 0.02, 0.03, 0.04];
        let mut out = [0.0; 2];
        let ok = var_cvar(&rets, 0.10, &mut out);
        assert!(ok);
        let var = out[0];
        let cvar = out[1];
        assert!(var > 0.0, "VaR must be positive: {var}");
        assert!(cvar >= var, "CVaR ({cvar}) must be >= VaR ({var})");
    }

    #[test]
    fn vwap_and_macd_computations() {
        let prices = [100.0, 101.0, 102.0, 101.5, 103.0];
        let volumes = [10.0, 20.0, 30.0, 20.0, 20.0];
        let mut vwap = [0.0; 5];
        let mut std_dev = [0.0; 5];
        vwap_bands(&prices, &volumes, &mut vwap, &mut std_dev);
        assert!((vwap[0] - 100.0).abs() < 1e-12);
        assert!(vwap[4] > 100.0 && vwap[4] < 103.0);

        let mut macd_line = [0.0; 5];
        let mut sig_line = [0.0; 5];
        let mut hist = [0.0; 5];
        macd(&prices, 2, 4, 2, &mut macd_line, &mut sig_line, &mut hist);
        assert!((macd_line[0] - 0.0).abs() < 1e-12);
    }

    #[test]
    fn ncm_cosine_similarity_and_entropy_computations() {
        let query = [1.0f32, 0.0f32, 0.0f32];
        let matrix = [
            1.0f32, 0.0f32, 0.0f32,  // identical -> 1.0
            0.0f32, 1.0f32, 0.0f32,  // orthogonal -> 0.0
            -1.0f32, 0.0f32, 0.0f32, // opposite -> -1.0
        ];
        let mut scores = [0.0f32; 3];
        ncm_cosine_similarity(&query, &matrix, 3, 3, &mut scores);
        assert!((scores[0] - 1.0).abs() < 1e-6);
        assert!((scores[1] - 0.0).abs() < 1e-6);
        assert!((scores[2] - (-1.0)).abs() < 1e-6);

        // Uniform 2-state distribution entropy: -2 * 0.5 * ln(0.5) = ln(2) ~ 0.693147
        let probs = [0.5f64, 0.5f64];
        let ent = ncm_transition_entropy(&probs);
        assert!((ent - 2.0f64.ln()).abs() < 1e-10);
    }
}
