// Test-only parked native endpoint. No capture, hardware state or run authority.
#include "cpu_prefetch/runner/stage17_s180_channel_sink.hpp"
#include "cpu_prefetch/workload/working_set.hpp"

#include <array>
#include <charconv>
#include <cstdio>
#include <fcntl.h>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace {
using namespace cpu_prefetch;
using namespace runner::stage17;
template <class T> auto integer(std::string_view text) -> T {
  T value{};
  const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
  if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size())
    throw std::invalid_argument("fixture integer");
  return value;
}
struct UnusedOutput final : ArtifactSink {
  auto publish(ArtifactPayload) -> protocol::Result<ArtifactBinding> override {
    throw std::logic_error("fixture must use already published original checkpoint");
  }
};
auto checkpoint(int directory) -> ArtifactBinding {
  constexpr auto name = "s180-e0-checkpoint.json";
  const auto fd = ::openat(directory, name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0)
    throw std::runtime_error("fixture checkpoint open");
  struct Close final {
    int fd;
    ~Close() { static_cast<void>(::close(fd)); }
  } close{fd};
  struct stat before{};
  if (::fstat(fd, &before) != 0 || !S_ISREG(before.st_mode) || before.st_nlink != 1 ||
      before.st_size <= 0 || before.st_size > 131072)
    throw std::runtime_error("fixture checkpoint identity/bound");
  std::vector<std::byte> bytes(static_cast<std::size_t>(before.st_size));
  std::size_t offset = 0U;
  while (offset < bytes.size()) {
    const auto count = ::read(fd, bytes.data() + offset, bytes.size() - offset);
    if (count <= 0)
      throw std::runtime_error("fixture checkpoint read");
    offset += static_cast<std::size_t>(count);
  }
  return {"S180_CAPTURE_CHECKPOINT",
          "cpu-prefetch-stage17-s180-capture-checkpoint/1",
          "application/json",
          name,
          bytes.size(),
          workload::sha256(bytes).hex()};
}
} // namespace
auto main(int argc, char** argv) -> int {
  try {
    if (argc != 6)
      throw std::invalid_argument("fixture arguments");
    UnusedOutput output;
    std::array<std::uint64_t, 180U> intervals{};
    intervals.fill(90'000'000'000U);
    S180ChannelSink sink(
        output,
        {integer<int>(argv[1]), static_cast<int>(::getppid()), argv[3], argv[4]},
        intervals, 131072U);
    const auto original = checkpoint(integer<int>(argv[2]));
    const auto deadline = integer<std::uint64_t>(argv[5]);
    FormalArchiveDeadline guard({deadline});
    const auto result = sink.archive_checkpoint(original, deadline);
    if (!result) {
      static_cast<void>(std::puts("{\"accepted\":false}"));
      return sink.has_archive_checkpoint() ? 3 : 2;
    }
    if (result.value().role != "S180_ARCHIVE_CUSTODY" ||
        result.value().file_name != "s180-e0-archive-custody.json")
      throw std::runtime_error("fixture wrong custody role");
    static_cast<void>(std::puts("{\"accepted\":true}"));
    return 0;
  } catch (const std::exception& error) {
    static_cast<void>(std::fprintf(stderr, "%s\n", error.what()));
    return 1;
  }
}
