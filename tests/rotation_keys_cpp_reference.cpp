#include "fheco/dsl/ciphertext.hpp"
#include "fheco/dsl/compiler.hpp"
#include "fheco/dsl/ops_overloads.hpp"
#include "fheco/passes/reduce_rotation_keys.hpp"

#include <algorithm>
#include <iostream>
#include <memory>
#include <string>
#include <unordered_set>
#include <vector>

int main(int argc, char **argv)
{
  if (argc < 3)
  {
    std::cerr << "usage: rotation_keys_reference threshold step:frequency...\n";
    return 2;
  }

  const auto threshold = static_cast<std::size_t>(std::stoul(argv[1]));
  const auto &func = fheco::Compiler::create_func("rotation_reference", 64, 20, false, true);
  fheco::Compiler::disable_cse();

  std::size_t occurrence = 0;
  for (int i = 2; i < argc; ++i)
  {
    const std::string argument(argv[i]);
    const auto separator = argument.find(':');
    if (separator == std::string::npos)
    {
      std::cerr << "expected step:frequency, got: " << argument << '\n';
      return 2;
    }
    const auto step = std::stoi(argument.substr(0, separator));
    const auto frequency = std::stoul(argument.substr(separator + 1));
    for (std::size_t count = 0; count < frequency; ++count)
    {
      fheco::Ciphertext input("input_" + std::to_string(occurrence));
      auto rotated = input << step;
      rotated.set_output("output_" + std::to_string(occurrence));
      ++occurrence;
    }
  }

  try
  {
    const auto steps = fheco::passes::reduce_rotation_keys(func, threshold);
    std::vector<int> ordered_steps(steps.begin(), steps.end());
    std::sort(ordered_steps.begin(), ordered_steps.end());
    for (const auto step : ordered_steps)
      std::cout << step << ' ';
    std::cout << '\n';
  }
  catch (const std::logic_error &error)
  {
    std::cout << "ERROR: " << error.what() << '\n';
    return 3;
  }
}
