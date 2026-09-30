//! Aligned financial formatting and table helpers.
//!
//! Section 11:
//! Provides strictly aligned numeric columns, clear financial notations,
//! and clean visual hierarchy for high-density scanning.

pub fn format_currency(val: f64) -> String {
    let abs_v = val.abs();
    let sign = if val < 0.0 { "-" } else { "" };
    if abs_v >= 1_000_000_000.0 {
        format!("{sign}${:.2}B", abs_v / 1_000_000_000.0)
    } else if abs_v >= 1_000_000.0 {
        format!("{sign}${:.2}M", abs_v / 1_000_000.0)
    } else if abs_v >= 1_000.0 {
        format!("{sign}${:.2}K", abs_v / 1_000.0)
    } else {
        format!("{sign}${:.2}", abs_v)
    }
}

pub fn format_currency_exact(val: f64) -> String {
    let abs_v = val.abs();
    let sign = if val < 0.0 { "-" } else { "" };
    format!("{sign}${:.2}", abs_v)
}

pub fn format_pnl(val: f64) -> String {
    let sign = if val > 0.0 { "+" } else if val < 0.0 { "-" } else { " " };
    format!("{sign}${:.2}", val.abs())
}

pub fn format_percent(val: f64) -> String {
    let sign = if val > 0.0 { "+" } else if val < 0.0 { "-" } else { " " };
    format!("{sign}{:.2}%", val.abs())
}

pub fn format_ratio(val: f64) -> String {
    format!("{:.2}×", val)
}

pub fn format_bps(val: f64) -> String {
    let sign = if val > 0.0 { "+" } else if val < 0.0 { "-" } else { "" };
    format!("{sign}{:.1} bps", val.abs())
}

pub fn format_qty(val: f64) -> String {
    if val.fract() == 0.0 {
        format!("{:.0}", val)
    } else {
        format!("{:.2}", val)
    }
}

pub use format_bps as format_basis_points;
pub use format_qty as format_quantity;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_currency_compact() {
        assert_eq!(format_currency(1_240_000.0), "$1.24M");
        assert_eq!(format_currency(450.50), "$450.50");
        assert_eq!(format_currency(-25_000.0), "-$25.00K");
    }

    #[test]
    fn formats_percentages_and_ratios() {
        assert_eq!(format_percent(2.41), "+2.41%");
        assert_eq!(format_percent(-1.05), "-1.05%");
        assert_eq!(format_ratio(1.28), "1.28×");
        assert_eq!(format_bps(18.2), "+18.2 bps");
        assert_eq!(format_basis_points(5.0), "+5.0 bps");
    }
}
