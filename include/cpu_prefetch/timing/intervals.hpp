#ifndef CPU_PREFETCH_TIMING_INTERVALS_HPP
#define CPU_PREFETCH_TIMING_INTERVALS_HPP

#include "cpu_prefetch/protocol/model.hpp"

#include <cstdint>

namespace cpu_prefetch::timing {

[[nodiscard]] auto derive_joined_record(const protocol::ProducerRecord& producer,
                                        std::uint64_t producer_row_ordinal,
                                        const protocol::ConsumerRecord& consumer,
                                        std::uint64_t consumer_row_ordinal)
    -> protocol::Result<protocol::JoinedRecord>;

} // namespace cpu_prefetch::timing

#endif // CPU_PREFETCH_TIMING_INTERVALS_HPP
