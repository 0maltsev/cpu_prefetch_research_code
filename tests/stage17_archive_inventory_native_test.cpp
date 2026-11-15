// Link with tools/stage17_archive_inventory_native_v1.cpp and gtest_main.
// Optional fault coverage: -DCPU_PREFETCH_INVENTORY_FAULT_TESTS and linker
// --wrap=clock_gettime,--wrap=malloc,--wrap=realloc,--wrap=fstatat (ELF).
#include <gtest/gtest.h>

#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <dirent.h>
#include <fcntl.h>
#include <filesystem>
#include <map>
#include <string>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <vector>

// Intentionally repeated frozen C ABI: no new public header is needed.
struct InventoryUsage {
  uint64_t logical_size_bytes;
  uint64_t allocated_bytes;
  uint64_t quota_bytes;
  uint64_t unique_objects;
};
extern "C" int cpu_prefetch_archive_inventory_v1(const char*, uint64_t,
                                                 const char* const*, uint64_t, uint64_t,
                                                 InventoryUsage*) noexcept;

#ifdef CPU_PREFETCH_INVENTORY_FAULT_TESTS
namespace faults {
bool fail_clock = false;
bool fail_allocation = false;
unsigned int realloc_calls = 0;
unsigned int fail_realloc_on = 0;
unsigned int clock_calls = 0;
unsigned int expire_on_clock = 0;
unsigned int clock_shape = 0;
enum class Stat {
  normal,
  negative_size,
  negative_blocks,
  product,
  sum,
  hardlink,
  hardlink_type
};
Stat stat = Stat::normal;
} // namespace faults
extern "C" int __real_clock_gettime(clockid_t, timespec*) noexcept;
extern "C" int __wrap_clock_gettime(clockid_t id, timespec* value) noexcept {
  ++faults::clock_calls;
  if (faults::fail_clock) {
    errno = EIO;
    return -1;
  }
  if (faults::clock_shape != 0U) {
    switch (faults::clock_shape) {
    case 1:
      *value = {-1, 0};
      break;
    case 2:
      *value = {0, -1};
      break;
    case 3:
      *value = {0, 1000000000L};
      break;
    default:
      *value = {static_cast<time_t>(INT64_MAX), 0};
      break;
    }
    return 0;
  }
  if (faults::expire_on_clock != 0U && faults::clock_calls >= faults::expire_on_clock) {
    *value = {1, 0};
    return 0;
  }
  if (faults::expire_on_clock != 0U) {
    *value = {0, 0};
    return 0;
  }
  return __real_clock_gettime(id, value);
}
extern "C" void* __real_realloc(void*, size_t) noexcept;
extern "C" void* __wrap_realloc(void* pointer, size_t bytes) noexcept {
  ++faults::realloc_calls;
  if (faults::fail_allocation || (faults::fail_realloc_on != 0U &&
                                  faults::realloc_calls >= faults::fail_realloc_on))
    return nullptr;
  return __real_realloc(pointer, bytes);
}
extern "C" void* __real_malloc(size_t) noexcept;
extern "C" void* __wrap_malloc(size_t bytes) noexcept {
  if (faults::fail_allocation)
    return nullptr;
  return __real_malloc(bytes);
}
extern "C" int __real_fstatat(int, const char*, struct stat*, int) noexcept;
extern "C" int __wrap_fstatat(int fd, const char* name, struct stat* st,
                              int flags) noexcept {
  const int status = __real_fstatat(fd, name, st, flags);
  if (status != 0 || faults::stat == faults::Stat::normal)
    return status;
  const std::string leaf(name);
  if (leaf == "fault") {
    switch (faults::stat) {
    case faults::Stat::negative_size:
      st->st_size = -1;
      break;
    case faults::Stat::negative_blocks:
      st->st_blocks = -1;
      break;
    case faults::Stat::product:
      st->st_blocks = static_cast<blkcnt_t>(UINT64_MAX / 512U + 1U);
      break;
    case faults::Stat::sum:
      st->st_blocks = static_cast<blkcnt_t>(UINT64_MAX / 512U);
      break;
    default:
      break;
    }
  } else if (leaf == "sum-peer" && faults::stat == faults::Stat::sum) {
    st->st_blocks = 2;
  } else if (leaf == "later" && faults::stat == faults::Stat::hardlink) {
    // A later observation of an already-accounted hardlink must be type checked
    // but its numeric fields must not replace or invalidate the first fields.
    st->st_size = -1;
    st->st_blocks = -1;
  } else if (leaf == "later" && faults::stat == faults::Stat::hardlink_type) {
    st->st_mode = S_IFLNK | 0600;
  }
  return status;
}
#endif

namespace {
namespace fs = std::filesystem;
constexpr const char* directory_names[] = {"working",  "archives", "ledger",
                                           "metadata", "spool",    "release-hold"};

uint64_t deadline() {
  timespec current{};
  EXPECT_EQ(::clock_gettime(CLOCK_MONOTONIC, &current), 0);
  return static_cast<uint64_t>(current.tv_sec) * UINT64_C(1000000000) +
         static_cast<uint64_t>(current.tv_nsec) + UINT64_C(10000000000);
}

void expect_equal(const InventoryUsage& a, const InventoryUsage& b) {
  EXPECT_EQ(a.logical_size_bytes, b.logical_size_bytes);
  EXPECT_EQ(a.allocated_bytes, b.allocated_bytes);
  EXPECT_EQ(a.quota_bytes, b.quota_bytes);
  EXPECT_EQ(a.unique_objects, b.unique_objects);
}

size_t descriptor_count() {
  DIR* entries = ::opendir("/proc/self/fd");
  EXPECT_NE(entries, nullptr);
  if (entries == nullptr)
    return 0;
  size_t count = 0;
  while (::readdir(entries) != nullptr)
    ++count;
  EXPECT_EQ(::closedir(entries), 0);
  return count;
}

class InventoryTest : public ::testing::Test {
protected:
  fs::path temporary;
  fs::path root;
  const std::string family = std::string(64U, 'a');
  std::vector<fs::path> charged;
  InventoryUsage output{};

  void SetUp() override {
    char pattern[] = "/tmp/stage17-inventory-test-XXXXXX";
    const char* created = ::mkdtemp(pattern);
    ASSERT_NE(created, nullptr);
    temporary = created;
    root = temporary / "program";
    ASSERT_TRUE(fs::create_directory(root));
    charged.push_back(root);
    for (const auto* name : directory_names) {
      ASSERT_TRUE(fs::create_directory(root / name));
      charged.push_back(root / name);
    }
    file("scope.json", 31);
    file("broker.lock", 0);
  }

  void TearDown() override {
#ifdef CPU_PREFETCH_INVENTORY_FAULT_TESTS
    faults::fail_clock = false;
    faults::fail_allocation = false;
    faults::fail_realloc_on = 0;
    faults::expire_on_clock = 0;
    faults::clock_shape = 0;
    faults::stat = faults::Stat::normal;
#endif
    if (!temporary.empty())
      fs::remove_all(temporary);
  }

  void file(const std::string& relative, off_t size, bool account = true) {
    const int fd = ::open((root / relative).c_str(), O_CREAT | O_EXCL | O_WRONLY, 0600);
    ASSERT_GE(fd, 0);
    // Sparse logical size is intentional; oracle reads actual st_blocks.
    EXPECT_EQ(::ftruncate(fd, size), 0);
    EXPECT_EQ(::close(fd), 0);
    if (account)
      charged.push_back(root / relative);
  }

  std::string add_family(char digit = 'a') {
    const std::string relative = "working/" + std::string(64U, digit);
    EXPECT_TRUE(fs::create_directory(root / relative));
    charged.push_back(root / relative);
    return relative;
  }

  InventoryUsage oracle() {
    // Explicit fixture manifest, independent of implementation traversal/regex.
    std::map<std::pair<dev_t, ino_t>, struct stat> distinct;
    for (const auto& path : charged) {
      struct stat st{};
      EXPECT_EQ(::lstat(path.c_str(), &st), 0) << path;
      distinct.emplace(std::make_pair(st.st_dev, st.st_ino), st);
    }
    InventoryUsage expected{};
    for (const auto& [identity, st] : distinct) {
      static_cast<void>(identity);
      const auto logical = static_cast<uint64_t>(st.st_size);
      const auto allocated = static_cast<uint64_t>(st.st_blocks) * 512U;
      expected.logical_size_bytes += logical;
      expected.allocated_bytes += allocated;
      expected.quota_bytes += std::max(logical, allocated);
      ++expected.unique_objects;
    }
    return expected;
  }

  int run(uint64_t maximum = 1000U, const std::vector<std::string>& retained = {}) {
    std::vector<const char*> pointers;
    for (const auto& path : retained)
      pointers.push_back(path.c_str());
    output = {1, 2, 3, 4};
    const int status = cpu_prefetch_archive_inventory_v1(
        root.c_str(), maximum, pointers.data(), pointers.size(), deadline(), &output);
    if (status != 0)
      expect_equal(output, {1, 2, 3, 4});
    return status;
  }
};

TEST_F(InventoryTest, AccountsRootSixDirectoriesScopeAndLock) {
  ASSERT_EQ(run(1), 0);
  expect_equal(output, oracle());
  EXPECT_EQ(output.unique_objects, 9U);
}

TEST_F(InventoryTest, SparseHardlinksRetainedReceiptsAndPerObjectQuota) {
  const auto working = add_family();
  const auto receipt = working + "/formal-capture-000-final-checkpoint.json";
  file(receipt, 4 * 1024 * 1024);
  ASSERT_EQ(::link((root / receipt).c_str(), (root / "archives/hardlink").c_str()), 0);
  charged.push_back(root / "archives/hardlink");
  file("metadata/tiny", 1);
  const int fd = ::open((root / "metadata/tiny").c_str(), O_WRONLY);
  ASSERT_GE(fd, 0);
  EXPECT_EQ(::write(fd, "x", 1), 1);
  EXPECT_EQ(::close(fd), 0);
  file("ledger/record", 17);
  const auto retained = working + "/arbitrary-retained.json";
  file(retained, 512 * 1024);
  ASSERT_EQ(run(6, {retained, receipt, retained}), 0);
  expect_equal(output, oracle());
  EXPECT_GT(output.quota_bytes,
            std::max(output.logical_size_bytes, output.allocated_bytes));
  EXPECT_EQ(output.unique_objects, 14U);
}

TEST_F(InventoryTest, ExactReceiptGrammarPreservesRawWorkspaceExemption) {
  const auto working = add_family();
  const std::vector<std::string> raw = {"raw",
                                        "formal-capture--1-final-checkpoint.json",
                                        "formal-capture-1-final-checkpoint.json.bak",
                                        "formal-capture-1-archive-custodyXjson",
                                        "formal-capture-1-final-checkpoint.json\n",
                                        "formal-capture-\xd9\xa1-archive-custody.json",
                                        "formal-capture--archive-custody.json"};
  for (const auto& name : raw)
    ASSERT_EQ(::symlink("/nonexistent", (root / working / name).c_str()), 0);
  ASSERT_TRUE(fs::create_directory(root / working / "raw-directory"));
  ASSERT_EQ(::mkfifo((root / working / "raw-fifo").c_str(), 0600), 0);
  file(working + "/formal-capture-0-archive-custody.json", 12);
  ASSERT_EQ(run(10), 0);
  expect_equal(output, oracle());
  EXPECT_EQ(run(9), 3);
  ASSERT_EQ(
      ::symlink("/nonexistent",
                (root / working / "formal-capture-01-final-checkpoint.json").c_str()),
      0);
  EXPECT_EQ(run(11), 2);
}

TEST_F(InventoryTest, SharedFileLimitAndUncountedEmptyFamilies) {
  const auto working = add_family();
  for (char digit = 'b'; digit <= 'f'; ++digit)
    add_family(digit);
  ASSERT_EQ(run(1), 0);
  expect_equal(output, oracle());
  file(working + "/raw", 1024, false);
  file("archives/one", 1);
  file("metadata/two", 2);
  file("ledger/three", 3);
  ASSERT_EQ(run(4), 0);
  expect_equal(output, oracle());
  EXPECT_EQ(run(3), 3);
  file(working + "/another-raw", 0, false);
  EXPECT_EQ(run(1), 3);
  EXPECT_EQ(run(UINT64_MAX), 0);
}

TEST_F(InventoryTest, SpoolHoldAndUnlistedRootChildrenAreOutsideTheInventory) {
  file("spool/unlisted", 1000000, false);
  file("release-hold/unlisted", 2000000, false);
  file("other-root-file", 3000000, false);
  ASSERT_EQ(::symlink("/nonexistent", (root / "spool/raw-link").c_str()), 0);
  ASSERT_TRUE(fs::create_directory(root / "release-hold/raw-directory"));
  ASSERT_EQ(run(1), 0);
  expect_equal(output, oracle());
}

TEST_F(InventoryTest, EveryInvocationObservesFreshStatsAndDirectoryEntries) {
  file("archives/mutable", 0);
  ASSERT_EQ(run(), 0);
  const auto before = output;
  ASSERT_EQ(::truncate((root / "archives/mutable").c_str(), 8000000), 0);
  file("metadata/new", 9000000);
  ASSERT_EQ(run(), 0);
  expect_equal(output, oracle());
  EXPECT_GT(output.logical_size_bytes, before.logical_size_bytes);
  EXPECT_EQ(output.unique_objects, before.unique_objects + 1U);
  ASSERT_TRUE(fs::remove(root / "metadata/new"));
  charged.pop_back();
  ASSERT_EQ(run(), 0);
  expect_equal(output, oracle());
}

TEST_F(InventoryTest, RetainedPathsAreNotRawExemptAndCannotTraverse) {
  const auto working = add_family();
  file(working + "/retained", 29);
  ASSERT_EQ(run(1, {working + "/retained"}), 0);
  expect_equal(output, oracle());
  const std::vector<std::string> unsafe = {"",
                                           "scope.json",
                                           "/scope.json",
                                           "working/../scope.json",
                                           "working/" + std::string(64U, 'A') +
                                               "/retained",
                                           working + "/.",
                                           working + "/..",
                                           working + "/../retained",
                                           working + "/x/../retained",
                                           working + "/retained/",
                                           working + "/",
                                           working + "/" + std::string(256U, 'x')};
  for (const auto& path : unsafe)
    EXPECT_EQ(run(1, {path}), 1) << path;
  ASSERT_EQ(::symlink("retained", (root / working / "alias").c_str()), 0);
  EXPECT_EQ(run(2, {working + "/alias"}), 2);
  ASSERT_TRUE(fs::create_directory(root / working / "directory"));
  EXPECT_EQ(run(3, {working + "/directory"}), 2);
  EXPECT_EQ(run(3, {working + "/missing"}), 2);
}

TEST_F(InventoryTest, InvalidFamilyNamespacesAndNondirectoriesFailClosed) {
  for (const auto& name : {std::string("invalid"), std::string(64U, 'A'),
                           std::string(63U, 'a'), std::string(65U, 'a')}) {
    ASSERT_TRUE(fs::create_directory(root / "working" / name));
    EXPECT_EQ(run(), 1);
    fs::remove(root / "working" / name);
  }
  file("working/" + family, 0, false);
  EXPECT_EQ(run(), 2);
  fs::remove(root / "working" / family);
  ASSERT_EQ(::symlink("../metadata", (root / "working" / family).c_str()), 0);
  EXPECT_EQ(run(), 2);
}

TEST_F(InventoryTest, ChargedSymlinksDirectoriesAndSpecialFilesFailClosed) {
  for (const auto* name : {"archives", "metadata", "ledger"}) {
    const fs::path path = root / name / "unexpected";
    ASSERT_EQ(::symlink("../scope.json", path.c_str()), 0);
    EXPECT_EQ(run(), 2);
    fs::remove(path);
    ASSERT_TRUE(fs::create_directory(path));
    EXPECT_EQ(run(), 2);
    fs::remove(path);
    ASSERT_EQ(::mkfifo(path.c_str(), 0600), 0);
    EXPECT_EQ(run(), 2);
    fs::remove(path);
  }
  const auto working = add_family();
  ASSERT_TRUE(
      fs::create_directory(root / working / "formal-capture-3-archive-custody.json"));
  EXPECT_EQ(run(), 2);
}

TEST_F(InventoryTest, FixedDirectoriesRootAndEveryAncestorMustNotBeSymlinks) {
  for (const auto* name : directory_names) {
    fs::rename(root / name, root / "saved");
    ASSERT_EQ(::symlink("saved", (root / name).c_str()), 0);
    EXPECT_EQ(run(), 2) << name;
    fs::remove(root / name);
    fs::rename(root / "saved", root / name);
  }
  const auto original = root;
  ASSERT_EQ(::symlink("program", (temporary / "alias").c_str()), 0);
  root = temporary / "alias";
  EXPECT_EQ(run(), 2);
  root = temporary / "alias/../program";
  EXPECT_EQ(run(), 2); // cancelled symlink ancestor still forbidden
  root = original;
  const auto parent_alias = temporary / "parent-alias";
  ASSERT_EQ(::symlink(temporary.c_str(), parent_alias.c_str()), 0);
  root = parent_alias / "program";
  EXPECT_EQ(run(), 2);
  root = original;
  ASSERT_EQ(run(), 0);
}

TEST_F(InventoryTest, ScopeAndLockMustBePresentRegularFiles) {
  for (const auto* name : {"scope.json", "broker.lock"}) {
    fs::rename(root / name, root / "saved-file");
    EXPECT_EQ(run(), 2);
    ASSERT_EQ(::symlink("saved-file", (root / name).c_str()), 0);
    EXPECT_EQ(run(), 2);
    fs::remove(root / name);
    fs::rename(root / "saved-file", root / name);
  }
}

TEST_F(InventoryTest, ZeroNullWrappedCountsAndExpiredDeadlinesFailClosed) {
  const auto future = deadline();
  output = {1, 2, 3, 4};
  EXPECT_EQ(
      cpu_prefetch_archive_inventory_v1(root.c_str(), 1, nullptr, 0, future, nullptr),
      1);
  auto invoke = [&](const char* path, uint64_t maximum, const char* const* list,
                    uint64_t count, uint64_t until, int expected) {
    output = {1, 2, 3, 4};
    EXPECT_EQ(
        cpu_prefetch_archive_inventory_v1(path, maximum, list, count, until, &output),
        expected);
    expect_equal(output, {1, 2, 3, 4});
  };
  invoke(nullptr, 1, nullptr, 0, future, 1);
  invoke("relative", 1, nullptr, 0, future, 1);
  invoke(root.c_str(), 0, nullptr, 0, future, 1);
  invoke(root.c_str(), 1, nullptr, 1, future, 1);
  const char* one[] = {nullptr};
  invoke(root.c_str(), 1, one, 1, future, 1);
  invoke(root.c_str(), UINT64_MAX, one, UINT64_MAX, future, 1);
  const auto* wrapped = reinterpret_cast<const char* const*>(UINTPTR_MAX - 3U);
  invoke(root.c_str(), 1, wrapped, 1, future, 1);
  invoke(root.c_str(), 1, nullptr, 0, 0, 6);
  EXPECT_EQ(run(UINT64_MAX), 0);
}

TEST_F(InventoryTest, NoDescriptorLeaksOnRepeatedSuccessAndLateFailure) {
  add_family();
  file("archives/entry", 2);
  const size_t before = descriptor_count();
  for (unsigned int i = 0; i < 64U; ++i) {
    ASSERT_EQ(run(), 0);
    ASSERT_EQ(run(1, {"working/" + family + "/missing"}), 2);
  }
  EXPECT_EQ(descriptor_count(), before);
}

#ifdef CPU_PREFETCH_INVENTORY_FAULT_TESTS
TEST_F(InventoryTest, ClockAndInitialAndGrowthAllocationFailuresAreClosed) {
  const auto future = deadline();
  output = {1, 2, 3, 4};
  faults::fail_clock = true;
  EXPECT_EQ(cpu_prefetch_archive_inventory_v1(root.c_str(), 1000, nullptr, 0, future,
                                              &output),
            6);
  expect_equal(output, {1, 2, 3, 4});
  faults::fail_clock = false;
  for (unsigned int shape = 1; shape <= 4U; ++shape) {
    faults::clock_shape = shape;
    EXPECT_EQ(cpu_prefetch_archive_inventory_v1(root.c_str(), 1000, nullptr, 0,
                                                UINT64_MAX, &output),
              6);
    expect_equal(output, {1, 2, 3, 4});
  }
  faults::clock_shape = 0;
  faults::fail_allocation = true;
  EXPECT_EQ(run(), 5);
  faults::fail_allocation = false;
  // More than one allocation and more than 256 stat entries.
  for (unsigned int i = 0; i < 600U; ++i)
    file("archives/entry-" + std::to_string(i), 0);
  faults::realloc_calls = 0;
  faults::fail_realloc_on = 2;
  EXPECT_EQ(run(), 5);
  faults::fail_realloc_on = 0;
  ASSERT_EQ(run(), 0);
  expect_equal(output, oracle());
}

TEST_F(InventoryTest, NegativeStatOperandsProductAndSumOverflowAreClosed) {
  file("archives/fault", 1);
  file("metadata/sum-peer", 1);
  for (auto fault : {faults::Stat::negative_size, faults::Stat::negative_blocks,
                     faults::Stat::product, faults::Stat::sum}) {
    faults::stat = fault;
    EXPECT_EQ(run(), 4);
  }
}

TEST_F(InventoryTest, HardlinkFirstObservationWinsEvenIfLaterFieldsAreInvalid) {
  file("archives/first", 321);
  ASSERT_EQ(
      ::link((root / "archives/first").c_str(), (root / "metadata/later").c_str()), 0);
  charged.push_back(root / "metadata/later");
  const auto expected = oracle();
  faults::stat = faults::Stat::hardlink;
  ASSERT_EQ(run(), 0);
  expect_equal(output, expected);
  faults::stat = faults::Stat::hardlink_type;
  EXPECT_EQ(run(), 2);
}

TEST_F(InventoryTest, DeadlineIsCheckedDuringRawChildrenTraversal) {
  const auto working = add_family();
  for (unsigned int i = 0; i < 600U; ++i)
    file(working + "/raw-" + std::to_string(i), 0, false);
  // Startup: one clock check plus one per root component. Expire at the next
  // check, which must occur during traversal, before the final root reopening.
  const auto components =
      static_cast<unsigned int>(std::distance(root.begin(), root.end()));
  faults::clock_calls = 0;
  faults::expire_on_clock = components + 1U;
  output = {1, 2, 3, 4};
  EXPECT_EQ(
      cpu_prefetch_archive_inventory_v1(root.c_str(), 1000, nullptr, 0, 1, &output), 6);
  EXPECT_EQ(faults::clock_calls, faults::expire_on_clock);
  expect_equal(output, {1, 2, 3, 4});
}

TEST_F(InventoryTest, DeadlineIsCheckedDuringEmptyFamilyTraversal) {
  for (unsigned int i = 0; i < 600U; ++i) {
    const std::string suffix = std::to_string(i);
    ASSERT_TRUE(fs::create_directory(root / "working" /
                                     (std::string(64U - suffix.size(), '0') + suffix)));
  }
  const auto components =
      static_cast<unsigned int>(std::distance(root.begin(), root.end()));
  faults::clock_calls = 0;
  faults::expire_on_clock = components + 1U;
  output = {1, 2, 3, 4};
  EXPECT_EQ(cpu_prefetch_archive_inventory_v1(root.c_str(), 1, nullptr, 0, 1, &output),
            6);
  EXPECT_EQ(faults::clock_calls, faults::expire_on_clock);
  expect_equal(output, {1, 2, 3, 4});
}
#endif
} // namespace
