#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <atomic>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>

namespace {
using namespace cpu_prefetch;
using Stack = platform::MappedWorkerThread<test::SoftwareStackOperations>;

struct Callback final {
  Stack& stack;
  bool ran{false};
  bool prepared{false};
  bool address_inside{false};
  void* actual_stack{nullptr};
  std::size_t actual_size{0U};
  int attributes{-1};
  int attribute_stack{-1};
  int attribute_destroy{-1};

  static void run(void* context) noexcept {
    auto& self = *static_cast<Callback*>(context);
    self.ran = true;
    self.prepared = self.stack.prepared();
    pthread_attr_t attr;
    self.attributes = ::pthread_getattr_np(::pthread_self(), &attr);
    if (self.attributes == 0) {
      self.attribute_stack =
          ::pthread_attr_getstack(&attr, &self.actual_stack, &self.actual_size);
      self.attribute_destroy = ::pthread_attr_destroy(&attr);
    }
    // ASan may relocate address-taken locals; inspect the actual current frame.
    const auto address = reinterpret_cast<std::uintptr_t>(__builtin_frame_address(0));
    const auto bytes = self.stack.body();
    const auto begin = reinterpret_cast<std::uintptr_t>(bytes.data());
    self.address_inside = address >= begin && address < begin + bytes.size();
  }
};

TEST(WorkerStack, NativeWorkerUsesGuardedMappedStackAndPreservesLiveFrames) {
  test::SoftwareStackOperations operations;
  Stack stack(test::software_stack_plan(), operations);
  Callback callback{stack};
  ASSERT_TRUE(stack.start(&Callback::run, &callback));
  stack.join();
  EXPECT_TRUE(callback.ran);
  EXPECT_TRUE(callback.prepared);
  EXPECT_TRUE(callback.address_inside);
  EXPECT_EQ(callback.attributes, 0);
  EXPECT_EQ(callback.attribute_stack, 0);
  EXPECT_EQ(callback.attribute_destroy, 0);
  EXPECT_EQ(callback.actual_stack, stack.body().data());
  EXPECT_EQ(callback.actual_size, stack.body().size());
  EXPECT_TRUE(operations.live_bytes_preserved);
  constexpr std::array expected{1, 2, 3, 4, 5, 6, 4};
  EXPECT_EQ(operations.call_count, expected.size());
  EXPECT_TRUE(std::equal(expected.begin(), expected.end(), operations.calls.begin()));
  EXPECT_EQ(stack.evidence().thread.create, 0);
  EXPECT_EQ(stack.evidence().thread.join, 0);
  const auto& evidence = stack.evidence();
  if (!evidence.before_populate.has_value() || !evidence.mapping.has_value()) {
    FAIL() << "missing actual owner or mapping observation";
    return;
  }
  EXPECT_TRUE(evidence.before_populate->matches(evidence.requested.owner_cpu));
  const auto guard = reinterpret_cast<std::uintptr_t>(evidence.mapping->address);
  std::ifstream maps("/proc/self/maps");
  std::string line;
  bool guarded = false;
  while (std::getline(maps, line)) {
    std::istringstream fields(line);
    std::uintptr_t begin = 0U;
    std::uintptr_t end = 0U;
    char separator = '\0';
    std::string permissions;
    fields >> std::hex >> begin >> separator >> end >> permissions;
    if (begin <= guard && end >= guard + evidence.requested.verified_base_page_bytes) {
      guarded = permissions == "---p";
    }
  }
  EXPECT_TRUE(guarded);
  EXPECT_FALSE(stack.start(&Callback::run, &callback));
  EXPECT_TRUE(stack.release());
  EXPECT_FALSE(stack.prepared());
  EXPECT_TRUE(stack.body().empty());
  EXPECT_TRUE(stack.release());
}

TEST(WorkerStack, EveryControlFailureIsRetainedWithoutFallbackOrRetry) {
  using Failure = test::SoftwareStackOperations::Failure;
  constexpr std::array failures{Failure::bind,    Failure::no_huge,  Failure::guard,
                                Failure::observe, Failure::populate, Failure::lock,
                                Failure::after};
  constexpr std::array stops{platform::WorkerStackStop::binding_failure,
                             platform::WorkerStackStop::huge_page_control_failure,
                             platform::WorkerStackStop::guard_failure,
                             platform::WorkerStackStop::owner_readback_failure,
                             platform::WorkerStackStop::populate_failure,
                             platform::WorkerStackStop::lock_failure,
                             platform::WorkerStackStop::owner_readback_failure};
  for (std::size_t index = 0U; index < failures.size(); ++index) {
    test::SoftwareStackOperations operations;
    operations.failure = failures[index];
    Stack stack(test::software_stack_plan(), operations);
    Callback callback{stack};
    EXPECT_EQ(stack.start(&Callback::run, &callback), index >= 3U);
    stack.join();
    EXPECT_EQ(callback.ran, index >= 3U);
    EXPECT_FALSE(callback.prepared);
    EXPECT_EQ(stack.evidence().stop, stops[index]);
    EXPECT_EQ(operations.call_count, index + 1U);
    EXPECT_FALSE(stack.start(&Callback::run, &callback));
    EXPECT_TRUE(stack.release());
    EXPECT_EQ(stack.evidence().unlock.has_value(), index == 6U);
  }
}

TEST(WorkerStack, InvalidGeometryAndCpuCannotLaunchOrInventOwnerEvidence) {
  const auto valid = test::software_stack_plan();
  std::array plans{valid, valid, valid, valid, valid, valid};
  plans[0U].bytes = 0U;
  plans[1U].bytes += 1U;
  plans[2U].verified_base_page_bytes = 3U;
  plans[3U].bytes = std::numeric_limits<std::size_t>::max();
  plans[4U].bytes = valid.verified_base_page_bytes;
  plans[5U].owner_cpu = std::numeric_limits<std::uint32_t>::max();
  for (const auto plan : plans) {
    test::SoftwareStackOperations operations;
    Stack stack(plan, operations);
    Callback callback{stack};
    EXPECT_FALSE(stack.start(&Callback::run, &callback));
    stack.join();
    EXPECT_FALSE(callback.ran);
    EXPECT_FALSE(stack.evidence().before_populate.has_value());
    EXPECT_FALSE(stack.evidence().thread.create.has_value());
    EXPECT_TRUE(stack.release());
  }
}

TEST(WorkerStack, CannotReleaseLiveStackEvenAfterCallbackHasStarted) {
  test::SoftwareStackOperations operations;
  Stack stack(test::software_stack_plan(), operations);
  struct Context final {
    std::atomic<bool> entered{false};
    std::atomic<bool> finish{false};
  } context;
  ASSERT_TRUE(stack.start(
      +[](void* pointer) noexcept {
        auto& state = *static_cast<Context*>(pointer);
        state.entered.store(true, std::memory_order_release);
        while (!state.finish.load(std::memory_order_acquire)) {
          std::this_thread::yield();
        }
      },
      &context));
  while (!context.entered.load(std::memory_order_acquire)) {
    std::this_thread::yield();
  }
  EXPECT_FALSE(stack.release());
  context.finish.store(true, std::memory_order_release);
  stack.join();
  EXPECT_TRUE(stack.release());
}

} // namespace
