find_path(RapidCheck_INCLUDE_DIR NAMES rapidcheck.h)
find_library(RapidCheck_LIBRARY NAMES rapidcheck)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(
  RapidCheck
  REQUIRED_VARS RapidCheck_INCLUDE_DIR RapidCheck_LIBRARY)

if(RapidCheck_FOUND AND NOT TARGET RapidCheck::rapidcheck)
  add_library(RapidCheck::rapidcheck UNKNOWN IMPORTED)
  set_target_properties(
    RapidCheck::rapidcheck
    PROPERTIES
      IMPORTED_LOCATION "${RapidCheck_LIBRARY}"
      INTERFACE_INCLUDE_DIRECTORIES "${RapidCheck_INCLUDE_DIR}")
endif()

mark_as_advanced(RapidCheck_INCLUDE_DIR RapidCheck_LIBRARY)
