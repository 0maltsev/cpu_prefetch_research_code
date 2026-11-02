#include "cpu_prefetch/platform/thread_tls.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cerrno>

namespace {
using namespace cpu_prefetch;

// Software fixture capacity, not a prospective stand resource budget.
using Modules = std::array<platform::ThreadTlsModule, 128U>;
thread_local std::array<std::byte, 256U> anchor{};

auto covers(std::span<const platform::ThreadTlsModule> modules, const void* pointer,
            std::size_t bytes) -> bool {
  const auto address = reinterpret_cast<std::uintptr_t>(pointer);
  return std::ranges::any_of(modules, [=](const auto& module) {
    return module.address != 0U && address >= module.address &&
           address - module.address <= module.bytes &&
           bytes <= module.bytes - (address - module.address);
  });
}

TEST(ThreadTls, NativeSnapshotCoversActualExecutableAndLibcTls) {
  Modules before{};
  Modules after{};
  const auto first = platform::observe_thread_tls(before);
  const auto second = platform::observe_thread_tls(after);
  ASSERT_EQ(first.stop, platform::ThreadTlsStop::complete);
  ASSERT_EQ(second.stop, platform::ThreadTlsStop::complete);
  ASSERT_LE(first.used, before.size());
  EXPECT_GE(first.used, 2U);
  const auto observed = std::span(before).first(first.used);
  EXPECT_TRUE(covers(observed, anchor.data(), anchor.size()));
  EXPECT_TRUE(covers(observed, &errno, sizeof(errno)));
  EXPECT_TRUE(platform::same_thread_tls(first, before, second, after));
  EXPECT_GT(first.visited_objects, first.used);
  EXPECT_EQ(first.iteration_return, 0);

  auto changed = second;
  changed.fs_base = 0U;
  EXPECT_FALSE(platform::same_thread_tls(first, before, changed, after));
  changed = second;
  changed.loader_adds = 0U;
  EXPECT_FALSE(platform::same_thread_tls(first, before, changed, after));
  after[0U].address += 1U;
  EXPECT_FALSE(platform::same_thread_tls(first, before, second, after));
  EXPECT_FALSE(
      platform::same_thread_tls(first, std::span(before).first(1U), second, after));
}

TEST(ThreadTls, FiniteCapacityRetainsPrefixAndNeverAcceptsTruncation) {
  const auto empty = platform::observe_thread_tls({});
  EXPECT_EQ(empty.stop, platform::ThreadTlsStop::invalid_storage);
  EXPECT_FALSE(empty.thread_before.has_value());
  EXPECT_FALSE(empty.iteration_return.has_value());
  std::array<platform::ThreadTlsModule, 1U> short_output{};
  const auto result = platform::observe_thread_tls(short_output);
  EXPECT_EQ(result.stop, platform::ThreadTlsStop::capacity_exhausted);
  EXPECT_EQ(result.used, 1U);
  EXPECT_EQ(result.iteration_return, 1);
  EXPECT_NE(short_output[0U].module_id, 0U);
  EXPECT_TRUE(result.thread_after.has_value());
  EXPECT_FALSE(platform::same_thread_tls(result, short_output, result, short_output));
}

TEST(ThreadTls, MappedWorkerRetainsItsOwnTlsIdentityAndSeparatePayloads) {
  Modules creator_modules{};
  const auto creator = platform::observe_thread_tls(creator_modules);
  test::SoftwareStackOperations operations;
  platform::MappedWorkerThread worker(test::software_stack_plan(), operations);
  struct Context final {
    Modules modules{};
    platform::ThreadTlsSnapshot snapshot{};
    const void* anchor_address{nullptr};
    const void* errno_address{nullptr};
    static void run(void* pointer) noexcept {
      auto& self = *static_cast<Context*>(pointer);
      self.anchor_address = anchor.data();
      self.errno_address = &errno;
      self.snapshot = platform::observe_thread_tls(self.modules);
    }
  } context;
  ASSERT_TRUE(worker.start(&Context::run, &context));
  worker.join();
  ASSERT_TRUE(worker.prepared());
  ASSERT_EQ(context.snapshot.stop, platform::ThreadTlsStop::complete);
  const auto observed = std::span(context.modules).first(context.snapshot.used);
  EXPECT_TRUE(covers(observed, context.anchor_address, anchor.size()));
  EXPECT_TRUE(covers(observed, context.errno_address, sizeof(errno)));
  EXPECT_NE(context.anchor_address, anchor.data());
  EXPECT_NE(context.snapshot.fs_base, creator.fs_base);
  const auto stack_owner = worker.evidence().after_populate;
  const auto tls_owner = context.snapshot.thread_before;
  if (!stack_owner.has_value() || !tls_owner.has_value()) {
    FAIL() << "missing stack or TLS owner identity";
    return;
  }
  EXPECT_EQ(tls_owner->return_value, stack_owner->thread_id.return_value);
  EXPECT_FALSE(platform::same_thread_tls(creator, creator_modules, context.snapshot,
                                         context.modules));
}

} // namespace
