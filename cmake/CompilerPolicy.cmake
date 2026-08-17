include(CheckCXXSourceCompiles)

function(cpu_prefetch_enforce_compiler_policy)
  if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR "Stage 3 supports Linux only (ADR-0008).")
  endif()

  string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _processor)
  if(NOT _processor MATCHES "^(x86_64|amd64)$")
    message(FATAL_ERROR "Stage 3 supports x86-64 only (ADR-0008).")
  endif()

  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS "16.1" OR
       NOT CMAKE_CXX_COMPILER_VERSION VERSION_LESS "16.2")
      message(FATAL_ERROR
        "Primary toolchain requires GCC 16.1.x; found ${CMAKE_CXX_COMPILER_VERSION}.")
    endif()
    check_cxx_source_compiles(
      "#include <version>
       #if !defined(__GLIBCXX__)
       #error primary toolchain is not using libstdc++
       #endif
       int main() { return 0; }"
      CPU_PREFETCH_USES_LIBSTDCXX)
    if(NOT CPU_PREFETCH_USES_LIBSTDCXX)
      message(FATAL_ERROR "GCC must be paired with libstdc++ (ADR-0009).")
    endif()
    set(CPU_PREFETCH_STANDARD_LIBRARY "libstdc++" PARENT_SCOPE)
  elseif(CMAKE_CXX_COMPILER_ID MATCHES "^(Clang|AppleClang)$")
    if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
      message(FATAL_ERROR "AppleClang is outside the accepted Linux matrix.")
    endif()
    if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS "22.1" OR
       NOT CMAKE_CXX_COMPILER_VERSION VERSION_LESS "22.2")
      message(FATAL_ERROR
        "Secondary toolchain requires Clang 22.1.x; found ${CMAKE_CXX_COMPILER_VERSION}.")
    endif()
    if(NOT CPU_PREFETCH_USE_LIBCXX)
      message(FATAL_ERROR "Clang must be paired with libc++ (ADR-0009).")
    endif()
    add_compile_options(-stdlib=libc++)
    add_link_options(-stdlib=libc++)
    set(CMAKE_REQUIRED_FLAGS "-stdlib=libc++")
    check_cxx_source_compiles(
      "#include <version>
       #if !defined(_LIBCPP_VERSION) || _LIBCPP_VERSION < 220100 || _LIBCPP_VERSION >= 220200
       #error unsupported libc++ version
       #endif
       int main() { return 0; }"
      CPU_PREFETCH_LIBCXX_22_1)
    unset(CMAKE_REQUIRED_FLAGS)
    if(NOT CPU_PREFETCH_LIBCXX_22_1)
      message(FATAL_ERROR "Secondary toolchain requires libc++ 22.1.x.")
    endif()
    set(CPU_PREFETCH_STANDARD_LIBRARY "libc++" PARENT_SCOPE)
  else()
    message(FATAL_ERROR
      "Unsupported compiler ${CMAKE_CXX_COMPILER_ID}; use GCC 16.1.x or Clang 22.1.x.")
  endif()
endfunction()
