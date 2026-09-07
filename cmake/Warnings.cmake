function(cpu_prefetch_configure_warnings target)
  target_compile_options(
    "${target}"
    INTERFACE
      -Wall
      -Wextra
      -Wpedantic
      -Wconversion
      -Wsign-conversion
      -Wshadow
      -Wformat=2
      -Wundef)

  if(CPU_PREFETCH_WARNINGS_AS_ERRORS)
    target_compile_options("${target}" INTERFACE -Werror)
  endif()
endfunction()
