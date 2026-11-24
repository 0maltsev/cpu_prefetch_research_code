#include <array>
#include <bit>
#include <climits>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace {
static_assert(CHAR_BIT == 8);
constexpr std::size_t maximum_bytes = 4U * 1024U * 1024U;
constexpr std::size_t maximum_rows = 8192U;

[[maybe_unused]] constexpr auto reverse_bytes(std::uint64_t value) noexcept
    -> std::uint64_t {
  value = ((value & UINT64_C(0x00ff00ff00ff00ff)) << 8U) |
          ((value >> 8U) & UINT64_C(0x00ff00ff00ff00ff));
  value = ((value & UINT64_C(0x0000ffff0000ffff)) << 16U) |
          ((value >> 16U) & UINT64_C(0x0000ffff0000ffff));
  return (value << 32U) | (value >> 32U);
}

auto load_le(const unsigned char* source) noexcept -> std::uint64_t {
  if constexpr (std::endian::native == std::endian::little) {
    std::uint64_t value;
    std::memcpy(&value, source, sizeof(value));
    return value;
  } else if constexpr (std::endian::native == std::endian::big) {
    std::uint64_t value;
    std::memcpy(&value, source, sizeof(value));
    return reverse_bytes(value);
  } else {
    std::uint64_t value = 0U;
    for (unsigned int byte = 0U; byte < 8U; ++byte)
      value |= static_cast<std::uint64_t>(source[byte]) << (byte * 8U);
    return value;
  }
}

void store_le(unsigned char* destination, std::uint64_t value) noexcept {
  if constexpr (std::endian::native == std::endian::little) {
    std::memcpy(destination, &value, sizeof(value));
  } else if constexpr (std::endian::native == std::endian::big) {
    value = reverse_bytes(value);
    std::memcpy(destination, &value, sizeof(value));
  } else {
    for (unsigned int byte = 0U; byte < 8U; ++byte)
      destination[byte] = static_cast<unsigned char>(value >> (byte * 8U));
  }
}

// Eight adjacent columns fill a cache line per row instead of repeatedly
// revisiting one word of each row. State is fixed size, independent of geometry.
template <std::size_t Width>
void inverse_tile(const unsigned char* input, unsigned char* output, std::size_t rows,
                  std::size_t row_bytes) noexcept {
  std::array<std::uint64_t, Width> previous{};
  for (std::size_t row = 0U; row < rows; ++row) {
    for (std::size_t lane = 0U; lane < Width; ++lane) {
      previous[lane] += load_le(input + (lane * rows + row) * 8U);
      store_le(output + row * row_bytes + lane * 8U, previous[lane]);
    }
  }
}
} // namespace

// Cold D233 moddelta8192 inverse. Input and output must name accessible buffers
// of byte_count bytes; alignment is unrestricted. No allocation or I/O occurs.
// Returns 0 on success, 1 for geometry, 2 for null nonempty buffers, 3 for an
// address range that wraps uintptr_t, and 4 for overlapping nonempty ranges.
// Every rejection occurs before any read or write. Empty valid geometry permits
// null buffers. The caller retains responsibility for actual object lifetimes
// and accessible storage; arithmetic validation cannot establish those facts.
extern "C" int cpu_prefetch_archive_inverse_v1(const unsigned char* input,
                                               unsigned char* output,
                                               std::size_t byte_count,
                                               std::size_t row_bytes) noexcept {
  if (row_bytes == 0U || row_bytes % 8U != 0U || row_bytes > maximum_bytes ||
      byte_count > maximum_bytes || byte_count % row_bytes != 0U)
    return 1;
  const auto rows = byte_count / row_bytes;
  if (rows > maximum_rows)
    return 1;
  if (byte_count == 0U)
    return 0;
  if (input == nullptr || output == nullptr)
    return 2;

  const auto source = reinterpret_cast<std::uintptr_t>(input);
  const auto destination = reinterpret_cast<std::uintptr_t>(output);
  constexpr auto maximum_address = std::numeric_limits<std::uintptr_t>::max();
  if (byte_count > maximum_address - source ||
      byte_count > maximum_address - destination)
    return 3;
  if (source < destination + byte_count && destination < source + byte_count)
    return 4;

  if (rows == 1U) {
    std::memcpy(output, input, byte_count);
    return 0;
  }
  const auto columns = row_bytes / 8U;
  std::size_t column = 0U;
  for (; columns - column >= 8U; column += 8U)
    inverse_tile<8U>(input + column * rows * 8U, output + column * 8U, rows, row_bytes);
  for (; column < columns; ++column)
    inverse_tile<1U>(input + column * rows * 8U, output + column * 8U, rows, row_bytes);
  return 0;
}
