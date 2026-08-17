#ifndef CPU_PREFETCH_FOUNDATION_REPOSITORY_INFO_HPP
#define CPU_PREFETCH_FOUNDATION_REPOSITORY_INFO_HPP

#include <string_view>

namespace cpu_prefetch::foundation {

struct RepositoryInfo {
  std::string_view protocol_version;
  std::string_view source_revision;
  std::string_view source_revision_short;
  bool source_dirty;
  std::string_view compiler;
  std::string_view standard_library;
};

[[nodiscard]] RepositoryInfo repository_info() noexcept;

} // namespace cpu_prefetch::foundation

#endif
