#pragma once

#include "fheco/dsl/tensor.hpp"

#include <unordered_map>
#include <vector>

namespace fheco
{
class PlaintextMatrix
{
public:
  struct Conv2dParams
  {
    int image_height;
    int image_width;
    int kernel_size;
    int stride = 1;
    int padding = 0;
    int channels_in = 1;
    int channels_out = 1;
    PackingLayout layout = PackingLayout::ROW_MAJOR;
  };

  struct PoolParams
  {
    int input_height;
    int input_width;
    int kernel_size;
    int stride = 0;
    int channels = 1;
    PackingLayout layout = PackingLayout::ROW_MAJOR;
  };

  PlaintextMatrix(std::unordered_map<int, std::vector<double>> diagonals,
                  int total_slots, TensorShape output_shape,
                  PackingLayout layout = PackingLayout::ROW_MAJOR,
                  int fold_count = 0)
    : diagonals_(std::move(diagonals)), total_slots_(total_slots),
      output_shape_(output_shape), layout_(layout), fold_count_(fold_count) {}

  struct MultiplexParams
  {
    int channels;
    int height;
    int width;
    int stride;

    MultiplexParams(int c = 0, int h = 0, int w = 0, int s = 1) : channels(c), height(h), width(w), stride(s) {}
  };

  static PlaintextMatrix from_conv2d(const std::vector<std::vector<double>> &kernel,
                                     Conv2dParams params, int total_slots,
                                     bool is_last_layer = true);
  static PlaintextMatrix from_conv2d(
    const std::vector<std::vector<std::vector<std::vector<double>>>> &kernel,
    Conv2dParams params, int total_slots,
    bool is_last_layer = true);
  static PlaintextMatrix from_pool(PoolParams params, int total_slots);
  static PlaintextMatrix from_dense(const std::vector<std::vector<double>> &weights,
                                    int total_slots,
                                    PackingLayout layout = PackingLayout::ROW_MAJOR,
                                    bool is_last_layer = true);
  static PlaintextMatrix from_dense(const std::vector<std::vector<double>> &weights,
                                    int total_slots,
                                    PackingLayout layout,
                                    bool is_last_layer,
                                    MultiplexParams mpx);

  const std::unordered_map<int, std::vector<double>> &diagonals() const { return diagonals_; }
  int non_zero_diagonal_count() const { return static_cast<int>(diagonals_.size()); }
  int total_slots() const { return total_slots_; }
  const TensorShape &output_shape() const { return output_shape_; }
  PackingLayout layout() const { return layout_; }
  int fold_count() const { return fold_count_; }

private:
  std::unordered_map<int, std::vector<double>> diagonals_;
  int total_slots_;
  TensorShape output_shape_;
  PackingLayout layout_;
  int fold_count_;
};
} // namespace fheco
