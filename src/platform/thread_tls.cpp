#include "cpu_prefetch/platform/thread_tls.hpp"

#include <algorithm>
#include <asm/prctl.h>
#include <cerrno>
#include <link.h>
#include <sys/syscall.h>
#include <unistd.h>

namespace cpu_prefetch::platform {
namespace {

auto call_result(std::int64_t value) noexcept -> LinuxCallResult {
  return {value, value < 0 ? errno : 0};
}

struct Walk final {
  std::span<ThreadTlsModule> output;
  ThreadTlsSnapshot& result;

  auto reject(ThreadTlsStop stop) noexcept -> int {
    result.stop = stop;
    return 1;
  }
  static auto visit(dl_phdr_info* info, std::size_t size, void* context) noexcept
      -> int {
    auto& self = *static_cast<Walk*>(context);
    auto& result = self.result;
    if (size < offsetof(dl_phdr_info, dlpi_tls_data) + sizeof(info->dlpi_tls_data)) {
      return self.reject(ThreadTlsStop::unsupported_loader_abi);
    }
    ++result.visited_objects;
    if (!result.loader_adds.has_value()) {
      result.loader_adds = info->dlpi_adds;
      result.loader_subs = info->dlpi_subs;
    } else if (result.loader_adds != info->dlpi_adds ||
               result.loader_subs != info->dlpi_subs) {
      return self.reject(ThreadTlsStop::loader_changed);
    }
    if (info->dlpi_phnum != 0U && info->dlpi_phdr == nullptr) {
      return self.reject(ThreadTlsStop::invalid_module);
    }
    bool saw_tls = false;
    for (std::size_t index = 0U; index < info->dlpi_phnum; ++index) {
      const auto& header = info->dlpi_phdr[index];
      if (header.p_type != PT_TLS) {
        continue;
      }
      if (saw_tls || info->dlpi_tls_modid == 0U) {
        return self.reject(ThreadTlsStop::invalid_module);
      }
      saw_tls = true;
      if (result.used == self.output.size()) {
        return self.reject(ThreadTlsStop::capacity_exhausted);
      }
      const ThreadTlsModule module{
          info->dlpi_addr, info->dlpi_tls_modid,
          reinterpret_cast<std::uintptr_t>(info->dlpi_tls_data), header.p_memsz};
      self.output[result.used++] = module;
      if (module.address != 0U &&
          module.bytes > std::numeric_limits<std::uintptr_t>::max() - module.address) {
        return self.reject(ThreadTlsStop::invalid_module);
      }
    }
    if (!saw_tls && (info->dlpi_tls_modid != 0U || info->dlpi_tls_data != nullptr)) {
      return self.reject(ThreadTlsStop::invalid_module);
    }
    return 0;
  }
};

auto valid_identity(const ThreadTlsSnapshot& snapshot) noexcept -> bool {
  const auto before = snapshot.thread_before;
  const auto after = snapshot.thread_after;
  const auto fs = snapshot.fs_read;
  return before.has_value() && after.has_value() && fs.has_value() &&
         before->nonnegative_return() && before->return_value > 0 &&
         after->nonnegative_return() && after->return_value == before->return_value &&
         fs->zero_return() && snapshot.fs_base.has_value() && *snapshot.fs_base != 0U;
}

} // namespace

auto observe_thread_tls(std::span<ThreadTlsModule> output) noexcept
    -> ThreadTlsSnapshot {
  ThreadTlsSnapshot result;
  if (output.empty()) {
    return result;
  }
  result.thread_before = call_result(::syscall(SYS_gettid));
  unsigned long base = 0UL;
  const auto fs = call_result(::syscall(SYS_arch_prctl, ARCH_GET_FS, &base));
  result.fs_read = fs;
  if (fs.zero_return()) {
    result.fs_base = base;
  }
  const auto owner = *result.thread_before;
  if (!owner.nonnegative_return() || owner.return_value <= 0 || !fs.zero_return() ||
      base == 0UL) {
    result.stop = ThreadTlsStop::identity_failure;
    return result;
  }
  result.stop = ThreadTlsStop::complete;
  Walk walk{output, result};
  result.iteration_return = ::dl_iterate_phdr(&Walk::visit, &walk);
  result.thread_after = call_result(::syscall(SYS_gettid));
  if (result.stop == ThreadTlsStop::complete && !valid_identity(result)) {
    result.stop = ThreadTlsStop::identity_failure;
  }
  return result;
}

auto same_thread_tls(const ThreadTlsSnapshot& before,
                     std::span<const ThreadTlsModule> before_modules,
                     const ThreadTlsSnapshot& after,
                     std::span<const ThreadTlsModule> after_modules) noexcept -> bool {
  const auto before_owner = before.thread_before;
  const auto after_owner = after.thread_before;
  if (before.stop != ThreadTlsStop::complete || after.stop != ThreadTlsStop::complete ||
      !before_owner.has_value() || !after_owner.has_value() ||
      !valid_identity(before) || !valid_identity(after) ||
      before.iteration_return != 0 || after.iteration_return != 0 ||
      before.used > before_modules.size() || after.used > after_modules.size()) {
    return false;
  }
  return before_owner->return_value == after_owner->return_value &&
         before.fs_base == after.fs_base && before.loader_adds.has_value() &&
         before.loader_subs.has_value() && before.loader_adds == after.loader_adds &&
         before.loader_subs == after.loader_subs &&
         before.visited_objects == after.visited_objects &&
         std::ranges::equal(before_modules.first(before.used),
                            after_modules.first(after.used));
}

} // namespace cpu_prefetch::platform
