// Software-only clock process endpoint; never linked into the research worker.
#include <csignal>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

auto main(int argc, char** argv) -> int {
  if (argc != 5 || std::strcmp(argv[1], "--qualify-pair") != 0 ||
      std::strcmp(argv[3], "--output") != 0)
    return 91;
  const bool near = std::strcmp(argv[2], "near") == 0;
  if (!near && std::strcmp(argv[2], "far") != 0)
    return 92;
  char root[4096]{};
  if (std::snprintf(root, sizeof(root), "%s", argv[4]) < 0)
    return 93;
  for (int n = 0; n < 3; ++n) {
    auto* slash = std::strrchr(root, '/');
    if (slash == nullptr)
      return 94;
    *slash = '\0';
  }
  char witness[8192]{};
  static_cast<void>(std::snprintf(witness, sizeof(witness),
                                  "%s/compaction/worker-%s.json", root, argv[2]));
  // Wait for actual parent pidfd/image/cgroup registration. This is test-only
  // coordination, not a qualification time/count or a research entry point.
  struct stat st{};
  int polls = 0;
  while (::stat(witness, &st) != 0 && polls++ < 500)
    static_cast<void>(::usleep(10000));
  if (polls >= 500)
    return 95;
  char mode_path[8192]{};
  static_cast<void>(std::snprintf(mode_path, sizeof(mode_path), "%s/test-mode", root));
  char mode[64]{};
  if (auto* f = std::fopen(mode_path, "rb")) {
    static_cast<void>(std::fread(mode, 1, sizeof(mode) - 1, f));
    static_cast<void>(std::fclose(f));
  }
  if (std::strcmp(mode, "timeout") == 0) {
    for (;;)
      static_cast<void>(::pause());
  }
  if (std::strcmp(mode, "signal") == 0) {
    static_cast<void>(::kill(::getppid(), SIGTERM));
    for (;;)
      static_cast<void>(::pause());
  }
  if (std::strcmp(mode, "escape") == 0) {
    const auto child = ::fork();
    if (child < 0)
      return 97;
    if (child == 0) {
      static_cast<void>(::setsid());
      static_cast<void>(::close(STDOUT_FILENO));
      static_cast<void>(::close(STDERR_FILENO));
      for (;;)
        static_cast<void>(::pause());
    }
  }
  if (std::strcmp(mode, "console") == 0) {
    char block[4096]{};
    for (int n = 0; n < 16; ++n)
      static_cast<void>(::write(STDOUT_FILENO, block, sizeof(block)));
  }
  const bool fail = (near && std::strcmp(mode, "fail-near") == 0) ||
                    (!near && std::strcmp(mode, "fail-far") == 0);
  auto* output = std::fopen(argv[4], "wb");
  if (output == nullptr)
    return 96;
  if (std::strcmp(mode, "malformed") == 0) {
    static_cast<void>(std::fputs("{partial", output));
  } else {
    static_cast<void>(std::fprintf(
        output,
        "{\"consumer_cpu\":%d,\"consumer_delta_count\":10000000,"
        "\"consumer_per_core_passed\":true,\"consumer_pinned\":true,"
        "\"consumer_prime_read_count\":100000,\"consumer_to_producer_window_count\":3,"
        "\"cross_core_passed\":%s,\"exchanges_per_window\":100000,\"pair\":\"%s\","
        "\"producer_cpu\":0,\"producer_delta_count\":10000000,"
        "\"producer_per_core_passed\":true,\"producer_pinned\":true,"
        "\"producer_prime_read_count\":100000,\"producer_to_consumer_window_count\":3,"
        "\"schema_version\":\"cpu-prefetch-stage17-q15-clock-pair-raw/1\"}",
        near ? 1 : 8, fail ? "false" : "true", argv[2]));
  }
  static_cast<void>(std::fclose(output));
  return fail ? 7 : 0;
}
