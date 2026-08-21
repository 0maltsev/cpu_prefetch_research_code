#ifndef CPU_PREFETCH_PLATFORM_LINUX_INVENTORY_HPP
#define CPU_PREFETCH_PLATFORM_LINUX_INVENTORY_HPP

#include <map>
#include <string>
#include <string_view>

#include "cpu_prefetch/platform/platform.hpp"

namespace cpu_prefetch::platform {

struct LinuxSnapshot final {
  std::string snapshot_id;
  std::string captured_at_utc;
  std::string kernel_release;
  std::map<std::string, std::string, std::less<>> files;
};

[[nodiscard]] auto parse_cpu_list(std::string_view text, std::string path)
    -> Result<std::vector<std::uint32_t>>;
[[nodiscard]] auto parse_linux_snapshot(const LinuxSnapshot& snapshot)
    -> Result<PlatformInventory>;

class LinuxInventoryProvider final {
public:
  // This operation only reads procfs/sysfs and process-local runtime facts. The
  // caller supplies identity/time; neither is inferred from a filesystem path.
  [[nodiscard]] auto collect(std::string snapshot_id, std::string captured_at_utc) const
      -> Result<PlatformInventory>;
};

} // namespace cpu_prefetch::platform

#endif // CPU_PREFETCH_PLATFORM_LINUX_INVENTORY_HPP
