#include "cpu_prefetch/platform/prepared_prefetch_readback.hpp"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <unistd.h>

namespace cpu_prefetch::platform {
namespace {

auto observed_call(std::int64_t value) noexcept -> LinuxCallResult {
  return {value, value < 0 ? errno : 0};
}

} // namespace

auto LinuxPrefetchReadbackOperations::identity() -> Result<CpuFamilyModel> {
  return read_x86_family_model();
}

auto LinuxPrefetchReadbackOperations::open_file(const char* path, int flags) noexcept
    -> LinuxCallResult {
  return observed_call(::open(path, flags));
}

auto LinuxPrefetchReadbackOperations::read_at(int descriptor,
                                              std::span<std::byte> bytes,
                                              FileOffset offset) noexcept
    -> LinuxCallResult {
  return observed_call(::pread(descriptor, bytes.data(), bytes.size(),
                               static_cast<off_t>(offset.value)));
}

auto LinuxPrefetchReadbackOperations::close_file(int descriptor) noexcept
    -> LinuxCallResult {
  return observed_call(::close(descriptor));
}

PreparedPrefetchReadback::PreparedPrefetchReadback(
    PrefetchReadbackOperations& operations) noexcept
    : operations_(operations) {
  descriptors_.fill(-1);
}

PreparedPrefetchReadback::~PreparedPrefetchReadback() { static_cast<void>(release()); }

auto PreparedPrefetchReadback::prepare(
    CpuFamilyModel expected_identity,
    std::span<const HardwarePrefetchMsrValue> prestate) -> bool {
  if (preparation_.attempted) {
    return false;
  }
  preparation_.attempted = true;
  preparation_.requested_identity = expected_identity;
  const auto mapping = find_hardware_prefetch_mapping(expected_identity);
  if (!mapping.has_value() || !mapping->control_cpus.has_value() ||
      mapping->control_cpus->empty() ||
      mapping->control_cpus->size() > kPreparedPrefetchMaxCpus) {
    preparation_.stop = PrefetchReadbackPreparationStop::mapping_rejected;
    return false;
  }
  preparation_.mapping_id = mapping->mapping_id;
  preparation_.observed_identity = operations_.identity();
  const auto* observed = preparation_.observed_identity->value_if();
  if (observed == nullptr) {
    preparation_.stop = PrefetchReadbackPreparationStop::identity_failed;
    return false;
  }
  if (*observed != expected_identity) {
    preparation_.stop = PrefetchReadbackPreparationStop::identity_mismatch;
    return false;
  }
  const auto h0 = make_hardware_prefetch_plan(
      *observed, protocol::RequestedHardwareState::h0, prestate);
  const auto h1 = make_hardware_prefetch_plan(
      *observed, protocol::RequestedHardwareState::h1, prestate);
  const auto* h0_plan = h0.value_if();
  const auto* h1_plan = h1.value_if();
  if (h0_plan == nullptr || h1_plan == nullptr) {
    preparation_.resolver_errors = h0.errors();
    preparation_.resolver_errors.insert(preparation_.resolver_errors.end(),
                                        h1.errors().begin(), h1.errors().end());
    preparation_.stop = PrefetchReadbackPreparationStop::prestate_rejected;
    return false;
  }
  preparation_.cpu_count = mapping->control_cpus->size();
  // Resolver results are canonical and use the registered CPU order. Copy all
  // expectations before opening, so partial preparation retains the full plan.
  for (std::size_t index = 0U; index < preparation_.cpu_count; ++index) {
    auto& cpu = preparation_.cpus[index];
    cpu.cpu = h0_plan->requested[index].cpu;
    cpu.expected_h0 = h0_plan->requested[index].value;
    cpu.expected_h1 = h1_plan->requested[index].value;
  }
  for (std::size_t index = 0U; index < preparation_.cpu_count; ++index) {
    auto& cpu = preparation_.cpus[index];
    const auto path = "/dev/cpu/" + std::to_string(cpu.cpu) + "/msr";
    cpu.open = operations_.open_file(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (!cpu.open->nonnegative_return()) {
      preparation_.stop = PrefetchReadbackPreparationStop::open_failed;
      return false;
    }
    descriptors_[index] = static_cast<int>(cpu.open->return_value);
  }
  preparation_.stop = PrefetchReadbackPreparationStop::ready;
  return true;
}

auto PreparedPrefetchReadback::sample(protocol::RequestedHardwareState requested_state,
                                      PrefetchReadbackSample& output) noexcept -> bool {
  if (output.attempted) {
    return false;
  }
  output = {};
  output.attempted = true;
  output.requested_state = requested_state;
  if (preparation_.released ||
      preparation_.stop != PrefetchReadbackPreparationStop::ready) {
    return false;
  }
  if (requested_state != protocol::RequestedHardwareState::h0 &&
      requested_state != protocol::RequestedHardwareState::h1) {
    output.stop = PrefetchReadbackStop::invalid_state;
    return false;
  }
  // No Result/vector copy in this path: preparation verified this exact value.
  if (!preparation_.observed_identity.has_value()) {
    return false;
  }
  const auto* identity = preparation_.observed_identity->value_if();
  if (identity == nullptr) {
    return false;
  }
  output.prepared_controller_identity = *identity;
  output.mapping_id = preparation_.mapping_id;
  output.cpu_count = preparation_.cpu_count;
  bool all_read = true;
  bool all_match = true;
  for (std::size_t index = 0U; index < output.cpu_count; ++index) {
    const auto& prepared = preparation_.cpus[index];
    auto& cpu = output.cpus[index];
    cpu.cpu = prepared.cpu;
    cpu.expected_value = requested_state == protocol::RequestedHardwareState::h0
                             ? prepared.expected_h0
                             : prepared.expected_h1;
    cpu.read = operations_.read_at(descriptors_[index], cpu.raw_bytes,
                                   FileOffset{kHardwarePrefetchMsr});
    const auto read = *cpu.read;
    if (!read.nonnegative_return() ||
        read.return_value != static_cast<std::int64_t>(sizeof(std::uint64_t))) {
      all_read = false;
      all_match = false;
      continue;
    }
    std::uint64_t value{};
    std::memcpy(&value, cpu.raw_bytes.data(), sizeof(value));
    cpu.observed_value = value;
    cpu.matches = value == cpu.expected_value;
    all_match = all_match && cpu.matches;
  }
  output.stop = !all_read ? PrefetchReadbackStop::read_failed
                          : (all_match ? PrefetchReadbackStop::sampled
                                       : PrefetchReadbackStop::value_mismatch);
  return output.succeeded();
}

auto PreparedPrefetchReadback::release() noexcept -> bool {
  preparation_.attempted = true;
  preparation_.released = true;
  bool succeeded = true;
  for (std::size_t index = 0U; index < descriptors_.size(); ++index) {
    auto& cpu = preparation_.cpus[index];
    if (descriptors_[index] >= 0) {
      cpu.close = operations_.close_file(descriptors_[index]);
      // Linux close must not be retried, including EINTR.
      descriptors_[index] = -1;
    }
    if (cpu.close.has_value() && !cpu.close->zero_return()) {
      succeeded = false;
    }
  }
  return succeeded;
}

} // namespace cpu_prefetch::platform
