function(cpu_prefetch_configure_version_metadata)
  set(CPU_PREFETCH_PROTOCOL_VERSION "2.0.0-pre.3" PARENT_SCOPE)

  if(DEFINED CPU_PREFETCH_SOURCE_REVISION)
    set(_revision "${CPU_PREFETCH_SOURCE_REVISION}")
    set(_dirty "false")
  else()
    execute_process(
      COMMAND "${GIT_EXECUTABLE}" rev-parse HEAD
      WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
      RESULT_VARIABLE _git_result
      OUTPUT_VARIABLE _revision
      OUTPUT_STRIP_TRAILING_WHITESPACE
      ERROR_QUIET)
    if(NOT _git_result EQUAL 0)
      set(_revision "source-archive")
    endif()

    execute_process(
      COMMAND "${GIT_EXECUTABLE}" status --porcelain --untracked-files=normal
      WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
      RESULT_VARIABLE _status_result
      OUTPUT_VARIABLE _status
      OUTPUT_STRIP_TRAILING_WHITESPACE
      ERROR_QUIET)
    if(_status_result EQUAL 0 AND NOT _status STREQUAL "")
      set(_dirty "true")
    else()
      set(_dirty "false")
    endif()
  endif()

  string(SUBSTRING "${_revision}" 0 7 _revision_short)
  if(_dirty)
    set(_dirty_cpp "true")
    set(_dirty_json "true")
    set(_source_state_suffix "-dirty")
  else()
    set(_dirty_cpp "false")
    set(_dirty_json "false")
    set(_source_state_suffix "")
  endif()

  set(CPU_PREFETCH_PROTOCOL_VERSION "2.0.0-pre.3")
  set(CPU_PREFETCH_GIT_REVISION "${_revision}")
  set(CPU_PREFETCH_GIT_REVISION_SHORT "${_revision_short}")
  set(CPU_PREFETCH_GIT_DIRTY_CPP "${_dirty_cpp}")
  set(CPU_PREFETCH_GIT_DIRTY_JSON "${_dirty_json}")
  set(CPU_PREFETCH_COMPILER_DESCRIPTION
      "${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")

  file(MAKE_DIRECTORY
       "${PROJECT_BINARY_DIR}/generated/include/cpu_prefetch/foundation")
  configure_file(
    "${PROJECT_SOURCE_DIR}/cmake/build_metadata.hpp.in"
    "${PROJECT_BINARY_DIR}/generated/include/cpu_prefetch/foundation/build_metadata.hpp"
    @ONLY)
  configure_file(
    "${PROJECT_SOURCE_DIR}/cmake/version_metadata.json.in"
    "${PROJECT_BINARY_DIR}/generated/version_metadata.json"
    @ONLY)

  set(CPU_PREFETCH_PROTOCOL_VERSION "${CPU_PREFETCH_PROTOCOL_VERSION}" PARENT_SCOPE)
  set(CPU_PREFETCH_GIT_REVISION "${_revision}" PARENT_SCOPE)
  set(CPU_PREFETCH_GIT_REVISION_SHORT "${_revision_short}" PARENT_SCOPE)
  set(CPU_PREFETCH_SOURCE_STATE_SUFFIX "${_source_state_suffix}" PARENT_SCOPE)
endfunction()
