function(cpu_prefetch_configure_sanitizers target)
  if(CPU_PREFETCH_SANITIZER STREQUAL "NONE")
    return()
  endif()

  if(CPU_PREFETCH_SANITIZER STREQUAL "ADDRESS_UNDEFINED")
    set(_flags -fsanitize=address,undefined -fno-omit-frame-pointer)
  elseif(CPU_PREFETCH_SANITIZER STREQUAL "THREAD")
    set(_flags -fsanitize=thread -fno-omit-frame-pointer)
  else()
    message(FATAL_ERROR
      "CPU_PREFETCH_SANITIZER must be NONE, ADDRESS_UNDEFINED, or THREAD.")
  endif()

  target_compile_options("${target}" INTERFACE ${_flags})
  target_link_options("${target}" INTERFACE ${_flags})
endfunction()
