#include "fheco/fheco.hpp"
#include "fheco/ckks/ckks_params.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;
using namespace fheco;

namespace
{
constexpr int kDefaultSlots = 256;

vector<vector<double>> kernel3()
{
  return {{-1.0, -1.0, -1.0}, {-1.0, 8.0, -1.0}, {-1.0, -1.0, -1.0}};
}

vector<vector<double>> dense_weights(int outputs, int inputs)
{
  const double scale = 1.0 / static_cast<double>(inputs);
  vector<vector<double>> weights(outputs, vector<double>(inputs));
  for (int output = 0; output < outputs; ++output)
    for (int input = 0; input < inputs; ++input)
      weights[output][input] = static_cast<double>((output + input) % 3 - 1) * scale;
  return weights;
}

vector<vector<vector<vector<double>>>> conv_weights(int output_channels, int input_channels, int kernel_size)
{
  return vector<vector<vector<vector<double>>>>(
    output_channels, vector<vector<vector<double>>>(
      input_channels, vector<vector<double>>(kernel_size, vector<double>(kernel_size, 0.05))));
}


void build_conv2d(int slots)
{
  Tensor image("image", TensorShape{1, 16, 16});
  PlaintextMatrix::Conv2dParams params{16, 16, 3};
  params.layout = PackingLayout::MULTIPLEXED;
  matmul(image, PlaintextMatrix::from_conv2d(kernel3(), params, slots)).set_output("conv_output");
}

void build_full_dnn(int slots)
{
  Tensor image("image", TensorShape{1, 16, 16});
  PlaintextMatrix::Conv2dParams conv1{16, 16, 3};
  conv1.layout = PackingLayout::MULTIPLEXED;
  Tensor layer1 = poly_activate(matmul(image, PlaintextMatrix::from_conv2d(kernel3(), conv1, slots, false)), {0, 0, 1});
  PlaintextMatrix::PoolParams pool{14, 14, 2, 2};
  Tensor layer2 = matmul(layer1, PlaintextMatrix::from_pool(pool, slots));
  PlaintextMatrix::Conv2dParams conv2{7, 7, 3};
  conv2.layout = PackingLayout::MULTIPLEXED;
  Tensor layer3 = poly_activate(matmul(layer2, PlaintextMatrix::from_conv2d(kernel3(), conv2, slots, false)), {0, 0, 1});
  matmul(layer3, PlaintextMatrix::from_dense(dense_weights(10, 25), slots)).set_output("classification");
}

void build_cryptonets(int slots)
{
  Tensor image("image", TensorShape{1, 16, 16}, PackingLayout::INTERLEAVED_HWC);
  PlaintextMatrix::Conv2dParams conv1{16, 16, 3, 2, 0, 1, 3, PackingLayout::INTERLEAVED_HWC};
  Tensor layer1 = poly_activate(matmul(image, PlaintextMatrix::from_conv2d(conv_weights(3, 1, 3), conv1, slots)), {0, 0, 1});
  PlaintextMatrix::PoolParams pool{7, 7, 2, 2, 3, PackingLayout::INTERLEAVED_HWC};
  Tensor layer2 = matmul(layer1, PlaintextMatrix::from_pool(pool, slots));
  PlaintextMatrix::Conv2dParams conv2{3, 3, 3, 1, 0, 3, 4, PackingLayout::INTERLEAVED_HWC};
  Tensor layer3 = poly_activate(matmul(layer2, PlaintextMatrix::from_conv2d(conv_weights(4, 3, 3), conv2, slots)), {0, 0, 1});
  matmul(layer3, PlaintextMatrix::from_dense(dense_weights(10, 4), slots, PackingLayout::INTERLEAVED_HWC)).set_output("classification");
}



//LoLA: Low-Latency CryptoNet from Figure 3 of https://arxiv.org/pdf/1812.10659

void build_lola(int slots)
{
  Tensor image("image", TensorShape{1, 28, 28});
  PlaintextMatrix::Conv2dParams conv1_params{28, 28, 2, 2, 0, 1, 5, PackingLayout::MULTIPLEXED};
  Tensor conv1 = matmul(image, PlaintextMatrix::from_conv2d(conv_weights(5, 1, 2), conv1_params, slots, false));
  Tensor act1 = poly_activate(conv1, {0, 0, 1});

  Tensor dense1 = matmul(act1, PlaintextMatrix::from_dense(dense_weights(100, 980), slots, PackingLayout::MULTIPLEXED, false, {5, 14, 14, 2}));
  Tensor act2 = poly_activate(dense1, {0, 0, 1});

  matmul(act2, PlaintextMatrix::from_dense(dense_weights(10, 100), slots)).set_output("classification");
}


// MLP: Multi-Layer Perceptron from SecureML (https://eprint.iacr.org/2017/396.pdf)
 
void build_mlp(int slots)
{
  Tensor input("input", TensorShape{1, 1, 784});
  Tensor layer1 = poly_activate(matmul(input, PlaintextMatrix::from_dense(dense_weights(128, 784), slots, PackingLayout::ROW_MAJOR, false)), {0, 0, 1});
  Tensor layer2 = poly_activate(matmul(layer1, PlaintextMatrix::from_dense(dense_weights(128, 128), slots, PackingLayout::ROW_MAJOR, false)), {0, 0, 1});
  matmul(layer2, PlaintextMatrix::from_dense(dense_weights(10, 128), slots)).set_output("classification");
}

// LeNet: Orion's 28x28 grayscale network with strided convolutions.

void build_lenet(int slots)
{
  Tensor image("image", TensorShape{1, 28, 28});

  PlaintextMatrix::Conv2dParams conv1_params{28, 28, 5, 2, 2, 1, 32};
  Tensor conv1 = poly_activate(
    matmul(image, PlaintextMatrix::from_conv2d(conv_weights(32, 1, 5), conv1_params, slots, false)),
    {0, 0, 1});

  PlaintextMatrix::Conv2dParams conv2_params{14, 14, 5, 2, 2, 32, 64};
  Tensor conv2 = poly_activate(
    matmul(conv1, PlaintextMatrix::from_conv2d(conv_weights(64, 32, 5), conv2_params, slots, false)),
    {0, 0, 1});

  Tensor fc1 = poly_activate(
    matmul(conv2, PlaintextMatrix::from_dense(dense_weights(512, 7 * 7 * 64), slots,
                                               PackingLayout::ROW_MAJOR, false)),
    {0, 0, 1});
  matmul(fc1, PlaintextMatrix::from_dense(dense_weights(10, 512), slots)).set_output("classification");
}


enum class ResNetActivation { relu, silu };

vector<double> resnet_activation(ResNetActivation activation)
{
  // Integer-coefficient polynomial approximations used by the tensor DSL.
  return activation == ResNetActivation::relu ? vector<double>{0, 0, 1}
                                              : vector<double>{0, 1, 1};
}

Tensor resnet_conv(const Tensor &input, int height, int width, int kernel, int stride,
                   int input_channels, int output_channels, int slots)
{
  PlaintextMatrix::Conv2dParams params{
    height, width, kernel, stride, kernel / 2, input_channels, output_channels};
  return matmul(input, PlaintextMatrix::from_conv2d(
                         conv_weights(output_channels, input_channels, kernel),
                         params, slots));
}

Tensor resnet_block(const Tensor &input, int height, int width, int input_channels,
                    int output_channels, int stride, bool bottleneck,
                    ResNetActivation activation, int slots)
{
  const vector<double> coefficients = resnet_activation(activation);
  const int expansion = bottleneck ? 4 : 1;
  const int expanded_channels = output_channels * expansion;
  const int output_height = (height + 2 * (bottleneck ? 0 : 1) -
                             (bottleneck ? 1 : 3)) / stride + 1;
  const int output_width = output_height;

  Tensor out = input;
  if (bottleneck)
  {
    out = resnet_conv(out, height, width, 1, 1, input_channels, output_channels, slots);
    out = poly_activate(out, coefficients);
    out = resnet_conv(out, height, width, 3, stride, output_channels, output_channels, slots);
    out = poly_activate(out, coefficients);
    out = resnet_conv(out, output_height, output_width, 1, 1,
                      output_channels, expanded_channels, slots);
  }
  else
  {
    out = resnet_conv(out, height, width, 3, stride,
                      input_channels, output_channels, slots);
    out = poly_activate(out, coefficients);
    out = resnet_conv(out, output_height, output_width, 3, 1,
                      output_channels, expanded_channels, slots);
  }

  Tensor shortcut = input;
  if (stride != 1 || input_channels != expanded_channels)
    shortcut = resnet_conv(input, height, width, 1, stride,
                           input_channels, expanded_channels, slots);
  return poly_activate(out + shortcut, coefficients);
}

void build_resnet(int slots, const vector<int> &blocks, bool bottleneck,
                  ResNetActivation activation)
{
  constexpr int image_size = 16;
  constexpr int initial_channels = 8;
  const vector<int> channels = bottleneck ? vector<int>{8, 16, 32, 64}
                                          : vector<int>{8, 16, 32, 64};
  Tensor out("image", TensorShape{3, image_size, image_size});
  out = resnet_conv(out, image_size, image_size, 3, 1, 3, initial_channels, slots);
  out = poly_activate(out, resnet_activation(activation));

  int height = image_size;
  int width = image_size;
  int input_channels = initial_channels;
  for (size_t stage = 0; stage < blocks.size(); ++stage)
  {
    for (int block = 0; block < blocks[stage]; ++block)
    {
      const int stride = stage == 0 || block != 0 ? 1 : 2;
      out = resnet_block(out, height, width, input_channels, channels[stage],
                         stride, bottleneck, activation, slots);
      if (stride == 2)
      {
        height /= 2;
        width /= 2;
      }
      input_channels = channels[stage] * (bottleneck ? 4 : 1);
    }
  }

  PlaintextMatrix::PoolParams gap_params{height, width, height, width, input_channels};
  Tensor gap = matmul(out, PlaintextMatrix::from_pool(gap_params, slots));
  matmul(gap, PlaintextMatrix::from_dense(dense_weights(10, input_channels), slots))
    .set_output("classification");
}

void build_resnet20(int slots, ResNetActivation activation)
{
  build_resnet(slots, {3, 3, 3}, false, activation);
}

void build_resnet34(int slots, ResNetActivation activation)
{
  build_resnet(slots, {3, 4, 6, 3}, false, activation);
}

void build_resnet50(int slots, ResNetActivation activation)
{
  build_resnet(slots, {3, 4, 6, 3}, true, activation);
}

// AlexNet: Orion's 32x32 input network with five convolutional layers.

void build_alexnet(int slots)
{
  Tensor image("image", TensorShape{3, 32, 32});

  // Conv1 + Pool1
  PlaintextMatrix::Conv2dParams c1{32, 32, 3, 1, 1, 3, 64};
  Tensor c1_out = poly_activate(
    matmul(image, PlaintextMatrix::from_conv2d(conv_weights(64, 3, 3), c1, slots, false)),
    {0, 0, 1});
  PlaintextMatrix::PoolParams p1{32, 32, 2, 2, 64};
  Tensor p1_out = matmul(c1_out, PlaintextMatrix::from_pool(p1, slots));

  // Conv2 + Pool2
  PlaintextMatrix::Conv2dParams c2{16, 16, 3, 1, 1, 64, 192};
  Tensor c2_out = poly_activate(
    matmul(p1_out, PlaintextMatrix::from_conv2d(conv_weights(192, 64, 3), c2, slots, false)),
    {0, 0, 1});
  PlaintextMatrix::PoolParams p2{16, 16, 2, 2, 192};
  Tensor p2_out = matmul(c2_out, PlaintextMatrix::from_pool(p2, slots));

  // Conv3, Conv4, Conv5
  PlaintextMatrix::Conv2dParams c3{8, 8, 3, 1, 1, 192, 384};
  Tensor c3_out = poly_activate(
    matmul(p2_out, PlaintextMatrix::from_conv2d(conv_weights(384, 192, 3), c3, slots, false)),
    {0, 0, 1});

  PlaintextMatrix::Conv2dParams c4{8, 8, 3, 1, 1, 384, 256};
  Tensor c4_out = poly_activate(
    matmul(c3_out, PlaintextMatrix::from_conv2d(conv_weights(256, 384, 3), c4, slots, false)),
    {0, 0, 1});

  PlaintextMatrix::Conv2dParams c5{8, 8, 3, 1, 1, 256, 256};
  Tensor c5_out = poly_activate(
    matmul(c4_out, PlaintextMatrix::from_conv2d(conv_weights(256, 256, 3), c5, slots, false)),
    {0, 0, 1});

  // AdaptiveAvgPool2d((2, 2)): average pool the 8x8 feature maps to 2x2.
  PlaintextMatrix::PoolParams p3{8, 8, 4, 4, 256};
  Tensor p3_out = matmul(c5_out, PlaintextMatrix::from_pool(p3, slots));

  // Flatten (256*2*2 = 1024) + classifier.
  Tensor fc1 = poly_activate(
    matmul(p3_out, PlaintextMatrix::from_dense(dense_weights(4096, 1024), slots,
                                                PackingLayout::ROW_MAJOR, false)),
    {0, 0, 1});
  Tensor fc2 = poly_activate(
    matmul(fc1, PlaintextMatrix::from_dense(dense_weights(4096, 4096), slots,
                                             PackingLayout::ROW_MAJOR, false)),
    {0, 0, 1});
  matmul(fc2, PlaintextMatrix::from_dense(dense_weights(10, 4096), slots)).set_output("classification");
}

void build(const string &benchmark, int slots)
{
  if (benchmark == "conv2d") build_conv2d(slots);
  else if (benchmark == "full_dnn") build_full_dnn(slots);
  else if (benchmark == "cryptonets") build_cryptonets(slots);
  else if (benchmark == "lola") build_lola(slots);
  else if (benchmark == "mlp") build_mlp(slots);
  else if (benchmark == "lenet") build_lenet(slots);
  else if (benchmark == "resnet" || benchmark == "resnet20_relu")
    build_resnet20(slots, ResNetActivation::relu);
  else if (benchmark == "resnet20_silu")
    build_resnet20(slots, ResNetActivation::silu);
  else if (benchmark == "resnet34_relu")
    build_resnet34(slots, ResNetActivation::relu);
  else if (benchmark == "resnet34_silu")
    build_resnet34(slots, ResNetActivation::silu);
  else if (benchmark == "resnet50_relu")
    build_resnet50(slots, ResNetActivation::relu);
  else if (benchmark == "resnet50_silu")
    build_resnet50(slots, ResNetActivation::silu);
  else if (benchmark == "alexnet") build_alexnet(slots);
  else throw invalid_argument("--benchmark must be conv2d, full_dnn, cryptonets, lola, mlp, lenet, "
                              "resnet20_relu, resnet20_silu, resnet34_relu, resnet34_silu, "
                              "resnet50_relu, resnet50_silu, or alexnet");
}

int get_default_slots(const string &benchmark)
{
  if (benchmark == "lola" || benchmark == "mlp") return 4096;
  if (benchmark == "lenet") return 8192;
  if (benchmark == "resnet" || benchmark.rfind("resnet", 0) == 0) return 32768;
  if (benchmark == "alexnet") return 65536;
  return kDefaultSlots;
}

bool has_orion_ckks_params(const string &benchmark)
{
  return benchmark == "lola" || benchmark == "mlp" || benchmark == "lenet" ||
         benchmark == "resnet" || benchmark.rfind("resnet", 0) == 0 || benchmark == "alexnet" ||
         benchmark == "conv2d" || benchmark == "full_dnn" || benchmark == "cryptonets";
}

ckks::CKKSParams get_orion_ckks_params(const string &benchmark)
{
  ckks::CKKSParams params;
  if (benchmark == "lola" || benchmark == "mlp")
  {
    params.log_n = 13;
    params.log_q = {29, 26, 26, 26, 26, 26};
    params.log_p = {29, 29};
    params.log_scale = 26;
    params.hamming_weight = 8192;
    params.ring_type = ckks::RingType::ConjugateInvariant;
    params.enable_bootstrap = false;
  }
  else if (benchmark == "lenet")
  {
    params.log_n = 14;
    params.log_q = {55, 40, 40, 40, 40, 40, 40, 40};
    params.log_p = {61, 61, 61};
    params.log_scale = 40;
    params.hamming_weight = 192;
    params.ring_type = ckks::RingType::Standard;
    params.enable_bootstrap = false;
  }
  else if (benchmark == "conv2d")
  {
    params.log_n = 9;
    params.log_q = {29, 26};
    params.log_p = {29, 29};
    params.log_scale = 26;
    params.hamming_weight = 192;
    params.ring_type = ckks::RingType::Standard;
    params.enable_bootstrap = false;
  }
  else if (benchmark == "full_dnn" || benchmark == "cryptonets")
  {
    params.log_n = 9;
    params.log_q = {29, 26, 26, 26, 26, 26, 26};
    params.log_p = {29, 29};
    params.log_scale = 26;
    params.hamming_weight = 192;
    params.ring_type = ckks::RingType::Standard;
    params.enable_bootstrap = false;
  }
  else if (benchmark == "resnet" || benchmark.rfind("resnet", 0) == 0)
  {
    // Config for ResNet Parameter Set
    params.log_n = 16;
    params.log_q = {55, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40};
    params.log_p = {61, 61, 61};
    params.log_scale = 40;
    params.hamming_weight = 192;
    params.ring_type = ckks::RingType::Standard;
    params.log_p_boot = {61, 61, 61, 61, 61, 61, 61, 61};
    params.enable_bootstrap = true;
  }
  else if (benchmark == "alexnet")
  {
    // Config for AlexNet
    params.log_n = 17;
    params.log_q = {55, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40,
                    40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40};
    params.log_p = {61, 61, 61};
    params.log_scale = 40;
    params.hamming_weight = 192;
    params.ring_type = ckks::RingType::Standard;
    params.enable_bootstrap = false;
  }
  return params;
}

} // namespace

int main(int argc, char **argv)
{
  std::cout.setf(std::ios::unitbuf);
  std::cerr.setf(std::ios::unitbuf);
  string benchmark = "cryptonets";
  string backend = "lattigo";
  bool global_bsgs = false;
  bool optimize = true;
  string optimizer = "trs";
  float w_ops = 0.5f;
  int user_slots = -1;
  bool use_naf = false;
  size_t rotation_keys_threshold = 0;

  for (int index = 1; index < argc; ++index)
  {
    const string argument = argv[index];
    if (argument == "--benchmark" && ++index < argc) benchmark = argv[index];
    else if (argument == "--backend" && ++index < argc)
    {
      const string value = argv[index];
      if (value != "lattigo" && value != "heongpu")
      {
        throw invalid_argument("--backend must be lattigo or heongpu");
      }
      backend = value;
    }
    else if (argument == "--slots" && ++index < argc) user_slots = stoi(argv[index]);
    else if (argument == "--bsgs-base" && ++index < argc)
    {
      const string value = argv[index];
      if (value == "global") global_bsgs = true;
      else Compiler::set_canonical_bsgs_base(stoi(value));
    }
    else if (argument == "--naf")
    {
      use_naf = true;
    }
    else if (argument == "--naf-threshold" && ++index < argc)
    {
      const int threshold = stoi(argv[index]);
      if (threshold < 0)
        throw invalid_argument("--naf-threshold must be non-negative");
      rotation_keys_threshold = static_cast<size_t>(threshold);
    }
    else if (argument == "--optimizer" && ++index < argc)
    {
      const string value = argv[index];
      if (value == "none") optimize = false;
      else if (value != "trs" && value != "original_rl" && value != "morl" && value != "constrained_rl")
      {
        throw invalid_argument("--optimizer must be trs, original_rl, morl, constrained_rl, or none");
      }
      optimizer = value;
    }
    else if (argument == "--w-ops" && ++index < argc)
    {
      w_ops = stof(argv[index]);
    }
    else throw invalid_argument("unknown argument: " + argument);
  }

  const int slots = user_slots > 0 ? user_slots : get_default_slots(benchmark);

  Compiler::enable_cse();
  Compiler::enable_order_operands();
  Compiler::enable_const_folding();
  const string function_name = "tensor_" + benchmark;
  if (global_bsgs)
  {
    Compiler::clear_diag_collector();
    Compiler::create_func(function_name, slots, 20, false, true);
    build(benchmark, slots);
    Compiler::set_canonical_bsgs_base(Compiler::compute_global_bsgs_base());
    Compiler::clear_all_funcs();
    Compiler::clear_diag_collector();
  }

  const auto &func = Compiler::create_func(function_name, slots, 20, false, true);
  const auto started = chrono::steady_clock::now();
  build(benchmark, slots);
  if (optimizer != "none")
  {
    try
    {
      if (optimizer == "trs")
      {
        Compiler::compile(func, Compiler::Ruleset::depth, trs::RewriteHeuristic::bottom_up);
      }
      else if (optimizer == "original_rl")
      {
        Compiler::gen_vectorized_code(func, 0, 1, -1.0f, -1.0f, "original");
      }
      else if (optimizer == "morl")
      {
        Compiler::gen_vectorized_code(func, 0, 1, w_ops, 1.0f - w_ops, "morl");
      }
      else if (optimizer == "constrained_rl")
      {
        Compiler::gen_vectorized_code(func, 0, 1, -1.0f, -1.0f, "constrained");
      }
    }
    catch (const std::exception &e)
    {
      std::cerr << "CRITICAL ERROR in optimizer (" << optimizer << "): " << e.what() << std::endl;
      throw;
    }
  }

  string output;
  if (backend == "lattigo")
  {
    filesystem::create_directories("he");
    output = "he/" + function_name + "_auto.go";
    ofstream generated(output);
    if (!generated) throw runtime_error("cannot create " + output);

    if (has_orion_ckks_params(benchmark))
    {
      ckks::CKKSParams params = get_orion_ckks_params(benchmark);
      if (use_naf)
        Compiler::gen_lattigo_code(func, generated, params, rotation_keys_threshold);
      else
        Compiler::gen_lattigo_code(func, generated, params);
    }
    else
    {
      if (use_naf)
        Compiler::gen_lattigo_code(func, generated, rotation_keys_threshold);
      else
        Compiler::gen_lattigo_code(func, generated);
    }
  }
  else
  {
    if (use_naf)
      std::cerr << "warning: --naf is only supported by the lattigo backend; ignoring for heongpu\n";

    filesystem::create_directories("heongpu");
    output = "heongpu/generated_fhe.cu";
    ofstream generated(output);
    if (!generated) throw runtime_error("cannot create " + output);

    if (has_orion_ckks_params(benchmark))
    {
      ckks::CKKSParams params = get_orion_ckks_params(benchmark);
      Compiler::gen_heongpu_code(func, generated, 1, params);
    }
    else
    {
      Compiler::gen_heongpu_code(func, generated, 1);
    }

    // Also save a benchmark-named copy for reference
    const string named_output = "heongpu/" + function_name + "_auto.cu";
    try {
      filesystem::copy_file(output, named_output, filesystem::copy_options::overwrite_existing);
    } catch (...) {}
  }

  cout << "Tensor benchmark: " << benchmark << '\n'
       << "SIMD slots: " << slots << '\n'
       << "Backend: " << backend << '\n'
       << "DSL generation time: "
       << chrono::duration<double, milli>(chrono::steady_clock::now() - started).count() << " ms\n"
       << "Generated: " << output << endl;
}
