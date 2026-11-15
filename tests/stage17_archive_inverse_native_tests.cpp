#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" int cpu_prefetch_archive_inverse_v1(const unsigned char* input,
                                               unsigned char* output,
                                               std::size_t byte_count,
                                               std::size_t row_bytes) noexcept;
static_assert(noexcept(cpu_prefetch_archive_inverse_v1(nullptr, nullptr, 0U, 8U)));

namespace {
using Bytes = std::vector<unsigned char>;
constexpr std::size_t maximum_bytes = 4U * 1024U * 1024U;
std::size_t checks = 0U;

void require(bool condition, const char* message) {
  ++checks;
  if (!condition)
    throw std::runtime_error(message);
}

// Independent oracle uses explicit octets and walks rows, unlike the tiled
// column-wise inverse. Unsigned subtraction defines the forward modulo delta.
auto forward(const Bytes& raw, std::size_t row_bytes) -> Bytes {
  const auto rows = raw.size() / row_bytes;
  const auto columns = row_bytes / 8U;
  std::vector<std::uint64_t> previous(columns, 0U);
  Bytes encoded(raw.size());
  for (std::size_t row = 0U; row < rows; ++row) {
    for (std::size_t column = 0U; column < columns; ++column) {
      std::uint64_t value = 0U;
      for (unsigned int byte = 0U; byte < 8U; ++byte)
        value |= static_cast<std::uint64_t>(raw[row * row_bytes + column * 8U + byte])
                 << (byte * 8U);
      const auto delta = value - previous[column];
      previous[column] = value;
      for (unsigned int byte = 0U; byte < 8U; ++byte)
        encoded[(column * rows + row) * 8U + byte] =
            static_cast<unsigned char>(delta >> (byte * 8U));
    }
  }
  return encoded;
}

auto little_endian_words(const std::vector<std::uint64_t>& words) -> Bytes {
  Bytes bytes;
  bytes.reserve(words.size() * 8U);
  for (auto word : words) {
    for (unsigned int byte = 0U; byte < 8U; ++byte) {
      bytes.push_back(static_cast<unsigned char>(word & UINT64_C(255)));
      word >>= 8U;
    }
  }
  return bytes;
}

// Fixed xorshift state: deterministic, includes all octet values, no dependency
// on a platform's random distribution implementation.
auto random_word() -> std::uint64_t {
  static std::uint64_t state = UINT64_C(0xe259f2d0ca0b173d);
  state ^= state << 13U;
  state ^= state >> 7U;
  state ^= state << 17U;
  return state;
}

auto random_bytes(std::size_t count) -> Bytes {
  Bytes bytes(count);
  for (std::size_t offset = 0U; offset < count; offset += 8U) {
    auto word = random_word();
    for (std::size_t byte = 0U; byte < 8U && offset + byte < count; ++byte) {
      bytes[offset + byte] = static_cast<unsigned char>(word & UINT64_C(255));
      word >>= 8U;
    }
  }
  return bytes;
}

void verify_decode(const Bytes& encoded, const Bytes& expected, std::size_t row_bytes,
                   std::size_t input_offset = 9U, std::size_t output_offset = 11U) {
  Bytes input(encoded.size() + input_offset + 16U, 0x6bU);
  std::copy(encoded.begin(), encoded.end(),
            input.begin() + static_cast<std::ptrdiff_t>(input_offset));
  const auto original = input;
  Bytes output(expected.size() + output_offset + 16U, 0xa5U);
  require(cpu_prefetch_archive_inverse_v1(input.data() + input_offset,
                                          output.data() + output_offset, encoded.size(),
                                          row_bytes) == 0,
          "valid decode rejected");
  require(input == original, "decode changed input");
  require(std::equal(expected.begin(), expected.end(),
                     output.begin() + static_cast<std::ptrdiff_t>(output_offset)),
          "decoded bytes differ from independent oracle");
  require(std::all_of(output.begin(),
                      output.begin() + static_cast<std::ptrdiff_t>(output_offset),
                      [](unsigned char byte) { return byte == 0xa5U; }),
          "output prefix guard changed");
  require(std::all_of(output.begin() +
                          static_cast<std::ptrdiff_t>(output_offset + expected.size()),
                      output.end(), [](unsigned char byte) { return byte == 0xa5U; }),
          "output suffix guard changed");
}

void hand_vectors() {
  // Two columns, three rows. Encoded order is A0,dA1,dA2,B0,dB1,dB2.
  verify_decode(little_endian_words({10U, 2U, UINT64_MAX - 2U, 100U, UINT64_MAX, 8U}),
                little_endian_words({10U, 100U, 12U, 99U, 9U, 107U}), 16U);
  verify_decode(little_endian_words({UINT64_MAX, 1U, UINT64_MAX, 2U}),
                little_endian_words({UINT64_MAX, 0U, UINT64_MAX, 1U}), 8U);
  // Explicit byte vector checks wire endianness without the forward helper.
  verify_decode({0x08U, 0x07U, 0x06U, 0x05U, 0x04U, 0x03U, 0x02U, 0x01U, 0xf9U, 0xf8U,
                 0xf9U, 0xfaU, 0xfbU, 0xfcU, 0xfdU, 0xfeU},
                {0x08U, 0x07U, 0x06U, 0x05U, 0x04U, 0x03U, 0x02U, 0x01U, 0x01U, 0x00U,
                 0x00U, 0x00U, 0x00U, 0x00U, 0x00U, 0x00U},
                8U);
  // These words are opaque payloads, including NaN-like and sign-bit patterns.
  const auto raw = little_endian_words(
      {UINT64_C(0x7ff8000000000001), UINT64_C(0x8000000000000000),
       UINT64_C(0x7ff0000000000000), UINT64_C(0xfff800000000abcd), 0U, UINT64_MAX});
  verify_decode(forward(raw, 16U), raw, 16U);
}

void roundtrips() {
  for (const std::size_t rows : {0U, 1U, 2U, 17U, 8191U, 8192U}) {
    for (const std::size_t columns : {1U, 2U, 7U, 8U, 9U, 15U, 16U, 17U, 64U}) {
      const auto raw = random_bytes(rows * columns * 8U);
      verify_decode(forward(raw, columns * 8U), raw, columns * 8U);
    }
  }
  for (const std::size_t rows : {1U, 2U, 8U, 64U, 8192U}) {
    const auto row_bytes = maximum_bytes / rows;
    const auto raw = random_bytes(maximum_bytes);
    verify_decode(forward(raw, row_bytes), raw, row_bytes);
  }
  for (std::size_t iteration = 0U; iteration < 256U; ++iteration) {
    const auto rows = static_cast<std::size_t>(random_word() % 8193U);
    const auto columns = 1U + static_cast<std::size_t>(random_word() % 64U);
    const auto raw = random_bytes(rows * columns * 8U);
    verify_decode(forward(raw, columns * 8U), raw, columns * 8U,
                  static_cast<std::size_t>(random_word() % 16U),
                  static_cast<std::size_t>(random_word() % 16U));
  }
  for (std::size_t input_offset = 0U; input_offset < 16U; ++input_offset) {
    for (std::size_t output_offset = 0U; output_offset < 16U; ++output_offset) {
      const auto raw = random_bytes(23U * 72U);
      verify_decode(forward(raw, 72U), raw, 72U, input_offset, output_offset);
    }
  }
}

void invalid_inputs() {
  Bytes source(128U, 0x38U);
  Bytes output(128U, 0x97U);
  const auto source_before = source;
  const auto output_before = output;
  const auto reject = [&](const unsigned char* input, unsigned char* destination,
                          std::size_t count, std::size_t row_bytes) {
    require(cpu_prefetch_archive_inverse_v1(input, destination, count, row_bytes) != 0,
            "invalid input accepted");
    require(source == source_before, "rejected call changed source");
    require(output == output_before, "rejected call changed output");
  };
  reject(source.data(), output.data(), 0U, 0U);
  reject(nullptr, nullptr, 0U, 7U);
  reject(nullptr, nullptr, 0U, maximum_bytes + 8U);
  reject(source.data(), output.data(), 8U, 0U);
  reject(source.data(), output.data(), 8U, 7U);
  reject(source.data(), output.data(), 8U, 16U);
  reject(source.data(), output.data(), 17U, 8U);
  reject(source.data(), output.data(), 8193U * 8U, 8U);
  reject(source.data(), output.data(), maximum_bytes + 8U, 8U);
  reject(source.data(), output.data(), maximum_bytes, maximum_bytes + 8U);
  reject(source.data(), output.data(), std::numeric_limits<std::size_t>::max(), 8U);
  reject(source.data(), output.data(), 8U, std::numeric_limits<std::size_t>::max());
  reject(nullptr, output.data(), 8U, 8U);
  reject(source.data(), nullptr, 8U, 8U);
  reject(nullptr, nullptr, 8U, 8U);
  reject(source.data(), source.data(), 64U, 8U);
  reject(source.data(), source.data() + 1U, 64U, 8U);
  reject(source.data() + 1U, source.data(), 64U, 8U);
  reject(source.data(), source.data() + 63U, 64U, 8U);
  reject(source.data() + 63U, source.data(), 64U, 8U);
  constexpr auto top = std::numeric_limits<std::uintptr_t>::max();
  reject(reinterpret_cast<const unsigned char*>(top - 7U), output.data(), 8U, 8U);
  reject(source.data(), reinterpret_cast<unsigned char*>(top - 7U), 8U, 8U);
  reject(reinterpret_cast<const unsigned char*>(top), output.data(), 8U, 8U);
  require(cpu_prefetch_archive_inverse_v1(nullptr, nullptr, 0U, 8U) == 0,
          "null empty decode rejected");
  require(cpu_prefetch_archive_inverse_v1(nullptr, nullptr, 0U, maximum_bytes) == 0,
          "maximum-width empty decode rejected");
  require(cpu_prefetch_archive_inverse_v1(reinterpret_cast<const unsigned char*>(top),
                                          reinterpret_cast<unsigned char*>(top), 0U,
                                          8U) == 0,
          "empty decode dereferenced or validated unused pointers");
}

void adjacent_buffers() {
  const auto raw = random_bytes(19U * 72U);
  const auto encoded = forward(raw, 72U);
  for (const bool output_first : {false, true}) {
    Bytes both(raw.size() * 2U);
    auto* input = both.data() + (output_first ? raw.size() : 0U);
    auto* output = both.data() + (output_first ? 0U : raw.size());
    std::copy(encoded.begin(), encoded.end(), input);
    require(cpu_prefetch_archive_inverse_v1(input, output, raw.size(), 72U) == 0,
            "adjacent non-overlapping buffers rejected");
    require(std::equal(raw.begin(), raw.end(), output), "adjacent output mismatch");
    require(std::equal(encoded.begin(), encoded.end(), input),
            "adjacent input changed");
  }
}
} // namespace

int main() {
  try {
    hand_vectors();
    roundtrips();
    invalid_inputs();
    adjacent_buffers();
    std::cout << "PASS: " << checks << " archive inverse checks\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "FAIL after " << checks << " checks: " << error.what() << '\n';
    return 1;
  }
}
