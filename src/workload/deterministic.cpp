#include "cpu_prefetch/workload/deterministic.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <limits>
#include <memory>

namespace cpu_prefetch::workload {
namespace {

constexpr std::uint32_t kPhiloxMultiplier0 = 0xd2511f53U;
constexpr std::uint32_t kPhiloxMultiplier1 = 0xcd9e8d57U;
constexpr std::uint32_t kPhiloxWeyl0 = 0x9e3779b9U;
constexpr std::uint32_t kPhiloxWeyl1 = 0xbb67ae85U;

[[nodiscard]] std::uint8_t hex_nibble(char value) {
  if (value >= '0' && value <= '9') {
    return static_cast<std::uint8_t>(value - '0');
  }
  if (value >= 'a' && value <= 'f') {
    return static_cast<std::uint8_t>(value - 'a' + 10);
  }
  if (value >= 'A' && value <= 'F') {
    return static_cast<std::uint8_t>(value - 'A' + 10);
  }
  throw WorkloadSetupError("master seed must contain exactly 64 hexadecimal digits");
}

void append_u64_be(std::vector<std::byte>& output, std::uint64_t value) {
  for (unsigned int shift = 64U; shift != 0U; shift -= 8U) {
    output.push_back(static_cast<std::byte>((value >> (shift - 8U)) & 0xffU));
  }
}

void append_field(std::vector<std::byte>& output, std::string_view value) {
  append_u64_be(output, static_cast<std::uint64_t>(value.size()));
  output.insert(output.end(), reinterpret_cast<const std::byte*>(value.data()),
                reinterpret_cast<const std::byte*>(value.data() + value.size()));
}

[[nodiscard]] std::array<std::byte, 32> hmac_sha256(std::span<const std::byte, 32> key,
                                                    std::span<const std::byte> input) {
  std::array<std::byte, 32> output{};
  std::size_t output_size = 0U;
  const auto* result = EVP_Q_mac(
      nullptr, "HMAC", nullptr, "SHA256", nullptr,
      reinterpret_cast<const unsigned char*>(key.data()), key.size(),
      reinterpret_cast<const unsigned char*>(input.data()), input.size(),
      reinterpret_cast<unsigned char*>(output.data()), output.size(), &output_size);
  if (result == nullptr || output_size != output.size()) {
    throw WorkloadSetupError("OpenSSL HMAC-SHA-256 derivation failed");
  }
  return output;
}

[[nodiscard]] std::uint32_t read_u32_be(const std::byte* input) noexcept {
  return (std::to_integer<std::uint32_t>(input[0]) << 24U) |
         (std::to_integer<std::uint32_t>(input[1]) << 16U) |
         (std::to_integer<std::uint32_t>(input[2]) << 8U) |
         std::to_integer<std::uint32_t>(input[3]);
}

[[nodiscard]] PhiloxBlock philox_round(PhiloxBlock counter, PhiloxKey key) noexcept {
  const auto product0 =
      static_cast<std::uint64_t>(kPhiloxMultiplier0) * counter.words[0];
  const auto product1 =
      static_cast<std::uint64_t>(kPhiloxMultiplier1) * counter.words[2];
  const auto high0 = static_cast<std::uint32_t>(product0 >> 32U);
  const auto high1 = static_cast<std::uint32_t>(product1 >> 32U);
  const auto low0 = static_cast<std::uint32_t>(product0);
  const auto low1 = static_cast<std::uint32_t>(product1);
  return {{{high1 ^ counter.words[1] ^ key.words[0], low1,
            high0 ^ counter.words[3] ^ key.words[1], low0}}};
}

[[nodiscard]] std::uint64_t combine_words(std::uint32_t high,
                                          std::uint32_t low) noexcept {
  return (static_cast<std::uint64_t>(high) << 32U) | static_cast<std::uint64_t>(low);
}

} // namespace

MasterSeed MasterSeed::from_hex(std::string_view text) {
  if (text.size() != 64U) {
    throw WorkloadSetupError("master seed must contain exactly 64 hexadecimal digits");
  }
  std::array<std::byte, 32> bytes{};
  for (std::size_t index = 0; index < bytes.size(); ++index) {
    const auto high = hex_nibble(text[index * 2U]);
    const auto low = hex_nibble(text[(index * 2U) + 1U]);
    bytes[index] = static_cast<std::byte>((high << 4U) | low);
  }
  return MasterSeed(bytes);
}

std::string_view purpose_label(StreamPurpose purpose) noexcept {
  switch (purpose) {
  case StreamPurpose::event_order:
    return "event-order";
  case StreamPurpose::node_order:
    return "node-order";
  case StreamPurpose::event_payload:
    return "event-payload";
  case StreamPurpose::initial_consumer_state:
    return "initial-consumer-state";
  case StreamPurpose::arrival_schedule:
    return "arrival-schedule";
  }
  return {};
}

PhiloxKey derive_stream_key(const MasterSeed& master_seed, std::string_view name_space,
                            StreamPurpose purpose) {
  if (name_space.empty()) {
    throw WorkloadSetupError("deterministic stream namespace must not be empty");
  }
  const auto purpose_text = purpose_label(purpose);
  if (purpose_text.empty()) {
    throw WorkloadSetupError("deterministic stream purpose is unknown");
  }
  std::vector<std::byte> message;
  message.reserve((4U * sizeof(std::uint64_t)) +
                  kDerivationDomainProtocolVersion.size() + kDeterministicSuite.size() +
                  name_space.size() + purpose_text.size());
  append_field(message, kDerivationDomainProtocolVersion);
  append_field(message, kDeterministicSuite);
  append_field(message, name_space);
  append_field(message, purpose_text);
  const auto digest = hmac_sha256(master_seed.bytes(), message);
  return {{{read_u32_be(digest.data()), read_u32_be(digest.data() + 4U)}}};
}

PhiloxBlock philox4x32_10(std::uint64_t block_ordinal, PhiloxKey key) noexcept {
  PhiloxBlock counter{{{static_cast<std::uint32_t>(block_ordinal >> 32U),
                        static_cast<std::uint32_t>(block_ordinal), 0U, 0U}}};
  for (unsigned int round = 0; round < 10U; ++round) {
    counter = philox_round(counter, key);
    if (round != 9U) {
      key.words[0] += kPhiloxWeyl0;
      key.words[1] += kPhiloxWeyl1;
    }
  }
  return counter;
}

std::uint64_t DeterministicStream::draw(std::uint64_t draw_ordinal) const noexcept {
  const auto block = philox4x32_10(draw_ordinal / 2U, key_);
  if ((draw_ordinal & 1U) == 0U) {
    return combine_words(block.words[0], block.words[1]);
  }
  return combine_words(block.words[2], block.words[3]);
}

std::vector<std::size_t> make_permutation(std::size_t count,
                                          const DeterministicStream& stream) {
  if (count == 0U) {
    throw WorkloadSetupError("permutation cardinality must be nonzero");
  }
  static_assert(sizeof(std::size_t) <= sizeof(std::uint64_t));
  std::vector<std::size_t> result(count);
  for (std::size_t index = 0; index < count; ++index) {
    result[index] = index;
  }

  std::uint64_t draw_ordinal = 0U;
  for (std::size_t remaining = count; remaining > 1U; --remaining) {
    const auto bound = static_cast<std::uint64_t>(remaining);
    const auto threshold = (0U - bound) % bound;
    std::uint64_t draw = 0U;
    do {
      if (draw_ordinal == std::numeric_limits<std::uint64_t>::max()) {
        throw WorkloadSetupError("permutation draw ordinal exhausted");
      }
      draw = stream.draw(draw_ordinal);
      ++draw_ordinal;
    } while (draw < threshold);
    const auto selected = static_cast<std::size_t>(draw % bound);
    std::swap(result[remaining - 1U], result[selected]);
  }
  return result;
}

std::string Sha256Digest::hex() const {
  constexpr std::array<char, 16> digits{'0', '1', '2', '3', '4', '5', '6', '7',
                                        '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};
  std::string result;
  result.reserve(bytes_.size() * 2U);
  for (const auto value : bytes_) {
    const auto byte = std::to_integer<std::uint8_t>(value);
    result.push_back(digits[byte >> 4U]);
    result.push_back(digits[byte & 0x0fU]);
  }
  return result;
}

Sha256Digest sha256(std::span<const std::byte> input) {
  std::array<std::byte, 32> output{};
  std::size_t output_size = 0U;
  const auto success = EVP_Q_digest(
      nullptr, "SHA256", nullptr, reinterpret_cast<const unsigned char*>(input.data()),
      input.size(), reinterpret_cast<unsigned char*>(output.data()), &output_size);
  if (success != 1 || output_size != output.size()) {
    throw WorkloadSetupError("OpenSSL SHA-256 failed");
  }
  return Sha256Digest(output);
}

} // namespace cpu_prefetch::workload
