#ifndef CPU_PREFETCH_WORKLOAD_DETERMINISTIC_HPP
#define CPU_PREFETCH_WORKLOAD_DETERMINISTIC_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::workload {

inline constexpr std::string_view kDeterministicSuite = "PHILOX4X32-10-HMAC-SHA256-v1";
inline constexpr std::string_view kProtocolVersion = "2.0.0-pre.1";

class WorkloadSetupError final : public std::invalid_argument {
public:
  using std::invalid_argument::invalid_argument;
};

class MasterSeed final {
public:
  [[nodiscard]] static MasterSeed from_hex(std::string_view text);
  explicit MasterSeed(std::array<std::byte, 32> bytes) noexcept : bytes_(bytes) {}

  [[nodiscard]] std::span<const std::byte, 32> bytes() const noexcept { return bytes_; }
  auto operator==(const MasterSeed&) const -> bool = default;

private:
  std::array<std::byte, 32> bytes_{};
};

enum class StreamPurpose : std::uint8_t {
  event_order,
  node_order,
  event_payload,
  initial_consumer_state,
  arrival_schedule,
};

[[nodiscard]] std::string_view purpose_label(StreamPurpose purpose) noexcept;

struct PhiloxKey final {
  std::array<std::uint32_t, 2> words;
  auto operator==(const PhiloxKey&) const -> bool = default;
};

struct PhiloxBlock final {
  std::array<std::uint32_t, 4> words;
  auto operator==(const PhiloxBlock&) const -> bool = default;
};

[[nodiscard]] PhiloxKey derive_stream_key(const MasterSeed& master_seed,
                                          std::string_view name_space,
                                          StreamPurpose purpose);
[[nodiscard]] PhiloxBlock philox4x32_10(std::uint64_t block_ordinal,
                                        PhiloxKey key) noexcept;

class DeterministicStream final {
public:
  explicit DeterministicStream(PhiloxKey key) noexcept : key_(key) {}

  [[nodiscard]] std::uint64_t draw(std::uint64_t draw_ordinal) const noexcept;

private:
  PhiloxKey key_;
};

[[nodiscard]] std::vector<std::size_t>
make_permutation(std::size_t count, const DeterministicStream& stream);

class Sha256Digest final {
public:
  explicit Sha256Digest(std::array<std::byte, 32> bytes) noexcept : bytes_(bytes) {}

  [[nodiscard]] std::span<const std::byte, 32> bytes() const noexcept { return bytes_; }
  [[nodiscard]] std::string hex() const;
  auto operator==(const Sha256Digest&) const -> bool = default;

private:
  std::array<std::byte, 32> bytes_{};
};

[[nodiscard]] Sha256Digest sha256(std::span<const std::byte> input);

} // namespace cpu_prefetch::workload

#endif // CPU_PREFETCH_WORKLOAD_DETERMINISTIC_HPP
