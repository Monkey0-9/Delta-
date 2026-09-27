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
    }
}
