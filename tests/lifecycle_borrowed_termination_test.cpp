#include "cpu_prefetch/lifecycle/runtime.hpp"

#include <gtest/gtest.h>

#include <array>
#include <limits>
#include <memory>
#include <thread>

namespace {
using cpu_prefetch::lifecycle::TerminationControl;
using cpu_prefetch::queue::QueueSetupError;

TEST(BorrowedTermination, ExactGeometryAndOwnedCompatibility) {
  for (const std::size_t line : {64U, 128U}) {
    cpu_prefetch::queue::detail::AlignedBlock bytes(line, line);
    EXPECT_EQ(TerminationControl::storage_requirements({line}), line);
    TerminationControl borrowed({line}, {bytes.data(), bytes.size()});
    TerminationControl owned({line});
    for (auto* control : {&borrowed, &owned}) {
      EXPECT_FALSE(control->arrivals_finished());
      const auto facts = control->evidence();
      EXPECT_EQ(facts.requested_cache_line_bytes, line);
      EXPECT_TRUE(facts.dedicated_cache_line);
      EXPECT_TRUE(facts.runtime_lock_free);
      control->publish_arrivals_finished();
      EXPECT_TRUE(control->arrivals_finished());
      EXPECT_FALSE(control->reset_quiescent(false));
      EXPECT_TRUE(control->arrivals_finished());
      EXPECT_TRUE(control->reset_quiescent(true));
      EXPECT_FALSE(control->arrivals_finished());
    }
  }
}

TEST(BorrowedTermination,
     RejectsWrongSizeAlignmentAndGeometryBeforeAtomicConstruction) {
  alignas(128) std::array<std::byte, 256U> bytes;
  bytes.fill(std::byte{0x5a});
  const auto original = bytes;
  for (const auto span : {std::span(bytes).first(63U), std::span(bytes).first(65U),
                          std::span(bytes).subspan(1U, 64U), std::span<std::byte>{}}) {
    EXPECT_THROW((TerminationControl({64U}, span)), QueueSetupError);
    EXPECT_EQ(bytes, original);
  }
  for (const auto line : {0U, 3U, 63U}) {
    EXPECT_THROW(static_cast<void>(TerminationControl::storage_requirements({line})),
                 QueueSetupError);
  }
  constexpr auto oversized = std::size_t{1U}
                             << (std::numeric_limits<std::size_t>::digits - 1U);
  EXPECT_THROW(static_cast<void>(TerminationControl::storage_requirements({oversized})),
               QueueSetupError);
}

TEST(BorrowedTermination, RejectsControlObjectOverlappingItsBorrowedLine) {
  alignas(64) std::array<std::byte, 256U> bytes{};
  auto* object = reinterpret_cast<TerminationControl*>(bytes.data());
  EXPECT_THROW(std::construct_at(object, cpu_prefetch::queue::CacheLineBytes{64U},
                                 std::span(bytes).first(64U)),
               QueueSetupError);
}

TEST(BorrowedTermination, DestructionLeavesCallerStorageAndPaddingOwnedByCaller) {
  alignas(64) std::array<std::byte, 64U> bytes;
  bytes.fill(std::byte{0x7b});
  {
    TerminationControl control({64U}, bytes);
    control.publish_arrivals_finished();
  }
  for (std::size_t index = sizeof(std::atomic<std::uint32_t>); index < bytes.size();
       ++index) {
    EXPECT_EQ(bytes[index], std::byte{0x7b});
  }
  // Reconstruct in the same still-live caller bytes after the atomic's lifetime ends.
  TerminationControl again({64U}, bytes);
  EXPECT_FALSE(again.arrivals_finished());
}

TEST(BorrowedTermination, ReleaseAcquirePublishesOwnerDataAcrossTwoResetPhases) {
  alignas(64) std::array<std::byte, 64U> bytes{};
  TerminationControl control({64U}, bytes);
  for (unsigned phase = 1U; phase <= 2U; ++phase) {
    ASSERT_TRUE(control.reset_quiescent(true));
    unsigned payload = 0U;
    unsigned observed = 0U;
    std::thread consumer([&] {
      for (std::size_t poll = 0U; poll < 1'000'000U; ++poll) {
        if (control.arrivals_finished()) {
          observed = payload;
          return;
        }
        std::this_thread::yield();
      }
    });
    payload = phase;
    control.publish_arrivals_finished();
    consumer.join();
    EXPECT_EQ(observed, phase);
  }
}
} // namespace
