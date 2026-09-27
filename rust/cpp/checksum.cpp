#include <cstdint>
#include <cstddef>

extern "C" std::uint64_t delta_checksum(
    const std::uint64_t* values,
    std::size_t size
) {
    if (values == nullptr && size != 0) {
        return 0;
    }

    std::uint64_t result = 0;

    for (std::size_t i = 0; i < size; ++i) {
        result += values[i];
    }

    return result;
}