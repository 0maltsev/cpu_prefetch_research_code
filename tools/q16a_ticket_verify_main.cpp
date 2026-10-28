// Standalone, informal diagnostic ONLY -- verifies a hand-authored
// runner_admission ticket (for Q16a's R0 ring-off package) against the
// real load_admission/validate_admission_fields logic before it is ever
// submitted to the real formal admission ceremony. Not wired into any
// CMake target.

#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/runner.hpp"

#include <cstdio>
#include <fstream>
#include <sstream>

int main(int argument_count, char** arguments) {
  if (argument_count < 2) {
    std::fprintf(stderr, "usage: %s <ticket.json>\n", arguments[0]);
    return 1;
  }
  std::ifstream input(arguments[1]);
  if (!input) {
    std::fprintf(stderr, "cannot open %s\n", arguments[1]);
    return 1;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  const auto document = buffer.str();

  const auto parsed = cpu_prefetch::protocol::json::parse(document);
  if (!parsed) {
    std::fprintf(stderr, "outer JSON parse failed\n");
    return 1;
  }
  const auto* root_object = parsed.value().as_object();
  if (root_object == nullptr) {
    std::fprintf(stderr, "outer JSON is not an object\n");
    return 1;
  }
  const auto admission_it = root_object->find("runner_admission");
  if (admission_it == root_object->end()) {
    std::fprintf(stderr, "runner_admission field is absent\n");
    return 1;
  }
  const auto admission_canonical =
      cpu_prefetch::protocol::json::canonicalize(admission_it->second);
  if (!admission_canonical) {
    std::fprintf(stderr, "admission canonicalize failed\n");
    return 1;
  }

  const auto admission =
      cpu_prefetch::runner::load_admission(admission_canonical.value());
  if (!admission) {
    std::fprintf(stderr, "load_admission FAILED:\n");
    for (const auto& error : admission.errors()) {
      std::fprintf(stderr, "  %s %s: %s\n", error.path.c_str(), error.rule_id.c_str(),
                   error.message.c_str());
    }
    return 1;
  }
  std::printf("load_admission: PASS\n");

  const auto repository = cpu_prefetch::foundation::repository_info();
  const cpu_prefetch::runner::AdmissionTrustAnchor trust{
      std::string(repository.source_revision), admission.value().binary_sha256,
      admission.value().stand_id, admission.value().binding_id,
      repository.source_dirty};
  const auto errors =
      cpu_prefetch::runner::validate_admission_fields(admission.value(), trust);
  if (!errors.empty()) {
    std::fprintf(stderr, "validate_admission_fields FAILED:\n");
    for (const auto& error : errors) {
      std::fprintf(stderr, "  %s %s: %s\n", error.path.c_str(), error.rule_id.c_str(),
                   error.message.c_str());
    }
    return 1;
  }
  std::printf("validate_admission_fields: PASS\n");
  std::printf("real repository source_revision=%s source_dirty=%d\n",
              std::string(repository.source_revision).c_str(), repository.source_dirty);
  return 0;
}
