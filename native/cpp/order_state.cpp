#include <cstdint>

enum class State : std::uint8_t {
    Created,
    Validated,
    RiskApproved,
    Authorized,
    Submitted,
    Acknowledged,
    PartiallyFilled,
    Filled,
    Rejected,
    CancelPending,
    Cancelled,
    Expired,
    Failed,
    Unknown
};


bool legal_transition(
    State from,
    State to
) {

    switch (from) {

        case State::Created:
            return to == State::Validated
                || to == State::Rejected;

        case State::Validated:
            return to == State::RiskApproved
                || to == State::Rejected;

        case State::RiskApproved:
            return to == State::Authorized
                || to == State::Rejected;

        case State::Authorized:
            return to == State::Submitted
                || to == State::Rejected;

        case State::Submitted:
            return to == State::Acknowledged
                || to == State::Failed
                || to == State::Unknown;

        case State::Acknowledged:
            return to == State::PartiallyFilled
                || to == State::Filled
                || to == State::CancelPending
                || to == State::Expired;

        case State::PartiallyFilled:
            return to == State::PartiallyFilled
                || to == State::Filled
                || to == State::CancelPending;

        case State::CancelPending:
            return to == State::Cancelled
                || to == State::PartiallyFilled
                || to == State::Filled
                || to == State::Unknown;

        case State::Unknown:
            return to == State::Acknowledged
                || to == State::Filled
                || to == State::Cancelled
                || to == State::Failed;

        case State::Filled:
        case State::Rejected:
        case State::Cancelled:
        case State::Expired:
        case State::Failed:
            return false;
    }

    return false;
}