#include "cpu_prefetch/platform/linux_inventory.hpp"

#include <sys/utsname.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <charconv>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <system_error>
#include <tuple>
#include <utility>
#include <vector>

namespace cpu_prefetch::platform {
namespace {

[[nodiscard]] auto make_error(ErrorCategory category, std::string path,
                              std::string rule_id, std::string message) -> Error {
  return {category, std::move(path), std::move(rule_id), std::move(message)};
}

[[nodiscard]] auto trim(std::string_view text) -> std::string {
  while (!text.empty() && std::isspace(static_cast<unsigned char>(text.front())) != 0) {
    text.remove_prefix(1U);
  }
  while (!text.empty() && std::isspace(static_cast<unsigned char>(text.back())) != 0) {
    text.remove_suffix(1U);
  }
  return std::string(text);
}

template <typename T>
[[nodiscard]] auto parse_integer(std::string_view text, std::string path,
                                 std::string rule_id) -> Result<T> {
  const auto cleaned = trim(text);
  T value{};
  const auto [end, error] =
      std::from_chars(cleaned.data(), cleaned.data() + cleaned.size(), value);
  if (error != std::errc{} || end != cleaned.data() + cleaned.size()) {
    return Result<T>::failure(make_error(ErrorCategory::parse_error, std::move(path),
                                         std::move(rule_id),
                                         "expected a canonical decimal integer"));
  }
  return Result<T>::success(value);
}

[[nodiscard]] auto required_file(const LinuxSnapshot& snapshot, std::string_view path)
    -> Result<std::string> {
  const auto iterator = snapshot.files.find(path);
  if (iterator == snapshot.files.end()) {
    return Result<std::string>::failure(make_error(
        ErrorCategory::missing_evidence, std::string(path), "PLT-LINUX-REQUIRED-FILE",
        "required Linux inventory evidence is unavailable"));
  }
  return Result<std::string>::success(trim(iterator->second));
}

[[nodiscard]] auto optional_file(const LinuxSnapshot& snapshot, std::string_view path)
    -> std::optional<std::string> {
  const auto iterator = snapshot.files.find(path);
  if (iterator == snapshot.files.end()) {
    return std::nullopt;
  }
  return trim(iterator->second);
}

[[nodiscard]] auto cpuinfo_value(std::string_view cpuinfo, const char* key)
    -> std::optional<std::string> {
  std::istringstream input{std::string(cpuinfo)};
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) {
      break;
    }
    const auto colon = line.find(':');
    if (colon == std::string::npos) {
      continue;
    }
    if (trim(std::string_view(line).substr(0U, colon)) == key) {
      return trim(std::string_view(line).substr(colon + 1U));
    }
  }
  return std::nullopt;
}

[[nodiscard]] auto cache_size_bytes(std::string_view text, std::string path)
    -> Result<std::uint64_t> {
  const auto cleaned = trim(text);
  if (cleaned.empty()) {
    return Result<std::uint64_t>::failure(make_error(ErrorCategory::parse_error,
                                                     std::move(path), "PLT-CACHE-SIZE",
                                                     "cache size must not be empty"));
  }
  std::uint64_t multiplier = 1U;
  auto number = std::string_view(cleaned);
  const auto suffix = cleaned.back();
  if (suffix == 'K' || suffix == 'k') {
    multiplier = 1024U;
    number.remove_suffix(1U);
  } else if (suffix == 'M' || suffix == 'm') {
    multiplier = std::uint64_t{1024U} * 1024U;
    number.remove_suffix(1U);
  } else if (suffix == 'G' || suffix == 'g') {
    multiplier = std::uint64_t{1024U} * 1024U * 1024U;
    number.remove_suffix(1U);
  }
  auto parsed = parse_integer<std::uint64_t>(number, std::move(path), "PLT-CACHE-SIZE");
  if (!parsed) {
    return parsed;
  }
  if (parsed.value() > std::numeric_limits<std::uint64_t>::max() / multiplier) {
    return Result<std::uint64_t>::failure(
        make_error(ErrorCategory::parse_error, "$inventory/cache", "PLT-CACHE-SIZE",
                   "cache size overflows uint64 bytes"));
  }
  return Result<std::uint64_t>::success(parsed.value() * multiplier);
}

[[nodiscard]] auto source_value(const LinuxSnapshot& snapshot, std::string name,
                                const std::string& source) -> EvidenceValue {
  return {std::move(name), source, optional_file(snapshot, source)};
}

[[nodiscard]] auto combine_optional(const LinuxSnapshot& snapshot,
                                    std::span<const std::string_view> paths)
    -> std::optional<std::string> {
  std::string combined;
  for (const auto path : paths) {
    const auto value = optional_file(snapshot, path);
    if (!value.has_value()) {
      continue;
    }
    if (!combined.empty()) {
      combined += ';';
    }
    combined += std::string(path) + '=' + *value;
  }
  if (combined.empty()) {
    return std::nullopt;
  }
  return combined;
}

[[nodiscard]] auto compiler_identity() -> std::string {
#if defined(__clang__)
  return std::string("Clang ") + __clang_version__;
#elif defined(__GNUC__)
  return std::string("GCC ") + __VERSION__;
#else
  return "unsupported-compiler";
#endif
}

[[nodiscard]] auto standard_library_identity() -> std::string {
#if defined(_LIBCPP_VERSION)
  return "libc++ " + std::to_string(_LIBCPP_VERSION);
#elif defined(__GLIBCXX__)
  return "libstdc++ " + std::to_string(__GLIBCXX__);
#else
  return "unsupported-standard-library";
#endif
}

[[nodiscard]] auto read_text_file(const std::filesystem::path& path)
    -> std::optional<std::string> {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  std::ostringstream output;
  output << input.rdbuf();
  if (input.bad()) {
    return std::nullopt;
  }
  return output.str();
}

void collect_file(LinuxSnapshot& snapshot, const std::filesystem::path& path) {
  const auto value = read_text_file(path);
  if (value.has_value()) {
    snapshot.files.emplace(path.string(), *value);
  }
}

[[nodiscard]] auto directory_names(const std::filesystem::path& parent,
                                   std::string_view prefix)
    -> std::vector<std::filesystem::path> {
  std::vector<std::filesystem::path> output;
  std::error_code error;
  for (std::filesystem::directory_iterator iterator(parent, error), end;
       !error && iterator != end; iterator.increment(error)) {
    const auto name = iterator->path().filename().string();
    if (name.starts_with(prefix)) {
      output.push_back(iterator->path());
    }
  }
  std::sort(output.begin(), output.end());
  return output;
}

} // namespace

auto parse_cpu_list(std::string_view text, std::string path)
    -> Result<std::vector<std::uint32_t>> {
  const auto cleaned = trim(text);
  if (cleaned.empty()) {
    return Result<std::vector<std::uint32_t>>::success({});
  }
  std::set<std::uint32_t> values;
  std::size_t start = 0U;
  while (start < cleaned.size()) {
    const auto comma = cleaned.find(',', start);
    const auto end = comma == std::string::npos ? cleaned.size() : comma;
    const auto token = std::string_view(cleaned).substr(start, end - start);
    const auto dash = token.find('-');
    auto first = parse_integer<std::uint32_t>(
        dash == std::string_view::npos ? token : token.substr(0U, dash), path,
        "PLT-CPU-LIST");
    if (!first) {
      return Result<std::vector<std::uint32_t>>::failure(first.errors());
    }
    auto last = first.value();
    if (dash != std::string_view::npos) {
      auto parsed_last =
          parse_integer<std::uint32_t>(token.substr(dash + 1U), path, "PLT-CPU-LIST");
      if (!parsed_last) {
        return Result<std::vector<std::uint32_t>>::failure(parsed_last.errors());
      }
      last = parsed_last.value();
    }
    if (last < first.value()) {
      return Result<std::vector<std::uint32_t>>::failure(
          make_error(ErrorCategory::parse_error, std::move(path), "PLT-CPU-LIST-RANGE",
                     "CPU-list range ends before it starts"));
    }
    for (std::uint64_t value = first.value(); value <= last; ++value) {
      if (!values.insert(static_cast<std::uint32_t>(value)).second) {
        return Result<std::vector<std::uint32_t>>::failure(make_error(
            ErrorCategory::parse_error, std::move(path), "PLT-CPU-LIST-DUPLICATE",
            "CPU list contains a duplicate logical CPU"));
      }
    }
    start = end + 1U;
  }
  return Result<std::vector<std::uint32_t>>::success(
      std::vector<std::uint32_t>(values.begin(), values.end()));
}

auto parse_linux_snapshot(const LinuxSnapshot& snapshot) -> Result<PlatformInventory> {
  std::vector<Error> errors;
  if (snapshot.snapshot_id.empty()) {
    errors.push_back(make_error(ErrorCategory::missing_evidence, "$snapshot/id",
                                "PLT-SNAPSHOT-ID", "snapshot ID is required"));
  }
  if (snapshot.captured_at_utc.empty()) {
    errors.push_back(make_error(ErrorCategory::missing_evidence,
                                "$snapshot/captured_at_utc", "PLT-SNAPSHOT-TIME",
                                "explicit capture time is required"));
  }
  if (snapshot.kernel_release.empty()) {
    errors.push_back(make_error(ErrorCategory::missing_evidence, "$snapshot/kernel",
                                "PLT-SNAPSHOT-KERNEL", "kernel release is required"));
  }

  auto online_text = required_file(snapshot, "/sys/devices/system/cpu/online");
  auto cpuinfo = required_file(snapshot, "/proc/cpuinfo");
  auto page_size = required_file(snapshot, "runtime/base_page_bytes");
  if (!online_text) {
    errors.insert(errors.end(), online_text.errors().begin(),
                  online_text.errors().end());
  }
  if (!cpuinfo) {
    errors.insert(errors.end(), cpuinfo.errors().begin(), cpuinfo.errors().end());
  }
  if (!page_size) {
    errors.insert(errors.end(), page_size.errors().begin(), page_size.errors().end());
  }
  if (!errors.empty()) {
    return Result<PlatformInventory>::failure(std::move(errors));
  }
  auto online = parse_cpu_list(online_text.value(), "$snapshot/cpu/online");
  auto base_page = parse_integer<std::uint64_t>(
      page_size.value(), "$snapshot/memory/base_page_bytes", "PLT-BASE-PAGE");
  if (!online) {
    errors.insert(errors.end(), online.errors().begin(), online.errors().end());
  }
  if (!base_page) {
    errors.insert(errors.end(), base_page.errors().begin(), base_page.errors().end());
  }
  if (!errors.empty() || online.value().empty()) {
    if (errors.empty()) {
      errors.push_back(make_error(ErrorCategory::missing_evidence,
                                  "$snapshot/cpu/online", "PLT-ONLINE-CPU",
                                  "at least one online CPU is required"));
    }
    return Result<PlatformInventory>::failure(std::move(errors));
  }

  std::map<std::uint32_t, std::uint32_t> cpu_to_node;
  std::vector<NumaNode> numa_nodes;
  constexpr std::string_view node_prefix = "/sys/devices/system/node/node";
  constexpr std::string_view node_suffix = "/cpulist";
  for (const auto& [path, value] : snapshot.files) {
    if (!path.starts_with(node_prefix) || !path.ends_with(node_suffix)) {
      continue;
    }
    const auto id_text = std::string_view(path).substr(
        node_prefix.size(), path.size() - node_prefix.size() - node_suffix.size());
    auto node_id = parse_integer<std::uint32_t>(id_text, path, "PLT-NODE-ID");
    auto cpus = parse_cpu_list(value, path);
    if (!node_id || !cpus) {
      if (!node_id) {
        errors.insert(errors.end(), node_id.errors().begin(), node_id.errors().end());
      }
      if (!cpus) {
        errors.insert(errors.end(), cpus.errors().begin(), cpus.errors().end());
      }
      continue;
    }
    for (const auto cpu : cpus.value()) {
      if (!cpu_to_node.emplace(cpu, node_id.value()).second) {
        errors.push_back(make_error(ErrorCategory::parse_error, path,
                                    "PLT-NODE-MEMBERSHIP",
                                    "logical CPU belongs to multiple NUMA nodes"));
      }
    }
    numa_nodes.push_back({node_id.value(), cpus.value()});
  }
  std::sort(numa_nodes.begin(), numa_nodes.end(),
            [](const NumaNode& left, const NumaNode& right) {
              return left.node_id < right.node_id;
            });
  if (numa_nodes.empty()) {
    errors.push_back(make_error(ErrorCategory::missing_evidence,
                                "$snapshot/topology/numa", "PLT-NUMA-TOPOLOGY",
                                "NUMA topology must be read rather than inferred"));
  }

  struct CacheKey final {
    std::uint32_t level;
    std::string kind;
    std::vector<std::uint32_t> cpus;
    auto operator<(const CacheKey& other) const -> bool {
      return std::tie(level, kind, cpus) <
             std::tie(other.level, other.kind, other.cpus);
    }
  };
  std::map<CacheKey, std::uint64_t> cache_map;
  std::uint32_t last_level = 0U;
  std::optional<std::uint64_t> cache_line_bytes;
  for (const auto cpu_id : online.value()) {
    const auto cpu_root = "/sys/devices/system/cpu/cpu" + std::to_string(cpu_id);
    const auto cache_root = cpu_root + "/cache/";
    for (const auto& [path, ignored] : snapshot.files) {
      static_cast<void>(ignored);
      if (!path.starts_with(cache_root) || !path.ends_with("/level")) {
        continue;
      }
      const auto index_root =
          path.substr(0U, path.size() - std::string("/level").size());
      auto level_text = required_file(snapshot, index_root + "/level");
      auto kind = required_file(snapshot, index_root + "/type");
      auto shared_text = required_file(snapshot, index_root + "/shared_cpu_list");
      auto size_text = required_file(snapshot, index_root + "/size");
      auto line_text = required_file(snapshot, index_root + "/coherency_line_size");
      if (!level_text || !kind || !shared_text || !size_text || !line_text) {
        for (const auto* result :
             {&level_text, &kind, &shared_text, &size_text, &line_text}) {
          if (!*result) {
            errors.insert(errors.end(), result->errors().begin(),
                          result->errors().end());
          }
        }
        continue;
      }
      auto level = parse_integer<std::uint32_t>(level_text.value(), index_root,
                                                "PLT-CACHE-LEVEL");
      auto shared = parse_cpu_list(shared_text.value(), index_root);
      auto size = cache_size_bytes(size_text.value(), index_root);
      auto line =
          parse_integer<std::uint64_t>(line_text.value(), index_root, "PLT-CACHE-LINE");
      if (!level || !shared || !size || !line) {
        if (!level) {
          errors.insert(errors.end(), level.errors().begin(), level.errors().end());
        }
        if (!shared) {
          errors.insert(errors.end(), shared.errors().begin(), shared.errors().end());
        }
        if (!size) {
          errors.insert(errors.end(), size.errors().begin(), size.errors().end());
        }
        if (!line) {
          errors.insert(errors.end(), line.errors().begin(), line.errors().end());
        }
        continue;
      }
      const auto normalized_kind = trim(kind.value());
      if (normalized_kind == "Data" || normalized_kind == "Unified") {
        last_level = std::max(last_level, level.value());
      }
      const CacheKey key{level.value(), normalized_kind, shared.value()};
      const auto [position, inserted] = cache_map.emplace(key, size.value());
      if (!inserted && position->second != size.value()) {
        errors.push_back(make_error(ErrorCategory::parse_error, index_root,
                                    "PLT-CACHE-CONSISTENCY",
                                    "one cache domain has inconsistent sizes"));
      }
      if (cache_line_bytes.has_value() && *cache_line_bytes != line.value()) {
        errors.push_back(make_error(ErrorCategory::parse_error, index_root,
                                    "PLT-CACHE-LINE-CONSISTENCY",
                                    "cache-line size differs across observed caches"));
      }
      cache_line_bytes = line.value();
    }
  }
  if (cache_map.empty() || !cache_line_bytes.has_value()) {
    errors.push_back(make_error(ErrorCategory::missing_evidence,
                                "$snapshot/topology/cache", "PLT-CACHE-TOPOLOGY",
                                "cache domains and coherency line size are required"));
  }

  std::vector<CacheDomain> cache_domains;
  std::map<CacheKey, std::string> cache_ids;
  for (const auto& [key, size] : cache_map) {
    std::string id = "L" + std::to_string(key.level) + ":" + key.kind + ":";
    for (std::size_t index = 0U; index < key.cpus.size(); ++index) {
      if (index != 0U) {
        id += ',';
      }
      id += std::to_string(key.cpus[index]);
    }
    cache_ids.emplace(key, id);
    cache_domains.push_back(
        {id, key.level, key.kind, size, key.cpus,
         key.level == last_level && (key.kind == "Data" || key.kind == "Unified")});
  }

  std::vector<LogicalCpu> logical_cpus;
  for (const auto cpu_id : online.value()) {
    const auto cpu_root = "/sys/devices/system/cpu/cpu" + std::to_string(cpu_id);
    auto core_text = required_file(snapshot, cpu_root + "/topology/core_id");
    auto package_text =
        required_file(snapshot, cpu_root + "/topology/physical_package_id");
    auto sibling_text =
        required_file(snapshot, cpu_root + "/topology/thread_siblings_list");
    if (!core_text || !package_text || !sibling_text) {
      for (const auto* result : {&core_text, &package_text, &sibling_text}) {
        if (!*result) {
          errors.insert(errors.end(), result->errors().begin(), result->errors().end());
        }
      }
      continue;
    }
    auto core =
        parse_integer<std::uint32_t>(core_text.value(), cpu_root, "PLT-CORE-ID");
    auto package =
        parse_integer<std::uint32_t>(package_text.value(), cpu_root, "PLT-PACKAGE-ID");
    auto siblings = parse_cpu_list(sibling_text.value(), cpu_root);
    const auto node = cpu_to_node.find(cpu_id);
    if (!core || !package || !siblings || node == cpu_to_node.end()) {
      if (!core) {
        errors.insert(errors.end(), core.errors().begin(), core.errors().end());
      }
      if (!package) {
        errors.insert(errors.end(), package.errors().begin(), package.errors().end());
      }
      if (!siblings) {
        errors.insert(errors.end(), siblings.errors().begin(), siblings.errors().end());
      }
      if (node == cpu_to_node.end()) {
        errors.push_back(make_error(ErrorCategory::missing_evidence, cpu_root,
                                    "PLT-CPU-NODE",
                                    "online CPU has no NUMA-node readback"));
      }
      continue;
    }
    std::vector<std::string> domains;
    for (const auto& [key, id] : cache_ids) {
      if (std::binary_search(key.cpus.begin(), key.cpus.end(), cpu_id)) {
        domains.push_back(id);
      }
    }
    logical_cpus.push_back({cpu_id, core.value(), package.value(), node->second,
                            siblings.value(), std::move(domains), true});
  }

  const auto vendor = cpuinfo_value(cpuinfo.value(), "vendor_id");
  const auto model = cpuinfo_value(cpuinfo.value(), "model name");
  const auto stepping = cpuinfo_value(cpuinfo.value(), "stepping");
  const auto microcode = cpuinfo_value(cpuinfo.value(), "microcode");
  if (!vendor || !model || !stepping || !microcode) {
    errors.push_back(make_error(ErrorCategory::missing_evidence, "$snapshot/cpuinfo",
                                "PLT-CPU-IDENTITY",
                                "vendor, model, stepping, and microcode are required"));
  }

  std::vector<PciDevice> pci_devices;
  constexpr std::string_view pci_prefix = "/sys/bus/pci/devices/";
  constexpr std::string_view vendor_suffix = "/vendor";
  for (const auto& [path, value] : snapshot.files) {
    if (!path.starts_with(pci_prefix) || !path.ends_with(vendor_suffix)) {
      continue;
    }
    const auto address = path.substr(
        pci_prefix.size(), path.size() - pci_prefix.size() - vendor_suffix.size());
    const auto root = std::string(pci_prefix) + address;
    const auto device = optional_file(snapshot, root + "/device");
    const auto device_class = optional_file(snapshot, root + "/class");
    if (!device || !device_class) {
      continue;
    }
    std::optional<std::int32_t> node;
    if (const auto node_text = optional_file(snapshot, root + "/numa_node")) {
      auto parsed_node = parse_integer<std::int32_t>(*node_text, root, "PLT-PCI-NODE");
      if (!parsed_node) {
        errors.insert(errors.end(), parsed_node.errors().begin(),
                      parsed_node.errors().end());
      } else {
        node = parsed_node.value();
      }
    }
    std::vector<std::uint32_t> local_cpus;
    if (const auto local_text = optional_file(snapshot, root + "/local_cpulist")) {
      auto parsed_cpus = parse_cpu_list(*local_text, root);
      if (!parsed_cpus) {
        errors.insert(errors.end(), parsed_cpus.errors().begin(),
                      parsed_cpus.errors().end());
      } else {
        local_cpus = std::move(parsed_cpus).value();
      }
    }
    pci_devices.push_back(
        {address, trim(value), *device, *device_class, node, std::move(local_cpus)});
  }

  if (!errors.empty()) {
    return Result<PlatformInventory>::failure(std::move(errors));
  }

  std::atomic<void*> atomic_pointer;
  const auto firmware = combine_optional(
      snapshot, std::array<std::string_view, 4>{
                    "/sys/class/dmi/id/bios_vendor", "/sys/class/dmi/id/bios_version",
                    "/sys/class/dmi/id/bios_date", "/sys/class/dmi/id/product_name"});
  const auto cpufreq = combine_optional(
      snapshot, std::array<std::string_view, 2>{
                    "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor",
                    "/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq"});
  const auto turbo = combine_optional(
      snapshot,
      std::array<std::string_view, 2>{"/sys/devices/system/cpu/intel_pstate/no_turbo",
                                      "/sys/devices/system/cpu/cpufreq/boost"});
  const auto cpuidle = combine_optional(
      snapshot, std::array<std::string_view, 2>{
                    "/sys/devices/system/cpu/cpuidle/current_driver",
                    "/sys/devices/system/cpu/cpuidle/current_governor_ro"});
  const auto smt = combine_optional(
      snapshot, std::array<std::string_view, 2>{"/sys/devices/system/cpu/smt/active",
                                                "/sys/devices/system/cpu/smt/control"});
  const auto isolation = combine_optional(
      snapshot, std::array<std::string_view, 3>{"/sys/devices/system/cpu/isolated",
                                                "/sys/devices/system/cpu/nohz_full",
                                                "/proc/cmdline"});
  const auto huge_pages = combine_optional(
      snapshot, std::array<std::string_view, 2>{
                    "/sys/kernel/mm/transparent_hugepage/enabled", "/proc/meminfo"});
  std::vector<EvidenceValue> observations{
      {"firmware", "dmi-sysfs", firmware},
      {"cpufreq", "cpufreq-sysfs", cpufreq},
      {"turbo", "platform-turbo-sysfs", turbo},
      {"cpuidle", "cpuidle-sysfs", cpuidle},
      {"smt", "smt-sysfs", smt},
      source_value(snapshot, "interrupt_affinity", "/proc/irq/default_smp_affinity"),
      {"cpu_isolation", "sysfs+kernel-cmdline", isolation},
      source_value(snapshot, "clock_source",
                   "/sys/devices/system/clocksource/clocksource0/current_clocksource"),
      {"huge_pages", "thp-sysfs+proc-meminfo", huge_pages},
      source_value(snapshot, "memory_population", "/proc/meminfo"),
  };

  return Result<PlatformInventory>::success(PlatformInventory{
      snapshot.snapshot_id,
      snapshot.captured_at_utc,
      {*vendor, *model, *stepping, *microcode, *cache_line_bytes, sizeof(void*) * 8U,
       alignof(std::atomic<void*>), atomic_pointer.is_lock_free()},
      {"Linux", snapshot.kernel_release, compiler_identity(),
       standard_library_identity(), "C++20"},
      base_page.value(),
      std::move(logical_cpus),
      std::move(cache_domains),
      std::move(numa_nodes),
      std::move(pci_devices),
      std::move(observations),
  });
}

auto LinuxInventoryProvider::collect(std::string snapshot_id,
                                     std::string captured_at_utc) const
    -> Result<PlatformInventory> {
  if (snapshot_id.empty() || captured_at_utc.empty()) {
    return Result<PlatformInventory>::failure(make_error(
        ErrorCategory::missing_evidence, "$inventory", "PLT-INVENTORY-CONTEXT",
        "caller must supply explicit snapshot identity and capture time"));
  }
  utsname kernel{};
  if (::uname(&kernel) != 0) {
    return Result<PlatformInventory>::failure(
        make_error(ErrorCategory::io_error, "$inventory/kernel", "PLT-UNAME",
                   "uname failed while collecting the read-only inventory"));
  }
  const auto page_size = ::sysconf(_SC_PAGESIZE);
  if (page_size <= 0) {
    return Result<PlatformInventory>::failure(
        make_error(ErrorCategory::io_error, "$inventory/base_page_bytes",
                   "PLT-PAGE-SIZE", "sysconf(_SC_PAGESIZE) failed"));
  }

  LinuxSnapshot snapshot{
      std::move(snapshot_id), std::move(captured_at_utc), kernel.release, {}};
  collect_file(snapshot, "/proc/cpuinfo");
  collect_file(snapshot, "/proc/meminfo");
  collect_file(snapshot, "/proc/cmdline");
  collect_file(snapshot, "/proc/irq/default_smp_affinity");
  snapshot.files.emplace("runtime/base_page_bytes", std::to_string(page_size));

  constexpr std::array<std::string_view, 16> global_files{
      "/sys/devices/system/cpu/online",
      "/sys/devices/system/cpu/isolated",
      "/sys/devices/system/cpu/nohz_full",
      "/sys/devices/system/cpu/smt/active",
      "/sys/devices/system/cpu/smt/control",
      "/sys/devices/system/cpu/cpuidle/current_driver",
      "/sys/devices/system/cpu/cpuidle/current_governor_ro",
      "/sys/devices/system/cpu/intel_pstate/no_turbo",
      "/sys/devices/system/cpu/cpufreq/boost",
      "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor",
      "/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq",
      "/sys/devices/system/clocksource/clocksource0/current_clocksource",
      "/sys/kernel/mm/transparent_hugepage/enabled",
      "/sys/class/dmi/id/bios_vendor",
      "/sys/class/dmi/id/bios_version",
      "/sys/class/dmi/id/bios_date",
  };
  for (const auto path : global_files) {
    collect_file(snapshot, path);
  }
  collect_file(snapshot, "/sys/class/dmi/id/product_name");

  const auto online_text = optional_file(snapshot, "/sys/devices/system/cpu/online");
  if (online_text.has_value()) {
    const auto online = parse_cpu_list(*online_text, "$inventory/cpu/online");
    if (online) {
      for (const auto cpu : online.value()) {
        const auto root = std::filesystem::path("/sys/devices/system/cpu") /
                          ("cpu" + std::to_string(cpu));
        collect_file(snapshot, root / "topology/core_id");
        collect_file(snapshot, root / "topology/physical_package_id");
        collect_file(snapshot, root / "topology/thread_siblings_list");
        for (const auto& index : directory_names(root / "cache", "index")) {
          collect_file(snapshot, index / "level");
          collect_file(snapshot, index / "type");
          collect_file(snapshot, index / "shared_cpu_list");
          collect_file(snapshot, index / "size");
          collect_file(snapshot, index / "coherency_line_size");
        }
      }
    }
  }
  for (const auto& node : directory_names("/sys/devices/system/node", "node")) {
    collect_file(snapshot, node / "cpulist");
  }
  for (const auto& device : directory_names("/sys/bus/pci/devices", "")) {
    collect_file(snapshot, device / "vendor");
    collect_file(snapshot, device / "device");
    collect_file(snapshot, device / "class");
    collect_file(snapshot, device / "numa_node");
    collect_file(snapshot, device / "local_cpulist");
  }
  return parse_linux_snapshot(snapshot);
}

} // namespace cpu_prefetch::platform
