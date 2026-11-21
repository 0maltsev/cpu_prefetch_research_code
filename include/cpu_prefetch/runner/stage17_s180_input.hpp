#ifndef CPU_PREFETCH_RUNNER_STAGE17_S180_INPUT_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_S180_INPUT_HPP
#include "cpu_prefetch/runner/stage17_s180_session.hpp"

namespace cpu_prefetch::runner::stage17 {
// Owns the immutable parsed document, prestate and descriptor membership. Native
// spans are rebound on access after copies/moves. No schedule vectors, mappings,
// hardware actions or authority are created by this cold parser.
class ParsedS180Input final {
public:
  [[nodiscard]] auto input() const -> S180SessionInput;
  [[nodiscard]] auto document() const noexcept -> const protocol::json::Value::Object&;

private:
  friend auto parse_s180_session_input(protocol::json::Value::Object,
                                       const protocol::json::Value::Object&,
                                       std::span<const int>)
      -> protocol::Result<ParsedS180Input>;
  std::shared_ptr<const protocol::json::Value::Object> document_;
  std::vector<platform::HardwarePrefetchMsrValue> prestate_;
  std::vector<FormalScheduleSourceBinding> bindings_;
  std::vector<int> reserved_;
  S180SessionInput input_{};
};
[[nodiscard]] auto
parse_s180_session_input(protocol::json::Value::Object plan,
                         const protocol::json::Value::Object& source_context,
                         std::span<const int> reserved_descriptors)
    -> protocol::Result<ParsedS180Input>;
} // namespace cpu_prefetch::runner::stage17
#endif
