#include "cpu_prefetch/foundation/repository_info.hpp"

#include <iostream>

int main() {
  const auto info = cpu_prefetch::foundation::repository_info();
  std::cout << "protocol=" << info.protocol_version
            << " revision=" << info.source_revision
            << " dirty=" << (info.source_dirty ? "true" : "false")
            << " compiler=" << info.compiler
            << " standard_library=" << info.standard_library << '\n';
  return 0;
}
