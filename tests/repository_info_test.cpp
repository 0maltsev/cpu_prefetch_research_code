#include "cpu_prefetch/foundation/repository_info.hpp"

#include <gtest/gtest.h>

namespace {

TEST(RepositoryInfo, CarriesProtocolAndBuildIdentity) {
  const auto info = cpu_prefetch::foundation::repository_info();
  EXPECT_EQ(info.protocol_version, "2.0.0-pre.1");
  EXPECT_FALSE(info.source_revision.empty());
  EXPECT_FALSE(info.source_revision_short.empty());
  EXPECT_FALSE(info.compiler.empty());
  EXPECT_FALSE(info.standard_library.empty());
}

} // namespace
