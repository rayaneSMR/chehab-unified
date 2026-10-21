#pragma once

#include "fheco/dsl/ciphertext.hpp"
#include "fheco/dsl/compiler.hpp"
#include "fheco/dsl/ops_overloads.hpp"

#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace fheco
{
enum class PackingLayout
{
  ROW_MAJOR,
  INTERLEAVED_HWC,
  MULTIPLEXED,
};

struct TensorShape
{
  std::size_t channels = 1;
  std::size_t height = 1;
  std::size_t width = 1;

  TensorShape(std::size_t c = 1, std::size_t h = 1, std::size_t w = 1)
    : channels(c), height(h), width(w)
  {
    validate();
  }

  void validate() const
  {
    if (channels == 0 || height == 0 || width == 0)
      throw std::invalid_argument("Tensor dimensions (channels, height, width) must all be > 0");
    if (height > std::numeric_limits<std::size_t>::max() / channels)
      throw std::overflow_error("Integer overflow in TensorShape::numel (channels * height)");
    const std::size_t ch = channels * height;
    if (width > std::numeric_limits<std::size_t>::max() / ch)
      throw std::overflow_error("Integer overflow in TensorShape::numel (channels * height * width)");
  }

  std::size_t numel() const { return channels * height * width; }
};

class Tensor
{
public:
  explicit Tensor(const std::string &label, TensorShape shape,
                  PackingLayout layout = PackingLayout::ROW_MAJOR)
    : shape_(shape), layout_(layout)
  {
    validate_simd_capacity();
    ct_ = Ciphertext(label, std::vector<std::size_t>{Compiler::active_func()->slot_count()});
  }

  Tensor(Ciphertext ct, TensorShape shape, PackingLayout layout = PackingLayout::ROW_MAJOR)
    : ct_(std::move(ct)), shape_(shape), layout_(layout)
  {
    validate_simd_capacity();
  }

  Ciphertext &ciphertext() { return ct_; }
  const Ciphertext &ciphertext() const { return ct_; }
  const TensorShape &shape() const { return shape_; }
  PackingLayout layout() const { return layout_; }
  std::size_t id() const { return ct_.id(); }
  const Tensor &set_output(const std::string &label) const { ct_.set_output(label); return *this; }

  std::size_t slot_index(std::size_t ch, std::size_t row, std::size_t col) const
  {
    if (ch >= shape_.channels || row >= shape_.height || col >= shape_.width)
      throw std::out_of_range("Tensor slot index out of bounds");
    if (layout_ == PackingLayout::ROW_MAJOR)
      return (ch * shape_.height + row) * shape_.width + col;
    return (row * shape_.width + col) * shape_.channels + ch;
  }

private:
  void validate_simd_capacity() const
  {
    shape_.validate();
    const std::size_t slots = Compiler::active_func()->slot_count();
    if (shape_.numel() > slots)
      throw std::invalid_argument("Tensor numel exceeds available FHE SIMD slot capacity");
  }

  Ciphertext ct_;
  TensorShape shape_;
  PackingLayout layout_;
};

inline Tensor operator+(const Tensor &lhs, const Tensor &rhs)
{
  if (lhs.shape().numel() != rhs.shape().numel())
    throw std::invalid_argument("Tensor dimensions must match for addition");
  return Tensor(lhs.ciphertext() + rhs.ciphertext(), lhs.shape(), lhs.layout());
}

inline Tensor operator-(const Tensor &lhs, const Tensor &rhs)
{
  if (lhs.shape().numel() != rhs.shape().numel())
    throw std::invalid_argument("Tensor dimensions must match for subtraction");
  return Tensor(lhs.ciphertext() - rhs.ciphertext(), lhs.shape(), lhs.layout());
}
} // namespace fheco
