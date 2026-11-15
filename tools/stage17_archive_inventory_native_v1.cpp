// Cold, fresh physical inventory only. No lock, ledger replay, admission, or
// execution authority is supplied here; those remain the caller's obligations.
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

struct InventoryUsage {
  uint64_t logical_size_bytes;
  uint64_t allocated_bytes;
  uint64_t quota_bytes;
  uint64_t unique_objects;
};

namespace {
enum Error {
  ok = 0,
  invalid_input = 1,
  filesystem_error = 2,
  inventory_limit = 3,
  arithmetic_overflow = 4,
  allocation_failure = 5,
  deadline_failure = 6
};
constexpr const char* directories[] = {"working",  "archives", "ledger",
                                       "metadata", "spool",    "release-hold"};

struct Descriptor {
  int fd = -1;
  ~Descriptor() noexcept {
    if (fd >= 0)
      ::close(fd);
  }
};

struct Entries {
  DIR* stream = nullptr;
  ~Entries() noexcept {
    if (stream != nullptr)
      ::closedir(stream);
  }
  bool open(int fd) noexcept {
    // A new open file description: dup would share the directory offset.
    const int copy = ::openat(fd, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (copy < 0)
      return false;
    stream = ::fdopendir(copy);
    if (stream == nullptr)
      ::close(copy);
    return stream != nullptr;
  }
};

bool dot(const char* name) noexcept {
  return ::strcmp(name, ".") == 0 || ::strcmp(name, "..") == 0;
}

bool family_name(const char* name) noexcept {
  if (::strnlen(name, 65U) != 64U)
    return false;
  for (unsigned int i = 0; i < 64U; ++i)
    if (!((name[i] >= '0' && name[i] <= '9') || (name[i] >= 'a' && name[i] <= 'f')))
      return false;
  return true;
}

bool native_receipt(const char* name) noexcept {
  constexpr char prefix[] = "formal-capture-";
  if (::strncmp(name, prefix, sizeof(prefix) - 1U) != 0)
    return false;
  const char* cursor = name + sizeof(prefix) - 1U;
  if (*cursor < '0' || *cursor > '9')
    return false;
  do {
    ++cursor;
  } while (*cursor >= '0' && *cursor <= '9');
  return ::strcmp(cursor, "-final-checkpoint.json") == 0 ||
         ::strcmp(cursor, "-archive-custody.json") == 0;
}

int check_time(uint64_t deadline) noexcept {
  timespec current{};
  if (::clock_gettime(CLOCK_MONOTONIC, &current) != 0 || current.tv_sec < 0 ||
      current.tv_nsec < 0 || current.tv_nsec >= 1000000000L)
    return deadline_failure;
  const auto seconds = static_cast<uint64_t>(current.tv_sec);
  const auto nanos = static_cast<uint64_t>(current.tv_nsec);
  if (seconds > (UINT64_MAX - nanos) / UINT64_C(1000000000))
    return deadline_failure;
  return seconds * UINT64_C(1000000000) + nanos < deadline ? ok : deadline_failure;
}

// Walk every ancestor from / without following symlinks, including components
// subsequently cancelled by '..'. Only a bounded POSIX pathname is copied.
int open_root(const char* path, uint64_t deadline, int* result) noexcept {
  if (path == nullptr || path[0] != '/')
    return invalid_input;
  const size_t length = ::strnlen(path, PATH_MAX);
  if (length == PATH_MAX)
    return invalid_input;
  char copy[PATH_MAX];
  ::memcpy(copy, path, length + 1U);
  Descriptor current;
  current.fd = ::open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (current.fd < 0)
    return filesystem_error;
  char* cursor = copy + 1;
  while (*cursor != '\0') {
    if (check_time(deadline) != ok)
      return deadline_failure;
    if (*cursor == '/') {
      ++cursor;
      continue;
    }
    char* end = ::strchr(cursor, '/');
    if (end != nullptr)
      *end = '\0';
    const int next =
        ::openat(current.fd, cursor, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (next < 0)
      return filesystem_error;
    ::close(current.fd);
    current.fd = next;
    if (end == nullptr)
      break;
    cursor = end + 1;
  }
  *result = current.fd;
  current.fd = -1;
  return ok;
}

struct Observation {
  dev_t device;
  ino_t inode;
  off_t size;
  blkcnt_t blocks;
  size_t ordinal;
};

int compare_observations(const void* left, const void* right) noexcept {
  const auto& a = *static_cast<const Observation*>(left);
  const auto& b = *static_cast<const Observation*>(right);
  if (a.device != b.device)
    return a.device < b.device ? -1 : 1;
  if (a.inode != b.inode)
    return a.inode < b.inode ? -1 : 1;
  return (a.ordinal > b.ordinal) - (a.ordinal < b.ordinal);
}

struct Inventory {
  uint64_t deadline;
  uint64_t maximum;
  uint64_t counted = 0;
  unsigned int pending = 0;
  Observation* observations = nullptr;
  size_t used = 0;
  size_t capacity = 0;

  ~Inventory() noexcept { ::free(observations); }

  int tick() noexcept {
    // Includes exempt children and empty families, neither of which may bypass
    // deadline enforcement. Each charged stat is preceded by a tick as well.
    if (++pending == 256U) {
      pending = 0;
      return check_time(deadline);
    }
    return ok;
  }

  int count() noexcept {
    // Compare before increment: UINT64_MAX is a valid maximum, never max+1.
    if (counted == maximum)
      return inventory_limit;
    ++counted;
    return ok;
  }

  int append(const struct stat& st, bool directory) noexcept {
    // Type validation precedes deduplication, as in both Python authorities.
    if (!(directory ? S_ISDIR(st.st_mode) : S_ISREG(st.st_mode)))
      return filesystem_error;
    if (used == capacity) {
      constexpr size_t max_capacity = SIZE_MAX / sizeof(Observation);
      if (capacity == max_capacity)
        return arithmetic_overflow;
      size_t next = capacity == 0U ? 256U : capacity;
      if (capacity != 0U)
        next = capacity > max_capacity / 2U ? max_capacity : capacity * 2U;
      if (next > max_capacity)
        return arithmetic_overflow;
      void* storage = ::realloc(observations, next * sizeof(Observation));
      if (storage == nullptr)
        return allocation_failure;
      observations = static_cast<Observation*>(storage);
      capacity = next;
    }
    observations[used] = {st.st_dev, st.st_ino, st.st_size, st.st_blocks, used};
    ++used;
    return ok;
  }

  int account(int fd, const char* name, bool directory = false) noexcept {
    int error = tick();
    if (error != ok)
      return error;
    struct stat st{};
    if (::fstatat(fd, name, &st, AT_SYMLINK_NOFOLLOW) != 0)
      return filesystem_error;
    return append(st, directory);
  }

  int total(InventoryUsage* output) noexcept {
    if (check_time(deadline) != ok)
      return deadline_failure;
    ::qsort(observations, used, sizeof(Observation), compare_observations);
    InventoryUsage sum{};
    for (size_t i = 0; i < used; ++i) {
      if (tick() != ok)
        return deadline_failure;
      const auto& st = observations[i];
      if (i != 0U && st.device == observations[i - 1U].device &&
          st.inode == observations[i - 1U].inode)
        continue;
      // Only the first observation's numeric fields are used for hardlinks.
      if (st.size < 0 || st.blocks < 0)
        return arithmetic_overflow;
      const auto logical = static_cast<uint64_t>(st.size);
      const auto blocks = static_cast<uint64_t>(st.blocks);
      if (blocks > UINT64_MAX / 512U)
        return arithmetic_overflow;
      const uint64_t allocated = blocks * 512U;
      const uint64_t quota = logical > allocated ? logical : allocated;
      if (logical > UINT64_MAX - sum.logical_size_bytes ||
          allocated > UINT64_MAX - sum.allocated_bytes ||
          quota > UINT64_MAX - sum.quota_bytes || sum.unique_objects == UINT64_MAX)
        return arithmetic_overflow;
      sum.logical_size_bytes += logical;
      sum.allocated_bytes += allocated;
      sum.quota_bytes += quota;
      ++sum.unique_objects;
    }
    if (check_time(deadline) != ok)
      return deadline_failure;
    *output = sum;
    return ok;
  }
};

bool same_directory(int parent, const char* name,
                    const struct stat& original) noexcept {
  struct stat current{};
  return ::fstatat(parent, name, &current, AT_SYMLINK_NOFOLLOW) == 0 &&
         S_ISDIR(current.st_mode) && current.st_dev == original.st_dev &&
         current.st_ino == original.st_ino;
}

int scan_family(Inventory& inventory, int working, const char* name) noexcept {
  if (!family_name(name))
    return invalid_input;
  Descriptor family;
  family.fd = ::openat(working, name, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (family.fd < 0)
    return filesystem_error;
  struct stat original{};
  if (::fstat(family.fd, &original) != 0)
    return filesystem_error;
  int error = inventory.append(original, true);
  if (error != ok)
    return error;
  Entries children;
  if (!children.open(family.fd))
    return filesystem_error;
  for (;;) {
    if (inventory.tick() != ok)
      return deadline_failure;
    errno = 0;
    const dirent* child = ::readdir(children.stream);
    if (child == nullptr)
      return errno != 0 || !same_directory(working, name, original) ? filesystem_error
                                                                    : ok;
    if (dot(child->d_name))
      continue;
    error = inventory.count();
    if (error != ok)
      return error;
    // Exact raw-workspace exemption: count all children, but neither stat nor
    // type-check unmatched names, including raw directories and raw symlinks.
    if (native_receipt(child->d_name)) {
      error = inventory.account(family.fd, child->d_name);
      if (error != ok)
        return error;
    }
  }
}

int scan(Inventory& inventory, int fd, bool working) noexcept {
  Entries entries;
  if (!entries.open(fd))
    return filesystem_error;
  for (;;) {
    if (inventory.tick() != ok)
      return deadline_failure;
    errno = 0;
    const dirent* entry = ::readdir(entries.stream);
    if (entry == nullptr)
      return errno == 0 ? ok : filesystem_error;
    if (dot(entry->d_name))
      continue;
    int error = ok;
    if (working) {
      error = scan_family(inventory, fd, entry->d_name);
    } else {
      error = inventory.count();
      if (error == ok)
        error = inventory.account(fd, entry->d_name);
    }
    if (error != ok)
      return error;
  }
}

int retained(Inventory& inventory, int working, const char* path) noexcept {
  constexpr size_t prefix_size = sizeof("working/") - 1U;
  constexpr size_t maximum_path = prefix_size + 64U + 1U + NAME_MAX;
  if (path == nullptr)
    return invalid_input;
  const size_t length = ::strnlen(path, maximum_path + 1U);
  if (length <= prefix_size + 65U || length > maximum_path ||
      ::strncmp(path, "working/", prefix_size) != 0 || path[prefix_size + 64U] != '/')
    return invalid_input;
  char family[65];
  ::memcpy(family, path + prefix_size, 64U);
  family[64] = '\0';
  const char* name = path + prefix_size + 65U;
  if (!family_name(family) || dot(name) || ::strchr(name, '/') != nullptr)
    return invalid_input;
  Descriptor directory;
  directory.fd =
      ::openat(working, family, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (directory.fd < 0)
    return filesystem_error;
  return inventory.account(directory.fd, name);
}
} // namespace

// ABI v1. Strings/array/output must be accessible for the call's duration; the
// caller holds the custody lock and provides a validated retained receipt list.
// deadline is an absolute CLOCK_MONOTONIC nanosecond deadline, never a duration.
// 0 success; 1 invalid input/path; 2 filesystem/type/identity; 3 inventory limit;
// 4 arithmetic overflow; 5 allocation failure; 6 expired deadline/clock failure.
// Output is written only on success and remains unchanged on every failure.
// Build with -fno-exceptions -fno-rtti for a libc-only runtime dependency set.
extern "C" int cpu_prefetch_archive_inventory_v1(
    const char* absolute_root, uint64_t max_inventory_files,
    const char* const* retained_relative_paths, uint64_t retained_count,
    uint64_t deadline_monotonic_ns, InventoryUsage* out) noexcept {
  if (out == nullptr)
    return invalid_input;
  if (max_inventory_files == 0U ||
      (retained_count != 0U && retained_relative_paths == nullptr) ||
      retained_count > SIZE_MAX / sizeof(*retained_relative_paths))
    return invalid_input;
  const auto address = reinterpret_cast<uintptr_t>(retained_relative_paths);
  if (retained_count * sizeof(*retained_relative_paths) > UINTPTR_MAX - address)
    return invalid_input;
  if (check_time(deadline_monotonic_ns) != ok)
    return deadline_failure;
  Descriptor root;
  int error = open_root(absolute_root, deadline_monotonic_ns, &root.fd);
  if (error != ok)
    return error;
  Inventory inventory{deadline_monotonic_ns, max_inventory_files};
  struct stat root_stat{};
  if (::fstat(root.fd, &root_stat) != 0)
    return filesystem_error;
  error = inventory.append(root_stat, true);
  if (error != ok)
    return error;
  Descriptor pinned[6];
  struct stat identities[6]{};
  for (unsigned int i = 0; i < 6U; ++i) {
    if (inventory.tick() != ok)
      return deadline_failure;
    pinned[i].fd = ::openat(root.fd, directories[i],
                            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (pinned[i].fd < 0 || ::fstat(pinned[i].fd, &identities[i]) != 0 ||
        identities[i].st_dev != root_stat.st_dev)
      return filesystem_error;
    error = inventory.append(identities[i], true);
    if (error != ok)
      return error;
  }
  error = scan(inventory, pinned[0].fd, true);
  if (error == ok)
    error = inventory.account(root.fd, "scope.json");
  if (error == ok)
    error = inventory.account(root.fd, "broker.lock");
  // Exact Python visit order: archives, metadata, ledger (not DIRECTORIES order).
  constexpr unsigned int charged[] = {1U, 3U, 2U};
  for (const auto index : charged) {
    if (error == ok)
      error = scan(inventory, pinned[index].fd, false);
  }
  for (uint64_t i = 0; error == ok && i < retained_count; ++i) {
    error = inventory.tick();
    if (error == ok)
      error = retained(inventory, pinned[0].fd, retained_relative_paths[i]);
  }
  if (error != ok)
    return error;
  // Fail closed on namespace replacement while pinned descriptors were in use.
  for (unsigned int i = 0; i < 6U; ++i)
    if (!same_directory(root.fd, directories[i], identities[i]))
      return filesystem_error;
  Descriptor current_root;
  error = open_root(absolute_root, deadline_monotonic_ns, &current_root.fd);
  if (error != ok)
    return error;
  struct stat current{};
  if (::fstat(current_root.fd, &current) != 0 || current.st_dev != root_stat.st_dev ||
      current.st_ino != root_stat.st_ino)
    return filesystem_error;
  return inventory.total(out);
}
