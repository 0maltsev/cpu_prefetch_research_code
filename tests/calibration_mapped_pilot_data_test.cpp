#include "cpu_prefetch/calibration/mapped_pilot_data.hpp"

#include <gtest/gtest.h>

#include <cerrno>
#include <unistd.h>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
// Real mapping/mprotect/unmap; all placement and locking calls are explicitly
// simulated. These results establish storage/lifetime correctness, NOT NUMA,
// affinity, qualification, native timing or permission to execute a pilot.
struct Memory final {
  platform::LinuxOwnerMemoryOperations native;
  bool fail_bind{false}, fail_protect{false};
  std::size_t unmaps{0U};
  auto base_page_bytes() const noexcept { return native.base_page_bytes(); }
  auto map_private(std::size_t size) const noexcept { return native.map_private(size); }
  auto bind_pages(std::span<std::byte>, std::uint32_t) const noexcept
      -> platform::LinuxCallResult {
    return fail_bind ? platform::LinuxCallResult{-1, EPERM}
                     : platform::LinuxCallResult{0, 0};
  }
  auto disable_huge_pages(std::span<std::byte> bytes) const noexcept {
    return native.disable_huge_pages(bytes);
  }
  auto bind_current_thread(std::uint32_t) const noexcept -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto observe_current_thread(std::uint32_t cpu) const noexcept
      -> platform::OwnerThreadObservation {
    return {{0, 0}, {cpu, 0}, {::gettid(), 0}, {0, 0}, 0, 0, 1, true};
  }
  auto lock_pages(std::span<std::byte>) const noexcept -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto protect_read_only(std::span<std::byte> bytes) const noexcept
      -> platform::LinuxCallResult {
    return fail_protect ? platform::LinuxCallResult{-1, EPERM}
                        : native.protect_read_only(bytes);
  }
  auto unlock_pages(std::span<std::byte>) const noexcept -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto unmap(std::span<std::byte> bytes) noexcept {
    ++unmaps;
    return native.unmap(bytes);
  }
};
auto plan() -> c::MappedPilotDataPlan {
  const auto observed_page = platform::LinuxOwnerMemoryOperations{}.base_page_bytes();
  if (!observed_page.nonnegative_return() || observed_page.return_value <= 0)
    throw std::runtime_error("software test page query failed");
  const auto page = static_cast<std::size_t>(observed_page.return_value);
  return {
      {protocol::Placement::near, protocol::WorkingSetClass::l2_resident},
      {512U, 64U, page, workload::MasterSeed::from_hex(std::string(64U, 'a')),
       "pilot-arena-test"},
      {workload::MasterSeed::from_hex(std::string(64U, 'b')), "pilot-node-test", page},
      0U,
      0U};
}
TEST(MappedPilotData, RetainsOneMappedArenaAndBothQueuesAcrossPairedResets) {
  const auto p = plan();
  c::MappedPilotData<Memory> data(p);
  EXPECT_THROW(static_cast<void>(data.view()), std::logic_error);
  ASSERT_TRUE(data.prepare());
  const auto first = data.view();
  const auto content = first.data->arena().content_checksum();
  const auto nodes = first.data->identity().node_bytes;
  const auto protection = first.mappings[0U]->read_only;
  if (!protection.has_value())
    FAIL() << "missing read-only evidence";
  EXPECT_TRUE(protection->zero_return());
  EXPECT_EQ(first.regions[0U].mapping.size(), data.layout().records_bytes);
  EXPECT_EQ(first.regions[1U].mapping.size(), data.layout().queues_bytes);
  EXPECT_EQ(first.node_order.size(), 513U);
  for (unsigned capture = 0U; capture < 30U; ++capture) {
    const auto pointer =
        queue::EventPointer::from(first.data->arena().select({capture}).record);
    if (!pointer.has_value())
      FAIL() << "invalid event pointer";
    ASSERT_EQ(first.data->ring().try_enqueue(*pointer), queue::EnqueueResult::accepted);
    EXPECT_EQ(first.data->ring().try_dequeue().event, pointer->get());
    ASSERT_TRUE(first.data->ring().reset_quiescent());
    ASSERT_EQ(first.data->linked().try_enqueue(*pointer),
              queue::EnqueueResult::accepted);
    EXPECT_EQ(first.data->linked().try_dequeue().event, pointer->get());
    ASSERT_TRUE(first.data->linked().reset_quiescent());
  }
  const auto after = data.view();
  EXPECT_EQ(after.data, first.data);
  EXPECT_EQ(after.data->identity().node_bytes, nodes);
  EXPECT_EQ(after.data->arena().content_checksum(), content);
  EXPECT_FALSE(data.records_evidence().cleanup_attempted);
  EXPECT_FALSE(data.queues_evidence().cleanup_attempted);
  EXPECT_FALSE(data.prepare());
  EXPECT_TRUE(data.release());
  EXPECT_TRUE(data.release());
  EXPECT_EQ(data.operations(0U).unmaps, 1U);
  EXPECT_EQ(data.operations(1U).unmaps, 1U);
  EXPECT_THROW(static_cast<void>(data.view()), std::logic_error);
  EXPECT_FALSE(data.prepare());
}
TEST(MappedPilotData, OwnershipOrReadOnlyFailureCannotExposeAReadyContext) {
  for (const bool protect : {false, true}) {
    c::MappedPilotData<Memory> data(plan());
    if (protect)
      data.operations(0U).fail_protect = true;
    else
      data.operations(1U).fail_bind = true;
    EXPECT_FALSE(data.prepare());
    EXPECT_FALSE(data.prepare());
    EXPECT_THROW(static_cast<void>(data.view()), std::logic_error);
    EXPECT_TRUE(data.release());
    EXPECT_EQ(data.operations(0U).unmaps, 1U);
    EXPECT_EQ(data.operations(1U).unmaps, 1U);
  }
}
TEST(MappedPilotData, InvalidGeometryAndNamespaceDriftFailCold) {
  auto p = plan();
  p.node_order.seed_namespace = p.arena.seed_namespace;
  EXPECT_THROW(static_cast<void>(c::mapped_pilot_data_layout(p)),
               std::invalid_argument);
  p = plan();
  p.arena.capacity = std::numeric_limits<std::size_t>::max();
  EXPECT_THROW(static_cast<void>(c::mapped_pilot_data_layout(p)),
               std::invalid_argument);
  p = plan();
  p.node_order.arena_alignment_bytes *= 2U;
  EXPECT_THROW(static_cast<void>(c::mapped_pilot_data_layout(p)),
               std::invalid_argument);
  p = plan();
  p.key.placement = protocol::Placement::stage_c_other;
  EXPECT_THROW(static_cast<void>(c::mapped_pilot_data_layout(p)),
               std::invalid_argument);
}
TEST(MappedPilotData, NodeOrderUsesTheExistingGeneratorWithNoRegenerationDuringReset) {
  const auto p = plan();
  c::MappedPilotData<Memory> data(p);
  ASSERT_TRUE(data.prepare());
  const auto view = data.view();
  const workload::NodeOrderPlan expected(
      {p.arena.capacity, 64U, 64U, p.arena.base_page_bytes}, p.node_order.master_seed,
      p.node_order.seed_namespace);
  EXPECT_TRUE(std::equal(view.node_order.begin(), view.node_order.end(),
                         expected.order().begin()));
  EXPECT_EQ(view.node_pattern.transition_count, expected.summary().transition_count);
  EXPECT_EQ(view.node_pattern.modal_nonzero_delta_count,
            expected.summary().modal_nonzero_delta_count);
  EXPECT_EQ(view.node_pattern.shortest_period, p.arena.capacity + 1U);
}
TEST(MappedPilotData, ReleaseBeforePreparationNeverReopensMappings) {
  c::MappedPilotData<Memory> data(plan());
  EXPECT_TRUE(data.release());
  EXPECT_FALSE(data.prepare());
  EXPECT_EQ(data.operations(0U).unmaps, 0U);
  EXPECT_THROW(static_cast<void>(data.view()), std::logic_error);
}
} // namespace
