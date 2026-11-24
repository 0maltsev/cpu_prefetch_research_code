#include "cpu_prefetch/platform/owner_mapping.hpp"
#include "cpu_prefetch/platform/prepared_residency.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <bit>
#include <cerrno>
#include <limits>
#include <linux/mempolicy.h>
#include <thread>

namespace {
using namespace cpu_prefetch;

enum class Call : std::uint8_t {
  page,
  map,
  bind,
  no_huge,
  affinity,
  observe,
  lock,
  read_only,
  unlock,
  unmap,
};

class InjectedOperations final {
public:
  alignas(4096) std::array<std::byte, 8192U> memory;
  std::array<Call, 32U> calls{};
  std::size_t call_count{0U};
  std::optional<std::size_t> failing_call;
  std::int64_t page_bytes{4096};
  std::uint32_t requested_node{std::numeric_limits<std::uint32_t>::max()};
  std::uint32_t requested_cpu{std::numeric_limits<std::uint32_t>::max()};
  platform::OwnerThreadObservation observation{{0, 0}, {8, 0}, {101, 0}, {0, 0},
                                               3,      0,      1,        true};
  std::optional<platform::OwnerThreadObservation> second_observation;
  std::size_t observations{0U};

  InjectedOperations() { memory.fill(std::byte{0xa5}); }

  auto record(Call call) noexcept -> platform::LinuxCallResult {
    calls[call_count++] = call;
    return failing_call == call_count ? platform::LinuxCallResult{-1, EACCES}
                                      : platform::LinuxCallResult{0, 0};
  }
  auto base_page_bytes() noexcept -> platform::LinuxCallResult {
    const auto result = record(Call::page);
    return result.zero_return() ? platform::LinuxCallResult{page_bytes, 0} : result;
  }
  auto map_private(std::size_t) noexcept -> platform::LinuxMappingResult {
    const auto result = record(Call::map);
    return {result.zero_return() ? memory.data() : nullptr, result.error_number};
  }
  auto bind_pages(std::span<std::byte>, std::uint32_t node) noexcept
      -> platform::LinuxCallResult {
    requested_node = node;
    return record(Call::bind);
  }
  auto disable_huge_pages(std::span<std::byte>) noexcept -> platform::LinuxCallResult {
    return record(Call::no_huge);
  }
  auto bind_current_thread(std::uint32_t cpu) noexcept -> platform::LinuxCallResult {
    requested_cpu = cpu;
    return record(Call::affinity);
  }
  auto observe_current_thread(std::uint32_t) noexcept
      -> platform::OwnerThreadObservation {
    const auto result = record(Call::observe);
    ++observations;
    auto value = observations == 2U && second_observation.has_value()
                     ? *second_observation
                     : observation;
    if (!result.zero_return()) {
      value.affinity = result;
    }
    return value;
  }
  auto lock_pages(std::span<std::byte>) noexcept -> platform::LinuxCallResult {
    return record(Call::lock);
  }
  auto protect_read_only(std::span<std::byte>) noexcept -> platform::LinuxCallResult {
    return record(Call::read_only);
  }
  auto unlock_pages(std::span<std::byte>) noexcept -> platform::LinuxCallResult {
    return record(Call::unlock);
  }
  auto unmap(std::span<std::byte>) noexcept -> platform::LinuxCallResult {
    return record(Call::unmap);
  }
};

constexpr platform::OwnerMappingPlan kPlan{8192U, 4096U, 8U, 1U};

TEST(OwnerMapping, ControlsPrecedeOwnerTouchAndEveryActualPageIsPrefaulted) {
  InjectedOperations operations;
  platform::OwnerMapping mapping(kPlan, operations);
  EXPECT_FALSE(mapping.ready());
  EXPECT_TRUE(mapping.mapped_bytes().empty());
  ASSERT_TRUE(mapping.prepare());
  EXPECT_TRUE(mapping.ready());
  EXPECT_EQ(mapping.evidence().stop, platform::OwnerMappingStop::ready);
  EXPECT_EQ(mapping.evidence().requested.owner_cpu, 8U);
  EXPECT_EQ(mapping.evidence().requested.requested_node, 1U);
  EXPECT_EQ(operations.requested_cpu, 8U);
  EXPECT_EQ(operations.requested_node, 1U);
  EXPECT_EQ(mapping.evidence().prefaulted_pages, 2U);
  ASSERT_EQ(operations.call_count, 8U);
  constexpr std::array expected{Call::page,    Call::map,      Call::bind,
                                Call::no_huge, Call::affinity, Call::observe,
                                Call::lock,    Call::observe};
  EXPECT_TRUE(std::equal(expected.begin(), expected.end(), operations.calls.begin()));
  EXPECT_EQ(operations.memory[0U], std::byte{0});
  EXPECT_EQ(operations.memory[4096U], std::byte{0});
  EXPECT_EQ(operations.memory[1U], std::byte{0xa5});
  EXPECT_EQ(operations.memory[8191U], std::byte{0xa5});
  EXPECT_FALSE(mapping.prepare());
  EXPECT_EQ(operations.call_count, 8U);
  ASSERT_TRUE(mapping.protect_read_only());
  EXPECT_FALSE(mapping.protect_read_only());
  EXPECT_EQ(operations.call_count, 9U);
  EXPECT_TRUE(mapping.release());
  EXPECT_FALSE(mapping.ready());
  EXPECT_TRUE(mapping.mapped_bytes().empty());
  EXPECT_EQ(operations.calls[9U], Call::unlock);
  EXPECT_EQ(operations.calls[10U], Call::unmap);
  EXPECT_TRUE(mapping.release());
  EXPECT_EQ(operations.call_count, 11U);
}

TEST(OwnerMapping, InvalidOrMismatchedPageGeometryCannotMapOrTouchMemory) {
  std::array plans{kPlan, kPlan, kPlan, kPlan, kPlan, kPlan};
  plans[0U].bytes = 0U;
  plans[1U].verified_base_page_bytes = 0U;
  plans[2U].verified_base_page_bytes = 3072U;
  plans[3U].bytes = 8191U;
  plans[4U].bytes = std::numeric_limits<std::size_t>::max() - 4095U;
  plans[5U].requested_node = std::numeric_limits<unsigned long>::digits;
  for (const auto plan : plans) {
    InjectedOperations operations;
    platform::OwnerMapping mapping(plan, operations);
    EXPECT_FALSE(mapping.prepare());
    EXPECT_EQ(mapping.evidence().stop, platform::OwnerMappingStop::invalid_plan);
    EXPECT_EQ(operations.call_count, 0U);
    EXPECT_FALSE(mapping.evidence().mapping.has_value());
    EXPECT_TRUE(std::all_of(operations.memory.begin(), operations.memory.end(),
                            [](auto byte) { return byte == std::byte{0xa5}; }));
  }
  InjectedOperations operations;
  operations.page_bytes = 65536;
  platform::OwnerMapping mapping(kPlan, operations);
  EXPECT_FALSE(mapping.prepare());
  EXPECT_EQ(mapping.evidence().stop, platform::OwnerMappingStop::page_geometry_failure);
  const auto actual_page = mapping.evidence().base_page_bytes;
  if (!actual_page.has_value()) {
    FAIL() << "missing actual page observation";
    return;
  }
  EXPECT_EQ(actual_page->return_value, 65536);
  EXPECT_EQ(operations.call_count, 1U);
}

TEST(OwnerMapping, EveryFailedPreparationBoundaryRetainsFactsWithoutRetryOrNextStep) {
  constexpr std::array stops{platform::OwnerMappingStop::page_geometry_failure,
                             platform::OwnerMappingStop::map_failure,
                             platform::OwnerMappingStop::binding_failure,
                             platform::OwnerMappingStop::huge_page_control_failure,
                             platform::OwnerMappingStop::affinity_failure,
                             platform::OwnerMappingStop::owner_readback_failure,
                             platform::OwnerMappingStop::lock_failure,
                             platform::OwnerMappingStop::owner_readback_failure};
  for (std::size_t boundary = 0U; boundary < stops.size(); ++boundary) {
    InjectedOperations operations;
    operations.failing_call = boundary + 1U;
    platform::OwnerMapping mapping(kPlan, operations);
    EXPECT_FALSE(mapping.prepare());
    EXPECT_FALSE(mapping.ready());
    EXPECT_EQ(mapping.evidence().stop, stops[boundary]);
    EXPECT_EQ(operations.call_count, boundary + 1U);
    EXPECT_EQ(mapping.evidence().prefaulted_pages, boundary >= 6U ? 2U : 0U);
    EXPECT_FALSE(mapping.prepare());
    EXPECT_EQ(operations.call_count, boundary + 1U);
    EXPECT_TRUE(mapping.release());
    if (boundary >= 2U) {
      const auto unmapped = mapping.evidence().unmap;
      if (!unmapped.has_value()) {
        FAIL() << "mapped region was not released";
        return;
      }
      EXPECT_TRUE(unmapped->zero_return());
    } else {
      EXPECT_FALSE(mapping.evidence().unmap.has_value());
    }
    EXPECT_EQ(mapping.evidence().unlock.has_value(), boundary == 7U);
  }
}

TEST(OwnerMapping, WrongAffinityCpuThreadOrFaultReadbackCannotBecomeReady) {
  InjectedOperations reference;
  std::array observations{reference.observation, reference.observation,
                          reference.observation, reference.observation,
                          reference.observation, reference.observation};
  observations[0U].affinity_cpu_count = 2;
  observations[1U].requested_cpu_in_affinity = false;
  observations[2U].current_cpu.return_value = 0;
  observations[3U].thread_id.return_value = -1;
  observations[4U].faults = {-1, EPERM};
  observations[5U].minor_faults = -1;
  for (const auto& observation : observations) {
    InjectedOperations operations;
    operations.observation = observation;
    platform::OwnerMapping mapping(kPlan, operations);
    EXPECT_FALSE(mapping.prepare());
    EXPECT_EQ(mapping.evidence().stop,
              platform::OwnerMappingStop::owner_readback_failure);
    EXPECT_EQ(mapping.evidence().prefaulted_pages, 0U);
    EXPECT_FALSE(mapping.evidence().lock.has_value());
  }
  for (const bool changed_thread : {false, true}) {
    InjectedOperations operations;
    auto changed = operations.observation;
    if (changed_thread) {
      changed.thread_id.return_value = 102;
    } else {
      changed.minor_faults = 2;
    }
    operations.second_observation = changed;
    platform::OwnerMapping mapping(kPlan, operations);
    EXPECT_FALSE(mapping.prepare());
    EXPECT_EQ(mapping.evidence().stop,
              platform::OwnerMappingStop::owner_readback_failure);
    EXPECT_EQ(mapping.evidence().prefaulted_pages, 2U);
    ASSERT_TRUE(mapping.evidence().lock.has_value());
    EXPECT_TRUE(mapping.release());
    ASSERT_TRUE(mapping.evidence().unlock.has_value());
  }
}

TEST(OwnerMapping,
     ReadOnlyAndCleanupFailuresRemainDistinctAndCannotRestartPreparation) {
  for (const std::size_t failed_call : {9U, 10U, 11U}) {
    InjectedOperations operations;
    platform::OwnerMapping mapping(kPlan, operations);
    ASSERT_TRUE(mapping.prepare());
    operations.failing_call = failed_call;
    EXPECT_EQ(mapping.protect_read_only(), failed_call != 9U);
    if (failed_call == 9U) {
      EXPECT_EQ(mapping.evidence().stop, platform::OwnerMappingStop::read_only_failure);
      EXPECT_FALSE(mapping.ready());
    }
    EXPECT_EQ(mapping.release(), failed_call == 9U);
    const auto unlock = mapping.evidence().unlock;
    const auto unmap = mapping.evidence().unmap;
    if (!unlock.has_value() || !unmap.has_value()) {
      FAIL() << "cleanup did not retain both syscall results";
      return;
    }
    EXPECT_EQ(unlock->zero_return(), failed_call != 10U);
    EXPECT_EQ(unmap->zero_return(), failed_call != 11U);
    EXPECT_EQ(mapping.mapped_bytes().empty(), failed_call != 11U);
    EXPECT_FALSE(mapping.ready());
    EXPECT_FALSE(mapping.prepare());
    EXPECT_EQ(operations.call_count, 11U);
    EXPECT_EQ(mapping.release(), failed_call == 9U);
    EXPECT_EQ(operations.call_count, 11U);
  }
}

TEST(OwnerMapping, DestructorReleasesOnlyItsOwnMappingAfterPartialPreparation) {
  InjectedOperations operations;
  {
    platform::OwnerMapping mapping(kPlan, operations);
    operations.failing_call = 3U;
    EXPECT_FALSE(mapping.prepare());
  }
  EXPECT_EQ(operations.call_count, 4U);
  EXPECT_EQ(operations.calls[3U], Call::unmap);
  {
    platform::OwnerMapping mapping(kPlan, operations);
    EXPECT_TRUE(mapping.release());
    EXPECT_FALSE(mapping.prepare());
  }
  EXPECT_EQ(operations.call_count, 4U);
}

TEST(OwnerMapping, AcceptedBindingAndLockingDoNotStandInForActualPageResidency) {
  InjectedOperations operations;
  platform::OwnerMapping mapping(kPlan, operations);
  ASSERT_TRUE(mapping.prepare());
  std::array<void*, 2U> pages{};
  std::array<int, 2U> status{};
  platform::PreparedPageResidencyQuery query(mapping.mapped_bytes(), 4096U, pages,
                                             status);
  struct WrongNodeQuery final {
    auto query_pages(std::span<void* const>, std::span<int> nodes) const noexcept
        -> platform::PageResidencyQueryResult {
      std::fill(nodes.begin(), nodes.end(), 0);
      return {0, 0};
    }
  } actual;
  const auto sampled = query.sample(actual);
  EXPECT_TRUE(mapping.ready());
  EXPECT_FALSE(query.all_pages_on(sampled, kPlan.requested_node));
  EXPECT_EQ(status, (std::array<int, 2U>{0, 0}));
}

TEST(OwnerMappingLinux, InvalidInputsAreRejectedWithoutMappingOrChangingAffinity) {
  platform::LinuxOwnerMemoryOperations operations;
  const auto invalid_map = operations.map_private(0U);
  EXPECT_EQ(invalid_map.address, nullptr);
  EXPECT_EQ(invalid_map.error_number, EINVAL);
  EXPECT_EQ(operations.bind_current_thread(std::numeric_limits<std::uint32_t>::max())
                .error_number,
            EINVAL);
  EXPECT_EQ(operations.bind_pages({}, 0U).error_number, EINVAL);
  EXPECT_EQ(operations.disable_huge_pages({}).error_number, EINVAL);
  EXPECT_EQ(operations.lock_pages({}).error_number, EINVAL);
  EXPECT_EQ(operations.protect_read_only({}).error_number, EINVAL);
  EXPECT_EQ(operations.unlock_pages({}).error_number, EINVAL);
  EXPECT_EQ(operations.unmap({}).error_number, EINVAL);
}

TEST(OwnerMappingLinux, NativeMappingHasActualPageGeometryAndIndependentLifecycle) {
  platform::LinuxOwnerMemoryOperations operations;
  const auto page = operations.base_page_bytes();
  ASSERT_TRUE(page.nonnegative_return());
  ASSERT_GT(page.return_value, 0);
  const auto size = static_cast<std::size_t>(page.return_value);
  const auto mapping = operations.map_private(size);
  ASSERT_NE(mapping.address, nullptr);
  ASSERT_EQ(mapping.error_number, 0);
  const std::span bytes(mapping.address, size);
  EXPECT_TRUE(operations.disable_huge_pages(bytes).zero_return());
  bytes[0U] = std::byte{0x73};
  bytes[size - 1U] = std::byte{0x91};
  EXPECT_TRUE(operations.protect_read_only(bytes).zero_return());
  EXPECT_EQ(bytes[0U], std::byte{0x73});
  EXPECT_EQ(bytes[size - 1U], std::byte{0x91});
  EXPECT_EQ(operations.bind_pages(bytes, std::numeric_limits<unsigned long>::digits)
                .error_number,
            EINVAL);
  EXPECT_TRUE(operations.unmap(bytes).zero_return());
}

TEST(OwnerMappingLinux,
     NativeBindRequestPreservesNodeZeroAndEveryMaskBitWithoutMigration) {
  std::array<std::byte, 1U> bytes{};
  constexpr auto bits = std::numeric_limits<unsigned long>::digits;
  for (const auto node : {0U, 1U, static_cast<std::uint32_t>(bits - 1)}) {
    const auto request = platform::linux_owner_binding_request(bytes, node);
    if (!request.has_value()) {
      FAIL() << "valid node cannot form native binding request";
      return;
    }
    EXPECT_EQ(request->bytes.data(), bytes.data());
    EXPECT_EQ(request->bytes.size(), bytes.size());
    EXPECT_EQ(request->policy, MPOL_BIND);
    EXPECT_EQ(request->flags, 0UL);
    EXPECT_EQ(std::popcount(request->node_mask), 1);
    EXPECT_EQ((request->node_mask >> node) & 1UL, 1UL);
    // Independently apply the kernel's import convention: subtract one from
    // maxnode, then copy ceil(bit_count / word_bits) words and mask high bits.
    ASSERT_GT(request->max_node, 0UL);
    const auto imported_bits = request->max_node - 1UL;
    EXPECT_GT(imported_bits, node);
    EXPECT_EQ((imported_bits + bits - 1UL) / bits, 1UL);
  }
  EXPECT_FALSE(platform::linux_owner_binding_request({}, 0U).has_value());
  EXPECT_FALSE(platform::linux_owner_binding_request(bytes, bits).has_value());
}

TEST(OwnerMappingLinux, WorkerCanBindAndReadBackItsActualCpuWithoutAssumingTopology) {
  platform::LinuxOwnerMemoryOperations operations;
  platform::OwnerThreadObservation observed{};
  platform::LinuxCallResult binding{-1, EINVAL};
  std::thread worker([&] {
    const auto entry = operations.observe_current_thread(0U);
    if (!entry.current_cpu.nonnegative_return()) {
      return;
    }
    const auto cpu = static_cast<std::uint32_t>(entry.current_cpu.return_value);
    binding = operations.bind_current_thread(cpu);
    observed = operations.observe_current_thread(cpu);
  });
  worker.join();
  ASSERT_TRUE(binding.zero_return());
  ASSERT_TRUE(observed.current_cpu.nonnegative_return());
  EXPECT_TRUE(
      observed.matches(static_cast<std::uint32_t>(observed.current_cpu.return_value)));
}

} // namespace
