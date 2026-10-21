#include "fheco/dsl/plaintext_matrix.hpp"

#include <stdexcept>

using namespace std;

namespace fheco
{
namespace
{
void validate_common(int height, int width, int kernel, int stride, int channels, int slots)
{
  if (height <= 0 || width <= 0 || kernel <= 0 || stride <= 0 || channels <= 0 || slots <= 0)
    throw invalid_argument("Tensor matrix dimensions, stride, channels, and slots must be positive");
}
}

PlaintextMatrix PlaintextMatrix::from_conv2d(
  const vector<vector<double>> &kernel, Conv2dParams params, int total_slots, bool is_last_layer)
{
  if (kernel.size() != static_cast<size_t>(params.kernel_size) || kernel.empty() ||
      kernel.front().size() != static_cast<size_t>(params.kernel_size))
    throw invalid_argument("kernel dimensions must match kernel_size");
  vector<vector<vector<vector<double>>>> expanded(
    params.channels_out, vector<vector<vector<double>>>(params.channels_in, kernel));
  return from_conv2d(expanded, params, total_slots, is_last_layer);
}

PlaintextMatrix PlaintextMatrix::from_conv2d(
  const vector<vector<vector<vector<double>>>> &kernel, Conv2dParams params, int total_slots,
  bool is_last_layer)
{
  validate_common(params.image_height, params.image_width, params.kernel_size, params.stride,
                  params.channels_in, total_slots);
  if (params.channels_out <= 0 || params.padding < 0 ||
      kernel.size() != static_cast<size_t>(params.channels_out))
    throw invalid_argument("invalid convolution parameters or kernel output channels");
  for (const auto &out_channel : kernel)
    if (out_channel.size() != static_cast<size_t>(params.channels_in))
      throw invalid_argument("kernel input channels must match channels_in");

  const int h_out = (params.image_height + 2 * params.padding - params.kernel_size) / params.stride + 1;
  const int w_out = (params.image_width + 2 * params.padding - params.kernel_size) / params.stride + 1;
  if (h_out <= 0 || w_out <= 0)
    throw invalid_argument("convolution kernel does not fit input");

  if (params.layout == PackingLayout::MULTIPLEXED)
  {
    const int iG = 1;
    const int oG = params.stride;
    const int on_Ci = (params.channels_in + iG * iG - 1) / (iG * iG);
    const int on_Co = (params.channels_out + oG * oG - 1) / (oG * oG);
    const int on_Hi = params.image_height;
    const int on_Wi = params.image_width;
    const int on_Ho = max(on_Hi, h_out * oG);
    const int on_Wo = max(on_Wi, w_out * oG);
    const int n_rows = on_Co * on_Ho * on_Wo;
    const int n_cols = on_Ci * on_Hi * on_Wi;

    vector<vector<double>> toeplitz(n_rows, vector<double>(n_cols, 0.0));
    for (int oh = 0; oh < h_out; ++oh)
    {
      for (int ow = 0; ow < w_out; ++ow)
      {
        const int start_in_idx = (oh * params.stride) * on_Wi + (ow * params.stride);
        for (int c = 0; c < params.channels_out; ++c)
        {
          const int co = c / (oG * oG);
          const int rem = c % (oG * oG);
          const int ry = rem / oG;
          const int rx = rem % oG;
          const int row = co * (on_Ho * on_Wo) + (oh * oG + ry) * on_Wo + (ow * oG + rx);
          for (int ci = 0; ci < params.channels_in; ++ci)
          {
            const auto &plane = kernel[c][ci];
            for (int kh = 0; kh < params.kernel_size; ++kh)
            {
              for (int kw = 0; kw < params.kernel_size; ++kw)
              {
                const int col = start_in_idx + kh * on_Wi + kw;
                if (col < n_cols)
                  toeplitz[row][col] += plane[kh][kw];
              }
            }
          }
        }
      }
    }

    int block_height = total_slots;
    int fold_count = 0;
    if (!is_last_layer && n_rows < total_slots)
    {
      block_height = 1;
      while (block_height < n_rows) block_height <<= 1;
      int R = total_slots / block_height;
      int tmp = R;
      while (tmp > 1) { ++fold_count; tmp >>= 1; }
    }

    unordered_map<int, vector<double>> diagonals;
    if (fold_count > 0)
    {
      for (int d = 0; d < block_height; ++d)
      {
        vector<double> values(total_slots, 0.0);
        bool has_nonzero = false;
        for (int k = 0; k < total_slots; ++k)
        {
          int r = k % block_height;
          int c = (d + k) % total_slots;
          if (r < n_rows && c < n_cols)
          {
            double val = toeplitz[r][c];
            if (val != 0.0)
            {
              values[k] = val;
              has_nonzero = true;
            }
          }
        }
        if (has_nonzero) diagonals[d] = values;
      }
    }
    else
    {
      for (int r = 0; r < n_rows; ++r)
      {
        for (int c = 0; c < n_cols; ++c)
        {
          if (toeplitz[r][c] == 0.0) continue;
          int d = ((c - r) % total_slots + total_slots) % total_slots;
          auto &values = diagonals[d];
          if (values.empty()) values.assign(total_slots, 0.0);
          values[r] += toeplitz[r][c];
        }
      }
    }

    return PlaintextMatrix(move(diagonals), total_slots,
                           TensorShape{static_cast<size_t>(params.channels_out),
                                       static_cast<size_t>(h_out), static_cast<size_t>(w_out)},
                           params.layout, fold_count);
  }

  const int output_size = params.channels_out * h_out * w_out;
  int block_height = total_slots;
  int fold_count = 0;
  if (!is_last_layer && output_size < total_slots)
  {
    block_height = 1;
    while (block_height < output_size) block_height <<= 1;
    int R = total_slots / block_height;
    int tmp = R;
    while (tmp > 1) { ++fold_count; tmp >>= 1; }
  }

  unordered_map<int, vector<double>> diagonals;
  const auto in_slot = [&](int channel, int row, int col) {
    return params.layout == PackingLayout::ROW_MAJOR
      ? (channel * params.image_height + row) * params.image_width + col
      : (row * params.image_width + col) * params.channels_in + channel;
  };
  const auto out_slot = [&](int channel, int row, int col) {
    return params.layout == PackingLayout::ROW_MAJOR
      ? (channel * h_out + row) * w_out + col
      : (row * w_out + col) * params.channels_out + channel;
  };

  for (int row_out = 0; row_out < h_out; ++row_out)
    for (int col_out = 0; col_out < w_out; ++col_out)
      for (int out_channel = 0; out_channel < params.channels_out; ++out_channel)
      {
        const int output = out_slot(out_channel, row_out, col_out);
        for (int kernel_row = 0; kernel_row < params.kernel_size; ++kernel_row)
          for (int kernel_col = 0; kernel_col < params.kernel_size; ++kernel_col)
          {
            const int row_in = row_out * params.stride + kernel_row - params.padding;
            const int col_in = col_out * params.stride + kernel_col - params.padding;
            if (row_in < 0 || row_in >= params.image_height || col_in < 0 || col_in >= params.image_width)
              continue;
            for (int input_channel = 0; input_channel < params.channels_in; ++input_channel)
            {
              const auto &plane = kernel[out_channel][input_channel];
              if (plane.size() != static_cast<size_t>(params.kernel_size) ||
                  plane[kernel_row].size() != static_cast<size_t>(params.kernel_size))
                throw invalid_argument("kernel dimensions must match kernel_size");
              const int input = in_slot(input_channel, row_in, col_in);
              const double w = plane[kernel_row][kernel_col];
              if (w == 0.0) continue;
              if (fold_count > 0)
              {
                const int d = ((input - output) % block_height + block_height) % block_height;
                const int q = ((input - output) % total_slots + total_slots) % total_slots;
                const int m = q / block_height;
                const int k = output + m * block_height;
                auto &values = diagonals[d];
                if (values.empty()) values.assign(total_slots, 0.0);
                values[k] += w;
              }
              else
              {
                const int diagonal = ((input - output) % total_slots + total_slots) % total_slots;
                auto &values = diagonals[diagonal];
                if (values.empty()) values.assign(total_slots, 0.0);
                values[output] += w;
              }
            }
          }
      }

  return PlaintextMatrix(move(diagonals), total_slots,
                         TensorShape{static_cast<size_t>(params.channels_out),
                                     static_cast<size_t>(h_out), static_cast<size_t>(w_out)},
                         params.layout, fold_count);
}

PlaintextMatrix PlaintextMatrix::from_pool(PoolParams params, int total_slots)
{
  const int stride = params.stride == 0 ? params.kernel_size : params.stride;
  validate_common(params.input_height, params.input_width, params.kernel_size, stride,
                  params.channels, total_slots);
  const int h_out = (params.input_height - params.kernel_size) / stride + 1;
  const int w_out = (params.input_width - params.kernel_size) / stride + 1;
  if (h_out <= 0 || w_out <= 0) throw invalid_argument("pooling kernel does not fit input");

  unordered_map<int, vector<double>> diagonals;
  const auto in_slot = [&](int channel, int row, int col) {
    return params.layout == PackingLayout::ROW_MAJOR
      ? (channel * params.input_height + row) * params.input_width + col
      : (row * params.input_width + col) * params.channels + channel;
  };
  const auto out_slot = [&](int channel, int row, int col) {
    return params.layout == PackingLayout::ROW_MAJOR
      ? (channel * h_out + row) * w_out + col
      : (row * w_out + col) * params.channels + channel;
  };
  const double scale = 1.0 / (params.kernel_size * params.kernel_size);
  for (int row_out = 0; row_out < h_out; ++row_out)
    for (int col_out = 0; col_out < w_out; ++col_out)
      for (int channel = 0; channel < params.channels; ++channel)
      {
        const int output = out_slot(channel, row_out, col_out);
        for (int kernel_row = 0; kernel_row < params.kernel_size; ++kernel_row)
          for (int kernel_col = 0; kernel_col < params.kernel_size; ++kernel_col)
          {
            const int input = in_slot(channel, row_out * stride + kernel_row, col_out * stride + kernel_col);
            const int diagonal = ((input - output) % total_slots + total_slots) % total_slots;
            auto &values = diagonals[diagonal];
            if (values.empty()) values.assign(total_slots, 0.0);
            values[output] += scale;
          }
      }
  return PlaintextMatrix(move(diagonals), total_slots,
                         TensorShape{static_cast<size_t>(params.channels),
                                     static_cast<size_t>(h_out), static_cast<size_t>(w_out)},
                         params.layout);
}

PlaintextMatrix PlaintextMatrix::from_dense(
  const vector<vector<double>> &weights, int total_slots, PackingLayout layout, bool is_last_layer)
{
  return from_dense(weights, total_slots, layout, is_last_layer, MultiplexParams());
}

PlaintextMatrix PlaintextMatrix::from_dense(
  const vector<vector<double>> &weights, int total_slots, PackingLayout layout, bool is_last_layer,
  MultiplexParams mpx)
{
  if (weights.empty() || weights.front().empty() || total_slots <= 0)
    throw invalid_argument("dense weights and slots must not be empty");
  const int output_size = static_cast<int>(weights.size());
  const int input_size = static_cast<int>(weights.front().size());

  const vector<vector<double>> *weights_ptr = &weights;
  vector<vector<double>> expanded_weights;

  if (layout == PackingLayout::MULTIPLEXED && mpx.channels > 0)
  {
    const int r = mpx.stride;
    const int on_Co_mpx = (mpx.channels + r * r - 1) / (r * r);
    const int on_Ho_mpx = mpx.height * r;
    const int on_Wo_mpx = mpx.width * r;
    const int expanded_cols = on_Co_mpx * on_Ho_mpx * on_Wo_mpx;
    expanded_weights.assign(output_size, vector<double>(expanded_cols, 0.0));
    for (int out_f = 0; out_f < output_size; ++out_f)
    {
      for (int k = 0; k < mpx.channels; ++k)
      {
        const int co = k / (r * r);
        const int rem = k % (r * r);
        const int ry = rem / r;
        const int rx = rem % r;
        for (int h = 0; h < mpx.height; ++h)
        {
          for (int w = 0; w < mpx.width; ++w)
          {
            const int in_idx = (k * mpx.height + h) * mpx.width + w;
            if (in_idx < input_size)
            {
              const int slot = co * (on_Ho_mpx * on_Wo_mpx) + (h * r + ry) * on_Wo_mpx + (w * r + rx);
              if (slot < expanded_cols)
              {
                expanded_weights[out_f][slot] = weights[out_f][in_idx];
              }
            }
          }
        }
      }
    }
    weights_ptr = &expanded_weights;
  }

  const int effective_input_size = static_cast<int>(weights_ptr->front().size());
  unordered_map<int, vector<double>> diagonals;

  int block_height = total_slots;
  int fold_count = 0;
  if (!is_last_layer && output_size < total_slots)
  {
    block_height = 1;
    while (block_height < output_size) block_height <<= 1;
    int R = total_slots / block_height;
    int tmp = R;
    while (tmp > 1) { ++fold_count; tmp >>= 1; }
  }

  if (fold_count > 0)
  {
    for (int d = 0; d < block_height; ++d)
    {
      vector<double> values(total_slots, 0.0);
      bool has_nonzero = false;
      for (int k = 0; k < total_slots; ++k)
      {
        int r = k % block_height;
        int c = (d + k) % total_slots;
        if (r < output_size && c < effective_input_size)
        {
          double val = (*weights_ptr)[r][c];
          if (val != 0.0)
          {
            values[k] = val;
            has_nonzero = true;
          }
        }
      }
      if (has_nonzero) diagonals[d] = values;
    }
  }
  else
  {
    for (int output = 0; output < output_size; ++output)
    {
      if (static_cast<int>((*weights_ptr)[output].size()) != effective_input_size)
        throw invalid_argument("dense weight rows must have equal size");
      for (int input = 0; input < effective_input_size; ++input)
      {
        if ((*weights_ptr)[output][input] == 0.0) continue;
        const int diagonal = ((input - output) % total_slots + total_slots) % total_slots;
        auto &values = diagonals[diagonal];
        if (values.empty()) values.assign(total_slots, 0.0);
        values[output] += (*weights_ptr)[output][input];
      }
    }
  }
  return PlaintextMatrix(move(diagonals), total_slots,
                         TensorShape{1, 1, weights.size()}, layout, fold_count);
}
} // namespace fheco
