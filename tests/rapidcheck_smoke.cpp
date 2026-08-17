#include <rapidcheck.h>

#include <algorithm>
#include <exception>
#include <iostream>
#include <vector>

int main() {
  try {
    const bool passed = rc::check("reversing a vector twice preserves it",
                                  [](const std::vector<int>& input) {
                                    auto copy = input;
                                    std::reverse(copy.begin(), copy.end());
                                    std::reverse(copy.begin(), copy.end());
                                    RC_ASSERT(copy == input);
                                  });
    return passed ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "RapidCheck smoke test failed with exception: " << error.what()
              << '\n';
  } catch (...) {
    std::cerr << "RapidCheck smoke test failed with an unknown exception\n";
  }
  return 2;
}
