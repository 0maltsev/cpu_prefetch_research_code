cmake_minimum_required(VERSION 4.3)

project(
  cpu_prefetch_foundation
  VERSION 2.0.0
  DESCRIPTION "Typed protocol and deterministic lifecycle foundation for the CPU prefetch research protocol"
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
  src/platform/platform.cpp)
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

add_executable(cpu_prefetch_smoke tools/smoke_main.cpp)
target_link_libraries(
  cpu_prefetch_smoke PRIVATE cpu_prefetch::foundation cpu_prefetch_project_options)

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

  add_test(
    NAME schedule.python_generator
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tests/test_schedule_generator.py")
  set_tests_properties(schedule.python_generator PROPERTIES LABELS "schedule;python")

  add_custom_target(
    schedule-check
    COMMAND "${Python3_EXECUTABLE}"
            "${PROJECT_SOURCE_DIR}/tests/test_schedule_generator.py"
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    COMMENT "Checking deterministic Stage 7 schedule generation and schemas")

  if(NOT (CPU_PREFETCH_SANITIZER STREQUAL "THREAD" AND
          CMAKE_CXX_COMPILER_ID MATCHES "Clang"))
    add_executable(cpu_prefetch_workload_noalloc tests/workload_noalloc_test.cpp)
    target_link_libraries(
      cpu_prefetch_workload_noalloc
      PRIVATE cpu_prefetch::workload cpu_prefetch_project_options GTest::gtest_main)
    gtest_discover_tests(cpu_prefetch_workload_noalloc PREFIX "workload.noalloc.")
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
    PROPERTIES PASS_REGULAR_EXPRESSION "protocol=2.0.0-pre.1")

  if(CPU_PREFETCH_ENABLE_PROPERTY_TESTS)
    find_package(RapidCheck REQUIRED)
    add_executable(cpu_prefetch_rapidcheck_smoke tests/rapidcheck_smoke.cpp)
    target_link_libraries(
      cpu_prefetch_rapidcheck_smoke
      PRIVATE
        cpu_prefetch::protocol
        cpu_prefetch::queue
        cpu_prefetch::workload
        cpu_prefetch_project_options
        RapidCheck::rapidcheck)
    add_test(NAME property.framework_smoke COMMAND cpu_prefetch_rapidcheck_smoke)
    set_tests_properties(
      property.framework_smoke
      PROPERTIES ENVIRONMENT "RC_PARAMS=seed=20260817")
  endif()
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

find_program(CPU_PREFETCH_CLANG_FORMAT NAMES clang-format REQUIRED)
find_program(CPU_PREFETCH_CLANG_TIDY NAMES clang-tidy REQUIRED)
find_program(CPU_PREFETCH_GNU_OBJDUMP NAMES objdump REQUIRED)
cpu_prefetch_enforce_tool_versions()

set(
  CPU_PREFETCH_FORMAT_FILES
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/foundation/repository_info.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/executor.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/runtime.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/lifecycle/state_machine.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/linux_inventory.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/platform/platform.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/json.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/model.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/validation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/adapters.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/common.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/linked_spsc.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/ring_spsc.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/schedule/schedule.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/capture.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/clock.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/intervals.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/timing/qualification.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/deterministic.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/packages.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/records.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/workload/working_set.hpp"
  "${PROJECT_SOURCE_DIR}/src/repository_info.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/state_machine.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/linux_inventory.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/platform.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/json.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/load.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/model.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/semantic.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/validation.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/schedule/schedule.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/clock.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/intervals.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/deterministic.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/packages.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/records.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/working_set.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_concurrency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_state_machine_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_phase_test_access.hpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/schedule_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/timing_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_probe.cpp"
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
  "${PROJECT_SOURCE_DIR}/src/lifecycle/runtime.cpp"
  "${PROJECT_SOURCE_DIR}/src/lifecycle/state_machine.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/linux_inventory.cpp"
  "${PROJECT_SOURCE_DIR}/src/platform/platform.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/json.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/load.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/model.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/semantic.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/validation.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/schedule/schedule.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/capture.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/clock.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/intervals.cpp"
  "${PROJECT_SOURCE_DIR}/src/timing/qualification.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/deterministic.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/packages.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/records.cpp"
  "${PROJECT_SOURCE_DIR}/src/workload/working_set.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_concurrency_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/lifecycle_state_machine_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/platform_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/schedule_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/timing_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/workload_noalloc_test.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_probe.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/timing_codegen_probe.cpp"
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
  DEPENDS cpu_prefetch_smoke
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
    cpu_prefetch_foundation
    cpu_prefetch_lifecycle
    cpu_prefetch_platform
    cpu_prefetch_protocol
    cpu_prefetch_queue
    cpu_prefetch_schedule
    cpu_prefetch_timing
    cpu_prefetch_workload
    cpu_prefetch_smoke
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
install(DIRECTORY include/ DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(
  PROGRAMS "${PROJECT_SOURCE_DIR}/tools/generate_schedule.py"
  DESTINATION "${CMAKE_INSTALL_BINDIR}"
  RENAME cpu-prefetch-generate-schedule)
install(
  FILES
    "${PROJECT_BINARY_DIR}/generated/include/cpu_prefetch/foundation/build_metadata.hpp"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/cpu_prefetch/foundation")
install(
  FILES
    "${PROJECT_BINARY_DIR}/generated/version_metadata.json"
    "${PROJECT_SOURCE_DIR}/protocol/2.0.0-pre.1/handoff/PROTOCOL_VERSION.md"
    "${PROJECT_SOURCE_DIR}/config/dependencies.json"
    "${PROJECT_SOURCE_DIR}/docs/PLATFORM_CONTROL.md"
    "${PROJECT_SOURCE_DIR}/docs/LIFECYCLE.md"
    "${PROJECT_SOURCE_DIR}/docs/PROTOCOL_MODEL.md"
    "${PROJECT_SOURCE_DIR}/docs/QUEUE_CORRECTNESS.md"
    "${PROJECT_SOURCE_DIR}/docs/SCHEDULE_GENERATION.md"
    "${PROJECT_SOURCE_DIR}/docs/TIMING.md"
    "${PROJECT_SOURCE_DIR}/docs/WORKLOAD_CONSTRUCTION.md"
    "${PROJECT_SOURCE_DIR}/docs/NO_LICENSE_GRANT.md"
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

set(CPACK_GENERATOR "TGZ")
set(CPACK_PACKAGE_NAME "cpu-prefetch-stand-foundation")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_FILE_NAME
    "${CPACK_PACKAGE_NAME}-${PROJECT_VERSION}-${CPU_PREFETCH_GIT_REVISION_SHORT}${CPU_PREFETCH_SOURCE_STATE_SUFFIX}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Non-measuring Stage 10 deterministic lifecycle foundation")
set(CPACK_PACKAGE_VENDOR "Private repository; no license grant")
include(CPack)
