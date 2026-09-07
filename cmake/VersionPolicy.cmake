function(cpu_prefetch_enforce_tool_versions)
  if(CMAKE_VERSION VERSION_LESS "4.3" OR NOT CMAKE_VERSION VERSION_LESS "4.4")
    message(FATAL_ERROR "CMake 4.3.x is required; found ${CMAKE_VERSION}.")
  endif()
  if(GIT_VERSION_STRING VERSION_LESS "2.54" OR
     NOT GIT_VERSION_STRING VERSION_LESS "2.55")
    message(FATAL_ERROR "Git 2.54.x is required; found ${GIT_VERSION_STRING}.")
  endif()
  if(Python3_VERSION VERSION_LESS "3.14" OR
     NOT Python3_VERSION VERSION_LESS "3.15")
    message(FATAL_ERROR "Python 3.14.x is required; found ${Python3_VERSION}.")
  endif()

  execute_process(
    COMMAND "${CMAKE_MAKE_PROGRAM}" --version
    RESULT_VARIABLE _ninja_result
    OUTPUT_VARIABLE _ninja_version
    OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(NOT _ninja_result EQUAL 0 OR _ninja_version VERSION_LESS "1.13" OR
     NOT _ninja_version VERSION_LESS "1.14")
    message(FATAL_ERROR "Ninja 1.13.x is required; found ${_ninja_version}.")
  endif()

  foreach(_tool IN ITEMS CPU_PREFETCH_CLANG_FORMAT CPU_PREFETCH_CLANG_TIDY)
    execute_process(
      COMMAND "${${_tool}}" --version
      RESULT_VARIABLE _llvm_result
      OUTPUT_VARIABLE _llvm_version
      OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(NOT _llvm_result EQUAL 0 OR NOT _llvm_version MATCHES "version 22\\.1\\.")
      message(FATAL_ERROR "${_tool} must be LLVM 22.1.x; found ${_llvm_version}.")
    endif()
  endforeach()

  if(NOT CPU_PREFETCH_RAPIDCHECK_REVISION STREQUAL "ff6af6f")
    message(FATAL_ERROR
      "Set CPU_PREFETCH_RAPIDCHECK_REVISION=ff6af6f for the accepted dependency input.")
  endif()
endfunction()
