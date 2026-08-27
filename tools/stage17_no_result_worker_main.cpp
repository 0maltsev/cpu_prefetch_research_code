#include <string_view>

#if defined(__SANITIZE_ADDRESS__)
extern "C" const char* __asan_default_options() { return "detect_leaks=0"; }
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
extern "C" const char* __asan_default_options() { return "detect_leaks=0"; }
#endif
#endif

[[gnu::used]] static const char kProfile[] = "STAGE17-FIXED-ACTION-WORKER-v2";
[[gnu::used]] static const char kQ15R[] = "Q15-R";
[[gnu::used]] static const char kQ15W[] = "Q15-W";
[[gnu::used]] static const char kQ16a[] = "Q16a";
[[gnu::used]] static const char kQ16b[] = "Q16b";
[[gnu::used]] static const char kQ16c[] = "Q16c";
[[gnu::used]] static const char kPilot[] = "STAGE17-BLINDED-PILOT";

// Deliberately faulty, test-only compiled worker. It accepts only the fixed
// dispatcher shape and exits zero without publishing the mandatory typed
// result. The production controller integration suite must reject it.
int main(int argc, char** argv) {
  return argc == 10 &&
                 std::string_view(argv[1]) == "--execute-fixed-stage17-action-v2" &&
                 std::string_view(argv[3]) == "--request-fd" &&
                 std::string_view(argv[5]) == "--context-fd" &&
                 std::string_view(argv[7]) == "--output-dir-fd" &&
                 std::string_view(argv[9]) == "--fixed-dispatch-end"
             ? 0
             : 1;
}
