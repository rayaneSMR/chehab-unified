#include "fheco/dsl/matmul.hpp"

#include "fheco/dsl/compiler.hpp"
#include "fheco/dsl/ops_overloads.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

using namespace std;

namespace fheco
{
namespace
{
int best_bsgs_base(const vector<int> &diagonals, int slots)
{
  int best = 1;
  size_t fewest_keys = numeric_limits<size_t>::max();
  for (int n1 = 1; n1 <= min(slots, 256); n1 <<= 1)
  {
    unordered_set<int> keys;
    for (int diagonal : diagonals)
    {
      const int rotation = ((diagonal % slots) + slots) % slots;
      const int baby = n1 > 1 ? rotation & (n1 - 1) : 0;
      const int giant = n1 > 1 ? ((rotation / n1) * n1) & (slots - 1) : rotation;
      if (baby) keys.insert(baby);
      if (giant) keys.insert(giant);
    }
    if (keys.size() < fewest_keys) { fewest_keys = keys.size(); best = n1; }
  }
  return best;
}
}

Tensor matmul(const Tensor &input, const PlaintextMatrix &matrix)
{
  const int slots = static_cast<int>(Compiler::active_func()->slot_count());
  if (matrix.total_slots() != slots)
    throw invalid_argument("matrix slot count must match active function slot count");
  const auto &diagonals = matrix.diagonals();
  if (diagonals.empty()) throw invalid_argument("matmul: matrix has no non-zero diagonals");

  vector<int> indices;
  indices.reserve(diagonals.size());
  for (const auto &[index, values] : diagonals) indices.push_back(index);
  Compiler::register_layer_diags(indices);

  int n1 = Compiler::canonical_bsgs_base();
  if (n1 <= 0) n1 = best_bsgs_base(indices, slots);
  n1 = min(n1, slots);

  struct Diagonal { int index; int baby; };
  map<int, vector<Diagonal>> giant_groups;
  for (int index : indices)
  {
    const int rotation = ((index % slots) + slots) % slots;
    const int baby = n1 > 1 ? rotation & (n1 - 1) : 0;
    const int giant = n1 > 1 ? ((rotation / n1) * n1) & (slots - 1) : rotation;
    giant_groups[giant].push_back({index, baby});
  }

  const Ciphertext x = input.ciphertext();
  unordered_map<int, Ciphertext> baby_steps;
  for (const auto &[giant, group] : giant_groups)
    for (const auto &diagonal : group)
      if (baby_steps.find(diagonal.baby) == baby_steps.end())
        baby_steps.emplace(diagonal.baby, diagonal.baby == 0 ? x : x << diagonal.baby);

  Ciphertext accumulator;
  bool first_group = true;
  for (const auto &[giant, group] : giant_groups)
  {
    Ciphertext inner_sum;
    bool first_entry = true;
    for (const auto &diagonal : group)
    {
      const auto &values = diagonals.at(diagonal.index);
      vector<double> double_vals(slots, 0.0);
      PackedVal packed(slots, 0);
      for (int slot = 0; slot < slots; ++slot)
      {
        const int source = ((slot - giant) % slots + slots) % slots;
        const double value = source < static_cast<int>(values.size()) ? values[source] : 0.0;
        double_vals[slot] = value;
        packed[slot] = value != 0.0 && round(value) == 0.0
          ? (value > 0.0 ? 1 : -1)
          : static_cast<integer>(round(value));
      }
      const Ciphertext product = baby_steps.at(diagonal.baby) * Plaintext(double_vals, packed);
      if (first_entry) { inner_sum = product; first_entry = false; }
      else inner_sum = inner_sum + product;
    }
    const Ciphertext result = giant == 0 ? inner_sum : inner_sum << giant;
    if (first_group) { accumulator = result; first_group = false; }
    else accumulator = accumulator + result;
  }
  if (matrix.fold_count() > 0)
  {
    int block_height = slots >> matrix.fold_count();
    for (int step = block_height; step < slots; step <<= 1)
      accumulator = accumulator + (accumulator << step);
  }
  accumulator = rescale(accumulator);
  return Tensor(accumulator, matrix.output_shape(), matrix.layout());
}

Tensor poly_activate(const Tensor &input, const vector<double> &coefficients)
{
  if (coefficients.empty()) throw invalid_argument("poly_activate: coefficients must not be empty");
  if (coefficients.size() == 3 && coefficients[0] == 0.0 && coefficients[1] == 0.0 && coefficients[2] == 1.0)
  {
    const Ciphertext x = input.ciphertext();
    return Tensor(x * x, input.shape(), input.layout());
  }
  const auto scalar = [](double value) { return Plaintext(static_cast<integer>(round(value))); };
  const Ciphertext x = input.ciphertext();
  if (coefficients.size() == 1)
    return Tensor(x * scalar(0.0) + scalar(coefficients[0]), input.shape(), input.layout());
  Ciphertext result = x * scalar(coefficients.back());
  for (int degree = static_cast<int>(coefficients.size()) - 2; degree >= 0; --degree)
  {
    if (coefficients[degree] != 0.0) result = result + scalar(coefficients[degree]);
    if (degree > 0) result = result * x;
  }
  return Tensor(result, input.shape(), input.layout());
}
} // namespace fheco
