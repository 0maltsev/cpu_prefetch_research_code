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
  PRIVATE cpu_prefetch_project_options OpenSSL::Crypto)
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
  src/platform/q15_runtime.cpp)
add_library(cpu_prefetch::platform ALIAS cpu_prefetch_platform)
target_link_libraries(
  cpu_prefetch_platform
  PUBLIC cpu_prefetch::protocol cpu_prefetch::workload
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
  src/runner/runner.cpp)
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
  src/storage/raw_observations.cpp)
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

# ADR-0044's owner-thread preparation uses the already-allocated Stage 11
# private streams. The dependency is declared only after the storage target is
# available; storage itself has no runner dependency.
target_link_libraries(cpu_prefetch_runner_core PUBLIC cpu_prefetch::storage)

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

add_library(cpu_prefetch_calibration STATIC src/calibration/calibration.cpp)
add_library(cpu_prefetch::calibration ALIAS cpu_prefetch_calibration)
target_link_libraries(
  cpu_prefetch_calibration
  PUBLIC
    cpu_prefetch::protocol
    cpu_prefetch::queue
    cpu_prefetch::timing
    cpu_prefetch::workload
  PRIVATE cpu_prefetch_project_options)
target_include_directories(
  cpu_prefetch_calibration
  PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")

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

  add_executable(cpu_prefetch_platform_tests tests/platform_model_test.cpp)
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

  add_executable(cpu_prefetch_runner_tests tests/runner_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_runner_tests
    PRIVATE cpu_prefetch::runner cpu_prefetch_project_options GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_runner_tests
    PREFIX "runner."
    PROPERTIES LABELS "runner;pre-pilot;synthetic")

  add_test(NAME runner.qualification_self_test COMMAND cpu_prefetch_qualification
                 --self-test)
  set_tests_properties(
    runner.qualification_self_test
    PROPERTIES
      LABELS "runner;qualification;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "qualification-self-test: PASS.*stand=NOT_ACCESSED.*authority=Q15_REQUIRED")
  add_test(NAME q15.tool_self_test COMMAND cpu_prefetch_q15_tool --self-test)
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
    NAME runner.stage17_operational_successor
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_operational_successor.py"
            --self-test)
  set_tests_properties(
    runner.stage17_operational_successor
    PROPERTIES
      LABELS "runner;authorization;governance;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS.*legacy_template=true.*state=PREPARED.*transitions=0.*external_inputs=10.*pilot_ready=false.*stand=NOT_ACCESSED")
  add_test(
    NAME runner.stage17_state_journal
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tools/check_stage17_state_journal.py"
            --self-test)
  set_tests_properties(
    runner.stage17_state_journal
    PROPERTIES
      LABELS "runner;authorization;governance;state-journal;pre-pilot;synthetic"
      PASS_REGULAR_EXPRESSION
        "PASS.*state=PREPARED.*resolved=0.*missing=10.*pilot_ready=false.*semantic_positive=1/1.*mechanics_positive=10/3.*negative=52.*nonexistent_evidence=REJECTED.*generic_evidence=REJECTED.*reload=PASS.*Stage18=false.*stand=NOT_ACCESSED")
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
            "${PROJECT_SOURCE_DIR}/tools/check_d100_p4_r_c_decision.py")
  set_tests_properties(
    q15.r_p4_r_c_d100_decision
    PROPERTIES LABELS "q15;qualification;security;custody;decision;authorization;schema;pre-pilot;synthetic")
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

  add_executable(cpu_prefetch_calibration_tests tests/calibration_model_test.cpp)
  target_link_libraries(
    cpu_prefetch_calibration_tests
    PRIVATE cpu_prefetch::calibration cpu_prefetch_project_options
            GTest::gtest_main)
  gtest_discover_tests(
    cpu_prefetch_calibration_tests
    PREFIX "calibration."
    PROPERTIES LABELS "calibration;synthetic")

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
    PROPERTIES PASS_REGULAR_EXPRESSION "protocol=2.0.0-pre.2")

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
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/runner/software_prefetch.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/calibration/calibration.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/foundation/repository_info.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/executor.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/state_machine.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/linux_inventory.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/platform.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/q15_probe.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/q15_msr.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/q15_runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/qualification/p4_k_a_controller.hpp"
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
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/clock.hpp"
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
  "${PROJECT_SOURCE_DIR}/src/lifecycle/runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/state_machine.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/linux_inventory.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/platform.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_counted_region.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_probe.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_msr.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/p4_k_a_controller.cpp"
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
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/schedule/schedule.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifact_store.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifacts.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/budget.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/finalization.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/raw_observations.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/clock.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/intervals.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/deterministic.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/packages.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/records.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/working_set.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/analysis_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/orchestration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_concurrency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_state_machine_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_phase_test_access.hpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/p4_k_a_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_probe_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_collectors_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_prestate_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_msr_tool_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/reconciliation_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/runner_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/schedule_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_model_test.cpp"
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
  "${PROJECT_SOURCE_DIR}/tools/runner_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/qualification_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_qualification_tool_main.cpp"
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
  "${PROJECT_SOURCE_DIR}/src/lifecycle/runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/state_machine.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/linux_inventory.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/platform.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_counted_region.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_probe.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_msr.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/q15_runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/qualification/p4_k_a_controller.cpp"
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
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/schedule/schedule.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifact_store.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/artifacts.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/budget.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/finalization.cpp"
  "${PROJECT_SOURCE_DIR}/src/storage/raw_observations.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/clock.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/intervals.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/deterministic.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/packages.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/records.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/working_set.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/analysis_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/orchestration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/calibration_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_concurrency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_state_machine_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/p4_k_a_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_probe_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_runtime_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_collectors_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_controller_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_prestate_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/q15_msr_tool_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/reconciliation_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/runner_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/schedule_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/storage_model_test.cpp"
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
  "${PROJECT_SOURCE_DIR}/tools/runner_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/qualification_main.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_probe_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_runtime_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_controller_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/q15_qualification_tool_main.cpp"
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
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_operational_successor.py"
    --self-test
  COMMAND
    "${Python3_EXECUTABLE}"
    "${PROJECT_SOURCE_DIR}/tools/check_stage17_state_journal.py"
    --self-test
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
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Checking append-only Stage 17 mechanics and default-deny semantic evidence admission")
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
    "${PROJECT_SOURCE_DIR}/protocol/2.0.0-pre.2/handoff/PROTOCOL_VERSION.md"
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

add_custom_target(
  pilot-candidate-bundle
  COMMAND
    "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/create_stand_bundle.py"
    --source-root "${PROJECT_SOURCE_DIR}"
    --build-dir "${PROJECT_BINARY_DIR}"
    --output-dir "${PROJECT_BINARY_DIR}/pilot-candidate-bundle"
    --profile stage17-pilot-candidate
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
    runner-combined-codegen-check
    runner-relax-codegen-check
    storage-codegen-check
    timing-codegen-check
    workload-codegen-check
  COMMENT
    "Creating the clean, no-authority Stage 17 pilot-candidate bundle; all strict codegen gates must pass")

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
