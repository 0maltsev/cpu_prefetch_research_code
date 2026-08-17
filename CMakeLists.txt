cmake_minimum_required(VERSION 4.3)

project(
  cpu_prefetch_foundation
  VERSION 2.0.0
  DESCRIPTION "Typed protocol and queue correctness foundation for the CPU prefetch research protocol"
  LANGUAGES CXX)

list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cmake")

include(CTest)
include(GNUInstallDirs)
include(CompilerPolicy)
include(Sanitizers)
include(VersionPolicy)
include(Warnings)

find_package(Git 2.54 REQUIRED)
find_package(Python3 3.14 REQUIRED COMPONENTS Interpreter)

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

find_program(CPU_PREFETCH_CLANG_FORMAT NAMES clang-format REQUIRED)
find_program(CPU_PREFETCH_CLANG_TIDY NAMES clang-tidy REQUIRED)
find_program(CPU_PREFETCH_GNU_OBJDUMP NAMES objdump REQUIRED)
cpu_prefetch_enforce_tool_versions()

set(
  CPU_PREFETCH_FORMAT_FILES
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/foundation/repository_info.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/json.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/model.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/protocol/validation.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/adapters.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/common.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/linked_spsc.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpu_prefetch/queue/ring_spsc.hpp"
  "${PROJECT_SOURCE_DIR}/src/repository_info.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/json.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/load.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/model.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/semantic.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/validation.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_phase_test_access.hpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_probe.cpp"
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
  "${PROJECT_SOURCE_DIR}/src/protocol/json.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/load.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/model.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/semantic.cpp"
  "${PROJECT_SOURCE_DIR}/src/protocol/validation.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/common.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/linked_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/src/queue/ring_spsc.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/queue_stress.cpp"
  "${PROJECT_SOURCE_DIR}/tests/rapidcheck_smoke.cpp"
  "${PROJECT_SOURCE_DIR}/tests/protocol_model_test.cpp"
  "${PROJECT_SOURCE_DIR}/tests/repository_info_test.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_mutant.cpp"
  "${PROJECT_SOURCE_DIR}/tools/queue_codegen_probe.cpp"
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
    cpu_prefetch_protocol
    cpu_prefetch_queue
    cpu_prefetch_smoke
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
install(DIRECTORY include/ DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(
  FILES
    "${PROJECT_BINARY_DIR}/generated/include/cpu_prefetch/foundation/build_metadata.hpp"
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/cpu_prefetch/foundation")
install(
  FILES
    "${PROJECT_BINARY_DIR}/generated/version_metadata.json"
    "${PROJECT_SOURCE_DIR}/protocol/2.0.0-pre.1/handoff/PROTOCOL_VERSION.md"
    "${PROJECT_SOURCE_DIR}/config/dependencies.json"
    "${PROJECT_SOURCE_DIR}/docs/PROTOCOL_MODEL.md"
    "${PROJECT_SOURCE_DIR}/docs/QUEUE_CORRECTNESS.md"
    "${PROJECT_SOURCE_DIR}/docs/NO_LICENSE_GRANT.md"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation")
install(
  DIRECTORY "${PROJECT_SOURCE_DIR}/config/queue-provenance"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/cpu-prefetch-foundation"
  FILES_MATCHING
  PATTERN "*.json")

set(CPACK_GENERATOR "TGZ")
set(CPACK_PACKAGE_NAME "cpu-prefetch-stand-foundation")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_FILE_NAME
    "${CPACK_PACKAGE_NAME}-${PROJECT_VERSION}-${CPU_PREFETCH_GIT_REVISION_SHORT}${CPU_PREFETCH_SOURCE_STATE_SUFFIX}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Non-measuring Stage 5 queue correctness foundation")
set(CPACK_PACKAGE_VENDOR "Private repository; no license grant")
include(CPack)
