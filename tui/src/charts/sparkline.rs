//! Terminal financial charts and sparklines.
//!
//! Section 12:
//! Real charts for price trend, returns, equity curve, drawdown, and exposure.

/// Converts a slice of f64 prices into a scaled u64 vector suitable for Ratatui's Sparkline widget.
pub fn scale_for_sparkline(data: &[f64], max_val: u64) -> Vec<u64> {
    if data.is_empty() {
        return Vec::new();
    }
    let min = data.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = data.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let range = max - min;

    if range <= 1e-9 {
        return vec![max_val / 2; data.len()];
    }

    data.iter()
        .map(|&v| {
            let norm = ((v - min) / range).clamp(0.0, 1.0);
            (norm * max_val as f64) as u64
        })
        .collect()
}

/// Generates an inline unicode text sparkline (e.g.  ▂▄▆█) from f64 data.
pub fn text_sparkline(data: &[f64]) -> String {
    if data.is_empty() {
        return "───".to_string();
    }
    let glyphs = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
    let min = data.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = data.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let range = max - min;

    if range <= 1e-9 {
        return "▅".repeat(data.len().min(20));
    }

    data.iter()
        .map(|&v| {
            let norm = ((v - min) / range).clamp(0.0, 1.0);
            let idx = (norm * (glyphs.len() - 1) as f64).round() as usize;
            glyphs[idx.min(glyphs.len() - 1)]
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn text_sparkline_generates_correct_gradient() {
        let data = [10.0, 20.0, 30.0, 40.0, 50.0];
        let spark = text_sparkline(&data);
        assert_eq!(spark.chars().count(), 5);
        assert_eq!(spark.chars().next().unwrap(), ' ');
        assert_eq!(spark.chars().last().unwrap(), '█');
    }
}
