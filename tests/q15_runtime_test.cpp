#include "cpu_prefetch/platform/q15_runtime.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <new>
#include <string>
#include <utility>
#include <vector>

namespace {

using cpu_prefetch::platform::BackendResult;
using cpu_prefetch::platform::ErrorCategory;
using cpu_prefetch::platform::Q15CounterReading;
using cpu_prefetch::platform::Q15MemoryBindingRequest;
using cpu_prefetch::platform::Q15PeerCredentials;
using cpu_prefetch::platform::Q15PerfEventRequest;
using cpu_prefetch::platform::Q15PerfOperations;
using cpu_prefetch::platform::Q15PlatformOperations;
using cpu_prefetch::platform::Q15PointerProbePreparation;
using cpu_prefetch::platform::Q15PreparedProbeMemory;
using cpu_prefetch::platform::Q15ProbeKind;
using cpu_prefetch::platform::Q15ProbePlatformBinding;
using cpu_prefetch::platform::Q15ProbeSessionStateMachine;
using cpu_prefetch::platform::Q15ResidencySnapshot;
using cpu_prefetch::platform::Q15SessionAction;
using cpu_prefetch::platform::Q15SessionActionInput;
using cpu_prefetch::platform::Q15SessionBinding;
using cpu_prefetch::platform::Q15SessionState;
using cpu_prefetch::platform::Q15ThreadFaults;
using cpu_prefetch::platform::Result;

constexpr std::string_view kHash0 =
    "0000000000000000000000000000000000000000000000000000000000000000";
constexpr std::string_view kHash1 =
    "1111111111111111111111111111111111111111111111111111111111111111";
constexpr std::string_view kHash2 =
    "2222222222222222222222222222222222222222222222222222222222222222";
constexpr std::string_view kHash3 =
    "3333333333333333333333333333333333333333333333333333333333333333";

[[nodiscard]] auto success(std::string evidence) -> BackendResult {
  return {true, std::move(evidence), "complete", std::nullopt};
}

[[nodiscard]] auto failure(std::string detail) -> BackendResult {
  return {false, {}, std::move(detail), ErrorCategory::io_error};
}

class FakePlatform final : public Q15PlatformOperations {
public:
  ~FakePlatform() override {
    if (allocation_ != nullptr) {
      ::operator delete(allocation_, std::align_val_t(4096U));
    }
  }

  [[nodiscard]] auto bind_current_thread(std::uint32_t cpu) -> BackendResult override {
    calls.push_back("bind-thread");
    bound_cpu = cpu;
    return bind_succeeds ? success("fake-bind") : failure("fake bind failure");
  }

  [[nodiscard]] auto singleton_affinity_matches(std::uint32_t cpu)
      -> Result<bool> override {
    calls.push_back("read-affinity");
    return Result<bool>::success(affinity_matches && cpu == bound_cpu);
  }

  [[nodiscard]] auto current_cpu() -> Result<std::uint32_t> override {
    calls.push_back("current-cpu");
    return Result<std::uint32_t>::success(observed_cpu);
  }

  [[nodiscard]] auto map_private_anonymous(std::size_t byte_count)
      -> Result<std::byte*> override {
    calls.push_back("map");
    if (allocation_ != nullptr) {
      return Result<std::byte*>::failure(
          {ErrorCategory::apply_failure, "$fake", "FAKE-MAP", "duplicate map"});
    }
    allocation_ =
        static_cast<std::byte*>(::operator new(byte_count, std::align_val_t(4096U)));
    allocation_bytes_ = byte_count;
    return Result<std::byte*>::success(allocation_);
  }

  [[nodiscard]] auto bind_memory(const Q15MemoryBindingRequest& request)
      -> BackendResult override {
    calls.push_back("bind-memory");
    EXPECT_EQ(request.address, allocation_);
    EXPECT_EQ(request.byte_count, allocation_bytes_);
    EXPECT_EQ(request.numa_node, expected_node);
    return memory_bind_succeeds ? success("fake-mbind") : failure("fake mbind failure");
  }

  [[nodiscard]] auto disable_transparent_huge_pages(std::byte* address,
                                                    std::size_t byte_count)
      -> BackendResult override {
    calls.push_back("no-huge");
    EXPECT_EQ(address, allocation_);
    EXPECT_EQ(byte_count, allocation_bytes_);
    return no_huge_succeeds ? success("fake-nohuge") : failure("fake nohuge failure");
  }

  [[nodiscard]] auto query_residency(std::byte* address, std::size_t byte_count,
                                     std::size_t page_bytes)
      -> Result<Q15ResidencySnapshot> override {
    calls.push_back("residency");
    EXPECT_EQ(address, allocation_);
    std::vector<std::int32_t> nodes(byte_count / page_bytes,
                                    static_cast<std::int32_t>(residency_node));
    return Result<Q15ResidencySnapshot>::success({std::move(nodes)});
  }

  [[nodiscard]] auto thread_faults() -> Result<Q15ThreadFaults> override {
    calls.push_back("faults");
    const auto result = fault_reads == 0U ? faults_before : faults_after;
    ++fault_reads;
    return Result<Q15ThreadFaults>::success(result);
  }

  [[nodiscard]] auto monotonic_raw_nanoseconds() -> Result<std::uint64_t> override {
    calls.push_back("clock");
    return Result<std::uint64_t>::success(clock_reads++ == 0U ? begin_time : end_time);
  }

  [[nodiscard]] auto unmap(std::byte* address, std::size_t byte_count)
      -> BackendResult override {
    calls.push_back("unmap");
    EXPECT_EQ(address, allocation_);
    EXPECT_EQ(byte_count, allocation_bytes_);
    ::operator delete(allocation_, std::align_val_t(4096U));
    allocation_ = nullptr;
    allocation_bytes_ = 0U;
    return success("fake-unmap");
  }

  std::vector<std::string> calls;
  std::uint32_t bound_cpu{0U};
  std::uint32_t observed_cpu{0U};
  std::uint32_t expected_node{0U};
  std::uint32_t residency_node{0U};
  bool bind_succeeds{true};
  bool memory_bind_succeeds{true};
  bool no_huge_succeeds{true};
  bool affinity_matches{true};
  Q15ThreadFaults faults_before{10U, 2U};
  Q15ThreadFaults faults_after{10U, 2U};
  std::uint64_t begin_time{100U};
  std::uint64_t end_time{150U};
  std::size_t fault_reads{0U};
  std::size_t clock_reads{0U};

private:
  std::byte* allocation_{nullptr};
  std::size_t allocation_bytes_{0U};
};

class FakePerf final : public Q15PerfOperations {
public:
  [[nodiscard]] auto open_event(const Q15PerfEventRequest& request)
      -> Result<int> override {
    calls.push_back("open");
    observed_request = request;
    ++open_count;
    return Result<int>::success(17);
  }
  [[nodiscard]] auto reset(int descriptor) noexcept -> bool override {
    calls.push_back("reset");
    EXPECT_EQ(descriptor, 17);
    return reset_succeeds;
  }
  [[nodiscard]] auto enable(int descriptor) noexcept -> bool override {
    calls.push_back("enable");
    EXPECT_EQ(descriptor, 17);
    return enable_succeeds;
  }
  [[nodiscard]] auto disable(int descriptor) noexcept -> bool override {
    calls.push_back("disable");
    EXPECT_EQ(descriptor, 17);
    return disable_succeeds;
  }
  [[nodiscard]] auto read(int descriptor) -> Result<Q15CounterReading> override {
    calls.push_back("read");
    EXPECT_EQ(descriptor, 17);
    return Result<Q15CounterReading>::success(counter);
  }
  [[nodiscard]] auto close(int descriptor) noexcept -> bool override {
    calls.push_back("close");
    EXPECT_EQ(descriptor, 17);
    ++close_count;
    return true;
  }

  std::vector<std::string> calls;
  Q15PerfEventRequest observed_request{};
  Q15CounterReading counter{7U, 100U, 100U};
  bool reset_succeeds{true};
  bool enable_succeeds{true};
  bool disable_succeeds{true};
  std::size_t open_count{0U};
  std::size_t close_count{0U};
};

[[nodiscard]] auto prepared(FakePlatform& platform)
    -> std::unique_ptr<Q15PreparedProbeMemory> {
  auto memory = Q15PreparedProbeMemory::create(
      Q15ProbePlatformBinding{0U, 0U, 4096U, 4096U}, platform);
  EXPECT_TRUE(memory.has_value());
  return memory.has_value() ? std::move(memory.value()) : nullptr;
}

[[nodiscard]] auto binding() -> Q15SessionBinding {
  return {"q15-session",
          "stand",
          "binding",
          std::string(kHash0),
          std::string(kHash1),
          std::string(kHash1),
          std::string(kHash2),
          std::string(kHash3),
          0U,
          0U,
          4096U,
          4096U,
          {101, 1000U, 1000U},
          {202, 2000U, 2000U},
          0x123456789abcdef0U,
          0x123456789abcdeffU,
          10'000U};
}

[[nodiscard]] auto action(Q15SessionAction kind, const Q15PreparedProbeMemory& memory,
                          std::string authorization,
                          Q15PeerCredentials peer = {101, 1000U, 1000U})
    -> Q15SessionActionInput {
  return {kind,
          peer,
          100U,
          std::move(authorization),
          "evidence",
          std::string(kHash2),
          {},
          0U,
          memory.address(),
          memory.prepared_sha256()};
}

TEST(Q15DynamicProfile, PerfRequestAndWorkingSetAreExactAndFailClosed) {
  const auto request = cpu_prefetch::platform::q15_perf_event_request();
  EXPECT_TRUE(cpu_prefetch::platform::is_exact_q15_perf_event_request(request));
  EXPECT_EQ(request.config, 0xf824U);
  EXPECT_EQ(request.pid, 0);
  EXPECT_EQ(request.cpu, -1);
  EXPECT_EQ(request.group_fd, -1);
  EXPECT_TRUE(request.pinned);
  EXPECT_TRUE(request.exclude_kernel);
  EXPECT_TRUE(request.exclude_hypervisor);
  EXPECT_TRUE(request.exclude_guest);
  EXPECT_FALSE(request.exclude_user);

  auto changed = request;
  changed.pinned = false;
  EXPECT_FALSE(cpu_prefetch::platform::is_exact_q15_perf_event_request(changed));
  const auto bytes = cpu_prefetch::platform::q15_working_set_bytes(
      {26U, 1U, 25ULL * 1024ULL * 1024ULL, 4096U});
  ASSERT_TRUE(bytes.has_value());
  EXPECT_EQ(bytes.value(), 50U * 1024U * 1024U);
  EXPECT_FALSE(cpu_prefetch::platform::q15_working_set_bytes(
      {26U, 0U, 25ULL * 1024ULL * 1024ULL, 4096U}));
  EXPECT_FALSE(cpu_prefetch::platform::q15_working_set_bytes(
      {0U, 0U, 4096U, 2ULL * 1024ULL * 1024ULL}));
}

TEST(Q15DynamicMemory, FakePreparationUsesRequiredOrderAndExternalInitializer) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  EXPECT_EQ(memory->byte_count(), 8192U);
  EXPECT_EQ(memory->page_count(), 2U);
  EXPECT_EQ(memory->line_count(), 128U);
  EXPECT_TRUE(cpu_prefetch::platform::validate_q15_pointer_cycle(
      memory->bytes(), memory->line_count(), memory->start_index()));
  EXPECT_EQ((std::vector<std::string>{"map", "bind-memory", "no-huge", "bind-thread",
                                      "read-affinity", "current-cpu"}),
            platform.calls);

  std::vector<std::byte> external(std::size_t{8U} * 64U);
  const Q15PointerProbePreparation preparation =
      cpu_prefetch::platform::prepare_q15_pointer_probe_buffer(external, 8U);
  EXPECT_EQ(preparation.prepared_sha256.hex(),
            "7cefdcad16f83055ae3a1b3219ebfcfe8b131a82afa959fe0fc348818724d540");
}

TEST(Q15DynamicProbe, FakePassUsesOneExactCounterLifecycleAndRetainsRawEvidence) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  platform.calls.clear();
  FakePerf perf;
  const auto observation = cpu_prefetch::platform::run_q15_probe_pass(
      Q15ProbeKind::pointer_dependent, *memory, perf, platform);
  ASSERT_TRUE(observation.has_value());
  EXPECT_TRUE(
      cpu_prefetch::platform::is_exact_q15_perf_event_request(perf.observed_request));
  EXPECT_EQ(
      (std::vector<std::string>{"open", "reset", "enable", "disable", "read", "close"}),
      perf.calls);
  EXPECT_EQ(perf.open_count, 1U);
  EXPECT_EQ(perf.close_count, 1U);
  EXPECT_EQ(observation.value().counted.counter.all_pf_count, 7U);
  EXPECT_EQ(observation.value().diagnostic_begin_nanoseconds, 100U);
  EXPECT_EQ(observation.value().diagnostic_end_nanoseconds, 150U);
  EXPECT_TRUE(observation.value().integrity.passes_pointer_cycle(memory->line_count()));
  EXPECT_TRUE(observation.value().residency_passes(0U, 2U));
  EXPECT_TRUE(observation.value().cpu_passes(0U));
}

TEST(Q15DynamicProbe, CounterFailureClosesOnceWithoutRetryOrFallback) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  FakePerf perf;
  perf.enable_succeeds = false;
  const auto observation = cpu_prefetch::platform::run_q15_probe_pass(
      Q15ProbeKind::regular_stream, *memory, perf, platform);
  EXPECT_FALSE(observation.has_value());
  EXPECT_EQ(perf.open_count, 1U);
  EXPECT_EQ(perf.close_count, 1U);
  EXPECT_EQ((std::vector<std::string>{"open", "reset", "enable", "close"}), perf.calls);
}

TEST(Q15DynamicProbe, DisableFailureIsTerminalAndDoesNotRetryTraversal) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  FakePerf perf;
  perf.disable_succeeds = false;
  const auto observation = cpu_prefetch::platform::run_q15_probe_pass(
      Q15ProbeKind::pointer_dependent, *memory, perf, platform);
  EXPECT_FALSE(observation.has_value());
  EXPECT_EQ(perf.open_count, 1U);
  EXPECT_EQ(perf.close_count, 1U);
  EXPECT_EQ((std::vector<std::string>{"open", "reset", "enable", "disable", "close"}),
            perf.calls);
}

TEST(Q15DynamicFraming, ExactU32BeCanonicalFramesRejectLengthAndJsonMutations) {
  constexpr std::string_view canonical = R"({"a":1,"b":true})";
  const auto encoded =
      cpu_prefetch::platform::encode_q15_evidence_frame(canonical, 1024U);
  ASSERT_TRUE(encoded.has_value());
  ASSERT_EQ(encoded.value().size(), canonical.size() + 4U);
  EXPECT_EQ(std::to_integer<std::uint8_t>(encoded.value()[0]), 0U);
  EXPECT_EQ(std::to_integer<std::uint8_t>(encoded.value()[1]), 0U);
  EXPECT_EQ(std::to_integer<std::uint8_t>(encoded.value()[2]), 0U);
  EXPECT_EQ(std::to_integer<std::uint8_t>(encoded.value()[3]), canonical.size());
  const auto decoded =
      cpu_prefetch::platform::decode_q15_evidence_frame(encoded.value(), 1024U);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded.value(), canonical);

  EXPECT_FALSE(
      cpu_prefetch::platform::encode_q15_evidence_frame(R"({"b":true, "a":1})", 1024U));
  EXPECT_FALSE(cpu_prefetch::platform::encode_q15_evidence_frame(canonical, 4U));
  auto wrong_length = encoded.value();
  wrong_length[3] = std::byte{1U};
  EXPECT_FALSE(cpu_prefetch::platform::decode_q15_evidence_frame(wrong_length, 1024U));
  auto truncated = encoded.value();
  truncated.pop_back();
  EXPECT_FALSE(cpu_prefetch::platform::decode_q15_evidence_frame(truncated, 1024U));
}

TEST(Q15DynamicSession, ExactLegalSequenceRetainsOneBufferAcrossBothPhases) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  auto session_result = Q15ProbeSessionStateMachine::create(binding(), *memory);
  ASSERT_TRUE(session_result.has_value());
  auto session = std::move(session_result.value());

  auto apply = [&](Q15SessionAction kind, std::string authorization,
                   std::uint64_t value = 0U) {
    const bool q15_w = kind == Q15SessionAction::verify_h1_readback ||
                       kind == Q15SessionAction::record_h1_regular ||
                       kind == Q15SessionAction::record_h1_pointer ||
                       kind == Q15SessionAction::verify_restoration_readback ||
                       kind == Q15SessionAction::finalize;
    auto input = action(kind, *memory, std::move(authorization),
                        q15_w ? Q15PeerCredentials{202, 2000U, 2000U}
                              : Q15PeerCredentials{101, 1000U, 1000U});
    input.observed_complete_value = value;
    if (kind == Q15SessionAction::seal_h0 ||
        kind == Q15SessionAction::verify_h1_readback) {
      input.q15_r_evidence_set_sha256 = kHash3;
    }
    return session->advance(input);
  };

  EXPECT_TRUE(apply(Q15SessionAction::record_h0_regular, std::string(kHash0)));
  EXPECT_TRUE(apply(Q15SessionAction::record_h0_pointer, std::string(kHash0)));
  EXPECT_TRUE(apply(Q15SessionAction::seal_h0, std::string(kHash0)));
  EXPECT_EQ(session->state(), Q15SessionState::h0_sealed_waiting_for_q15_w);
  EXPECT_TRUE(apply(Q15SessionAction::verify_h1_readback, std::string(kHash2),
                    0x123456789abcdeffU));
  EXPECT_TRUE(apply(Q15SessionAction::record_h1_regular, std::string(kHash2)));
  EXPECT_TRUE(apply(Q15SessionAction::record_h1_pointer, std::string(kHash2)));
  EXPECT_TRUE(apply(Q15SessionAction::verify_restoration_readback, std::string(kHash2),
                    0x123456789abcdef0U));
  EXPECT_TRUE(apply(Q15SessionAction::finalize, std::string(kHash2)));
  EXPECT_EQ(session->state(), Q15SessionState::completed);
  EXPECT_EQ(session->transitions().size(), 8U);
  EXPECT_TRUE(session->buffer_identity_unchanged(*memory));
  EXPECT_FALSE(apply(Q15SessionAction::finalize, std::string(kHash2)));
  EXPECT_EQ(session->state(), Q15SessionState::completed);
  EXPECT_EQ(session->transitions().size(), 8U);
}

TEST(Q15DynamicSession, WrongPeerExpiryAndBufferMismatchFailTerminally) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  auto created = Q15ProbeSessionStateMachine::create(binding(), *memory);
  ASSERT_TRUE(created.has_value());
  auto session = std::move(created.value());

  auto wrong_peer = action(Q15SessionAction::record_h0_regular, *memory,
                           std::string(kHash0), {999, 999U, 999U});
  EXPECT_FALSE(session->advance(wrong_peer));
  EXPECT_EQ(session->state(), Q15SessionState::failed);
  const auto* wrong_peer_failure = session->failure();
  ASSERT_NE(wrong_peer_failure, nullptr);
  EXPECT_EQ(wrong_peer_failure->peer, wrong_peer.peer);
  EXPECT_EQ(wrong_peer_failure->at_monotonic_nanoseconds,
            wrong_peer.now_monotonic_nanoseconds);
  EXPECT_FALSE(session->advance(wrong_peer));

  created = Q15ProbeSessionStateMachine::create(binding(), *memory);
  ASSERT_TRUE(created.has_value());
  session = std::move(created.value());
  auto expired =
      action(Q15SessionAction::record_h0_regular, *memory, std::string(kHash0));
  expired.now_monotonic_nanoseconds = 10'000U;
  EXPECT_FALSE(session->advance(expired));
  EXPECT_EQ(session->state(), Q15SessionState::failed);

  created = Q15ProbeSessionStateMachine::create(binding(), *memory);
  ASSERT_TRUE(created.has_value());
  session = std::move(created.value());
  auto wrong_buffer =
      action(Q15SessionAction::record_h0_regular, *memory, std::string(kHash0));
  wrong_buffer.buffer_address += 64U;
  EXPECT_FALSE(session->advance(wrong_buffer));
  EXPECT_EQ(session->state(), Q15SessionState::failed);

  created = Q15ProbeSessionStateMachine::create(binding(), *memory);
  ASSERT_TRUE(created.has_value());
  session = std::move(created.value());
  memory->mutable_bytes()[0] ^= std::byte{1U};
  auto mutated =
      action(Q15SessionAction::record_h0_regular, *memory, std::string(kHash0));
  mutated.buffer_sha256 = memory->prepared_sha256();
  EXPECT_FALSE(session->advance(mutated));
  EXPECT_EQ(session->state(), Q15SessionState::failed);

  created = Q15ProbeSessionStateMachine::create(binding(), *memory);
  EXPECT_FALSE(created.has_value());
}

TEST(Q15DynamicSession, DisconnectRetainsActorTimestampAndPartialTransitions) {
  FakePlatform platform;
  auto memory = prepared(platform);
  ASSERT_NE(memory, nullptr);
  auto created = Q15ProbeSessionStateMachine::create(binding(), *memory);
  ASSERT_TRUE(created.has_value());
  auto session = std::move(created.value());
  auto first =
      action(Q15SessionAction::record_h0_regular, *memory, std::string(kHash0));
  ASSERT_TRUE(session->advance(first));
  const Q15PeerCredentials peer{101, 1000U, 1000U};
  EXPECT_FALSE(session->record_control_disconnect(peer, 321U));
  EXPECT_EQ(session->state(), Q15SessionState::failed);
  EXPECT_EQ(session->transitions().size(), 1U);
  const auto* disconnect_failure = session->failure();
  ASSERT_NE(disconnect_failure, nullptr);
  EXPECT_EQ(disconnect_failure->from, Q15SessionState::h0_regular_complete);
  EXPECT_EQ(disconnect_failure->peer, peer);
  EXPECT_EQ(disconnect_failure->at_monotonic_nanoseconds, 321U);
  EXPECT_EQ(disconnect_failure->error.rule_id, "Q15-SESSION-DISCONNECT");
}

} // namespace
