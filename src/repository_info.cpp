#include "cpu_prefetch/foundation/repository_info.hpp"

#include "cpu_prefetch/foundation/build_metadata.hpp"

namespace cpu_prefetch::foundation {

RepositoryInfo repository_info() noexcept {
  return {
      .protocol_version = build_metadata::protocol_version,
      .source_revision = build_metadata::source_revision,
      .source_revision_short = build_metadata::source_revision_short,
      .source_dirty = build_metadata::source_dirty,
      .compiler = build_metadata::compiler,
      .standard_library = build_metadata::standard_library,
  };
}

} // namespace cpu_prefetch::foundation
