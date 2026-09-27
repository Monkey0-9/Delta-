#[inline]
pub fn rolling_mean(
    values: &[f64],
    window: usize,
) -> Vec<f64> {

    if window == 0
        || values.len() < window
    {
        return Vec::new();
    }

    let mut output =
        Vec::with_capacity(
            values.len() - window + 1
        );

    let mut sum = 0.0;

    for i in 0..values.len() {

        sum += values[i];

        if i >= window {
            sum -= values[
                i - window
            ];
        }

        if i + 1 >= window {

            output.push(
                sum
                    / window as f64
            );
        }
    }

    output
}


#[cfg(test)]
mod tests {

    use super::*;

    #[test]
    fn rolling_mean_is_correct() {

        assert_eq!(
            rolling_mean(
                &[1.0, 2.0, 3.0],
                2
            ),
            vec![1.5, 2.5]
        );
    }
}
pub mod rolling;