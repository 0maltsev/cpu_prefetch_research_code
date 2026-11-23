cmake_minimum_required(VERSION 4.3)

project(
  cpu_prefetch_foundation
  VERSION 2.0.0
  DESCRIPTION "Typed protocol, correctness, storage, reconciliation, calibration, orchestration, and synthetic offline-analysis foundation for the CPU prefetch research protocol"
  LANGUAGES CXX)

list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cmake")

include(CTest)
include(GNUInstallDirs)
include(CompilerPolicy)
include(Sanitizers)
include(VersionPolicy)
include(Warnings)

find_package(Git 2.54 REQUIRED)
find_package(OpenSSL 3.0...<4.0 REQUIRED COMPONENTS Crypto)
find_package(Python3 3.14 REQUIRED COMPONENTS Interpreter)
find_package(Threads REQUIRED)
find_package(zstd 1.5.7 EXACT CONFIG REQUIRED)

option(CPU_PREFETCH_USE_LIBCXX "Pair Clang with libc++" OFF)
option(CPU_PREFETCH_WARNINGS_AS_ERRORS "Treat project warnings as errors" ON)
option(CPU_PREFETCH_ENABLE_PROPERTY_TESTS "Build RapidCheck smoke tests" ON)
set(CPU_PREFETCH_SANITIZER "NONE" CACHE STRING "NONE, ADDRESS_UNDEFINED, or THREAD")
set(CPU_PREFETCH_RAPIDCHECK_REVISION "" CACHE STRING "Provisioned RapidCheck revision")
set(CPU_PREFETCH_Q15_QUALIFICATION_ARCHIVE "" CACHE FILEPATH
    "Explicit external Q15 qualification archive for integration checking")
set(CPU_PREFETCH_Q15_QUALIFICATION_SIDECAR "" CACHE FILEPATH
    "Explicit external Q15 qualification archive sidecar for integration checking")
set(CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_ARCHIVE "" CACHE FILEPATH
    "Caller-supplied exact Stage 17 pilot-candidate archive for integration checking")
set(CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_SIDECAR "" CACHE FILEPATH
    "Caller-supplied exact Stage 17 pilot-candidate sidecar for integration checking")
set_property(
  CACHE CPU_PREFETCH_SANITIZER
  PROPERTY STRINGS NONE ADDRESS_UNDEFINED THREAD)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

cpu_prefetch_enforce_compiler_policy()

add_library(cpu_prefetch_project_options INTERFACE)
cpu_prefetch_configure_warnings(cpu_prefetch_project_options)
cpu_prefetch_configure_sanitizers(cpu_prefetch_project_options)

include(VersionMetadata)
cpu_prefetch_configure_version_metadata()

add_library(cpu_prefetch_foundation STATIC src/repository_info.cpp)
add_library(cpu_prefetch::foundation ALIAS cpu_prefetch_foundation)
target_link_libraries(cpu_prefetch_foundation PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_foundation
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<BUILD_INTERFACE:${PROJECT_BINARY_DIR}/generated/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_protocol STATIC
  src/protocol/json.cpp
  src/protocol/load.cpp
  src/protocol/model.cpp
  src/protocol/semantic.cpp
  src/protocol/validation.cpp)
add_library(cpu_prefetch::protocol ALIAS cpu_prefetch_protocol)
target_link_libraries(cpu_prefetch_protocol PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_protocol
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_queue STATIC
  src/queue/common.cpp
  src/queue/linked_spsc.cpp
  src/queue/ring_spsc.cpp)
add_library(cpu_prefetch::queue ALIAS cpu_prefetch_queue)
target_link_libraries(cpu_prefetch_queue PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_queue
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_workload STATIC
  src/workload/deterministic.cpp
  src/workload/packages.cpp
  src/workload/records.cpp
  src/workload/working_set.cpp)
add_library(cpu_prefetch::workload ALIAS cpu_prefetch_workload)
target_link_libraries(
  cpu_prefetch_workload
  PUBLIC cpu_prefetch::protocol cpu_prefetch::queue
  PRIVATE cpu_prefetch_project_options OpenSSL::Crypto zstd::libzstd_shared)
target_include_directories(
  cpu_prefetch_workload
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(cpu_prefetch_schedule STATIC src/schedule/schedule.cpp)
add_library(cpu_prefetch::schedule ALIAS cpu_prefetch_schedule)
target_link_libraries(
  cpu_prefetch_schedule
  PUBLIC cpu_prefetch::protocol
  PRIVATE cpu_prefetch_project_options OpenSSL::Crypto)
target_include_directories(
  cpu_prefetch_schedule
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_timing STATIC
  src/timing/capture.cpp
  src/timing/clock.cpp
  src/timing/cross_core_exchange.cpp
  src/timing/intervals.cpp
  src/timing/qualification.cpp)
add_library(cpu_prefetch::timing ALIAS cpu_prefetch_timing)
target_link_libraries(
  cpu_prefetch_timing
  PUBLIC cpu_prefetch::protocol cpu_prefetch::workload
  PRIVATE cpu_prefetch_project_options ${CMAKE_DL_LIBS})
target_include_directories(
  cpu_prefetch_timing
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_platform STATIC
  src/platform/linux_inventory.cpp
  src/platform/platform.cpp
  src/platform/q15_counted_region.cpp
  src/platform/q15_probe.cpp
  src/platform/q15_msr.cpp
  src/platform/q15_runtime.cpp
  src/platform/prepared_residency.cpp
  src/platform/owner_mapping.cpp
  src/platform/worker_stack.cpp
  src/platform/thread_tls.cpp
  src/platform/thread_monitor.cpp
  src/platform/prepared_file_snapshot.cpp
  src/platform/prepared_prefetch_readback.cpp)
add_library(cpu_prefetch::platform ALIAS cpu_prefetch_platform)
target_link_libraries(
  cpu_prefetch_platform
  PUBLIC cpu_prefetch::protocol cpu_prefetch::workload Threads::Threads
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_platform
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_lifecycle STATIC
  src/lifecycle/runtime.cpp
  src/lifecycle/state_machine.cpp)
add_library(cpu_prefetch::lifecycle ALIAS cpu_prefetch_lifecycle)
target_link_libraries(
  cpu_prefetch_lifecycle
  PUBLIC cpu_prefetch::protocol cpu_prefetch::queue Threads::Threads
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_lifecycle
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_runner_core STATIC
  src/runner/qualification.cpp
  src/runner/runner.cpp
  src/runner/stage17_discovery_action.cpp
  src/runner/stage17_formal_ring_action.cpp
  src/runner/stage17_formal_service_action.cpp
  src/runner/stage17_formal_family.cpp
  src/runner/stage17_formal_checkpoint.cpp
  src/runner/stage17_schedule_source.cpp
  src/runner/stage17_s180_sources.cpp
  src/runner/stage17_s180_input.cpp
  src/runner/stage17_s180_worker.cpp
  src/runner/stage17_s180_session.cpp
  src/runner/stage17_s180_native_session.cpp
  src/runner/stage17_s180_channel_sink.cpp
  src/runner/stage17_archive_channel.cpp
  src/runner/stage17_formal_scheduled_action.cpp
  src/runner/stage17_discovery_publication.cpp
  src/runner/stage17_fixed_action.cpp)
add_library(cpu_prefetch::runner ALIAS cpu_prefetch_runner_core)
target_link_libraries(
  cpu_prefetch_runner_core
  PUBLIC cpu_prefetch::lifecycle cpu_prefetch::protocol
  PRIVATE cpu_prefetch_project_options OpenSSL::Crypto)
target_include_directories(
  cpu_prefetch_runner_core
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_q15_qualification STATIC
  src/qualification/p4_k_a_controller.cpp
  src/qualification/q15_clock_pair_qualification.cpp
  src/qualification/q15_controller.cpp
  src/qualification/q15_collectors.cpp
  src/qualification/q15_prestate.cpp
  src/qualification/q15_trust_anchor_adapter.cpp)
add_library(cpu_prefetch::q15_qualification ALIAS cpu_prefetch_q15_qualification)
target_link_libraries(
  cpu_prefetch_q15_qualification
  PUBLIC
    cpu_prefetch::lifecycle
    cpu_prefetch::platform
    cpu_prefetch::queue
    cpu_prefetch::runner
    cpu_prefetch::timing
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_q15_qualification
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(
  cpu_prefetch_storage STATIC
  src/storage/artifact_store.cpp
  src/storage/artifacts.cpp
  src/storage/budget.cpp
  src/storage/finalization.cpp
  src/storage/raw_observations.cpp
  src/storage/post_measure_archive.cpp)
add_library(cpu_prefetch::storage ALIAS cpu_prefetch_storage)
target_link_libraries(
  cpu_prefetch_storage
  PUBLIC
    cpu_prefetch::lifecycle
    cpu_prefetch::protocol
    cpu_prefetch::timing
    cpu_prefetch::workload
  PRIVATE cpu_prefetch_project_options OpenSSL::Crypto)
target_include_directories(
  cpu_prefetch_storage
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

# D233 cold-only archive encoder. Its fd-only CLI enforces the separately
# admitted process ceiling; no capture path invokes it here.
add_executable(cpu_prefetch_stage17_archive_encoder tools/stage17_archive_encoder_main.cpp)
target_link_libraries(cpu_prefetch_stage17_archive_encoder PRIVATE
  cpu_prefetch::storage cpu_prefetch_project_options OpenSSL::Crypto
  zstd::libzstd_shared ${CMAKE_DL_LIBS})

# D252 cold-only inverse. It is deliberately independent of the qualified
# measurement executable and has no allocation, I/O or external codec linkage.
add_library(cpu_prefetch_stage17_archive_inverse SHARED
  tools/stage17_archive_inverse_native_v1.cpp)
target_link_libraries(cpu_prefetch_stage17_archive_inverse PRIVATE cpu_prefetch_project_options)

# D253 cold-only complete fresh inventory; never linked into the measured worker.
add_library(cpu_prefetch_stage17_archive_inventory SHARED
  tools/stage17_archive_inventory_native_v1.cpp)
target_link_libraries(cpu_prefetch_stage17_archive_inventory PRIVATE cpu_prefetch_project_options)
target_compile_options(cpu_prefetch_stage17_archive_inventory PRIVATE -fno-exceptions -fno-rtti)
if(CPU_PREFETCH_SANITIZER STREQUAL "NONE")
  target_link_options(cpu_prefetch_stage17_archive_inventory PRIVATE -nodefaultlibs)
  target_link_libraries(cpu_prefetch_stage17_archive_inventory PRIVATE c)
endif()

# ADR-0044's owner-thread preparation uses the already-allocated Stage 11
# private streams. The dependency is declared only after the storage target is
# available; storage itself has no runner dependency.
target_link_libraries(
  cpu_prefetch_runner_core
  PUBLIC cpu_prefetch::storage cpu_prefetch::foundation)

add_library(cpu_prefetch_reconciliation STATIC
            src/reconciliation/reconciliation.cpp)
add_library(cpu_prefetch::reconciliation ALIAS cpu_prefetch_reconciliation)
target_link_libraries(
  cpu_prefetch_reconciliation
  PUBLIC cpu_prefetch::protocol cpu_prefetch::storage cpu_prefetch::timing
  PRIVATE cpu_prefetch_project_options cpu_prefetch::workload)
target_include_directories(
  cpu_prefetch_reconciliation
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

# The Stage 17 fixed worker performs exact post-run reconciliation before it
# can publish any terminal run artifact.  This dependency is intentionally
# outside the timed data plane.
target_link_libraries(cpu_prefetch_runner_core PUBLIC cpu_prefetch::reconciliation)

add_library(cpu_prefetch_calibration STATIC src/calibration/calibration.cpp
  src/calibration/service_session.cpp
  src/calibration/scheduled_session.cpp
  src/calibration/ring_demand_window.cpp
  src/calibration/service_interval_count.cpp
  src/calibration/native_discovery_capture.cpp
  src/calibration/native_formal_ring_capture.cpp
  src/calibration/native_formal_service_capture.cpp
  src/calibration/native_formal_scheduled_capture.cpp
  src/calibration/native_pilot_capture.cpp)
add_library(cpu_prefetch::calibration ALIAS cpu_prefetch_calibration)
target_link_libraries(
  cpu_prefetch_calibration
  PUBLIC
    cpu_prefetch::platform
    cpu_prefetch::storage
    cpu_prefetch::protocol
    cpu_prefetch::queue
    cpu_prefetch::timing
    cpu_prefetch::workload
    cpu_prefetch::lifecycle
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_calibration
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

# The Stage 17 fixed worker is compiled into the production runner and calls
# the accepted Q15/platform and calibration/data-plane implementations.  The
# dependencies are declared after all participating targets exist to avoid a
# fake or path-selected runtime plugin seam.
target_link_libraries(
  cpu_prefetch_runner_core
  PUBLIC cpu_prefetch::calibration cpu_prefetch::platform
  PRIVATE cpu_prefetch_project_options)

add_library(
  cpu_prefetch_orchestration STATIC
  src/orchestration/access.cpp
  src/orchestration/block_planning.cpp
  src/orchestration/precision.cpp)
add_library(cpu_prefetch::orchestration ALIAS cpu_prefetch_orchestration)
target_link_libraries(
  cpu_prefetch_orchestration
  PUBLIC cpu_prefetch::protocol cpu_prefetch::workload
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_orchestration
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_library(cpu_prefetch_analysis STATIC src/analysis/analysis.cpp)
add_library(cpu_prefetch::analysis ALIAS cpu_prefetch_analysis)
target_link_libraries(
  cpu_prefetch_analysis
  PUBLIC
    cpu_prefetch::orchestration
    cpu_prefetch::reconciliation
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_analysis
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

add_executable(cpu_prefetch_smoke tools/smoke_main.cpp)
target_link_libraries(
  cpu_prefetch_smoke PRIVATE cpu_prefetch::foundation cpu_prefetch_project_options)

add_executable(cpu_prefetch_preflight tools/stand_preflight_main.cpp)
target_link_libraries(
  cpu_prefetch_preflight
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::platform
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_runner tools/runner_main.cpp)
target_link_libraries(
  cpu_prefetch_runner
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::runner
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_qualification tools/qualification_main.cpp)
target_link_libraries(
  cpu_prefetch_qualification
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::platform
    cpu_prefetch::runner
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_q15_tool tools/q15_qualification_tool_main.cpp)
target_link_libraries(
  cpu_prefetch_q15_tool
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::platform
    cpu_prefetch::q15_qualification
    cpu_prefetch_project_options)

add_executable(
  cpu_prefetch_q15_clock_qualification_tool
  tools/q15_clock_qualification_tool_main.cpp)
target_link_libraries(
  cpu_prefetch_q15_clock_qualification_tool
  PRIVATE
    cpu_prefetch::platform
    cpu_prefetch::q15_qualification
    cpu_prefetch::runner
    cpu_prefetch::timing
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_clock_vdso_probe_tool tools/clock_vdso_probe_tool_main.cpp)
target_link_libraries(
  cpu_prefetch_clock_vdso_probe_tool
  PRIVATE cpu_prefetch::timing cpu_prefetch_project_options)

add_executable(
  cpu_prefetch_q15_qualification_evidence_tool
  tools/q15_qualification_evidence_tool_main.cpp)
target_link_libraries(
  cpu_prefetch_q15_qualification_evidence_tool
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::protocol
    cpu_prefetch::runner
    cpu_prefetch::workload
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_q15_controller tools/q15_controller_main.cpp)
target_link_libraries(
  cpu_prefetch_q15_controller
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::q15_qualification
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_q15_prestate_collector
               tools/q15_prestate_collector_main.cpp)
target_link_libraries(
  cpu_prefetch_q15_prestate_collector
  PRIVATE
    cpu_prefetch::foundation
    cpu_prefetch::q15_qualification
    cpu_prefetch_project_options)

add_executable(cpu_prefetch_storage_fixture tools/storage_fixture_main.cpp)
target_link_libraries(
  cpu_prefetch_storage_fixture
  PRIVATE cpu_prefetch::storage cpu_prefetch_project_options)

add_executable(cpu_prefetch_storage_large_smoke tools/storage_large_smoke.cpp)
target_link_libraries(
  cpu_prefetch_storage_large_smoke
  PRIVATE cpu_prefetch::storage cpu_prefetch_project_options)

if(BUILD_TESTING)
  find_package(GTest 1.17.0 EXACT CONFIG REQUIRED)
  include(GoogleTest)

  add_executable(cpu_prefetch_foundation_tests tests/repository_info_test.cpp)
  target_link_libraries(
    cpu_prefetch_foundation_tests
    PRIVATE cpu_prefetch::foundation cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_foundation_tests PREFIX "unit.")

  add_executable(cpu_prefetch_protocol_tests tests/protocol_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_protocol_tests
    PRIVATE cpu_prefetch::protocol cpu_prefetch_project_options GTest::gtest_main)
  target_compile_definitions(
    cpu_prefetch_protocol_tests
    PRIVATE CPU_PREFETCH_SOURCE_DIR="${PROJECT_SOURCE_DIR}")
  gtest_discover_tests(cpu_prefetch_protocol_tests PREFIX "protocol.")

  add_executable(cpu_prefetch_queue_tests tests/queue_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_queue_tests
    PRIVATE cpu_prefetch::queue cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_queue_tests PREFIX "queue.")

  add_executable(cpu_prefetch_linked_storage_tests tests/queue_linked_storage_test.cpp)
  target_link_libraries(cpu_prefetch_linked_storage_tests
    PRIVATE cpu_prefetch::workload cpu_prefetch_project_options GTest::gtest_main)
  if(CPU_PREFETCH_SANITIZER STREQUAL "THREAD" AND
     CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    target_compile_definitions(cpu_prefetch_linked_storage_tests
      PRIVATE CPU_PREFETCH_LINKED_ALLOCATION_HOOK=0)
  endif()
  gtest_discover_tests(cpu_prefetch_linked_storage_tests PREFIX "queue.linked_storage."
    PROPERTIES LABELS "queue;storage;synthetic")

  add_executable(cpu_prefetch_queue_stress tests/queue_stress.cpp)
  target_link_libraries(
    cpu_prefetch_queue_stress
    PRIVATE cpu_prefetch::queue cpu_prefetch_project_options)
  add_test(NAME queue.concurrent_stress COMMAND cpu_prefetch_queue_stress)
  set_tests_properties(queue.concurrent_stress PROPERTIES LABELS "queue;stress")

  add_executable(cpu_prefetch_workload_tests tests/workload_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_workload_tests
    PRIVATE cpu_prefetch::workload cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_workload_tests PREFIX "workload.")

  set(CPU_PREFETCH_STAGE7_FIXTURE_DIR
      "${PROJECT_BINARY_DIR}/generated/stage7-fixture")
  set(CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT
      "${CPU_PREFETCH_STAGE7_FIXTURE_DIR}/stage7-golden.bin")
  set(CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE
      "${CPU_PREFETCH_STAGE7_FIXTURE_DIR}/stage7-golden.json")
  set(CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION
      "${CPU_PREFETCH_STAGE7_FIXTURE_DIR}/stage7-golden-derivation.json")
  add_custom_command(
    OUTPUT
      "${CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT}"
      "${CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE}"
      "${CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION}"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${CPU_PREFETCH_STAGE7_FIXTURE_DIR}"
    COMMAND
      "${CMAKE_COMMAND}" -E rm -f "${CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT}"
      "${CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE}"
      "${CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION}"
    COMMAND
      "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/generate_schedule.py"
      --schedule-id stage7-golden
      --schedule-kind CONFIRMATORY
      --namespace-id stage7-schedule-test
      --parent-namespace-id stage-a-common
      --seed-id stage7-test-seed
      --derivation-record-id stage7-test-derivation
      --master-seed-hex
      000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
      --origin-ticks 0
      --horizon-ticks 10000
      --rate-numerator-events 1
      --rate-denominator-ticks 100
      --artifact-id stage7-golden-artifact
      --artifact-uri stage7-golden.bin
      --output-artifact "${CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT}"
      --output-envelope "${CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE}"
      --output-derivation-record "${CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION}"
    DEPENDS "${PROJECT_SOURCE_DIR}/tools/generate_schedule.py"
    COMMENT "Generating the accepted synthetic Stage 7 golden schedule")
  add_custom_target(
    cpu_prefetch_stage7_golden_fixture
    DEPENDS
      "${CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT}"
      "${CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE}"
      "${CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION}")

  add_executable(cpu_prefetch_schedule_tests tests/schedule_model_test.cpp)
  add_dependencies(cpu_prefetch_schedule_tests cpu_prefetch_stage7_golden_fixture)
  target_link_libraries(
    cpu_prefetch_schedule_tests
    PRIVATE
      cpu_prefetch::schedule
      cpu_prefetch::workload
      cpu_prefetch_project_options
      GTest::gtest_main)
  target_compile_definitions(
    cpu_prefetch_schedule_tests
    PRIVATE
      CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT="${CPU_PREFETCH_STAGE7_GOLDEN_ARTIFACT}"
      CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE="${CPU_PREFETCH_STAGE7_GOLDEN_ENVELOPE}"
      CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION="${CPU_PREFETCH_STAGE7_GOLDEN_DERIVATION}")
  gtest_discover_tests(
    cpu_prefetch_schedule_tests
    PREFIX "schedule."
    PROPERTIES LABELS "schedule")

  add_executable(cpu_prefetch_timing_tests tests/timing_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_timing_tests
    PRIVATE
      cpu_prefetch::timing
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_timing_tests
    PREFIX "timing."
    PROPERTIES LABELS "timing")

  add_executable(cpu_prefetch_platform_tests tests/platform_model_test.cpp
    tests/platform_prepared_residency_test.cpp
    tests/platform_owner_mapping_test.cpp
    tests/platform_worker_stack_test.cpp
    tests/platform_thread_tls_test.cpp
    tests/platform_thread_monitor_test.cpp
    tests/platform_prepared_file_snapshot_test.cpp
    tests/platform_prepared_prefetch_readback_test.cpp)
  target_link_libraries(
    cpu_prefetch_platform_tests
    PRIVATE
      cpu_prefetch::platform
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_platform_tests
    PREFIX "platform."
    PROPERTIES LABELS "platform")

  add_executable(cpu_prefetch_q15_tool_tests tests/q15_msr_tool_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_tool_tests
    PRIVATE
      cpu_prefetch::platform
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_q15_tool_tests
    PREFIX "q15."
    PROPERTIES LABELS "q15;qualification;platform;synthetic")

  add_executable(
    cpu_prefetch_q15_probe_tests
    tests/q15_probe_test.cpp
    tests/q15_runtime_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_probe_tests
    PRIVATE
      cpu_prefetch::platform
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_q15_probe_tests
    PREFIX "q15.probe."
    PROPERTIES LABELS "q15;qualification;platform;synthetic")

  add_executable(cpu_prefetch_q15_collector_tests tests/q15_collectors_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_collector_tests
    PRIVATE
      cpu_prefetch::q15_qualification
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_q15_collector_tests
    PREFIX "q15.collector."
    PROPERTIES LABELS "q15;qualification;platform;synthetic")

  add_executable(
    cpu_prefetch_q15_clock_pair_qualification_tests
    tests/q15_clock_pair_qualification_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_clock_pair_qualification_tests
    PRIVATE
      cpu_prefetch::q15_qualification
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_q15_clock_pair_qualification_tests
    PREFIX "q15.clock_pair."
    PROPERTIES LABELS "q15;qualification;timing")

  add_executable(
    cpu_prefetch_q15_controller_tests
    tests/p4_k_a_controller_test.cpp
    tests/q15_controller_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_controller_tests
    PRIVATE
      cpu_prefetch::q15_qualification
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_q15_controller_tests
    PREFIX "q15.controller."
    PROPERTIES LABELS "q15;qualification;controller;authorization;synthetic")

  add_executable(cpu_prefetch_q15_prestate_tests tests/q15_prestate_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_prestate_tests
    PRIVATE
      cpu_prefetch::q15_qualification
      cpu_prefetch_project_options
      GTest::gtest_main)
  target_compile_definitions(
    cpu_prefetch_q15_prestate_tests
    PRIVATE CPU_PREFETCH_SOURCE_DIR="${PROJECT_SOURCE_DIR}")
  gtest_discover_tests(
    cpu_prefetch_q15_prestate_tests
    PREFIX "q15.prestate."
    PROPERTIES LABELS "q15;qualification;prestate;synthetic")

  add_executable(
    cpu_prefetch_q15_runtime_noalloc_tests
    tests/q15_runtime_noalloc_test.cpp)
  target_link_libraries(
    cpu_prefetch_q15_runtime_noalloc_tests
    PRIVATE
      cpu_prefetch::platform
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_q15_runtime_noalloc_tests
    PREFIX "q15.runtime.noalloc."
    PROPERTIES LABELS "q15;qualification;platform;synthetic;noalloc")

  add_executable(
    cpu_prefetch_lifecycle_tests
    tests/lifecycle_concurrency_test.cpp
    tests/lifecycle_borrowed_termination_test.cpp
    tests/lifecycle_state_machine_test.cpp)
  target_link_libraries(
    cpu_prefetch_lifecycle_tests
    PRIVATE
      cpu_prefetch::lifecycle
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_lifecycle_tests
    PREFIX "lifecycle."
    PROPERTIES LABELS "lifecycle")

  add_executable(cpu_prefetch_runner_tests
                 tests/runner_model_test.cpp
                 tests/stage17_discovery_action_test.cpp
                 tests/stage17_formal_ring_action_test.cpp
                 tests/stage17_formal_service_action_test.cpp
                 tests/stage17_formal_scheduled_action_test.cpp
                 tests/stage17_formal_family_test.cpp
                 tests/stage17_formal_ring_publication_test.cpp
                 tests/stage17_formal_service_publication_test.cpp
                 tests/stage17_formal_scheduled_publication_test.cpp
                 tests/stage17_discovery_publication_test.cpp
                 tests/stage17_fixed_action_test.cpp)
  target_link_libraries(
    cpu_prefetch_runner_tests
    PRIVATE cpu_prefetch::runner cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_runner_tests
    PREFIX "runner."
    PROPERTIES LABELS "runner;pre-pilot;synthetic")

  add_executable(cpu_prefetch_s180_io_tests tests/stage17_s180_io_test.cpp tests/stage17_s180_session_test.cpp tests/stage17_s180_channel_test.cpp tests/stage17_s180_input_test.cpp)
  target_compile_definitions(cpu_prefetch_s180_io_tests PRIVATE CPU_PREFETCH_SOURCE_DIR="${PROJECT_SOURCE_DIR}")
  target_link_libraries(cpu_prefetch_s180_io_tests PRIVATE
    cpu_prefetch::runner cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_s180_io_tests
    TEST_PREFIX "runner.s180."
    PROPERTIES LABELS "runner\;pilot\;synthetic")

  add_executable(cpu_prefetch_s180_channel_fixture tests/stage17_s180_channel_fixture.cpp)
  target_link_libraries(cpu_prefetch_s180_channel_fixture PRIVATE
    cpu_prefetch::runner cpu_prefetch_project_options)
  add_executable(cpu_prefetch_s180_launcher_fixture tests/stage17_s180_launcher_fixture.cpp)
  target_link_libraries(cpu_prefetch_s180_launcher_fixture PRIVATE
    cpu_prefetch::runner cpu_prefetch_project_options)
  add_executable(cpu_prefetch_s180_clock_fixture tests/stage17_s180_clock_fixture.cpp)
  target_link_libraries(cpu_prefetch_s180_clock_fixture PRIVATE cpu_prefetch_project_options)
  add_executable(cpu_prefetch_s180_q15_fixture tests/stage17_s180_q15_fixture.cpp)
  target_link_libraries(cpu_prefetch_s180_q15_fixture PRIVATE
    cpu_prefetch::runner cpu_prefetch_project_options)

  # Separate test-linked backend: production cpu_prefetch_runner has no CLI
  # switch, environment variable, plugin path, or linkage that can select it.
  add_executable(cpu_prefetch_stage17_test_worker
                 tools/stage17_test_worker_main.cpp)
  target_link_libraries(
    cpu_prefetch_stage17_test_worker
    PRIVATE cpu_prefetch::runner cpu_prefetch_project_options)
  add_executable(cpu_prefetch_stage17_no_result_worker
                 tools/stage17_no_result_worker_main.cpp)
  target_link_libraries(
    cpu_prefetch_stage17_no_result_worker
    PRIVATE cpu_prefetch_project_options)

  add_test(NAME runner.qualification_self_test COMMAND cpu_prefetch_qualification
                 --self-test)
  set_tests_properties(
    runner.qualification_self_test
    PROPERTIES
      LABELS "runner;qualification;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "qualification-self-test: PASS.*stand=NOT_ACCESSED.*authority=Q15_REQUIRED")
  add_test(NAME q15.tool_self_test COMMAND cpu_prefetch_q15_tool --self-test)
  add_test(NAME q15.qualification_evidence_tool_self_test
    COMMAND cpu_prefetch_q15_qualification_evidence_tool --self-test)
  set_tests_properties(q15.qualification_evidence_tool_self_test PROPERTIES
    LABELS "runner;qualification;synthetic" TIMEOUT 30
    PASS_REGULAR_EXPRESSION
      "q15-qualification-evidence-tool-self-test: PASS.*device=NOT_OPENED.*stand=NOT_ACCESSED.*clock=NOT_READ")
  set_tests_properties(
    q15.tool_self_test
    PROPERTIES
      LABELS "q15;qualification;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "q15-tool-self-test: PASS.*device=NOT_OPENED.*msr=NOT_ACCESSED.*authority=NONE")
  add_test(NAME q15.controller_self_test
           COMMAND cpu_prefetch_q15_controller --self-test)
  set_tests_properties(
    q15.controller_self_test
    PROPERTIES
      LABELS "q15;qualification;controller;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "q15-controller-self-test: PASS.*stand=NOT_ACCESSED.*authority=NONE.*execution=NOT_STARTED")
  add_test(NAME q15.controller_scope
           COMMAND cpu_prefetch_q15_controller --describe-scope)
  set_tests_properties(
    q15.controller_scope
    PROPERTIES
      LABELS "q15;qualification;controller;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "Q15-R-STATIC-CONTROLLER-v1.*graph_steps=15.*q15_w=false.*stand_access=false.*authority=NONE")
  add_test(NAME q15.prestate_collector_self_test
           COMMAND cpu_prefetch_q15_prestate_collector --self-test)
  set_tests_properties(
    q15.prestate_collector_self_test
    PROPERTIES
      LABELS "q15;qualification;prestate;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "q15-prestate-self-test: PASS.*stand=NOT_ACCESSED.*execution=NOT_STARTED.*authority=NONE")
  add_test(NAME q15.prestate_collector_scope
           COMMAND cpu_prefetch_q15_prestate_collector --describe-contract)
  set_tests_properties(
    q15.prestate_collector_scope
    PROPERTIES
      LABELS "q15;qualification;prestate;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1.*commands=25.*retries=0.*stand_access=false.*authority=NONE")
  add_test(
    NAME q15.p4_r_c_executor_no_network_self_test
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/execute_d104_p4_r_c.py" --self-test)
  set_tests_properties(
    q15.p4_r_c_executor_no_network_self_test
    PROPERTIES
      LABELS "q15;qualification;p4-r-c;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "SELF-TEST PASS.*fake failures.*no network")
  add_test(
    NAME calibration.q16a_discovery_design
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_q16a_discovery.py")
  set_tests_properties(calibration.q16a_discovery_design PROPERTIES
    LABELS "calibration;diagnostic;synthetic"
    TIMEOUT 60)
  add_test(
    NAME calibration.discovery_plan_contract
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_contract.py")
  set_tests_properties(calibration.discovery_plan_contract PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 60)
  add_test(
    NAME runner.discovery_action_admission
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_action.py"
            --worker "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>")
  set_tests_properties(runner.discovery_action_admission PROPERTIES
    LABELS "runner;diagnostic;synthetic" TIMEOUT 180)
  add_test(
    NAME calibration.discovery_v2_contract
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_v2.py")
  set_tests_properties(calibration.discovery_v2_contract PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 60)
  add_test(
    NAME runner.discovery_v2_action_admission
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_action_v2.py"
            --worker "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>")
  set_tests_properties(runner.discovery_v2_action_admission PROPERTIES
    LABELS "runner;diagnostic;synthetic" TIMEOUT 180)
  add_test(
    NAME calibration.discovery_v2_retained_validation
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_validation_v2.py")
  set_tests_properties(calibration.discovery_v2_retained_validation PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 120)
  add_test(
    NAME calibration.discovery_v3_retained_validation
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_validation_v3.py")
  set_tests_properties(calibration.discovery_v3_retained_validation PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 120)
  add_test(
    NAME runner.stage17_discovery_v2_policy
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_preflight_successor_v2.py"
            --root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(runner.stage17_discovery_v2_policy PROPERTIES
    LABELS "runner;qualification;diagnostic;synthetic" TIMEOUT 180)
  add_test(
    NAME runner.stage17_preflight_successor
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_preflight_successor.py"
            --root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(runner.stage17_preflight_successor PROPERTIES
    LABELS "runner;qualification;synthetic" TIMEOUT 180)
  add_test(
    NAME calibration.discovery_environment_validation
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tests/test_stage17_discovery_environment.py")
  set_tests_properties(calibration.discovery_environment_validation PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 60)
  add_test(
    NAME calibration.discovery_retained_validation
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_validation.py")
  set_tests_properties(calibration.discovery_retained_validation PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 120)
  add_test(
    NAME calibration.discovery_metadata_validation
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tests/test_stage17_discovery_metadata.py")
  set_tests_properties(calibration.discovery_metadata_validation PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 180)
  add_executable(cpu_prefetch_stage17_formal_ring_fixture
    tools/stage17_formal_ring_fixture_main.cpp)
  target_link_libraries(cpu_prefetch_stage17_formal_ring_fixture PRIVATE
    cpu_prefetch::runner cpu_prefetch::calibration cpu_prefetch_project_options)
  add_test(
    NAME calibration.formal_ring_cpp_publication_validation
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_ring_cpp_bridge.py"
      --binary "$<TARGET_FILE:cpu_prefetch_stage17_formal_ring_fixture>")
  set_tests_properties(calibration.formal_ring_cpp_publication_validation PROPERTIES
    LABELS "calibration;synthetic;python" TIMEOUT 120)
  add_test(
    NAME runner.formal_service_cpp_bridge
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_service_cpp_bridge.py"
      --binary "$<TARGET_FILE:cpu_prefetch_stage17_formal_ring_fixture>")
  set_tests_properties(runner.formal_service_cpp_bridge PROPERTIES
    LABELS "runner;calibration;synthetic;python" TIMEOUT 120)
  add_test(
    NAME runner.formal_service_capture_validation
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_service_capture_validation_v1.py")
  set_tests_properties(runner.formal_service_capture_validation PROPERTIES
    LABELS "runner;calibration;synthetic;python" TIMEOUT 120)
  add_executable(cpu_prefetch_stage17_discovery_fixture
    tools/stage17_discovery_fixture_main.cpp)
  target_link_libraries(cpu_prefetch_stage17_discovery_fixture PRIVATE
    cpu_prefetch::runner cpu_prefetch::calibration cpu_prefetch_project_options)
  add_test(
    NAME calibration.discovery_cpp_publication_validation
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_discovery_cpp_bridge.py"
      --binary "$<TARGET_FILE:cpu_prefetch_stage17_discovery_fixture>")
  set_tests_properties(calibration.discovery_cpp_publication_validation PROPERTIES
    LABELS "calibration;diagnostic;synthetic" TIMEOUT 120)

  add_test(
    NAME runner.stage17_calibration_mapping
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_calibration_mapping.py"
            --root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(runner.stage17_calibration_mapping PROPERTIES
    LABELS "runner;calibration;synthetic"
    TIMEOUT 60)

  add_test(
    NAME runner.stage17_operational_successor
    COMMAND "${Python3_EXECUTABLE}"
            -B "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture.py"
            successor)
  set_tests_properties(
    runner.stage17_operational_successor
    PROPERTIES
      LABELS "runner;authorization;governance;pre-pilot;synthetic;historical;policy18"
      PASS_REGULAR_EXPRESSION
        "PASS.*legacy_template=true.*state=PREPARED.*transitions=0.*external_inputs=10.*pilot_ready=false.*stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_state_journal
    COMMAND "${Python3_EXECUTABLE}"
            -B "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture.py"
            journal)
  set_tests_properties(
    runner.stage17_state_journal
    PROPERTIES
      LABELS "runner;authorization;governance;state-journal;pre-pilot;synthetic;historical;policy18"
      PASS_REGULAR_EXPRESSION
        "PASS.*state=PREPARED.*resolved=0.*missing=10.*pilot_ready=false.*semantic_positive=1/1.*mechanics_positive=10/3.*runtime_positive=2.*stage17a4_positive=7.*stage17a4_negative=5.*negative=79.*nonexistent_evidence=REJECTED.*generic_evidence=REJECTED.*reload=PASS.*Stage18=false.*stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_external_journal_preflight
    COMMAND "${Python3_EXECUTABLE}"
            -B "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture.py"
            preflight)
  set_tests_properties(
    runner.stage17_external_journal_preflight
    PROPERTIES
      LABELS "runner;authorization;external-journal;preflight;pre-pilot;synthetic;historical;policy18"
      PASS_REGULAR_EXPRESSION
        "PASS positive=2 negative=3 transport=0 marker=0")
  add_test(
    NAME runner.stage17_external_journal_preflight_v2
    COMMAND "${Python3_EXECUTABLE}"
            -B "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture.py"
            preflight-v2)
  set_tests_properties(
    runner.stage17_external_journal_preflight_v2
    PROPERTIES
      LABELS "runner;authorization;external-journal;preflight;pre-pilot;synthetic;historical;policy18"
      PASS_REGULAR_EXPRESSION
        "PASS positive=4 negative=5 transport=0 marker=0")
  add_test(
    NAME runner.stage17_historical_fixture_preservation
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture_test.py")
  set_tests_properties(runner.stage17_historical_fixture_preservation PROPERTIES
    LABELS "runner;governance;synthetic;historical;policy18"
    TIMEOUT 30)
  add_test(
    NAME runner.stage17_pre_marker_runtime_cardinality
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_pre_marker_runtime_cardinality.py"
            --self-test)
  set_tests_properties(
    runner.stage17_pre_marker_runtime_cardinality
    PROPERTIES
      LABELS "runner;authorization;preflight;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS positive=4 negative=5 stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_preflight_terminal_compatibility
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_preflight_terminal_compatibility.py"
            --self-test)
  set_tests_properties(
    runner.stage17_preflight_terminal_compatibility
    PROPERTIES
      LABELS "runner;authorization;preflight;openssh;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS positive=8 negative=19 transport=0 stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_openssh_snapshot_consumption
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_openssh_snapshot_consumption.py"
            --self-test)
  set_tests_properties(
    runner.stage17_openssh_snapshot_consumption
    PROPERTIES
      LABELS "runner;authorization;openssh;state-journal;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS.*positive=8.*negative=20.*real_openssh=true.*network=false")
  add_test(
    NAME runner.stage17_authority_child_lifecycle
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_authority_child_lifecycle.py"
            --self-test)
  set_tests_properties(
    runner.stage17_authority_child_lifecycle
    PROPERTIES
      LABELS "runner;authorization;openssh;lifecycle;state-journal;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS.*positive=6.*negative=25.*actual_openssh_in_place=KNOWN_HOSTS_AND_TRANSPORT_IDENTITY.*actual_openssh_atomic=KNOWN_HOSTS_AND_TRANSPORT_IDENTITY.*network=false")
  add_test(
    NAME runner.stage17_process_group_quiescence
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_process_group_quiescence.py"
            --self-test)
  set_tests_properties(
    runner.stage17_process_group_quiescence
    PROPERTIES
      LABELS "runner;authorization;process-group;lifecycle;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS positive=3 negative=6 stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_process_group_evidence
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_process_group_evidence.py"
            --self-test)
  set_tests_properties(
    runner.stage17_process_group_evidence
    PROPERTIES
      LABELS "runner;authorization;process-group;evidence;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS positive=4 negative=8 stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_pid_namespace_supervisor
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_pid_namespace_supervisor.py"
            --self-test)
  set_tests_properties(
    runner.stage17_pid_namespace_supervisor
    PROPERTIES
      LABELS "runner;authorization;process-group;pid-namespace;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS positive=8 negative=8 stand=NOT_ACCESSED")
  if(CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_ARCHIVE
      AND CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_SIDECAR)
    add_test(
      NAME runner.stage17_fixed_action_production
      COMMAND "${Python3_EXECUTABLE}"
              "${PROJECT_SOURCE_DIR}/tools/check_stage17_production_handoff_v4.py"
              --run-hermetic-workflow
              --worker "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>"
              --no-result-worker "$<TARGET_FILE:cpu_prefetch_stage17_no_result_worker>"
              --bundle-archive "${CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_ARCHIVE}"
              --bundle-sidecar "${CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_SIDECAR}")
    set_tests_properties(
      runner.stage17_fixed_action_production
      PROPERTIES
        LABELS "runner;authorization;controller;stage17b;phase18;pre-pilot;synthetic"
        PASS_REGULAR_EXPRESSION
          "PASS positive=12 negative=12 compiled_dispatch=true state_gate_mock=false.*stand=NOT_ACCESSED")
  else()
  add_test(
    NAME runner.stage17_pilot_semantics_v3
      COMMAND "${Python3_EXECUTABLE}"
              "${PROJECT_SOURCE_DIR}/tools/check_stage17_pilot_semantics_v3.py"
              --self-test)
    set_tests_properties(
      runner.stage17_pilot_semantics_v3
      PROPERTIES
        LABELS "runner;controller;stage17b;pilot;pre-pilot;synthetic"
        PASS_REGULAR_EXPRESSION "PASS positive=2 negative=5")
  endif()
  add_test(
    NAME runner.stage17_pilot_semantics_v4
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_pilot_semantics_v4.py"
            --self-test)
  set_tests_properties(
    runner.stage17_pilot_semantics_v4
    PROPERTIES
      LABELS "runner;controller;stage17b2;pilot;raw;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION "PASS \\(2 positive, 9 negative\\)")
  add_test(
    NAME runner.stage17_raw_stream_decoder_v1
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/stage17_raw_stream_decoder_v1.py"
            --self-test)
  set_tests_properties(
    runner.stage17_raw_stream_decoder_v1
    PROPERTIES
      LABELS "runner;controller;stage17b2;pilot;raw;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION "PASS \\(3 positive, 4 negative\\)")
  add_test(
    NAME runner.stage17_formal_worker_boundary
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_worker_boundary.py"
      --worker "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>")
  set_tests_properties(runner.stage17_formal_worker_boundary PROPERTIES
    LABELS "runner;calibration;synthetic;python" TIMEOUT 120)

  add_test(
    NAME calibration.formal_native_codegen_rules
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_formal_codegen.py")
  set_tests_properties(calibration.formal_native_codegen_rules PROPERTIES
    LABELS "calibration;codegen;synthetic;python" TIMEOUT 60)

  add_test(
    NAME runner.stage17_q16a_capture_validation_v1
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_capture_validation_v1.py")
  set_tests_properties(runner.stage17_q16a_capture_validation_v1 PROPERTIES
    LABELS "runner;calibration;synthetic;python")

  add_test(
    NAME runner.stage17_formal_ring_plan_v1
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_ring_plan_v1.py")
  set_tests_properties(runner.stage17_formal_ring_plan_v1 PROPERTIES
    LABELS "runner;calibration;synthetic;python")
  add_test(
    NAME runner.stage17_formal_plan_v1
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_plan_v1.py")
  set_tests_properties(runner.stage17_formal_plan_v1 PROPERTIES
    LABELS "runner;calibration;synthetic;python" TIMEOUT 180)
  add_test(
    NAME runner.stage17_output_registry_v11
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_output_registry_v11.py")
  set_tests_properties(runner.stage17_output_registry_v11 PROPERTIES
    LABELS "runner;calibration;synthetic;python" TIMEOUT 180)
  add_test(
    NAME runner.stage17_bundle_v26
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_bundle_v26.py")
  set_tests_properties(runner.stage17_bundle_v26 PROPERTIES
    LABELS "runner;release;synthetic;python" TIMEOUT 60)
  add_test(
    NAME runner.operational_cli_v18
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_operational_cli_v18.py")
  set_tests_properties(runner.operational_cli_v18 PROPERTIES
    LABELS "runner;synthetic;python" TIMEOUT 240)
  add_test(
    NAME runner.fixed_action_executor_v10
    COMMAND "${Python3_EXECUTABLE}" -B
      "${PROJECT_SOURCE_DIR}/tests/test_stage17_fixed_action_executor_v10.py")
  set_tests_properties(runner.fixed_action_executor_v10 PROPERTIES
    LABELS "runner;synthetic;python" TIMEOUT 180)

  add_test(
    NAME runner.stage17_q16a_demand_decoder_v1
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_demand_decoder_v1.py")
  set_tests_properties(runner.stage17_q16a_demand_decoder_v1 PROPERTIES
    LABELS "runner;calibration;raw;synthetic;python")

  add_test(
    NAME runner.stage17_raw_stream_decoder_v2
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tests/test_stage17_raw_stream_decoder_v2.py")
  set_tests_properties(
    runner.stage17_raw_stream_decoder_v2
    PROPERTIES LABELS "runner;calibration;raw;service;synthetic;python")
  add_test(NAME q15.controller_no_authority_execute
           COMMAND cpu_prefetch_q15_controller --execute-q15-r
                   /nonexistent/authorization.json /nonexistent/authorization.sshsig)
  set_tests_properties(
    q15.controller_no_authority_execute
    PROPERTIES
      LABELS "q15;qualification;controller;pre-pilot;negative;synthetic"
      WILL_FAIL TRUE)
  add_test(NAME q15.tool_scope COMMAND cpu_prefetch_q15_tool --describe-fixed-scope)
  set_tests_properties(
    q15.tool_scope
    PROPERTIES
      LABELS "q15;qualification;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "family=06 model=55 msr=000001a4.*cpus=0,1,26.*measurement=false.*authority=NONE")
  add_test(NAME q15.tool_dynamic_scope
           COMMAND cpu_prefetch_q15_tool --describe-dynamic-scope)
  set_tests_properties(
    q15.tool_dynamic_scope
    PROPERTIES
      LABELS "q15;qualification;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "Q15-DYNAMIC-IMPLEMENTATION-PROFILE-v1.*cpus=0,1,26.*collectors=7.*real_pmu=false.*authority=NONE")
  add_test(NAME q15.tool_rejects_missing_authority_hash
           COMMAND cpu_prefetch_q15_tool --read-fixed-values invalid)
  set_tests_properties(
    q15.tool_rejects_missing_authority_hash
    PROPERTIES
      LABELS "q15;qualification;pre-pilot;negative;synthetic"
      WILL_FAIL TRUE)
  add_test(
    NAME runner.hardware_prefetch_plan_self_test
    COMMAND cpu_prefetch_qualification --hardware-prefetch-plan H1
            123456789abcdef0 fedcba9876543210 0f0f0f0f0f0f0f00)
  set_tests_properties(
    runner.hardware_prefetch_plan_self_test
    PROPERTIES
      LABELS "runner;qualification;platform;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "hardware-prefetch-plan: PASS.*dynamic=NOT_EXECUTED")

  add_test(
    NAME runner.qualification_schema
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_qualification_schema.py")
  set_tests_properties(
    runner.qualification_schema
    PROPERTIES LABELS "runner;qualification;schema;pre-pilot;synthetic")
  add_test(
    NAME platform.hardware_prefetch_qualification_schema
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_hardware_prefetch_schema.py")
  set_tests_properties(
    platform.hardware_prefetch_qualification_schema
    PROPERTIES LABELS "platform;qualification;schema;pre-pilot;synthetic")

  add_test(
    NAME runner.stage17_authorization_schema
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_authorization_schema.py")
  set_tests_properties(
    runner.stage17_authorization_schema
    PROPERTIES LABELS "runner;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.split_authorization_schema
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_authorization_schema.py")
  set_tests_properties(
    q15.split_authorization_schema
    PROPERTIES LABELS "q15;qualification;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_decision_input
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_decision_input.py")
  set_tests_properties(
    q15.r_decision_input
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_operational_prerequisite
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_operational_prerequisite.py")
  set_tests_properties(
    q15.r_operational_prerequisite
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p2_acceptance
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p2_acceptance.py")
  set_tests_properties(
    q15.r_p2_acceptance
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.trust_anchor_adapter_profile
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_trust_anchor_adapter_profile.py")
  set_tests_properties(
    q15.trust_anchor_adapter_profile
    PROPERTIES LABELS "q15;qualification;controller;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_stand_setup_authorization_preparation
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_stand_setup_authorization_preparation.py")
  set_tests_properties(
    q15.r_stand_setup_authorization_preparation
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_operational_release_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_operational_release_decision.py")
  set_tests_properties(
    q15.r_operational_release_decision
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p3_acceptance
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p3_acceptance.py")
  set_tests_properties(
    q15.r_p3_acceptance
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_stand_setup_authorization_preparation_v2
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_stand_setup_authorization_preparation_v2.py")
  set_tests_properties(
    q15.r_stand_setup_authorization_preparation_v2
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_external_input_acquisition_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_external_input_acquisition.py")
  set_tests_properties(
    q15.r_external_input_acquisition_decision
    PROPERTIES LABELS "q15;qualification;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_d_implementation
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_d_implementation.py")
  set_tests_properties(
    q15.r_p4_d_implementation
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_r_collector_release_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_collector_release_decision.py")
  set_tests_properties(
    q15.r_p4_r_collector_release_decision
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_e_acceptance
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_e_acceptance.py")
  set_tests_properties(
    q15.r_p4_e_acceptance
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_r_preparation_v2
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_preparation_v2.py")
  set_tests_properties(
    q15.r_p4_r_preparation_v2
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_r_staging_authorization_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_staging_authorization_decision.py")
  set_tests_properties(
    q15.r_p4_r_staging_authorization_decision
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_f_acceptance
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_f_acceptance.py")
  set_tests_properties(
    q15.r_p4_f_acceptance
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_r_successor_templates
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_successor_templates.py")
  set_tests_properties(
    q15.r_p4_r_successor_templates
    PROPERTIES LABELS "q15;qualification;prestate;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_decision_input
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_decision_input.py")
  set_tests_properties(
    q15.r_p4_k_decision_input
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_d_acceptance
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_d_acceptance.py")
  set_tests_properties(
    q15.r_p4_k_d_acceptance
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_successor_templates
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_successor_templates.py")
  set_tests_properties(
    q15.r_p4_k_successor_templates
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_a_operational_input_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_operational_input_decision.py")
  set_tests_properties(
    q15.r_p4_k_a_operational_input_decision
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_a_d_acceptance
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_d_acceptance.py")
  set_tests_properties(
    q15.r_p4_k_a_d_acceptance
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_a_controller_profile
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_controller_profile.py")
  set_tests_properties(
    q15.r_p4_k_a_controller_profile
    PROPERTIES LABELS "q15;qualification;security;custody;controller;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_bootstrap_governance_root_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_r_bootstrap_governance_root_decision.py")
  set_tests_properties(
    q15.r_bootstrap_governance_root_decision
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_bootstrap_d093_authorization
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d093_bootstrap_authorization.py")
  set_tests_properties(
    q15.r_bootstrap_d093_authorization
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_bootstrap_d093_evidence
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d093_bootstrap_evidence.py")
  set_tests_properties(
    q15.r_bootstrap_d093_evidence
    PROPERTIES LABELS "q15;qualification;security;custody;evidence;lifecycle;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_bootstrap_d094_activation
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d094_bootstrap_activation.py")
  set_tests_properties(
    q15.r_bootstrap_d094_activation
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;evidence;lifecycle;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_a_d095_terminal_failure
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d095_terminal_failure.py")
  set_tests_properties(
    q15.r_p4_k_a_d095_terminal_failure
    PROPERTIES LABELS "q15;qualification;security;custody;failure;evidence;lifecycle;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_a_d096_authorization
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d096_authorization.py")
  set_tests_properties(
    q15.r_p4_k_a_d096_authorization
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;regression;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_a_d096_complete_evidence
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d096_complete_evidence.py")
  set_tests_properties(
    q15.r_p4_k_a_d096_complete_evidence
    PROPERTIES LABELS "q15;qualification;security;custody;evidence;lifecycle;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_r_d097_preparation
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d097_p4_k_r_preparation.py")
  set_tests_properties(
    q15.r_p4_k_r_d097_preparation
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_r_d097_authorization
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d097_authorization.py")
  set_tests_properties(
    q15.r_p4_k_r_d097_authorization
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_k_r_d097_complete_evidence
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d097_complete_evidence.py")
  set_tests_properties(
    q15.r_p4_k_r_d097_complete_evidence
    PROPERTIES LABELS "q15;qualification;security;custody;evidence;lifecycle;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p5_d098_preparation
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d098_p5_preparation.py")
  set_tests_properties(
    q15.r_p5_d098_preparation
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_r_i_d099_complete
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d099_p4_r_i_complete.py")
  set_tests_properties(
    q15.r_p4_r_i_d099_complete
    PROPERTIES LABELS "q15;qualification;security;custody;evidence;lifecycle;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.r_p4_r_c_d100_decision
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_d100_p4_r_c_decision.py"
            --self-test)
  set_tests_properties(
    q15.r_p4_r_c_d100_decision
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.d100_self_test_boundary
    COMMAND "${Python3_EXECUTABLE}" -B
            "${PROJECT_SOURCE_DIR}/tools/check_d100_self_test_boundary.py")
  set_tests_properties(q15.d100_self_test_boundary PROPERTIES
    LABELS "q15;qualification;synthetic;hermetic"
    TIMEOUT 30)
  add_test(
    NAME q15.fixed_controller_authorization_v2
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_authorization_v2.py")
  set_tests_properties(
    q15.fixed_controller_authorization_v2
    PROPERTIES LABELS "q15;qualification;controller;authorization;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.fixed_controller_profile
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_controller_profile.py")
  set_tests_properties(
    q15.fixed_controller_profile
    PROPERTIES LABELS "q15;qualification;controller;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.bundle_profile_policy
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_bundle_profile.py")
  set_tests_properties(
    q15.bundle_profile_policy
    PROPERTIES LABELS "q15;qualification;stand-bundle;pre-pilot;synthetic")
  add_test(
    NAME q15.probe_collector_contract
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_collector_contract.py")
  set_tests_properties(
    q15.probe_collector_contract
    PROPERTIES LABELS "q15;qualification;contract;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.probe_implementation_profile
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_implementation.py")
  set_tests_properties(
    q15.probe_implementation_profile
    PROPERTIES LABELS "q15;qualification;contract;schema;pre-pilot;synthetic")
  add_test(
    NAME q15.dynamic_implementation_profile
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_q15_dynamic_implementation.py"
            --source-root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(
    q15.dynamic_implementation_profile
    PROPERTIES LABELS "q15;qualification;contract;schema;pre-pilot;synthetic")

  add_executable(cpu_prefetch_archive_tests tests/storage_post_measure_archive_test.cpp)
  target_link_libraries(cpu_prefetch_archive_tests PRIVATE cpu_prefetch::storage
    cpu_prefetch_project_options zstd::libzstd_shared GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_archive_tests TEST_PREFIX "storage.archive."
    PROPERTIES LABELS "storage;archive;synthetic")

  add_executable(cpu_prefetch_archive_channel_tests tests/stage17_archive_channel_test.cpp)
  target_link_libraries(cpu_prefetch_archive_channel_tests PRIVATE cpu_prefetch::runner
    cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_archive_channel_tests TEST_PREFIX "runner.archive_channel."
    PROPERTIES LABELS "runner" TIMEOUT 30)

  add_executable(cpu_prefetch_schedule_source_tests tests/stage17_schedule_source_test.cpp)
  target_link_libraries(cpu_prefetch_schedule_source_tests PRIVATE cpu_prefetch::runner
    cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_schedule_source_tests TEST_PREFIX "runner.schedule_source."
    PROPERTIES LABELS "runner")

  add_executable(cpu_prefetch_formal_checkpoint_tests tests/stage17_formal_checkpoint_test.cpp)
  target_link_libraries(cpu_prefetch_formal_checkpoint_tests PRIVATE cpu_prefetch::runner
    cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(cpu_prefetch_formal_checkpoint_tests TEST_PREFIX "runner.checkpoint."
    PROPERTIES LABELS "runner;archive;synthetic")

  add_test(NAME runner.formal_archive_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_v1.py")
  set_tests_properties(runner.formal_archive_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_executable(cpu_prefetch_stage17_archive_inverse_tests
    tests/stage17_archive_inverse_native_tests.cpp)
  target_link_libraries(cpu_prefetch_stage17_archive_inverse_tests PRIVATE
    cpu_prefetch_stage17_archive_inverse cpu_prefetch_project_options)
  add_test(NAME runner.archive_inverse_native
    COMMAND cpu_prefetch_stage17_archive_inverse_tests)
  set_tests_properties(runner.archive_inverse_native PROPERTIES
    LABELS "runner;archive;synthetic" TIMEOUT 60)
  add_executable(cpu_prefetch_stage17_archive_inventory_tests
    tests/stage17_archive_inventory_native_test.cpp)
  target_link_libraries(cpu_prefetch_stage17_archive_inventory_tests PRIVATE
    cpu_prefetch_stage17_archive_inventory cpu_prefetch_project_options GTest::gtest_main)
  add_test(NAME runner.archive_inventory_native
    COMMAND cpu_prefetch_stage17_archive_inventory_tests)
  set_tests_properties(runner.archive_inventory_native PROPERTIES
    LABELS "runner;archive;synthetic" TIMEOUT 60)
  add_executable(cpu_prefetch_stage17_archive_inventory_fault_tests
    tests/stage17_archive_inventory_native_test.cpp tools/stage17_archive_inventory_native_v1.cpp)
  target_compile_definitions(cpu_prefetch_stage17_archive_inventory_fault_tests PRIVATE
    CPU_PREFETCH_INVENTORY_FAULT_TESTS)
  target_link_libraries(cpu_prefetch_stage17_archive_inventory_fault_tests PRIVATE
    cpu_prefetch_project_options GTest::gtest_main)
  target_link_options(cpu_prefetch_stage17_archive_inventory_fault_tests PRIVATE
    "-Wl,--wrap=clock_gettime,--wrap=malloc,--wrap=realloc,--wrap=fstatat")
  add_test(NAME runner.archive_inventory_native_faults
    COMMAND cpu_prefetch_stage17_archive_inventory_fault_tests)
  set_tests_properties(runner.archive_inventory_native_faults PROPERTIES
    LABELS "runner;archive;synthetic" TIMEOUT 60)
  add_test(NAME runner.formal_archive_custody_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_custody_v1.py")
  set_tests_properties(runner.formal_archive_custody_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.formal_storage_budget_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_storage_budget_v1.py")
  set_tests_properties(runner.formal_storage_budget_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.formal_plan_v2
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_plan_v2.py")
  set_tests_properties(runner.formal_plan_v2 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.formal_ring_continuation_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_ring_continuation_v1.py")
  set_tests_properties(runner.formal_ring_continuation_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.continuation_routing_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_continuation_routing_v1.py")
  set_tests_properties(runner.continuation_routing_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.q16a_continuation_admission_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_continuation_admission_v1.py")
  set_tests_properties(runner.q16a_continuation_admission_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.q16a_composite_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_composite_v1.py")
  set_tests_properties(runner.q16a_composite_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.q16a_suffix_admission_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_suffix_admission_v1.py")
  set_tests_properties(runner.q16a_suffix_admission_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.q16a_geometry_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_geometry_v1.py")
  set_tests_properties(runner.q16a_geometry_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.q16a_handoff_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_q16a_handoff_v1.py")
  set_tests_properties(runner.q16a_handoff_v1 PROPERTIES
    LABELS "runner;archive;python" TIMEOUT 300)
  add_test(NAME runner.operational_cli_v20
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_operational_cli_v20.py")
  set_tests_properties(runner.operational_cli_v20 PROPERTIES
    LABELS "runner;archive;python" TIMEOUT 180)
  add_test(NAME runner.formal_admin_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_admin_v1.py")
  set_tests_properties(runner.formal_admin_v1 PROPERTIES
    LABELS "runner;archive;python" TIMEOUT 180)
  add_test(NAME runner.formal_admin_v2
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_admin_v2.py")
  set_tests_properties(runner.formal_admin_v2 PROPERTIES
    LABELS "runner;archive;python" TIMEOUT 180)
  foreach(_d252_test IN ITEMS phase_controller_v28 operational_cli_v21 formal_admin_v3
      archive_canonical_fast_v1 archive_metadata_fast_v1 archive_metadata_fast_v2
      formal_service_daycap_v1 service_daycap_execution_v1 e26_transition_renewal
      supervisor_proc_exit retained_capture_inspection_v1 formal_service_continuation_v1
      formal_control_reader_v1 post_exit_custody_v1 policy_v60 daycap_qualification_v2
      service_continuation_execution_v1 q16a_service_continuation_handoff_v1
      service_continuation_administration_v1 service_prefix_admission_v1
      formal_service_continuation_v2 service_continuation_namespace_v1
      service_continuation_packet_v1 service_continuation_calibration_v1
      service_prefix_admission_v2 service_continuation_administration_v2
      service_continuation_packet_v2 service_continuation_packet_v3 q16b_handoff_v1
      formal_scheduled_descriptive_v1 q16c_schedule_provenance_v2 q16c_source_execution_v1
      formal_scheduled_capture_validation_v2 q16c_descriptive_calibration_v1
      q16a_q16c_descriptive_handoff_v1 q16b_q16c_descriptive_handoff_v1
      policy_v61 daycap_qualification_v3 policy_v62 daycap_qualification_v4
      formal_scheduled_continuation_v1 q16c_source_execution_v2
      q16c_compaction_integration_v2 q16c_platform_metadata_v1 q16c_analysis_v2
      q16c_execution_window_v3 q16c_execution_window_v4 q16c_execution_window_v5 q16c_completed_prefix_v1 q16c_descriptive_calibration_v3
      q16c_source_receipts_v2 q16c_prefix_reuse_v1 q16c_incident_metadata_v1 q16c_qualified_continuation_v1 q16c_saved_request_v1 q16c_prefix_compatibility_v1 q16c_retained_prefix_v1
      q16c_operator_d288
      q16c_descriptive_administration_v4 q16a_q16c_descriptive_handoff_v3
      q16b_q16c_descriptive_handoff_v3 policy_v63)
    add_test(NAME runner.${_d252_test}
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_${_d252_test}.py")
    set_tests_properties(runner.${_d252_test} PROPERTIES
      LABELS "runner;archive;python" TIMEOUT 180)
  endforeach()
  # ASan/TSan reserve virtual address space beyond the approved 2-GiB
  # standalone codec ceiling. Instrumented core tests exercise encoding independently;
  # the real CLI bridge requires an ordinary development/release executable.
  if(CPU_PREFETCH_SANITIZER STREQUAL "NONE")
    add_test(NAME runner.fixed_action_executor_v12
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_fixed_action_executor_v12.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>")
    set_tests_properties(runner.fixed_action_executor_v12 PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180)
    add_test(NAME runner.archive_inventory_native_python
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_archive_inventory_native_v1.py"
        --library "$<TARGET_FILE:cpu_prefetch_stage17_archive_inventory>")
    set_tests_properties(runner.archive_inventory_native_python PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180)
    add_test(NAME runner.archive_inverse_native_python
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_archive_inverse_native_v1.py"
        --library "$<TARGET_FILE:cpu_prefetch_stage17_archive_inverse>")
    set_tests_properties(runner.archive_inverse_native_python PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180)
    add_test(NAME runner.archive_overlay_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_archive_overlay_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>"
        --library "$<TARGET_FILE:cpu_prefetch_stage17_archive_inverse>")
    set_tests_properties(runner.archive_overlay_v1 PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180)
    add_test(NAME runner.formal_archive_cpp_bridge
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_cpp_bridge.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>"
        --fixture "$<TARGET_FILE:cpu_prefetch_stage17_formal_ring_fixture>")
    set_tests_properties(runner.formal_archive_cpp_bridge PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180)
    add_test(NAME runner.formal_archive_runtime_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_runtime_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>")
    set_tests_properties(runner.formal_archive_runtime_v1 PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180)
    file(MAKE_DIRECTORY "${PROJECT_BINARY_DIR}/stage17-archive-jobs-tmp")
    add_test(NAME runner.formal_archive_broker_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_broker_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>")
    set_tests_properties(runner.formal_archive_broker_v1 PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180
      ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-archive-jobs-tmp")
    add_test(NAME runner.s180_archive_broker_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_archive_broker_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>"
        --channel-fixture "$<TARGET_FILE:cpu_prefetch_s180_channel_fixture>")
    set_tests_properties(runner.s180_archive_broker_v1 PROPERTIES
      LABELS "runner;pilot;archive;synthetic;python" TIMEOUT 180
      ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-archive-jobs-tmp")
    add_test(NAME runner.s180_parent_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_parent_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>"
        --channel-fixture "$<TARGET_FILE:cpu_prefetch_s180_channel_fixture>")
    set_tests_properties(runner.s180_parent_v1 PROPERTIES
      LABELS "runner;pilot;archive;synthetic;python" TIMEOUT 180
      ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-archive-jobs-tmp")
    add_test(NAME runner.s180_launcher_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_launcher_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>"
        --endpoint "$<TARGET_FILE:cpu_prefetch_s180_launcher_fixture>"
        --describer "$<TARGET_FILE:cpu_prefetch_runner>")
    set_tests_properties(runner.s180_launcher_v1 PROPERTIES
      LABELS "runner;pilot;archive;synthetic;python" TIMEOUT 180
      ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-archive-jobs-tmp")
    add_test(NAME runner.formal_archive_jobs_v1
      COMMAND "${Python3_EXECUTABLE}" -B
        "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_jobs_v1.py"
        --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>")
    set_tests_properties(runner.formal_archive_jobs_v1 PROPERTIES
      LABELS "runner;archive;synthetic;python" TIMEOUT 180
      ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-archive-jobs-tmp")
  endif()

  add_test(NAME runner.archive_plan_identity_v2
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_archive_plan_identity_v2.py")
  set_tests_properties(runner.archive_plan_identity_v2 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.archive_bundle_profile_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_archive_bundle_profile_v1.py")
  set_tests_properties(runner.archive_bundle_profile_v1 PROPERTIES
    LABELS "runner;archive;synthetic;python" TIMEOUT 180)

  add_test(NAME runner.formal_checkpoint_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_checkpoint_v1.py")
  set_tests_properties(runner.formal_checkpoint_v1 PROPERTIES
    LABELS "runner;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.calibration_export_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_calibration_export_v1.py")
  set_tests_properties(runner.calibration_export_v1 PROPERTIES
    LABELS "runner;synthetic;python" TIMEOUT 300)
  add_test(NAME runner.calibration_export_v2
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_calibration_export_v2.py")
  set_tests_properties(runner.calibration_export_v2 PROPERTIES
    LABELS "runner;synthetic;python" TIMEOUT 300)
  add_test(NAME runner.archive_channel_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_archive_channel_v1.py")
  set_tests_properties(runner.archive_channel_v1 PROPERTIES
    LABELS "runner;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_checkpoint_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_checkpoint_v1.py")
  add_test(NAME runner.s180_archive_channel_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_archive_channel_v1.py")
  set_tests_properties(runner.s180_checkpoint_v1 runner.s180_archive_channel_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_worker_cli
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_worker_cli.py"
      --worker "$<TARGET_FILE:cpu_prefetch_runner>")
  set_tests_properties(runner.s180_worker_cli PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_plan_prepare_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_plan_prepare_v1.py"
      --worker "$<TARGET_FILE:cpu_prefetch_runner>")
  set_tests_properties(runner.s180_plan_prepare_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_authority_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_authority_v1.py"
      --worker "$<TARGET_FILE:cpu_prefetch_runner>")
  set_tests_properties(runner.s180_authority_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_archive_reservation_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_archive_reservation_v1.py")
  set_tests_properties(runner.s180_archive_reservation_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_journal_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_journal_v1.py"
      --worker "$<TARGET_FILE:cpu_prefetch_runner>")
  set_tests_properties(runner.s180_journal_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_source_provenance_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_source_provenance_v1.py")
  set_tests_properties(runner.s180_source_provenance_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_verified_sources_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_verified_sources_v1.py")
  set_tests_properties(runner.s180_verified_sources_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_environment_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_environment_v1.py")
  set_tests_properties(runner.s180_environment_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_compaction_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_compaction_v1.py")
  set_tests_properties(runner.s180_compaction_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_clock_qualification_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_clock_qualification_v1.py"
      --endpoint "$<TARGET_FILE:cpu_prefetch_s180_clock_fixture>")
  set_tests_properties(runner.s180_clock_qualification_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_q15_authority_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_q15_authority_v1.py")
  set_tests_properties(runner.s180_q15_authority_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 120)
  add_test(NAME runner.s180_q15_session_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_q15_session_v1.py"
      --endpoint "$<TARGET_FILE:cpu_prefetch_s180_q15_fixture>")
  set_tests_properties(runner.s180_q15_session_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 300)
  add_test(NAME runner.s180_qualification_evidence_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_qualification_evidence_v1.py"
      --endpoint "$<TARGET_FILE:cpu_prefetch_s180_q15_fixture>"
      --helper "$<TARGET_FILE:cpu_prefetch_q15_qualification_evidence_tool>")
  set_tests_properties(runner.s180_qualification_evidence_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 420)
  add_test(NAME runner.s180_calibration_compatibility_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_calibration_compatibility_v1.py")
  set_tests_properties(runner.s180_calibration_compatibility_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 120)
  add_test(NAME runner.s180_platform_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_platform_v1.py")
  set_tests_properties(runner.s180_platform_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_namespace_admission_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_namespace_admission_v1.py")
  set_tests_properties(runner.s180_namespace_admission_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_source_author_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_source_author_v1.py")
  set_tests_properties(runner.s180_source_author_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_plan_admission_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_plan_admission_v1.py")
  set_tests_properties(runner.s180_plan_admission_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 240)
  add_test(NAME runner.s180_admission_custody_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_admission_custody_v1.py")
  set_tests_properties(runner.s180_admission_custody_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 120)
  add_test(NAME runner.s180_tail_numerics_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_tail_numerics_v1.py")
  set_tests_properties(runner.s180_tail_numerics_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_raw_join_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_raw_join_v1.py")
  set_tests_properties(runner.s180_raw_join_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.software_prefetch_t0_codegen
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_software_prefetch_t0_codegen.py")
  set_tests_properties(runner.software_prefetch_t0_codegen PROPERTIES
    LABELS "runner;codegen;synthetic;python" TIMEOUT 60)
  add_test(NAME runner.s180_archive_bundle_profile_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_archive_bundle_profile_v1.py"
      --encoder "$<TARGET_FILE:cpu_prefetch_stage17_archive_encoder>")
  set_tests_properties(runner.s180_archive_bundle_profile_v1 PROPERTIES
    LABELS "runner;pilot;archive;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_resource_admission_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_resource_admission_v1.py"
      --worker "$<TARGET_FILE:cpu_prefetch_runner>")
  set_tests_properties(runner.s180_resource_admission_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_namespace_audit_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_namespace_audit_v1.py")
  set_tests_properties(runner.s180_namespace_audit_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.s180_resource_plan_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_resource_plan_v1.py"
      --worker "$<TARGET_FILE:cpu_prefetch_runner>")
  set_tests_properties(runner.s180_resource_plan_v1 PROPERTIES
    LABELS "runner;pilot;synthetic;python" TIMEOUT 180)

  file(MAKE_DIRECTORY "${PROJECT_BINARY_DIR}/stage17-registry-tmp")
  add_test(NAME runner.formal_archive_registry_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_archive_registry_v1.py")
  set_tests_properties(runner.formal_archive_registry_v1 PROPERTIES
    LABELS "runner;qualification;synthetic;python" TIMEOUT 180
    ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-registry-tmp")
  add_test(NAME runner.output_registry_v12
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_output_registry_v12.py")
  set_tests_properties(runner.output_registry_v12 PROPERTIES
    LABELS "runner;qualification;synthetic;python" TIMEOUT 180
    ENVIRONMENT "TMPDIR=${PROJECT_BINARY_DIR}/stage17-registry-tmp")

  add_test(NAME runner.phase_controller_v26
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_phase_controller_v26.py")
  set_tests_properties(runner.phase_controller_v26 PROPERTIES
    LABELS "runner;qualification;synthetic;python" TIMEOUT 180)

  add_test(NAME runner.formal_policy_v1
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_formal_policy_v1.py")
  set_tests_properties(runner.formal_policy_v1 PROPERTIES
    LABELS "runner;qualification;synthetic;python" TIMEOUT 180)
  add_test(NAME runner.discovery_validation_parallel_v2
    COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tests/test_stage17_discovery_validation_parallel_v2.py")
  set_tests_properties(runner.discovery_validation_parallel_v2 PROPERTIES
    LABELS "runner;analysis;synthetic;python" TIMEOUT 180)

  add_executable(cpu_prefetch_storage_tests tests/storage_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_storage_tests
    PRIVATE
      cpu_prefetch::storage
      cpu_prefetch_project_options
      GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_storage_tests
    PREFIX "storage."
    PROPERTIES LABELS "storage")

  add_executable(cpu_prefetch_reconciliation_tests
                 tests/reconciliation_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_reconciliation_tests
    PRIVATE cpu_prefetch::reconciliation cpu_prefetch_project_options
            GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_reconciliation_tests
    PREFIX "reconciliation."
    PROPERTIES LABELS "reconciliation")

  add_executable(cpu_prefetch_service_session_tests tests/calibration_service_session_test.cpp)
  target_link_libraries(cpu_prefetch_service_session_tests
    PRIVATE cpu_prefetch::calibration cpu_prefetch_project_options GTest::gtest_main)
  if(CPU_PREFETCH_SANITIZER STREQUAL "THREAD" AND
     CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    target_compile_definitions(cpu_prefetch_service_session_tests
      PRIVATE CPU_PREFETCH_SERVICE_ALLOCATION_HOOK=0)
  endif()
  gtest_discover_tests(cpu_prefetch_service_session_tests PREFIX "calibration.service."
    PROPERTIES LABELS "calibration;synthetic;service")

  add_executable(cpu_prefetch_calibration_tests
    tests/calibration_model_test.cpp tests/calibration_discovery_capture_test.cpp
    tests/calibration_discovery_session_test.cpp
    tests/calibration_service_interval_count_test.cpp
    tests/calibration_formal_ring_session_test.cpp
    tests/calibration_formal_service_session_test.cpp
    tests/calibration_scheduled_session_test.cpp
    tests/calibration_ring_demand_window_test.cpp
    tests/calibration_discovery_consumer_test.cpp
    tests/calibration_caller_owned_trace_test.cpp
    tests/calibration_discovery_event_test.cpp
    tests/calibration_discovery_backend_test.cpp
    tests/calibration_discovery_residency_test.cpp
    tests/calibration_discovery_control_test.cpp
    tests/calibration_native_discovery_test.cpp
    tests/calibration_native_formal_ring_test.cpp
    tests/calibration_mapped_service_test.cpp
    tests/calibration_mapped_scheduled_test.cpp
    tests/calibration_mapped_discovery_test.cpp)
  target_link_libraries(
    cpu_prefetch_calibration_tests
    PRIVATE cpu_prefetch::calibration cpu_prefetch_project_options
            GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_calibration_tests
    PREFIX "calibration."
    PROPERTIES LABELS "calibration;synthetic")

  add_executable(cpu_prefetch_pilot_capture_tests tests/calibration_pilot_capture_test.cpp tests/calibration_mapped_pilot_data_test.cpp tests/calibration_mapped_pilot_capture_test.cpp)
  target_link_libraries(cpu_prefetch_pilot_capture_tests
    PRIVATE cpu_prefetch::calibration cpu_prefetch_project_options GTest::gtest_main)
  if(CPU_PREFETCH_SANITIZER STREQUAL "THREAD" AND
     CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    target_compile_definitions(cpu_prefetch_pilot_capture_tests
      PRIVATE CPU_PREFETCH_PILOT_ALLOCATION_HOOK=0)
  endif()
  gtest_discover_tests(cpu_prefetch_pilot_capture_tests
    TEST_PREFIX "calibration.pilot."
    PROPERTIES LABELS "calibration\;pilot\;synthetic")

  add_test(
    NAME calibration.python_statistics
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tests/test_calibration_statistics.py")
  set_tests_properties(
    calibration.python_statistics PROPERTIES LABELS "calibration;synthetic;python")

  add_test(
    NAME calibration.schema
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/tools/check_calibration_schemas.py"
      --source-root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(
    calibration.schema PROPERTIES LABELS "calibration;synthetic;schema")

  add_custom_target(
    calibration-check
    COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}"
            --output-on-failure -L calibration
    DEPENDS cpu_prefetch_calibration_tests
    COMMENT "Checking synthetic-only Stage 13 calibration contracts")

  add_executable(cpu_prefetch_orchestration_tests
                 tests/orchestration_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_orchestration_tests
    PRIVATE cpu_prefetch::orchestration cpu_prefetch_project_options
            GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_orchestration_tests
    PREFIX "orchestration."
    PROPERTIES LABELS "orchestration;synthetic")

  add_test(
    NAME orchestration.schema
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/tools/check_orchestration_schemas.py"
      --source-root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(
    orchestration.schema PROPERTIES LABELS "orchestration;synthetic;schema")

  add_custom_target(
    orchestration-check
    COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}"
            --output-on-failure -L orchestration
    DEPENDS cpu_prefetch_orchestration_tests
    COMMENT "Checking synthetic-only Stage 14 orchestration contracts")

  add_executable(cpu_prefetch_analysis_tests tests/analysis_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_analysis_tests
    PRIVATE cpu_prefetch::analysis cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_analysis_tests
    PREFIX "analysis."
    PROPERTIES LABELS "analysis;synthetic")

  add_custom_target(
    analysis-check
    COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}"
            --output-on-failure -L analysis
    DEPENDS cpu_prefetch_analysis_tests
    COMMENT "Checking synthetic-only Stage 15 offline analysis")

  add_executable(cpu_prefetch_storage_stress tests/storage_stress.cpp)
  target_link_libraries(
    cpu_prefetch_storage_stress
    PRIVATE cpu_prefetch::storage cpu_prefetch_project_options Threads::Threads)
  add_test(NAME storage.concurrent_private_streams COMMAND cpu_prefetch_storage_stress)
  set_tests_properties(
    storage.concurrent_private_streams PROPERTIES LABELS "storage;stress")

  add_test(
    NAME schedule.python_generator
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tests/test_schedule_generator.py")
  set_tests_properties(schedule.python_generator PROPERTIES LABELS "schedule;python")

  add_test(
    NAME storage.format_compatibility
    COMMAND
      "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_storage_format.py"
      --fixture-generator "$<TARGET_FILE:cpu_prefetch_storage_fixture>")
  set_tests_properties(
    storage.format_compatibility PROPERTIES LABELS "storage;python;format")

  add_test(
    NAME storage.schema_compatibility
    COMMAND
      "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_storage_schemas.py"
      --fixture-generator "$<TARGET_FILE:cpu_prefetch_storage_fixture>"
      --source-root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(
    storage.schema_compatibility PROPERTIES LABELS "storage;python;schema")

  add_test(
    NAME reconciliation.schema
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/tools/check_reconciliation_schema.py"
      --source-root "${PROJECT_SOURCE_DIR}")
  set_tests_properties(
    reconciliation.schema PROPERTIES LABELS "reconciliation;python;schema")

  add_test(NAME storage.large_synthetic COMMAND cpu_prefetch_storage_large_smoke)
  set_tests_properties(
    storage.large_synthetic
    PROPERTIES
      LABELS "storage;stress"
      PASS_REGULAR_EXPRESSION "correctness-only-no-performance-claim")

  add_custom_target(
    schedule-check
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tests/test_schedule_generator.py"
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    COMMENT "Checking deterministic Stage 7 schedule generation and schemas")

  add_custom_target(
    storage-format-check
    COMMAND
      "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_storage_format.py"
      --fixture-generator "$<TARGET_FILE:cpu_prefetch_storage_fixture>"
    DEPENDS cpu_prefetch_storage_fixture
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    COMMENT "Checking Stage 11 C++/Python physical-format compatibility")

  add_custom_target(
    storage-schema-check
    COMMAND
      "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_storage_schemas.py"
      --fixture-generator "$<TARGET_FILE:cpu_prefetch_storage_fixture>"
      --source-root "${PROJECT_SOURCE_DIR}"
    DEPENDS cpu_prefetch_storage_fixture
    COMMENT "Checking Stage 11 implementation-owned Draft 2020-12 records")

  if(NOT (CPU_PREFETCH_SANITIZER STREQUAL "THREAD" AND
          CMAKE_CXX_COMPILER_ID MATCHES "Clang"))
    add_executable(cpu_prefetch_workload_noalloc tests/workload_noalloc_test.cpp)
    target_link_libraries(
      cpu_prefetch_workload_noalloc
      PRIVATE cpu_prefetch::workload cpu_prefetch_project_options GTest::gtest_main)
    gtest_discover_tests(cpu_prefetch_workload_noalloc PREFIX "workload.noalloc.")

    add_executable(cpu_prefetch_storage_noalloc tests/storage_noalloc_test.cpp)
    target_link_libraries(
      cpu_prefetch_storage_noalloc
      PRIVATE cpu_prefetch::storage cpu_prefetch_project_options GTest::gtest_main)
    gtest_discover_tests(
      cpu_prefetch_storage_noalloc
      PREFIX "storage.noalloc."
      PROPERTIES LABELS "storage;noalloc")
  else()
    message(
      STATUS
        "The global-operator-new no-allocation hook is excluded from TSan: "
        "Clang TSan owns the same allocator interceptors; other matrices retain it")
  endif()

  add_test(
    NAME schema.protocol_fixtures
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_protocol_fixtures.py")
  add_test(
    NAME canonical.cross_language_fixtures
    COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_canonical.py")

  add_test(NAME smoke.executable COMMAND cpu_prefetch_smoke)
  set_tests_properties(
    smoke.executable
    PROPERTIES PASS_REGULAR_EXPRESSION "protocol=2.0.0-pre.3")

  add_test(NAME preflight.self_test COMMAND cpu_prefetch_preflight --self-test)
  set_tests_properties(
    preflight.self_test
    PROPERTIES
      LABELS "preflight;stand-bundle"
      PASS_REGULAR_EXPRESSION "qualification=INVENTORY_ONLY_NOT_QUALIFIED")

  add_test(NAME runner.self_test COMMAND cpu_prefetch_runner --self-test)
  set_tests_properties(
    runner.self_test
    PROPERTIES
      LABELS "runner;pre-pilot"
      PASS_REGULAR_EXPRESSION "execution=NOT_AUTHORIZED")

  add_test(
    NAME runner.schema
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_runner_schema.py")
  set_tests_properties(runner.schema PROPERTIES LABELS "runner;schema;pre-pilot")

  set(CPU_PREFETCH_RECONCILIATION_CHECK_DEPENDS
      cpu_prefetch_reconciliation_tests)
  if(CPU_PREFETCH_ENABLE_PROPERTY_TESTS)
    find_package(RapidCheck REQUIRED)
    add_executable(cpu_prefetch_rapidcheck_smoke tests/rapidcheck_smoke.cpp)
    target_link_libraries(
      cpu_prefetch_rapidcheck_smoke
      PRIVATE
        cpu_prefetch::protocol
        cpu_prefetch::queue
        cpu_prefetch::reconciliation
        cpu_prefetch::workload
        cpu_prefetch_project_options
        RapidCheck::rapidcheck)
    add_test(NAME property.framework_smoke COMMAND cpu_prefetch_rapidcheck_smoke)
    set_tests_properties(
      property.framework_smoke
      PROPERTIES
        ENVIRONMENT "RC_PARAMS=seed=20260817"
        LABELS "property;reconciliation")
    list(APPEND CPU_PREFETCH_RECONCILIATION_CHECK_DEPENDS
         cpu_prefetch_rapidcheck_smoke)
  endif()

  add_custom_target(
    reconciliation-check
    COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}"
            --output-on-failure -L reconciliation
    DEPENDS ${CPU_PREFETCH_RECONCILIATION_CHECK_DEPENDS}
    COMMENT "Checking exact Stage 12 reconciliation and independent run gates")
endif()

add_executable(
  cpu_prefetch_queue_codegen_probe EXCLUDE_FROM_ALL tools/queue_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_queue_codegen_probe
  PRIVATE cpu_prefetch::queue cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_queue_codegen_mutant EXCLUDE_FROM_ALL tools/queue_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_queue_codegen_mutant
  PRIVATE cpu_prefetch::queue cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_workload_codegen_probe EXCLUDE_FROM_ALL
  tools/workload_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_workload_codegen_probe
  PRIVATE cpu_prefetch::workload cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_workload_codegen_mutant EXCLUDE_FROM_ALL
  tools/workload_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_workload_codegen_mutant
  PRIVATE cpu_prefetch::workload cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_timing_codegen_probe EXCLUDE_FROM_ALL
  tools/timing_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_timing_codegen_probe
  PRIVATE cpu_prefetch::timing cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_timing_codegen_mutant EXCLUDE_FROM_ALL
  tools/timing_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_timing_codegen_mutant
  PRIVATE cpu_prefetch::timing cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_storage_codegen_probe EXCLUDE_FROM_ALL
  tools/storage_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_storage_codegen_probe
  PRIVATE cpu_prefetch::storage cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_storage_codegen_mutant EXCLUDE_FROM_ALL
  tools/storage_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_storage_codegen_mutant
  PRIVATE cpu_prefetch::storage cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_runner_codegen_probe EXCLUDE_FROM_ALL
  tools/runner_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_runner_codegen_probe
  PRIVATE cpu_prefetch::runner cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_runner_codegen_mutant EXCLUDE_FROM_ALL
  tools/runner_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_runner_codegen_mutant PRIVATE cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_software_prefetch_mapping_codegen_probe EXCLUDE_FROM_ALL
  tools/software_prefetch_mapping_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_software_prefetch_mapping_codegen_probe
  PRIVATE cpu_prefetch_project_options)
target_include_directories(cpu_prefetch_software_prefetch_mapping_codegen_probe
  PRIVATE "${PROJECT_SOURCE_DIR}/include")
add_executable(
  cpu_prefetch_software_prefetch_mapping_codegen_mutant EXCLUDE_FROM_ALL
  tools/software_prefetch_mapping_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_software_prefetch_mapping_codegen_mutant
  PRIVATE cpu_prefetch_project_options)
add_executable(cpu_prefetch_formal_codegen_probe EXCLUDE_FROM_ALL
  tools/formal_codegen_probe.cpp)
target_link_libraries(cpu_prefetch_formal_codegen_probe PRIVATE
  cpu_prefetch::calibration cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_runner_combined_codegen_probe EXCLUDE_FROM_ALL
  tools/runner_combined_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_runner_combined_codegen_probe
  PRIVATE cpu_prefetch::runner cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_runner_combined_codegen_mutant EXCLUDE_FROM_ALL
  tools/runner_combined_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_runner_combined_codegen_mutant PRIVATE cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_q15_probe_codegen_probe EXCLUDE_FROM_ALL
  tools/q15_probe_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_q15_probe_codegen_probe
  PRIVATE cpu_prefetch::platform cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_q15_probe_codegen_mutant EXCLUDE_FROM_ALL
  tools/q15_probe_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_q15_probe_codegen_mutant PRIVATE cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_q15_runtime_codegen_probe EXCLUDE_FROM_ALL
  tools/q15_runtime_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_q15_runtime_codegen_probe
  PRIVATE cpu_prefetch::platform cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_q15_runtime_codegen_mutant EXCLUDE_FROM_ALL
  tools/q15_runtime_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_q15_runtime_codegen_mutant
  PRIVATE cpu_prefetch::platform cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_q15_controller_codegen_probe EXCLUDE_FROM_ALL
  tools/q15_controller_codegen_probe.cpp)
target_link_libraries(
  cpu_prefetch_q15_controller_codegen_probe
  PRIVATE cpu_prefetch::q15_qualification cpu_prefetch_project_options)
add_executable(
  cpu_prefetch_q15_controller_codegen_mutant EXCLUDE_FROM_ALL
  tools/q15_controller_codegen_mutant.cpp)
target_link_libraries(
  cpu_prefetch_q15_controller_codegen_mutant
  PRIVATE cpu_prefetch::q15_qualification cpu_prefetch_project_options)

find_program(CPU_PREFETCH_CLANG_FORMAT NAMES clang-format REQUIRED)
find_program(CPU_PREFETCH_CLANG_TIDY NAMES clang-tidy REQUIRED)
find_program(CPU_PREFETCH_GNU_OBJDUMP NAMES objdump REQUIRED)
cpu_prefetch_enforce_tool_versions()

set(
  CPU_PREFETCH_FORMAT_FILES
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/analysis/analysis.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/orchestration/access.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/orchestration/block_planning.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/orchestration/precision.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/qualification.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/runner.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_fixed_action.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_discovery_publication.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_ring_publication.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_service_publication.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_scheduled_publication.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_s180_publication.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_s180_sources.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_s180_worker.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_s180_input.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_s180_session.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_s180_channel_sink.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_discovery_action.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_ring_action.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_service_action.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_scheduled_action.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_family.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_formal_checkpoint.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_schedule_source.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/stage17_archive_channel.hpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_input_detail.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/software_prefetch.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/calibration.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/caller_owned_trace.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_consumer_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_event_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_observed_drain.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_reconciliation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_ring_backend.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_session.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/service_session.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/detail/native_service_envelope.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/detail/native_capture_monitor.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/native_formal_ring_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/native_formal_service_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_formal_service_preparation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/formal_service_plan.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/formal_scheduled_plan.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_formal_scheduled_preparation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_formal_scheduled_runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/native_formal_scheduled_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_formal_ring_runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_formal_ring_preparation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/native_capture_plan.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/formal_ring_session.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/formal_service_session.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/scheduled_session.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/pilot_shared_data.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_pilot_data.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_pilot_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/native_pilot_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/pilot_scheduled_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/detail/scheduled_session_impl.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/service_interval_count.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/ring_demand_window.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_thread_launcher.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_discovery_preparation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/mapped_discovery_runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/native_discovery_capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_residency_observer.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/discovery_control_query.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/foundation/repository_info.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/executor.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/state_machine.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/linux_inventory.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/platform.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/owner_mapping.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/worker_stack.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/thread_tls.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/thread_monitor.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/prepared_file_snapshot.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/prepared_prefetch_readback.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/prepared_residency.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/q15_probe.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/q15_msr.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/q15_runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/p4_k_a_controller.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/q15_clock_pair_qualification.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/q15_collectors.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/q15_controller.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/q15_prestate.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/q15_trust_anchor_adapter.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/json.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/model.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/validation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/reconciliation/reconciliation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/adapters.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/common.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/linked_spsc.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/ring_spsc.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/schedule/schedule.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/artifact_store.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/artifacts.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/budget.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/capture_backend.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/finalization.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/raw_observations.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/storage/post_measure_archive.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/clock.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/cross_core_exchange.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/intervals.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/qualification.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/deterministic.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/packages.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/records.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/working_set.hpp"
  "${PROJECT_SOURCE_DIR}/src/repository_info.cpp"
  "${PROJECT_SOURCE_DIR}/src/analysis/analysis.cpp"
  "${PROJECT_SOURCE_DIR}/src/orchestration/access.cpp"
  "${PROJECT_SOURCE_DIR}/src/orchestration/block_planning.cpp"
  "${PROJECT_SOURCE_DIR}/src/orchestration/precision.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/calibration.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_discovery_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_formal_ring_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_formal_service_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_formal_scheduled_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_pilot_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/service_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/scheduled_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/ring_demand_window.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/service_interval_count.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/state_machine.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/linux_inventory.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/platform.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_counted_region.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_probe.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_msr.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/prepared_residency.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/owner_mapping.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/worker_stack.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/thread_tls.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/thread_monitor.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/prepared_file_snapshot.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/prepared_prefetch_readback.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/p4_k_a_controller.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_clock_pair_qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_collectors.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_controller.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_prestate.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_trust_anchor_adapter.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/json.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/load.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/model.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/semantic.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/validation.cpp"
  "${PROJECT_SOURCE_DIR}/src/reconciliation/reconciliation.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/runner.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_fixed_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_discovery_publication.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_discovery_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_ring_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_service_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_scheduled_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_family.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_checkpoint.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_schedule_source.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_sources.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_worker.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_input.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_native_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_channel_sink.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_archive_channel.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/schedule/schedule.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifact_store.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifacts.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/budget.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/finalization.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/raw_observations.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/post_measure_archive.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/clock.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/cross_core_exchange.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/intervals.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/deterministic.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/packages.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/records.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/working_set.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_linked_storage_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/analysis_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/orchestration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_capture_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_service_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_service_interval_count_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_formal_ring_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_formal_service_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_scheduled_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_pilot_capture_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_pilot_data_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_pilot_capture_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_ring_demand_window_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_consumer_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_caller_owned_trace_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_event_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_backend_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_residency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_control_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_discovery_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_native_discovery_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_native_formal_ring_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_service_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_scheduled_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/discovery_backend_test_support.hpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_concurrency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_borrowed_termination_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_state_machine_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_phase_test_access.hpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_prepared_residency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_owner_mapping_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_worker_stack_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_thread_tls_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_thread_monitor_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_prepared_file_snapshot_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_prepared_prefetch_readback_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/s180_session_test_support.hpp"
  "${PROJECT_SOURCE_DIR}/tests/worker_stack_test_support.hpp"
  "${PROJECT_SOURCE_DIR}/tests/p4_k_a_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_probe_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_collectors_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_clock_pair_qualification_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_prestate_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_msr_tool_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/reconciliation_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/runner_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_fixed_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_discovery_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_ring_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_service_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_scheduled_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_io_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_channel_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_channel_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_launcher_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_clock_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_q15_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_input_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_discovery_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_ring_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_service_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_scheduled_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_family_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_checkpoint_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_schedule_source_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_archive_channel_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/schedule_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_post_measure_archive_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/timing_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_fixture_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_large_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stand_preflight_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_combined_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_combined_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/formal_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_archive_encoder_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_discovery_fixture_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_formal_ring_fixture_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_no_result_worker_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_test_worker_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/qualification_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_qualification_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_clock_qualification_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_qualification_evidence_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/clock_vdso_probe_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_prestate_collector_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/workload_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/workload_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/smoke_main.cpp")

add_custom_target(
  format-check
  COMMAND "${CPU_PREFETCH_CLANG_FORMAT}" --dry-run --Werror ${CPU_PREFETCH_FORMAT_FILES}
  COMMENT "Checking C++ formatting")
add_custom_target(
  format
  COMMAND "${CPU_PREFETCH_CLANG_FORMAT}" -i ${CPU_PREFETCH_FORMAT_FILES}
  COMMENT "Formatting C++ sources")

set(
  CPU_PREFETCH_ANALYSIS_FILES
  "${PROJECT_SOURCE_DIR}/src/repository_info.cpp"
  "${PROJECT_SOURCE_DIR}/src/analysis/analysis.cpp"
  "${PROJECT_SOURCE_DIR}/src/orchestration/access.cpp"
  "${PROJECT_SOURCE_DIR}/src/orchestration/block_planning.cpp"
  "${PROJECT_SOURCE_DIR}/src/orchestration/precision.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/calibration.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_discovery_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_formal_ring_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_formal_service_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_formal_scheduled_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/native_pilot_capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/service_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/scheduled_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/ring_demand_window.cpp"
  "${PROJECT_SOURCE_DIR}/src/calibration/service_interval_count.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/state_machine.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/linux_inventory.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/platform.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_counted_region.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_probe.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_msr.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/prepared_residency.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/owner_mapping.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/worker_stack.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/thread_tls.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/thread_monitor.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/prepared_file_snapshot.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/prepared_prefetch_readback.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/p4_k_a_controller.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_clock_pair_qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_collectors.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_controller.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_prestate.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/q15_trust_anchor_adapter.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/json.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/load.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/model.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/semantic.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/validation.cpp"
  "${PROJECT_SOURCE_DIR}/src/reconciliation/reconciliation.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/runner.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_fixed_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_discovery_publication.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_discovery_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_ring_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_service_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_scheduled_action.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_family.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_formal_checkpoint.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_schedule_source.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_sources.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_worker.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_input.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_native_session.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_s180_channel_sink.cpp"
  "${PROJECT_SOURCE_DIR}/src/runner/stage17_archive_channel.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/schedule/schedule.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifact_store.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifacts.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/budget.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/finalization.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/raw_observations.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/post_measure_archive.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/clock.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/cross_core_exchange.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/intervals.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/deterministic.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/packages.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/records.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/working_set.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_linked_storage_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/analysis_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/orchestration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_capture_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_service_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_service_interval_count_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_formal_ring_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_formal_service_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_scheduled_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_pilot_capture_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_pilot_data_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_pilot_capture_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_ring_demand_window_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_consumer_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_caller_owned_trace_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_event_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_backend_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_residency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_discovery_control_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_discovery_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_native_discovery_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_native_formal_ring_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_service_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_mapped_scheduled_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_concurrency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_borrowed_termination_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_state_machine_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_prepared_residency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_owner_mapping_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_worker_stack_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_thread_tls_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_thread_monitor_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_prepared_file_snapshot_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_prepared_prefetch_readback_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/p4_k_a_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_probe_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_collectors_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_clock_pair_qualification_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_prestate_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_msr_tool_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/reconciliation_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/runner_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_fixed_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_discovery_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_ring_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_service_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_scheduled_publication_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_io_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_channel_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_channel_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_launcher_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_clock_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_q15_fixture.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_input_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_s180_session_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_discovery_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_ring_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_service_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_scheduled_action_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_family_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_formal_checkpoint_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_schedule_source_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/stage17_archive_channel_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/schedule_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_post_measure_archive_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/timing_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_fixture_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/storage_large_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stand_preflight_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_combined_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_combined_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/formal_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/runner_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_archive_encoder_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_discovery_fixture_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_formal_ring_fixture_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_no_result_worker_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/stage17_test_worker_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/qualification_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_qualification_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_clock_qualification_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_qualification_evidence_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/clock_vdso_probe_tool_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_prestate_collector_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/workload_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/workload_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/smoke_main.cpp")
add_custom_target(
  static-analysis
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/run_clang_tidy.py"
    --clang-tidy "${CPU_PREFETCH_CLANG_TIDY}"
    --build-directory "${PROJECT_BINARY_DIR}"
    ${CPU_PREFETCH_ANALYSIS_FILES}
  DEPENDS
    cpu_prefetch_preflight
    cpu_prefetch_qualification
    cpu_prefetch_q15_tool
    cpu_prefetch_q15_controller
    cpu_prefetch_q15_prestate_collector
    cpu_prefetch_runner
    cpu_prefetch_smoke
  COMMENT "Running clang-tidy over repository C++ targets")

add_custom_target(
  protocol-check
  COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_protocol.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking imported protocol integrity and schemas")
add_custom_target(
  schema-fixture-check
  COMMAND "${Python3_EXECUTABLE}"
          "${PROJECT_SOURCE_DIR}/tools/check_protocol_fixtures.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking positive and negative protocol schema fixtures")
add_custom_target(
  canonical-check
  COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_canonical.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking shared JCS-I64-v1 cross-language fixtures")
add_custom_target(
  queue-codegen-audit
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_queue_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_queue_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_queue_codegen_mutant>"
    --output "${PROJECT_BINARY_DIR}/queue_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
    --provenance "${PROJECT_SOURCE_DIR}/config/queue-provenance/ring-spsc.json"
    --provenance "${PROJECT_SOURCE_DIR}/config/queue-provenance/linked-spsc.json"
    --allow-missing-secondary
  DEPENDS cpu_prefetch_queue_codegen_probe cpu_prefetch_queue_codegen_mutant
  COMMENT "Auditing queue code generation and retaining partial evidence")
add_custom_target(
  queue-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_queue_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_queue_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_queue_codegen_mutant>"
    --output "${PROJECT_BINARY_DIR}/queue_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
    --provenance "${PROJECT_SOURCE_DIR}/config/queue-provenance/ring-spsc.json"
    --provenance "${PROJECT_SOURCE_DIR}/config/queue-provenance/linked-spsc.json"
  DEPENDS cpu_prefetch_queue_codegen_probe cpu_prefetch_queue_codegen_mutant
  COMMENT "Requiring dual-disassembler queue generated-code evidence")
add_custom_target(
  queue-provenance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_queue_provenance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking queue provenance, source hashes, mode, and license boundary")
add_custom_target(
  workload-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_workload_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_workload_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_workload_codegen_mutant>"
    --output "${PROJECT_BINARY_DIR}/workload_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_workload_codegen_probe cpu_prefetch_workload_codegen_mutant
  COMMENT "Requiring dual-disassembler Stage 6 generated-code evidence")
add_custom_target(
  timing-codegen-audit
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_timing_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_timing_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_timing_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/timing_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
    --allow-missing-secondary
  DEPENDS cpu_prefetch_timing_codegen_probe cpu_prefetch_timing_codegen_mutant
  COMMENT "Auditing timestamp boundaries and retaining partial evidence")
add_custom_target(
  timing-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_timing_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_timing_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_timing_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/timing_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_timing_codegen_probe cpu_prefetch_timing_codegen_mutant
  COMMENT "Requiring dual-disassembler Stage 8 timestamp evidence")
add_custom_target(
  storage-codegen-audit
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_storage_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_storage_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_storage_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/storage_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
    --allow-missing-secondary
  DEPENDS cpu_prefetch_storage_codegen_probe cpu_prefetch_storage_codegen_mutant
  COMMENT "Auditing Stage 11 bounded writer code generation")
add_custom_target(
  storage-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_storage_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_storage_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_storage_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/storage_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_storage_codegen_probe cpu_prefetch_storage_codegen_mutant
  COMMENT "Requiring dual-disassembler Stage 11 bounded-writer evidence")
add_custom_target(
  runner-relax-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_runner_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_runner_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_runner_codegen_mutant>"
    --output "${PROJECT_BINARY_DIR}/runner_relax_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_runner_codegen_probe cpu_prefetch_runner_codegen_mutant
  COMMENT "Requiring dual-disassembler Q13 one-PAUSE relax evidence")
add_custom_target(
  software-prefetch-mapping-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_software_prefetch_mapping_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_software_prefetch_mapping_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_software_prefetch_mapping_codegen_mutant>"
    --output
    "${PROJECT_BINARY_DIR}/software_prefetch_mapping_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS
    cpu_prefetch_software_prefetch_mapping_codegen_probe
    cpu_prefetch_software_prefetch_mapping_codegen_mutant
  COMMENT "Requiring dual-disassembler D-047 PREFETCHW/PREFETCHT0 mapping evidence")
add_custom_target(
  software-prefetch-t0-mapping-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_software_prefetch_mapping_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_software_prefetch_mapping_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_software_prefetch_mapping_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}" --mapping-id X86-64-PREFETCHT0-ONLY-v1
    --output "${PROJECT_BINARY_DIR}/software_prefetch_t0_mapping_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_software_prefetch_mapping_codegen_probe
    cpu_prefetch_software_prefetch_mapping_codegen_mutant
  COMMENT "Requiring dual-disassembler ADR-0175 T0-only mapping evidence")
add_custom_target(
  runner-combined-codegen-audit
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_runner_combined_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_runner_combined_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_runner_combined_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/runner_combined_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS
    cpu_prefetch_runner_combined_codegen_probe
    cpu_prefetch_runner_combined_codegen_mutant
  COMMENT "Auditing the resolved D-047 combined-operation mapping")
add_custom_target(
  runner-combined-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_runner_combined_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_runner_combined_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_runner_combined_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/runner_combined_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS
    cpu_prefetch_runner_combined_codegen_probe
    cpu_prefetch_runner_combined_codegen_mutant
  COMMENT "Requiring resolved Q14 combined-operation generated code")
add_custom_target(
  discovery-codegen-check
  COMMAND "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_discovery_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_runner>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/discovery_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_runner
  COMMENT "Requiring both disassemblers to qualify the actual native discovery worker")
add_custom_target(
  formal-codegen-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_formal_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_runner>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/formal_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS cpu_prefetch_runner
  COMMENT "Requiring both disassemblers to audit actual formal native active-phase code")
add_custom_target(
  s180-codegen-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_s180_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_runner>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/s180_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tests/test_stage17_s180_codegen.py"
    --report "${PROJECT_BINARY_DIR}/s180_codegen_report.json"
    --binary "$<TARGET_FILE:cpu_prefetch_runner>"
    --source-root "${PROJECT_SOURCE_DIR}"
  DEPENDS cpu_prefetch_runner
  COMMENT "Auditing all20 actual pilot and42 formal workers with both disassemblers and machine mutants")
add_custom_target(
  q15-probe-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_q15_probe_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_q15_probe_codegen_mutant>"
    --output "${PROJECT_BINARY_DIR}/q15_probe_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS
    cpu_prefetch_q15_probe_codegen_probe
    cpu_prefetch_q15_probe_codegen_mutant
  COMMENT "Requiring dual-disassembler D-052/D-053 counted-traversal evidence")
add_custom_target(
  q15-runtime-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_runtime_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_q15_runtime_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_q15_runtime_codegen_mutant>"
    --output "${PROJECT_BINARY_DIR}/q15_runtime_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS
    cpu_prefetch_q15_runtime_codegen_probe
    cpu_prefetch_q15_runtime_codegen_mutant
  COMMENT "Requiring dual-disassembler D-055 enable/traversal/disable evidence")
add_custom_target(
  q15-controller-codegen-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_controller_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_q15_controller_codegen_probe>"
    --mutant "$<TARGET_FILE:cpu_prefetch_q15_controller_codegen_mutant>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/q15_controller_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  DEPENDS
    cpu_prefetch_q15_controller_codegen_probe
    cpu_prefetch_q15_controller_codegen_mutant
  COMMENT "Requiring dual-disassembler D-057 fixed-graph and no-retry evidence")
add_custom_target(
  runner-schema-check
  COMMAND "${Python3_EXECUTABLE}"
          "${PROJECT_SOURCE_DIR}/tools/check_runner_schema.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the v1, Q14 v2, and Q15-P0 v3 runner-admission schemas")
add_custom_target(
  qualification-schema-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_hardware_prefetch_schema.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_qualification_schema.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_authorization_schema.py"
  COMMAND
    "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture.py" successor
  COMMAND
    "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_historical_fixture.py" journal
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_authorization_schema.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_decision_input.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_operational_prerequisite.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p2_acceptance.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_trust_anchor_adapter_profile.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_stand_setup_authorization_preparation.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_operational_release_decision.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p3_acceptance.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_stand_setup_authorization_preparation_v2.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_external_input_acquisition.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_d_implementation.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_collector_release_decision.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_e_acceptance.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_preparation_v2.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_staging_authorization_decision.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_f_acceptance.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_successor_templates.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_decision_input.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_d_acceptance.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_successor_templates.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_operational_input_decision.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_d_acceptance.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_controller_profile.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_bootstrap_governance_root_decision.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d093_bootstrap_authorization.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d093_bootstrap_evidence.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d094_bootstrap_activation.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_authorization_v2.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_controller_profile.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_collector_contract.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_implementation.py"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_dynamic_implementation.py"
    --source-root "${PROJECT_SOURCE_DIR}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking Q14, Q15-P0, split Q15-R/Q15-W, Q15-R decisions, and probe contracts")
add_custom_target(
  q15-r-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_decision_input.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the non-authorizing Q15-R decision/input bundle")
add_custom_target(
  q15-r-operational-prerequisite-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_operational_prerequisite.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the proposed no-authority Q15-R operational prerequisites")
add_custom_target(
  q15-r-p2-acceptance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p2_acceptance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the accepted repository-local Q15-R-P2 authority boundary")
add_custom_target(
  q15-trust-anchor-adapter-profile-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_trust_anchor_adapter_profile.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the fakeable no-authority Q15-R trust-anchor adapter")
add_custom_target(
  q15-r-stand-setup-preparation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_stand_setup_authorization_preparation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the exact blocked Q15-R stand-setup authorization preparation")
add_custom_target(
  q15-r-operational-release-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_operational_release_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the proposed no-authority Q15-R operational-release selection")
add_custom_target(
  q15-r-p3-acceptance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p3_acceptance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted D-065 and the repository-local-only authority boundary")
add_custom_target(
  q15-r-stand-setup-preparation-v2-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_stand_setup_authorization_preparation_v2.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the versioned no-authority successor stand-setup preparation")
add_custom_target(
  q15-r-external-input-acquisition-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_external_input_acquisition.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed D-066 through D-070 without external-input or stand authority")
add_custom_target(
  q15-r-p4-d-implementation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_d_implementation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted D-066 through D-070 and the no-authority prestate collector")
add_custom_target(
  q15-r-p4-r-collector-release-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_collector_release_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed D-071 no-authority collector-release selection")
add_custom_target(
  q15-r-p4-e-acceptance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_e_acceptance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted D-071 and the no-authority P4-E boundary")
add_custom_target(
  q15-r-p4-r-preparation-v2-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_preparation_v2.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the versioned P4-R successor with release evidence only")
add_custom_target(
  q15-r-p4-r-staging-authorization-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_staging_authorization_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed D-072 through D-075 without stand or execution authority")
add_custom_target(
  q15-r-p4-f-acceptance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_f_acceptance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted D-072 through D-075 without operational authority")
add_custom_target(
  q15-r-p4-r-successor-templates-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_r_successor_templates.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking still-unissued split P4-R-I and P4-R-C templates")
add_custom_target(
  q15-r-p4-k-decision-input-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_decision_input.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed P4-K owner inputs without key or stand authority")
add_custom_target(
  q15-r-p4-k-d-acceptance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_d_acceptance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted P4-K owner choices without key or stand authority")
add_custom_target(
  q15-r-p4-k-successor-templates-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_successor_templates.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking still-unissued split P4-K-A and P4-K-R templates")
add_custom_target(
  q15-r-p4-k-a-operational-input-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_operational_input_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed P4-K-A operational inputs without key authority")
add_custom_target(
  q15-r-p4-k-a-d-acceptance-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_d_acceptance.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted P4-K-A policy and absent-bootstrap fail-closed state")
add_custom_target(
  q15-r-p4-k-a-controller-profile-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_p4_k_a_controller_profile.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the generic no-authority P4-K-A controller profile")
add_custom_target(
  q15-r-bootstrap-governance-root-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_r_bootstrap_governance_root_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed bootstrap governance-root inputs without key authority")
add_custom_target(
  q15-r-bootstrap-d093-authorization-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d093_bootstrap_authorization.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the exact one-action D-093 bootstrap-root authorization")
add_custom_target(
  q15-r-bootstrap-d093-evidence-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d093_bootstrap_evidence.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking D-093 public evidence and the created/not-active boundary")
add_custom_target(
  q15-r-bootstrap-d094-activation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d094_bootstrap_activation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking exact root activation and the still-unissued P4-K-A successor")
add_custom_target(
  q15-r-p4-k-a-d095-terminal-failure-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d095_terminal_failure.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking terminal D-095 partial evidence and the no-retry boundary")
add_custom_target(
  q15-r-p4-k-a-d096-authorization-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d096_authorization.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the corrected one-shot D-096 authorization")
add_custom_target(
  q15-r-p4-k-a-d096-complete-evidence-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d096_complete_evidence.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking complete D-096 public/private-metadata evidence")
add_custom_target(
  q15-r-p4-k-r-d097-preparation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d097_p4_k_r_preparation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking still-unissued D-097 P4-K-R preparation")
add_custom_target(
  q15-r-p4-k-r-d097-authorization-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d097_authorization.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the one-shot public-only D-097 authorization")
add_custom_target(
  q15-r-p4-k-r-d097-complete-evidence-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d097_complete_evidence.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking complete D-097 public-only review evidence")
add_custom_target(
  q15-r-p5-d098-preparation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d098_p5_preparation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the D-097-bound still-unissued P5 preparation")
add_custom_target(
  q15-r-p4-r-i-d099-complete-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d099_p4_r_i_complete.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking complete D-099 read-only P4-R-I evidence")
add_custom_target(
  q15-r-p4-r-c-d100-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d100_p4_r_c_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed no-action D-100 through D-103 P4-R-C decisions")
add_custom_target(
  q15-r-p4-r-c-d104-implementation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d104_p4_r_c_implementation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted D-100 through D-103 P4-R-C implementation and blocked action gate")
add_custom_target(
  q15-r-p4-r-c-d105-runtime-decision-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_d105_runtime_decision.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking proposed no-action D-105 through D-108 runtime evidence decisions")
add_custom_target(
  stage17-operational-successor-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_operational_successor.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking immutable Stage 17 predecessor/templates and the journal successor")
add_custom_target(
  stage17-state-journal-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_state_journal.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_openssh_snapshot_consumption.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_authority_child_lifecycle.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_process_group_quiescence.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_process_group_evidence.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_external_journal_preflight.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_external_journal_preflight_v2.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_read_only_preflight_policy_v10.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v13.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_read_only_preflight_policy_v11.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v14.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v15.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_read_only_preflight_policy_v12.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v16.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_pre_marker_runtime_cardinality.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_read_only_preflight_policy_v13.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v17.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_preflight_terminal_compatibility.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_action_revalidation_binding.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_read_only_preflight_policy_v14.py"
    --check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v18.py"
    --check
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking Stage 17 journal admission and real local OpenSSH snapshot consumption")
add_custom_target(
  stage17-no-predecessor-attestation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_no_predecessor_attestation.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the D-124 no-predecessor-attestation branch (ADR-0124, PROPOSED; grants no authority)")
add_custom_target(
  stage17-executor-v13-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v13_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v13's action-readiness binding for both predecessor-evidence branches (ADR-0126, PROPOSED; grants no authority)")
add_custom_target(
  stage17-executor-v14-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v14_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v14's journal-reachability fix for both predecessor-evidence branches (ADR-0130, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v15-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v15_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v15's kernel-thread-tolerant process-group supervisor fix for both predecessor-evidence branches (ADR-0131, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v16-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v16_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v16's OpenSSH snapshot mechanism identity fix for both predecessor-evidence branches (ADR-0132, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v17-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v17_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v17's OpenSSH snapshot broker re-export completeness fix for both predecessor-evidence branches (ADR-0133, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v18-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v18_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v18's corrected read-only preflight archive-identity source (ADR-0134, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v19-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v19_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v19's corrected read-only preflight runtime-tool symlink identity (ADR-0135, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v20-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v20_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v20's completed journal reachability lockstep fix (ADR-0137, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v21-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v21_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v21's completed journal reachability lockstep fix (ADR-0139, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v22-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v22_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v22's completed journal reachability lockstep fix (ADR-0141, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-phase-controller-v11-journal-reachability-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_phase_controller_v11_journal_reachability.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking phase-controller v11's completed journal reachability fix (ADR-0142, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v23-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v23_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v23's completed journal reachability lockstep fix (ADR-0144, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-phase-controller-v12-journal-reachability-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_phase_controller_v12_journal_reachability.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking phase-controller v12's completed journal reachability fix (ADR-0144, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-q15-session-controller-v9-phase-controller-binding-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_q15_session_controller_v9_phase_controller_binding.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking q15-session-controller v9's phase_controller binding stays journal-current (ADR-0144, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v24-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v24_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v24's completed journal reachability lockstep fix (ADR-0145, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-phase-controller-v13-journal-reachability-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_phase_controller_v13_journal_reachability.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking phase-controller v13's completed journal reachability fix (ADR-0145, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-q15-session-controller-v11-phase-controller-binding-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_q15_session_controller_v11_phase_controller_binding.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking q15-session-controller v11's phase_controller binding stays journal-current (ADR-0145, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-q15-session-failure-retention-v10-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_q15_session_failure_retention_v10.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the real Q15 session failure-retention schema fix (ADR-0145, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-q15-session-execute-session-wiring-v12-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_q15_session_execute_session_wiring_v12.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the real Q15 session execute_session wiring fix (ADR-0146, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-q15-session-controller-v16-parse-prestate-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_q15_session_controller_v16_parse_prestate.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking q15-session-controller v16's _parse_prestate fix accepts both registered CPU mappings (ADR-0173, ACCEPTED; grants no authority)")
add_custom_target(
  q16a-discovery-design-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_q16a_discovery.py"
  VERBATIM)

add_custom_target(
  stage17-discovery-validation-v3-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_discovery_validation_v3.py"
  VERBATIM)

add_custom_target(
  stage17-calibration-mapping-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_calibration_mapping.py"
    --root "${PROJECT_SOURCE_DIR}"
  VERBATIM)

add_custom_target(
  stage17-calibration-policy-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/author_stage17_policy_v54.py"
    --root "${PROJECT_SOURCE_DIR}" --check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_calibration_mapping.py"
    --root "${PROJECT_SOURCE_DIR}" --check-policy
  VERBATIM)

add_custom_target(
  stage17-output-registry-v6-msr-map-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_output_registry_v6_msr_map.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking output-registry v6's _msr_map fix accepts both registered CPU mappings (ADR-0173, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-phase-controller-v14-journal-reachability-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_phase_controller_v14_journal_reachability.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking phase-controller v14's completed journal reachability fix (ADR-0146, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-executor-v25-action-readiness-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_executor_v25_action_readiness.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking executor v25's completed journal reachability lockstep fix (ADR-0146, ACCEPTED; grants no authority)")
add_custom_target(
  stage17-pilot-candidate-profile-recognition-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_pilot_candidate_profile_recognition.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking pilot-candidate artifact v5's broadened profile recognition against a real sealed bundle (ADR-0128, PROPOSED; grants no authority)")
add_custom_target(
  stage17-openssh-consumption-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_openssh_snapshot_consumption.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Characterizing OpenSSH fd hygiene and parent-procfd snapshot consumption locally")
add_custom_target(
  stage17-authority-child-lifecycle-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_authority_child_lifecycle.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking final authority guards and bounded SSH child/process-group cleanup locally")
add_custom_target(
  stage17-process-group-quiescence-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_process_group_quiescence.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_process_group_evidence.py"
    --self-test
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking held-leader group quiescence and typed cleanup evidence locally")
add_custom_target(
  stage17-complete-operational-admission-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_pid_namespace_supervisor.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_pilot_semantics_v3.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_pilot_semantics_v4.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/stage17_raw_stream_decoder_v1.py"
    --self-test
  DEPENDS cpu_prefetch_stage17_test_worker cpu_prefetch_stage17_no_result_worker
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking Stage 17 PID namespace, durable full pilot plan, and independent raw decoding locally")
add_custom_target(
  stage17-pilot-candidate-artifact-integration-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_pilot_candidate_artifact.py"
    --archive "${CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_ARCHIVE}"
    --sidecar "${CPU_PREFETCH_STAGE17_PILOT_CANDIDATE_SIDECAR}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking caller-supplied real pilot-candidate archive/sidecar bytes; never a self-test")
add_custom_target(
  q15-qualification-archive-integration-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_qualification_archive.py"
    --archive "${CPU_PREFETCH_Q15_QUALIFICATION_ARCHIVE}"
    --sidecar "${CPU_PREFETCH_Q15_QUALIFICATION_SIDECAR}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking an explicitly supplied exact external qualification archive; never a self-test")
add_custom_target(
  q15-authorization-v2-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_authorization_v2.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the fixed-controller Q15-R authorization-v2 envelope")
add_custom_target(
  q15-controller-profile-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_controller_profile.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the fixed controller and unapplied role/custody profiles")
add_custom_target(
  q15-probe-collector-contract-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_collector_contract.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the frozen no-execution Q15 probe/collector contract")
add_custom_target(
  q15-probe-implementation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_probe_implementation.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the accepted no-authority D-053 implementation profile")
add_custom_target(
  q15-dynamic-implementation-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_dynamic_implementation.py"
    --source-root "${PROJECT_SOURCE_DIR}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking accepted no-authority D-054 through D-056 implementation")
add_custom_target(
  q15-bundle-profile-check
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_q15_bundle_profile.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the separate no-authority Q15 bundle profile")
add_custom_target(
  document-check
  COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_docs.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking repository-local Markdown links")
add_custom_target(
  dependency-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_dependencies.py"
    "${PROJECT_SOURCE_DIR}/config/dependencies.json"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking the dependency and license inventory")
add_custom_target(
  ci-check
  COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_ci.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking pinned CI and local-command parity")
add_custom_target(
  release-policy-check
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/check_release_flags.py"
    "${PROJECT_BINARY_DIR}/compile_commands.json"
  COMMENT "Rejecting unsafe or host-native release flags")

install(
  TARGETS
    cpu_prefetch_analysis
    cpu_prefetch_calibration
    cpu_prefetch_orchestration
    cpu_prefetch_foundation
    cpu_prefetch_lifecycle
    cpu_prefetch_platform
    cpu_prefetch_q15_qualification
    cpu_prefetch_protocol
    cpu_prefetch_queue
    cpu_prefetch_reconciliation
    cpu_prefetch_runner_core
    cpu_prefetch_schedule
    cpu_prefetch_storage
    cpu_prefetch_timing
    cpu_prefetch_workload
    cpu_prefetch_preflight
    cpu_prefetch_qualification
    cpu_prefetch_q15_tool
    cpu_prefetch_q15_controller
    cpu_prefetch_q15_prestate_collector
    cpu_prefetch_runner
    cpu_prefetch_smoke
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
install(DIRECTORY include/ DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(
  PROGRAMS "${PROJECT_SOURCE_DIR}/tools/generate_schedule.py"
  DESTINATION "${CMAKE_INSTALL_BINDIR}"
  RENAME cpu-prefetch-generate-schedule)
install(
  PROGRAMS "${PROJECT_SOURCE_DIR}/tools/calibration_statistics.py"
  DESTINATION "${CMAKE_INSTALL_BINDIR}"
  RENAME cpu-prefetch-calibration-statistics)
install(
  FILES
    "${PROJECT_BINARY_DIR}/generated/include/cpu_prefetch/foundation/build_metadata.hpp"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/cpu_prefetch/foundation")
install(
  FILES
    "${PROJECT_BINARY_DIR}/generated/version_metadata.json"
    "${PROJECT_SOURCE_DIR}/protocol/2.0.0-pre.3/handoff/PROTOCOL_VERSION.md"
    "${PROJECT_SOURCE_DIR}/config/dependencies.json"
    "${PROJECT_SOURCE_DIR}/docs/PLATFORM_CONTROL.md"
    "${PROJECT_SOURCE_DIR}/docs/ANALYSIS.md"
    "${PROJECT_SOURCE_DIR}/docs/CALIBRATION.md"
    "${PROJECT_SOURCE_DIR}/docs/LIFECYCLE.md"
    "${PROJECT_SOURCE_DIR}/docs/ORCHESTRATION.md"
    "${PROJECT_SOURCE_DIR}/docs/PROTOCOL_MODEL.md"
    "${PROJECT_SOURCE_DIR}/docs/QUEUE_CORRECTNESS.md"
    "${PROJECT_SOURCE_DIR}/docs/RECONCILIATION.md"
    "${PROJECT_SOURCE_DIR}/docs/PRODUCTION_RUNNER.md"
    "${PROJECT_SOURCE_DIR}/docs/Q15_QUALIFICATION_CONTRACT.md"
    "${PROJECT_SOURCE_DIR}/docs/Q15_QUALIFICATION_TOOL.md"
    "${PROJECT_SOURCE_DIR}/docs/SCHEDULE_GENERATION.md"
    "${PROJECT_SOURCE_DIR}/docs/STORAGE.md"
    "${PROJECT_SOURCE_DIR}/docs/TIMING.md"
    "${PROJECT_SOURCE_DIR}/docs/WORKLOAD_CONSTRUCTION.md"
    "${PROJECT_SOURCE_DIR}/docs/NO_LICENSE_GRANT.md"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation")
install(
  FILES
    "${PROJECT_SOURCE_DIR}/docs/PRE_PILOT_READINESS_REPORT.md"
    "${PROJECT_SOURCE_DIR}/docs/Q15_R_DECISION_INPUT_BUNDLE.md"
    "${PROJECT_SOURCE_DIR}/docs/Q15_R_EXTERNAL_INPUT_ACQUISITION_DECISION_BUNDLE.md"
    "${PROJECT_SOURCE_DIR}/docs/Q15_R_PRESTATE_COLLECTOR.md"
    "${PROJECT_SOURCE_DIR}/docs/Q15_STAND_QUALIFICATION_DECISION_BUNDLE.md"
    "${PROJECT_SOURCE_DIR}/docs/STAGE17_PILOT_AUTHORIZATION_DECISION_BUNDLE.md"
    "${PROJECT_SOURCE_DIR}/docs/STAGE17_OPERATIONAL_AUTHORIZATION.md"
    "${PROJECT_SOURCE_DIR}/docs/STAND_BUNDLE.md"
    "${PROJECT_SOURCE_DIR}/docs/STAND_RUNBOOK.md"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation")
install(
  DIRECTORY "${PROJECT_SOURCE_DIR}/config/queue-provenance"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation"
  FILES_MATCHING
  PATTERN "*.json")
install(
  DIRECTORY "${PROJECT_SOURCE_DIR}/config/schemas"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation"
  FILES_MATCHING
  PATTERN "*.json"
  PATTERN "*.md")
install(
  DIRECTORY "${PROJECT_SOURCE_DIR}/config/q15"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation"
  FILES_MATCHING
  PATTERN "*.json")
install(
  DIRECTORY "${PROJECT_SOURCE_DIR}/config/stage17"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation"
  FILES_MATCHING
  PATTERN "*.json")

set(CPACK_GENERATOR "TGZ")
set(CPACK_PACKAGE_NAME "cpu-prefetch-stand-foundation")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_FILE_NAME
    "${CPACK_PACKAGE_NAME}-${PROJECT_VERSION}-${CPU_PREFETCH_GIT_REVISION_SHORT}${CPU_PREFETCH_SOURCE_STATE_SUFFIX}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Stage 16 verified stand-preflight foundation")
set(CPACK_PACKAGE_VENDOR "Private repository; no license grant")
include(CPack)

add_custom_target(
  stand-bundle
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/create_stand_bundle.py"
    --source-root "${PROJECT_SOURCE_DIR}"
    --build-dir "${PROJECT_BINARY_DIR}"
    --output-dir "${PROJECT_BINARY_DIR}/stand-bundle"
    --profile stage16-preflight
  DEPENDS
    cpu_prefetch_analysis
    cpu_prefetch_calibration
    cpu_prefetch_foundation
    cpu_prefetch_lifecycle
    cpu_prefetch_orchestration
    cpu_prefetch_platform
    cpu_prefetch_q15_qualification
    cpu_prefetch_preflight
    cpu_prefetch_protocol
    cpu_prefetch_queue
    cpu_prefetch_reconciliation
    cpu_prefetch_schedule
    cpu_prefetch_smoke
    cpu_prefetch_storage
    cpu_prefetch_timing
    cpu_prefetch_workload
  COMMENT "Creating the append-only Stage 16 stand-preflight bundle")

# These are prospective package inputs, not inferred host/runtime defaults.
set(CPU_PREFETCH_ARCHIVE_RUNTIME_ROOT "" CACHE PATH "Explicit accepted archive Python/zstd runtime root")
set(CPU_PREFETCH_ARCHIVE_WINDOW_LOG "" CACHE STRING "Explicit archive zstd window_log (10..31)")

add_custom_target(
  pilot-candidate-bundle
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/create_stand_bundle.py"
    --source-root "${PROJECT_SOURCE_DIR}"
    --build-dir "${PROJECT_BINARY_DIR}"
    --output-dir "${PROJECT_BINARY_DIR}/pilot-candidate-bundle"
    --profile stage17-pilot-candidate
    --archive-runtime-root "${CPU_PREFETCH_ARCHIVE_RUNTIME_ROOT}"
    --archive-window-log "${CPU_PREFETCH_ARCHIVE_WINDOW_LOG}"
  DEPENDS
    cpu_prefetch_stage17_archive_encoder
    cpu_prefetch_q15_clock_qualification_tool
    cpu_prefetch_q15_qualification_evidence_tool
    cpu_prefetch_analysis
    cpu_prefetch_calibration
    cpu_prefetch_foundation
    cpu_prefetch_lifecycle
    cpu_prefetch_orchestration
    cpu_prefetch_platform
    cpu_prefetch_q15_qualification
    cpu_prefetch_preflight
    cpu_prefetch_protocol
    cpu_prefetch_qualification
    cpu_prefetch_queue
    cpu_prefetch_reconciliation
    cpu_prefetch_runner
    cpu_prefetch_schedule
    cpu_prefetch_smoke
    cpu_prefetch_storage
    cpu_prefetch_timing
    cpu_prefetch_workload
    queue-codegen-check
    discovery-codegen-check
    formal-codegen-check
    runner-combined-codegen-check
    runner-relax-codegen-check
    storage-codegen-check
    timing-codegen-check
    workload-codegen-check
  COMMENT
    "Creating the clean, no-authority Stage 17 pilot-candidate bundle; all strict codegen gates must pass")

add_custom_target(
  stage17-hermetic-handoff-check
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_discovery_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/stage17-hermetic-codegen/discovery_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  COMMAND "${Python3_EXECUTABLE}" -B
    "${PROJECT_SOURCE_DIR}/tools/check_formal_codegen.py"
    --binary "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>"
    --source-root "${PROJECT_SOURCE_DIR}"
    --output "${PROJECT_BINARY_DIR}/stage17-hermetic-codegen/formal_codegen_report.json"
    --gnu-objdump "${CPU_PREFETCH_GNU_OBJDUMP}"
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/create_stand_bundle.py"
    --source-root "${PROJECT_SOURCE_DIR}"
    --build-dir "${PROJECT_BINARY_DIR}"
    --output-dir "${PROJECT_BINARY_DIR}/stage17-hermetic-handoff-bundle/${CPU_PREFETCH_GIT_REVISION_SHORT}"
    --profile stage17-hermetic-dry-run
    --archive-runtime-root "${CPU_PREFETCH_ARCHIVE_RUNTIME_ROOT}"
    --archive-window-log "${CPU_PREFETCH_ARCHIVE_WINDOW_LOG}"
    --native-codegen-report-dir "${PROJECT_BINARY_DIR}/stage17-hermetic-codegen"
    --test-linked-worker "$<TARGET_FILE:cpu_prefetch_stage17_test_worker>"
    --no-result-worker "$<TARGET_FILE:cpu_prefetch_stage17_no_result_worker>"
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/run_stage17_hermetic_handoff.py"
    --bundle-root "${PROJECT_SOURCE_DIR}"
    --bundle-directory "${PROJECT_BINARY_DIR}/stage17-hermetic-handoff-bundle/${CPU_PREFETCH_GIT_REVISION_SHORT}"
  DEPENDS
    cpu_prefetch_stage17_archive_encoder
    cpu_prefetch_q15_clock_qualification_tool
    cpu_prefetch_q15_qualification_evidence_tool
    cpu_prefetch_analysis
    cpu_prefetch_calibration
    cpu_prefetch_foundation
    cpu_prefetch_lifecycle
    cpu_prefetch_orchestration
    cpu_prefetch_platform
    cpu_prefetch_preflight
    cpu_prefetch_protocol
    cpu_prefetch_qualification
    cpu_prefetch_queue
    cpu_prefetch_reconciliation
    cpu_prefetch_runner
    cpu_prefetch_schedule
    cpu_prefetch_smoke
    cpu_prefetch_stage17_no_result_worker
    cpu_prefetch_stage17_test_worker
    cpu_prefetch_storage
    cpu_prefetch_timing
    cpu_prefetch_workload
    queue-codegen-check
    discovery-codegen-check
    formal-codegen-check
    runner-combined-codegen-check
    runner-relax-codegen-check
    storage-codegen-check
    timing-codegen-check
    workload-codegen-check
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT
    "Building, fully verifying, and executing the no-authority Stage 17 hermetic handoff")

add_custom_target(
  q15-qualification-tool-bundle
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/create_stand_bundle.py"
    --source-root "${PROJECT_SOURCE_DIR}"
    --build-dir "${PROJECT_BINARY_DIR}"
    --output-dir "${PROJECT_BINARY_DIR}/q15-qualification-tool-bundle"
    --profile q15-qualification-tool
  DEPENDS
    cpu_prefetch_foundation
    cpu_prefetch_platform
    cpu_prefetch_preflight
    cpu_prefetch_protocol
    cpu_prefetch_q15_controller
    cpu_prefetch_q15_prestate_collector
    cpu_prefetch_q15_tool
    cpu_prefetch_qualification
    cpu_prefetch_smoke
    cpu_prefetch_workload
    q15-bundle-profile-check
    q15-probe-codegen-check
    q15-runtime-codegen-check
    q15-controller-codegen-check
    q15-controller-profile-check
    q15-r-p2-acceptance-check
    q15-r-p4-d-implementation-check
    q15-r-stand-setup-preparation-check
    q15-trust-anchor-adapter-profile-check
    q15-probe-collector-contract-check
    q15-probe-implementation-check
    q15-dynamic-implementation-check
    qualification-schema-check
  COMMENT
    "Creating the clean, separate, no-authority Q15 qualification-tool bundle")
