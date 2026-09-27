#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EventTime {
    pub event_ns: i64,
    pub available_ns: i64,
}

#[inline]
pub fn eligible(
    event: EventTime,
    asof_ns: i64,
) -> bool {
    event.event_ns <= asof_ns
        && event.available_ns <= asof_ns
}

pub fn filter_indices(
    events: &[EventTime],
    asof_ns: i64,
) -> Vec<usize> {

    events
        .iter()
        .enumerate()
        .filter_map(
            |(index, event)| {
                eligible(*event, asof_ns)
                    .then_some(index)
            },
        )
        .collect()
}


#[cfg(test)]
mod tests {

    use super::*;

    #[test]
    fn publication_time_blocks_future_information() {

        let event = EventTime {
            event_ns: 10,
            available_ns: 20,
        };

        assert!(
            !eligible(event, 15)
        );

        assert!(
            eligible(event, 20)
        );
    }
}