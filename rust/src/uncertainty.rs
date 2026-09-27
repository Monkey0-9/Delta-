#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Uncertainty {
    pub aleatoric: f64,
    pub epistemic: f64,
    pub disagreement: f64,
    pub data: f64,
    pub regime: f64,
    pub execution: f64,
}

impl Uncertainty {

    pub fn aggregate(&self) -> f64 {

        let value =
            0.20 * self.aleatoric
            + 0.20 * self.epistemic
            + 0.20 * self.disagreement
            + 0.15 * self.data
            + 0.15 * self.regime
            + 0.10 * self.execution;

        value.clamp(0.0, 1.0)
    }
}


#[cfg(test)]
mod tests {

    use super::*;

    #[test]
    fn aggregate_is_bounded() {

        let u = Uncertainty {
            aleatoric: 1.0,
            epistemic: 1.0,
            disagreement: 1.0,
            data: 1.0,
            regime: 1.0,
            execution: 1.0,
        };

        assert_eq!(
            u.aggregate(),
            1.0
        );
    }

    #[test]
    fn zero_uncertainty_is_zero() {

        let u = Uncertainty {
            aleatoric: 0.0,
            epistemic: 0.0,
            disagreement: 0.0,
            data: 0.0,
            regime: 0.0,
            execution: 0.0,
        };

        assert_eq!(
            u.aggregate(),
            0.0
        );
    }
}