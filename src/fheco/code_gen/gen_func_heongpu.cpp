#include "fheco/code_gen/gen_func_heongpu.hpp"
#include "fheco/code_gen/constants_heongpu.hpp"
#include "fheco/param_select/enc_params.hpp"
#include "fheco/ckks/ckks_params.hpp"
#include "fheco/ir/common.hpp"
#include "fheco/ir/func.hpp"
#include "fheco/passes/prepare_code_gen.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <set>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

namespace fheco::code_gen::heongpu
{

namespace
{

string reference_name(size_t term_id)
{
  return "ref_" + to_string(term_id);
}

bool can_generate_primitive_reference(const shared_ptr<ir::Func> &func)
{
  unordered_set<size_t> supported;
  for (const auto &input : func->data_flow().inputs_info())
    if (input.first->type() == ir::Term::Type::cipher)
      supported.insert(input.first->id());
  for (const auto &constant : func->data_flow().constants_info())
    supported.insert(constant.first->id());

  for (const auto *term : func->get_top_sorted_terms())
  {
    if (!term->is_operation())
      continue;

    const auto type = term->op_code().type();
    const auto required_operands = type == ir::OpCode::Type::add ||
      type == ir::OpCode::Type::sub || type == ir::OpCode::Type::mul ? 2 : 1;
    if (term->operands().size() < required_operands)
      return false;
    for (size_t index = 0; index < required_operands; ++index)
      if (!supported.count(term->operands()[index]->id()))
        return false;

    switch (type)
    {
      case ir::OpCode::Type::encrypt:
      case ir::OpCode::Type::add:
      case ir::OpCode::Type::sub:
      case ir::OpCode::Type::negate:
      case ir::OpCode::Type::rotate:
      case ir::OpCode::Type::square:
      case ir::OpCode::Type::mul:
      case ir::OpCode::Type::mod_switch:
      case ir::OpCode::Type::relin:
      case ir::OpCode::Type::SumVec:
      case ir::OpCode::Type::rescale:
      case ir::OpCode::Type::bootstrap:
        supported.insert(term->id());
        break;
      default:
        return false;
    }
  }

  for (const auto &output : func->data_flow().outputs_info())
    if (output.first->type() != ir::Term::Type::cipher || !supported.count(output.first->id()))
      return false;
  return true;
}

void gen_primitive_reference_cu(const shared_ptr<ir::Func> &func, ostream &os, int scheme)
{
  unordered_map<size_t, string> references;
  for (const auto &input : func->data_flow().inputs_info())
  {
    if (input.first->type() != ir::Term::Type::cipher)
      continue;
    const auto id = input.first->id();
    const auto ref = reference_name(id);
    references.emplace(id, ref);
    if (scheme == 0) {
      os << "    std::vector<double> " << ref << "(slot_count);\n";
      os << "    for (std::size_t i = 0; i < slot_count; ++i) " << ref << "[i] = static_cast<double>(values[i]);\n";
    } else {
      os << "    std::vector<double> " << ref << " = values;\n";
    }
  }

  for (const auto &constant : func->data_flow().constants_info())
  {
    const auto id = constant.first->id();
    const auto ref = reference_name(id);
    references.emplace(id, ref);
    os << "    std::vector<double> " << ref << "(slot_count, 0.0);\n";
    if (constant.second.is_scalar_)
    {
      os << "    for (std::size_t i = 0; i < slot_count; ++i) " << ref << "[i] = "
         << constant.second.val_[0] << ";\n";
    }
    else
    {
      const auto &vec = constant.second.val_;
      size_t nz = 0;
      for (double v : vec)
      {
        if (v != 0.0) ++nz;
      }
      if (nz * 4 < vec.size())
      {
        for (size_t index = 0; index < vec.size(); ++index)
        {
          if (vec[index] != 0.0)
            os << "    " << ref << "[" << index << "] = " << vec[index] << ";\n";
        }
      }
      else
      {
        os << "    {\n";
        os << "        std::vector<double> tmp_c = {";
        for (size_t index = 0; index < constant.second.val_.size(); ++index)
        {
          if (index) os << ", ";
          os << constant.second.val_[index];
        }
        os << "};\n";
        os << "        for (std::size_t i = 0; i < tmp_c.size() && i < slot_count; ++i) " << ref << "[i] = tmp_c[i];\n";
        os << "    }\n";
      }
    }
  }

  for (const auto *term : func->get_top_sorted_terms())
  {
    if (!term->is_operation())
      continue;

    const auto ref = reference_name(term->id());
    const auto operand = references.at(term->operands()[0]->id());
    references.emplace(term->id(), ref);
    const auto type = term->op_code().type();
    if (type == ir::OpCode::Type::encrypt || type == ir::OpCode::Type::mod_switch ||
        type == ir::OpCode::Type::relin || type == ir::OpCode::Type::rescale ||
        type == ir::OpCode::Type::bootstrap)
    {
      os << "    std::vector<double> " << ref << " = " << operand << ";\n";
    }
    else if (type == ir::OpCode::Type::rotate)
    {
      int steps = term->op_code().steps();
      os << "    std::vector<double> " << ref << "(slot_count, 0.0);\n";
      os << "    for (std::size_t i = 0; i < slot_count; ++i) " << ref << "[i] = " << operand
         << "[(i + " << steps << " + slot_count) % slot_count];\n";
    }
    else if (type == ir::OpCode::Type::SumVec)
    {
      int size = term->op_code().size();
      os << "    std::vector<double> " << ref << " = " << operand << ";\n";
      for (int step = size / 2; step >= 1; step /= 2)
      {
        os << "    {\n";
        os << "        std::vector<double> next(slot_count, 0.0);\n";
        os << "        for (std::size_t i = 0; i < slot_count; ++i) next[i] = "
           << ref << "[i] + " << ref << "[(i + " << step << ") % slot_count];\n";
        os << "        " << ref << " = next;\n";
        os << "    }\n";
      }
    }
    else
    {
      os << "    std::vector<double> " << ref << "(slot_count, 0.0);\n";
      if (type == ir::OpCode::Type::negate)
      {
        os << "    for (std::size_t i = 0; i < slot_count; ++i) " << ref << "[i] = -" << operand << "[i];\n";
      }
      else if (type == ir::OpCode::Type::square)
      {
        os << "    for (std::size_t i = 0; i < slot_count; ++i) " << ref << "[i] = " << operand << "[i] * " << operand << "[i];\n";
      }
      else
      {
        const auto operand2 = references.at(term->operands()[1]->id());
        const char *op = type == ir::OpCode::Type::add ? "+" :
          type == ir::OpCode::Type::sub ? "-" : "*";
        os << "    for (std::size_t i = 0; i < slot_count; ++i) " << ref << "[i] = " << operand
           << "[i] " << op << " " << operand2 << "[i];\n";
      }
    }
  }

  os << "    std::unordered_map<std::string, std::vector<double>> expectedOutputs;\n";
  for (const auto &output : func->data_flow().outputs_info())
  {
    const auto &ref = references.at(output.first->id());
    for (const auto &label : output.second.labels_)
      os << "    expectedOutputs[\"" << label << "\"] = " << ref << ";\n";
  }
}

} // namespace

void gen_func_heongpu(
  const shared_ptr<ir::Func> &func,
  const unordered_set<int> &rotation_steps,
  ostream &os,
  string_view func_name,
  int scheme,
  const param_select::EncParams* bfv_params,
  const ckks::CKKSParams* ckks_params)
{
  passes::prepare_code_gen(func);
  
  os << header_includes << "\n";
  os << source_includes << "\n";
  os << source_usings << "\n";

  string scheme_str = (scheme == 0) ? "heongpu::Scheme::BFV" : "heongpu::Scheme::CKKS";
  os << "constexpr auto SCHEME = " << scheme_str << ";\n\n";

  // Generate rotation steps getter
  os << "std::vector<int> getRotationSteps() {\n";
  os << "    return {";
  bool first = true;
  for (int step : rotation_steps) {
    if (!first) os << ", ";
    os << step;
    first = false;
  }
  os << "};\n}\n\n";

  // Generate the main computation function signature
  os << "void " << func_name << "(\n";
  os << "    std::unordered_map<std::string, heongpu::Ciphertext<SCHEME>>& encryptedInputs,\n";
  os << "    std::unordered_map<std::string, heongpu::Plaintext<SCHEME>>& encodedInputs,\n";
  os << "    std::unordered_map<std::string, heongpu::Ciphertext<SCHEME>>& encryptedOutputs,\n";
  os << "    std::unordered_map<std::string, heongpu::Plaintext<SCHEME>>& encodedOutputs,\n";
  os << "    heongpu::HEContext<SCHEME>& context,\n";
  os << "    heongpu::HEEncoder<SCHEME>& encoder,\n";
  os << "    heongpu::HEEncryptor<SCHEME>& encryptor,\n";
  os << "    heongpu::HEArithmeticOperator<SCHEME>& ops,\n";
  os << "    heongpu::Relinkey<SCHEME>& relin_key,\n";
  os << "    heongpu::Galoiskey<SCHEME>& galois_keys,\n";
  os << "    double scale = 1.0) {\n\n";

  TermsCtxtObjectsInfo terms_ctxt_objects_info;
  gen_input_terms(func->data_flow().inputs_info(), os, terms_ctxt_objects_info, scheme);
  gen_const_terms(func->data_flow().constants_info(), func->clear_data_evaluator().signedness(), os, scheme);
  
  os << "    // FHE Operations\n";
  for (auto term : func->get_top_sorted_terms())
  {
    if (!term->is_operation()) continue;
    gen_term_eval(term, terms_ctxt_objects_info, os, scheme);
  }

  gen_output_terms(func->data_flow().outputs_info(), terms_ctxt_objects_info, os, scheme);

  os << "}\n\n";

  // Collect unique cipher input labels
  std::set<std::string> cipher_input_labels;
  for (const auto &input_info : func->data_flow().inputs_info())
  {
    if (input_info.first->type() == ir::Term::Type::cipher)
      cipher_input_labels.insert(input_info.second.label_);
  }

  // Collect unique plain input labels
  std::set<std::string> plain_input_labels;
  for (const auto &input_info : func->data_flow().inputs_info())
  {
    if (input_info.first->type() == ir::Term::Type::plain)
      plain_input_labels.insert(input_info.second.label_);
  }

  os << "struct GpuMemSampler {\n";
  os << "    std::atomic<bool> running{false};\n";
  os << "    std::atomic<size_t> peak_used{0};\n";
  os << "    std::thread th;\n\n";
  os << "    void start() {\n";
  os << "        peak_used = 0;\n";
  os << "        running = true;\n";
  os << "        th = std::thread([this]() {\n";
  os << "            while (running.load()) {\n";
  os << "                size_t used = heongpu::MemoryPool::instance()\n";
  os << "                                  .get_current_device_pool_memory_usage();\n";
  os << "                size_t prev = peak_used.load();\n";
  os << "                while (used > prev &&\n";
  os << "                       !peak_used.compare_exchange_weak(prev, used)) {}\n";
  os << "                std::this_thread::sleep_for(std::chrono::microseconds(100));\n";
  os << "            }\n";
  os << "        });\n";
  os << "    }\n\n";
  os << "    void stop() {\n";
  os << "        running = false;\n";
  os << "        if (th.joinable()) th.join();\n";
  os << "    }\n";
  os << "};\n\n";

  // Generate main()
  os << "int main(int argc, char **argv) {\n";
  os << "    int repetitions = 1;\n";
  os << "    for (int i = 1; i < argc; ++i) {\n";
  os << "        std::string arg = argv[i];\n";
  os << "        if ((arg == \"-repetitions\" || arg == \"--repetitions\") && i + 1 < argc) {\n";
  os << "            repetitions = std::max(1, std::atoi(argv[++i]));\n";
  os << "        }\n";
  os << "    }\n\n";
  os << "    GpuMemSampler sampler;\n";
  os << "    sampler.start();\n\n";

  if (scheme == 0) { // BFV
    if (bfv_params && !bfv_params->coeff_mod_bit_sizes().empty()) {
        os << "    int poly_modulus_degree = " << bfv_params->poly_mod_degree() << ";\n";
        os << "    std::vector<int> q_bits = {";
        auto sizes = bfv_params->coeff_mod_bit_sizes();
        for (size_t i = 0; i < sizes.size() - 1; ++i) {
            if (i > 0) os << ", ";
            os << sizes[i];
        }
        os << "};\n";
        os << "    std::vector<int> p_bits = {" << sizes.back() << "};\n";
        if (bfv_params->poly_mod_degree() >= 16384) {
            os << "    int plain_modulus = 786433;\n";
        } else {
            os << "    int plain_modulus = 1032193;\n";
        }
    } else {
        os << "    int poly_modulus_degree = 16384;\n";
        os << "    std::vector<int> q_bits = {60, 40, 40, 60};\n";
        os << "    std::vector<int> p_bits = {60};\n";
        os << "    int plain_modulus = 786433;\n";
    }
  } else { // CKKS
    if (ckks_params) {
        os << "    int poly_modulus_degree = " << ckks_params->poly_modulus_degree() << ";\n";
        os << "    std::vector<int> q_bits = {";
        for (size_t i = 0; i < ckks_params->log_q.size(); ++i) {
            if (i > 0) os << ", ";
            os << ckks_params->log_q[i];
        }
        os << "};\n";
        os << "    std::vector<int> p_bits = {";
        for (size_t i = 0; i < ckks_params->log_p.size(); ++i) {
            if (i > 0) os << ", ";
            os << std::max(50, ckks_params->log_p[i]);
        }
        os << "};\n";
        os << "    double scale = pow(2.0, " << ckks_params->log_scale << ");\n";
    } else {
        os << "    int poly_modulus_degree = 16384;\n";
        os << "    std::vector<int> q_bits = {60, 40, 40, 40, 40, 40, 40, 40};\n";
        os << "    std::vector<int> p_bits = {60};\n";
        os << "    double scale = pow(2.0, 40);\n";
    }
  }

  os << "    heongpu::HEContext<SCHEME> context = heongpu::GenHEContext<SCHEME>();\n";
  os << "    context->set_poly_modulus_degree(poly_modulus_degree);\n";
  os << "    context->set_coeff_modulus_bit_sizes(q_bits, p_bits);\n";
  if (scheme == 0) os << "    context->set_plain_modulus(plain_modulus);\n";
  os << "    context->generate();\n\n";

  os << "    heongpu::HEKeyGenerator<SCHEME> keygen(context);\n";
  os << "    heongpu::Secretkey<SCHEME> secret_key(context);\n";
  os << "    keygen.generate_secret_key(secret_key);\n";
  os << "    heongpu::Publickey<SCHEME> public_key(context);\n";
  os << "    keygen.generate_public_key(public_key, secret_key);\n";
  os << "    heongpu::Relinkey<SCHEME> relin_key(context);\n";
  os << "    keygen.generate_relin_key(relin_key, secret_key);\n\n";

  os << "    auto rotations = getRotationSteps();\n\n";

  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_keys_start = std::chrono::high_resolution_clock::now();\n";
  os << "    heongpu::Galoiskey<SCHEME> galois_keys(context, rotations);\n";
  os << "    if (!rotations.empty()) {\n";
  os << "        keygen.generate_galois_key(galois_keys, secret_key);\n";
  os << "    }\n";
  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_keys_end = std::chrono::high_resolution_clock::now();\n";
  os << "    double keys_elapsed = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_keys_end - t_keys_start).count();\n\n";

  os << "    std::ostringstream key_stream(std::ios::binary);\n";
  os << "    galois_keys.save(key_stream);\n";
  os << "    size_t galois_keys_total_size = key_stream.str().size();\n";
  os << "    std::cout << \"rotation_keys_size_(MB): \"\n";
  os << "              << galois_keys_total_size / (1024.0 * 1024.0) << \"\\n\\n\";\n\n";

  os << "    heongpu::HEEncoder<SCHEME> encoder(context);\n";
  os << "    heongpu::HEEncryptor<SCHEME> encryptor(context, public_key);\n";
  os << "    heongpu::HEDecryptor<SCHEME> decryptor(context, secret_key);\n";
  os << "    heongpu::HEArithmeticOperator<SCHEME> ops(context, encoder);\n\n";

  os << "    std::unordered_map<std::string, heongpu::Ciphertext<SCHEME>> encryptedInputs;\n";
  os << "    std::unordered_map<std::string, heongpu::Plaintext<SCHEME>> encodedInputs;\n";
  os << "    std::unordered_map<std::string, heongpu::Ciphertext<SCHEME>> encryptedOutputs;\n";
  os << "    std::unordered_map<std::string, heongpu::Plaintext<SCHEME>> encodedOutputs;\n\n";

  os << "    std::size_t slot_count = encoder.slot_count();\n";
  if (scheme == 0) {
      os << "    std::vector<uint64_t> values(slot_count);\n";
      os << "    for (std::size_t i = 0; i < slot_count; i++) values[i] = static_cast<uint64_t>(i);\n";
  } else {
      os << "    std::vector<double> values(slot_count);\n";
      os << "    for (std::size_t i = 0; i < slot_count; i++) values[i] = static_cast<double>((i % 17) + 1) / 17.0;\n";
  }

  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_enc_start = std::chrono::high_resolution_clock::now();\n";
  for (const auto &label : cipher_input_labels) {
    os << "    {\n";
    os << "        heongpu::Plaintext<SCHEME> pt(context);\n";
    if (scheme == 0) os << "        encoder.encode(pt, values);\n";
    else os << "        encoder.encode(pt, values, scale);\n";
    os << "        heongpu::Ciphertext<SCHEME> ct(context);\n";
    os << "        encryptor.encrypt(ct, pt);\n";
    os << "        encryptedInputs[\"" << label << "\"] = ct;\n";
    os << "    }\n";
  }
  for (const auto &label : plain_input_labels) {
    os << "    {\n";
    os << "        heongpu::Plaintext<SCHEME> pt(context);\n";
    if (scheme == 0) os << "        encoder.encode(pt, values);\n";
    else os << "        encoder.encode(pt, values, scale);\n";
    os << "        encodedInputs[\"" << label << "\"] = pt;\n";
    os << "    }\n";
  }
  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_enc_end = std::chrono::high_resolution_clock::now();\n";
  os << "    double encrypt_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_enc_end - t_enc_start).count();\n\n";

  bool can_ref = can_generate_primitive_reference(func);
  if (can_ref) {
    gen_primitive_reference_cu(func, os, scheme);
    os << "    bool precision_checked = true;\n";
  } else {
    os << "    std::unordered_map<std::string, std::vector<double>> expectedOutputs;\n";
    os << "    bool precision_checked = false;\n";
  }

  os << "\n    cudaDeviceSynchronize();\n";
  os << "    auto t_start = std::chrono::high_resolution_clock::now();\n";
  os << "    for (int rep = 0; rep < repetitions; ++rep) {\n";
  if (scheme == 0) {
    os << "        " << func_name << "(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, context, encoder, encryptor, ops, relin_key, galois_keys);\n";
  } else {
    os << "        " << func_name << "(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, context, encoder, encryptor, ops, relin_key, galois_keys, scale);\n";
  }
  os << "    }\n";
  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_end = std::chrono::high_resolution_clock::now();\n";
  os << "    double elapsed = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_end - t_start).count();\n";
  os << "    double compute_ms = elapsed / repetitions;\n\n";

  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_dec_start = std::chrono::high_resolution_clock::now();\n";
  os << "    double max_abs_error = 0.0;\n";
  os << "    for (auto& [name, ct] : encryptedOutputs) {\n";
  os << "        heongpu::Plaintext<SCHEME> pt_out(context);\n";
  os << "        decryptor.decrypt(pt_out, ct);\n\n";
  if (scheme == 0) {
      os << "        std::vector<uint64_t> out;\n";
  } else {
      os << "        std::vector<double> out;\n";
  }
  os << "        encoder.decode(out, pt_out);\n\n";
  os << "        std::cout << name << \": [\" << out[0] << \", \" << out[1] << \", \" << out[2] << \", ...]\\n\";\n";
  os << "        if (precision_checked && expectedOutputs.count(name)) {\n";
  os << "            for (std::size_t i = 0; i < out.size() && i < expectedOutputs[name].size(); ++i) {\n";
  os << "                double diff = std::abs(static_cast<double>(out[i]) - expectedOutputs[name][i]);\n";
  os << "                if (diff > max_abs_error) max_abs_error = diff;\n";
  os << "            }\n";
  os << "        }\n";
  if (scheme == 0) {
      os << "        int remaining_noise_budget = decryptor.remainder_noise_budget(ct);\n";
      os << "        std::cout << \"Remaining_noise_budget: \" << remaining_noise_budget << \" \\n\" << std::flush;\n";
  }
  os << "    }\n";
  os << "    cudaDeviceSynchronize();\n";
  os << "    auto t_dec_end = std::chrono::high_resolution_clock::now();\n";
  os << "    double decrypt_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_dec_end - t_dec_start).count();\n\n";

  os << "    std::cout << \"circuit_execution_time_(ms): \" << compute_ms << \"\\n\";\n";
  os << "    std::cout << \"galois_keys_generation_time_(ms): \" << keys_elapsed << \"\\n\";\n";
  os << "    std::cout << \"total_execution_time_(ms): \" << (compute_ms + keys_elapsed) << \"\\n\";\n";

  os << "    int level_start = (SCHEME == heongpu::Scheme::CKKS) ? static_cast<int>(q_bits.size()) - 1 : 0;\n";
  os << "    int level_end = -1;\n";
 os << "    for (auto& [name, ct] : encryptedOutputs) {\n";
if (scheme == 1)
  os << "        level_end = ct.level();\n";
else
  os << "        level_end = 0;\n";
  os << "        break;\n";
  os << "    }\n";
  os << "    std::string max_err_json = precision_checked ? std::to_string(max_abs_error) : \"null\";\n";
  os << "    std::cout << \"BENCHMARK_METRICS {\\\"repetitions\\\":\" << repetitions\n";
  os << "              << \",\\\"encrypt_ms\\\":\" << std::fixed << std::setprecision(3) << encrypt_ms\n";
  os << "              << \",\\\"compute_ms\\\":\" << compute_ms\n";
  os << "              << \",\\\"decrypt_ms\\\":\" << decrypt_ms\n";
  os << "              << \",\\\"galois_keys\\\":\" << rotations.size()\n";
  os << "              << \",\\\"bootstrap_count\\\":0\"\n";
  os << "              << \",\\\"level_start\\\":\" << level_start\n";
  os << "              << \",\\\"level_end\\\":\" << level_end\n";
  os << "              << \",\\\"max_abs_error\\\":\" << max_err_json\n";
  os << "              << \",\\\"precision_checked\\\":\" << (precision_checked ? \"true\" : \"false\")\n";
  os << "              << \"}\\n\";\n\n";

  os << "    cudaDeviceSynchronize();\n";
  os << "    sampler.stop();\n";
  os << "    std::cout << \"peak_gpu_memory_(MB): \"\n";
  os << "              << sampler.peak_used.load() / (1024.0 * 1024.0) << \"\\n\";\n\n";

  os << "    return 0;\n";
  os << "}\n";
}

void gen_cipher_var_id(std::size_t term_id, std::ostream &os) {
  os << "c" << term_id;
}

void gen_plain_var_id(std::size_t term_id, std::ostream &os) {
  os << "p" << term_id;
}

void gen_input_terms(
  const ir::InputTermsInfo &input_terms_info, std::ostream &os, TermsCtxtObjectsInfo &terms_ctxt_objects_info, int scheme)
{
  std::set<std::string> seen_cipher_labels;

  for (const auto &input_info : input_terms_info)
  {
    auto term = input_info.first;
    auto object_id = term->id();
    
    if (term->type() == ir::Term::Type::cipher)
    {
      terms_ctxt_objects_info.emplace(term->id(), CtxtObjectInfo{object_id, term->parents().size()});
      
      const auto &label = input_info.second.label_;
      if (seen_cipher_labels.find(label) == seen_cipher_labels.end()) {
        seen_cipher_labels.insert(label);
        os << "    // ";
        gen_cipher_var_id(object_id, os);
        os << " is a REFERENCE to the live ciphertext in the map (we mutate it in place).\n";
        os << "    heongpu::Ciphertext<SCHEME>& ";
        gen_cipher_var_id(object_id, os);
        os << " = encryptedInputs.at(\"" << label << "\");\n";
      } else {
        os << "    // ";
        gen_cipher_var_id(object_id, os);
        os << " is an independent COPY, so rotating it does not also mutate the original.\n";
        os << "    heongpu::Ciphertext<SCHEME> ";
        gen_cipher_var_id(object_id, os);
        os << " = encryptedInputs.at(\"" << label << "\");\n";
      }
    }
    else
    {
      os << "    heongpu::Plaintext<SCHEME>& ";
      gen_plain_var_id(object_id, os);
      os << " = encodedInputs.at(\"" << input_info.second.label_ << "\");\n";
    }
  }
}

void gen_const_terms(
  const ir::ConstTermsValues &const_terms_info, bool signedness, std::ostream &os, int scheme)
{
  if (const_terms_info.empty()) return;
  
  os << "    std::size_t slot_count = encoder.slot_count();\n";
  for (const auto &const_info : const_terms_info)
  {
    auto term = const_info.first;
    auto object_id = term->id();
    
    os << "    heongpu::Plaintext<SCHEME> ";
    gen_plain_var_id(object_id, os);
    os << "(context);\n";
    
    if (scheme == 0) { // BFV
      if (const_info.second.is_scalar_) {
        os << "    {\n";
        os << "        std::vector<uint64_t> vals(slot_count, " << static_cast<uint64_t>(const_info.second.val_[0]) << "ULL);\n";
        os << "        encoder.encode(";
        gen_plain_var_id(object_id, os);
        os << ", vals);\n";
        os << "    }\n";
      } else {
        const auto &vec = const_info.second.val_;
        size_t nz = 0;
        for (double v : vec) if (v != 0.0) ++nz;
        if (nz * 4 < vec.size()) {
          os << "    {\n";
          os << "        std::vector<uint64_t> vals(slot_count, 0ULL);\n";
          for (size_t i = 0; i < vec.size(); ++i) {
            if (vec[i] != 0.0) {
              os << "        vals[" << i << "] = " << static_cast<uint64_t>(vec[i]) << "ULL;\n";
            }
          }
          os << "        encoder.encode(";
          gen_plain_var_id(object_id, os);
          os << ", vals);\n";
          os << "    }\n";
        } else {
          os << "    {\n";
          os << "        std::vector<uint64_t> vals = {";
          for (size_t i = 0; i < vec.size(); ++i) {
            if (i > 0) os << ", ";
            os << static_cast<uint64_t>(vec[i]) << "ULL";
          }
          os << "};\n";
          os << "        vals.resize(slot_count, 0ULL);\n";
          os << "        encoder.encode(";
          gen_plain_var_id(object_id, os);
          os << ", vals);\n";
          os << "    }\n";
        }
      }
    } else { // CKKS
      if (const_info.second.is_scalar_) {
        os << "    {\n";
        os << "        std::vector<double> vals(slot_count, " << const_info.second.val_[0] << ");\n";
        os << "        encoder.encode(";
        gen_plain_var_id(object_id, os);
        os << ", vals, scale);\n";
        os << "    }\n";
      } else {
        const auto &vec = const_info.second.val_;
        size_t nz = 0;
        for (double v : vec) if (v != 0.0) ++nz;
        if (nz * 4 < vec.size()) {
          os << "    {\n";
          os << "        std::vector<double> vals(slot_count, 0.0);\n";
          for (size_t i = 0; i < vec.size(); ++i) {
            if (vec[i] != 0.0) {
              os << "        vals[" << i << "] = " << vec[i] << ";\n";
            }
          }
          os << "        encoder.encode(";
          gen_plain_var_id(object_id, os);
          os << ", vals, scale);\n";
          os << "    }\n";
        } else {
          os << "    {\n";
          os << "        std::vector<double> vals = {";
          for (size_t i = 0; i < vec.size(); ++i) {
            if (i > 0) os << ", ";
            os << vec[i];
          }
          os << "};\n";
          os << "        vals.resize(slot_count, 0.0);\n";
          os << "        encoder.encode(";
          gen_plain_var_id(object_id, os);
          os << ", vals, scale);\n";
          os << "    }\n";
        }
      }
    }
  }
}

void gen_sum_vec(
  const ir::Term *term, const std::vector<std::size_t> &operands_ids, TermsCtxtObjectsInfo &terms_ctxt_objects_info,
  std::ostream &os, int scheme)
{
  auto term_object_id = terms_ctxt_objects_info.at(term->id()).id_;
  if (term_object_id != operands_ids[0]) {
      os << "    ";
      gen_cipher_var_id(term_object_id, os);
      os << " = ";
      gen_cipher_var_id(operands_ids[0], os);
      os << ";\n";
  }
  int size = term->op_code().size();
  os << "    // SumVec reduction (size=" << size << ")\n";
  int step = size / 2;
  while (step >= 1) {
      os << "    {\n";
      os << "        heongpu::Ciphertext<SCHEME> temp_rot = ";
      gen_cipher_var_id(term_object_id, os);
      os << ";\n";
      os << "        ops.rotate_rows_inplace(temp_rot, galois_keys, " << step << ");\n";
      os << "        ops.add_inplace(";
      gen_cipher_var_id(term_object_id, os);
      os << ", temp_rot);\n";
      os << "    }\n";
      step /= 2;
  }
}

void gen_term_eval(
  const ir::Term *term, TermsCtxtObjectsInfo &terms_ctxt_objects_info, std::ostream &os, int scheme)
{
  static std::unordered_set<size_t> rescaled_terms;
  if (terms_ctxt_objects_info.empty()) {
    rescaled_terms.clear();
  }

  auto term_object_id = term->id();
  std::vector<size_t> operands_ctxt_objects_ids(term->operands().size());
  std::unordered_map<size_t, size_t> operands_multip;

  for (size_t i = 0; i < operands_ctxt_objects_ids.size(); ++i)
  {
    auto operand = term->operands()[i];
    if (operand->type() != ir::Term::Type::cipher) continue;

    auto multip = ++operands_multip[operand->id()];
    auto operand_object_info_it = terms_ctxt_objects_info.find(operand->id());
    
    if (operand_object_info_it == terms_ctxt_objects_info.end())
    {
      operands_ctxt_objects_ids[i] = term_object_id;
      continue;
    }
    auto &operand_object_info = operand_object_info_it->second;
    operands_ctxt_objects_ids[i] = operand_object_info.id_;
    
    if (operand->type() == ir::Term::Type::plain || multip > 1) continue;
    
    --operand_object_info.dep_count_;
    if (term_object_id == term->id() && operand_object_info.dep_count_ == 0)
    {
      term_object_id = operands_ctxt_objects_ids[i];
      terms_ctxt_objects_info.erase(operand_object_info_it);
    }
  }

  if (term_object_id == term->id())
  {
    for (auto it = terms_ctxt_objects_info.begin(); it != terms_ctxt_objects_info.end(); ++it)
    {
      if (it->second.dep_count_ == 0)
      {
        term_object_id = it->second.id_;
        terms_ctxt_objects_info.erase(it);
        break;
      }
    }
  }
  
  auto dep_count = term->parents().size();
  terms_ctxt_objects_info.emplace(term->id(), CtxtObjectInfo{term_object_id, dep_count});

  if (term_object_id == term->id())
  {
    os << "    heongpu::Ciphertext<SCHEME> ";
    gen_cipher_var_id(term_object_id, os);
    os << "(context);\n";
  }

  vector<ir::Term::Type> operands_types;
  for (auto op : term->operands()) operands_types.push_back(op->type());

  if (term->op_code() == ir::OpCode::encrypt)
  {
    os << "    encryptor.encrypt(";
    gen_cipher_var_id(term_object_id, os);
    os << ", ";
    gen_plain_var_id(term->operands()[0]->id(), os);
    os << ");\n";
  }
  else if (term->op_code().type() == ir::OpCode::Type::rotate)
  {
    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    os << "    ops.rotate_rows_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ", galois_keys, " << term->op_code().generators()[0] << ");\n";
  }
  else if (term->op_code().type() == ir::OpCode::Type::SumVec)
  {
    gen_sum_vec(term, operands_ctxt_objects_ids, terms_ctxt_objects_info, os, scheme);
  }
  else if (term->op_code().type() == ir::OpCode::Type::square)
  {
    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    os << "    ops.multiply_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ", ";
    gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
    os << ");\n";
    os << "    ops.relinearize_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ", relin_key);\n";
    if (scheme == 1) {
        os << "    ops.rescale_inplace(";
        gen_cipher_var_id(term_object_id, os);
        os << ");\n";
        rescaled_terms.insert(term->id());
    }
  }
  else if (term->op_code().type() == ir::OpCode::Type::relin)
  {
    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    os << "    ops.relinearize_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ", relin_key);\n";
    if (scheme == 1) {
        os << "    ops.rescale_inplace(";
        gen_cipher_var_id(term_object_id, os);
        os << ");\n";
        rescaled_terms.insert(term->id());
    }
  }
  else if (term->op_code().type() == ir::OpCode::Type::rescale)
  {
    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    if (!rescaled_terms.count(term->operands()[0]->id())) {
        os << "    ops.rescale_inplace(";
        gen_cipher_var_id(term_object_id, os);
        os << ");\n";
    }
    rescaled_terms.insert(term->id());
  }
  else if (term->op_code().type() == ir::OpCode::Type::mod_switch)
  {
    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    os << "    ops.mod_switch_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ");\n";
  }
  else if (term->op_code().type() == ir::OpCode::Type::negate)
  {
    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    os << "    ops.negate_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ");\n";
  }
  else
  {
    auto op_type = ir::OpType{term->op_code().type(), std::move(operands_types)};
    auto op_it = operation_mapping.find(op_type);
    if (op_it == operation_mapping.end()) {
        os << "    // WARNING: Unsupported op\n";
        return;
    }
    string op_name(op_it->second);

    if (term_object_id != operands_ctxt_objects_ids[0]) {
        os << "    ";
        gen_cipher_var_id(term_object_id, os);
        os << " = ";
        gen_cipher_var_id(operands_ctxt_objects_ids[0], os);
        os << ";\n";
    }
    os << "    ops." << op_name << "_inplace(";
    gen_cipher_var_id(term_object_id, os);
    os << ", ";
    
    auto operand1 = term->operands()[1];
    if (operand1->type() == ir::Term::Type::cipher) gen_cipher_var_id(operands_ctxt_objects_ids[1], os);
    else gen_plain_var_id(operand1->id(), os);
    
    os << ");\n";

    if (scheme == 1 && op_name == "multiply_plain") {
        os << "    ops.rescale_inplace(";
        gen_cipher_var_id(term_object_id, os);
        os << ");\n";
        rescaled_terms.insert(term->id());
    }
  }
}

void gen_output_terms(
  const ir::OutputTermsInfo &output_terms_info, const TermsCtxtObjectsInfo &terms_ctxt_objects_info, std::ostream &os, int scheme)
{
  os << "\n    // Store outputs\n";
  for (const auto &output_info : output_terms_info)
  {
    auto term = output_info.first;
    if (term->type() == ir::Term::Type::cipher)
    {
      auto ctxt_object_id = terms_ctxt_objects_info.at(term->id()).id_;
      for (const auto &label : output_info.second.labels_)
      {
        os << "    encryptedOutputs[\"" << label << "\"] = ";
        gen_cipher_var_id(ctxt_object_id, os);
        os << ";\n";
      }
    }
    else
    {
      for (const auto &label : output_info.second.labels_)
      {
        os << "    encodedOutputs[\"" << label << "\"] = ";
        gen_plain_var_id(term->id(), os);
        os << ";\n";
      }
    }
  }
}

} // namespace fheco::code_gen::heongpu
