#include "ufhe/seal_backend/bfv_noise_estimator.hpp"

#include "seal/seal.h"
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace
{
  struct Scenario
  {
    std::string name;
    int additions;
    int plain_additions;
    int plain_multiplications;
    int multiplications;
    int rotations;
    int modulus_switches;
  };

  struct Arguments
  {
    std::string output = "bfv_noise_upper_bound.csv";
    int trials = 5;
  };

  struct Aggregate
  {
    long long actual_remaining_noise_budget_bits_sum = 0;
    long long certified_remaining_noise_budget_bits_sum = 0;
    long double invariant_noise_bound_sum = 0.0L;
    bool all_certificates_decryptable = true;
    bool all_plaintexts_match = true;
  };

  Arguments parse_arguments(int argc, char **argv)
  {
    Arguments arguments;
    for (int index = 1; index < argc; ++index)
    {
      std::string argument = argv[index];
      if (argument == "--output" && index + 1 < argc)
        arguments.output = argv[++index];
      else if (argument == "--trials" && index + 1 < argc)
        arguments.trials = std::stoi(argv[++index]);
      else
        throw std::invalid_argument("usage: bfv_noise_upper_bound_benchmark [--output file] [--trials count]");
    }
    if (arguments.trials < 1)
      throw std::invalid_argument("trials must be positive");
    return arguments;
  }

  bool plaintext_matches(
    seal::Decryptor &decryptor, seal::BatchEncoder &encoder, const seal::Ciphertext &ciphertext,
    std::uint64_t expected, std::size_t slot_count)
  {
    seal::Plaintext decrypted;
    decryptor.decrypt(ciphertext, decrypted);
    std::vector<std::uint64_t> values;
    encoder.decode(decrypted, values);
    if (values.size() != slot_count)
      return false;
    for (std::uint64_t value : values)
    {
      if (value != expected)
        return false;
    }
    return true;
  }

  void accumulate(
    Aggregate &aggregate, int actual_budget, const ufhe::seal_backend::BFVNoiseEstimate &estimate,
    bool plaintext_is_correct)
  {
    aggregate.actual_remaining_noise_budget_bits_sum += actual_budget;
    aggregate.certified_remaining_noise_budget_bits_sum += estimate.remaining_noise_budget_lower_bound_bits;
    aggregate.invariant_noise_bound_sum += estimate.invariant_noise_bound;
    aggregate.all_certificates_decryptable = aggregate.all_certificates_decryptable && estimate.decryptable;
    aggregate.all_plaintexts_match = aggregate.all_plaintexts_match && plaintext_is_correct;
  }

  void write_row(
    std::ofstream &csv, const Scenario &scenario, int trials, int allocated_initial_noise_budget_bits,
    const Aggregate &aggregate)
  {
    int mean_actual_remaining_noise_budget_bits =
      static_cast<int>(aggregate.actual_remaining_noise_budget_bits_sum / trials);
    int mean_certified_remaining_noise_budget_bits =
      static_cast<int>(aggregate.certified_remaining_noise_budget_bits_sum / trials);
    int difference_bits = mean_actual_remaining_noise_budget_bits - mean_certified_remaining_noise_budget_bits;
    long double difference_percent_of_initial_budget =
      100.0L * static_cast<long double>(difference_bits) / allocated_initial_noise_budget_bits;
    csv << scenario.name << ',' << trials << ',' << scenario.additions << ',' << scenario.plain_additions << ','
        << scenario.plain_multiplications << ',' << scenario.multiplications << ',' << scenario.multiplications << ','
        << scenario.rotations << ',' << scenario.modulus_switches << ',' << allocated_initial_noise_budget_bits << ','
        << mean_actual_remaining_noise_budget_bits << ',' << mean_certified_remaining_noise_budget_bits << ','
        << difference_bits << ',' << std::setprecision(18) << static_cast<double>(difference_percent_of_initial_budget)
        << ',' << static_cast<double>(aggregate.invariant_noise_bound_sum / trials) << ','
        << (aggregate.all_certificates_decryptable ? 1 : 0) << ','
        << (aggregate.all_plaintexts_match ? 1 : 0) << '\n';
  }
}

int main(int argc, char **argv)
{
  Arguments arguments = parse_arguments(argc, argv);
  std::ofstream csv(arguments.output);
  if (!csv)
    throw std::runtime_error("failed to open output CSV");

  csv << "scenario,trials,add,add_plain,multiply_plain,multiply,relinearize,rotate,mod_switch,"
         "allocated_initial_noise_budget_bits,mean_actual_remaining_noise_budget_bits,"
         "mean_certified_remaining_noise_budget_bits,difference_bits,difference_percent_of_initial_budget,"
         "mean_invariant_noise_bound,all_certificates_decryptable,all_plaintexts_match\n";

  seal::EncryptionParameters parms(seal::scheme_type::bfv);
  constexpr std::size_t poly_modulus_degree = 8192;
  parms.set_poly_modulus_degree(poly_modulus_degree);
  parms.set_coeff_modulus(seal::CoeffModulus::Create(poly_modulus_degree, {50, 50, 50, 50}));
  parms.set_plain_modulus(seal::PlainModulus::Batching(poly_modulus_degree, 20));
  seal::SEALContext context(parms);
  ufhe::seal_backend::BFVNoiseEstimator estimator(context);
  int allocated_initial_noise_budget_bits =
    context.first_context_data()->total_coeff_modulus_bit_count() - parms.plain_modulus().bit_count();

  const std::vector<Scenario> scenarios = {
    {"additions", 32, 0, 0, 0, 0, 0},
    {"plain_operations", 0, 16, 8, 0, 0, 0},
    {"multiply_relinearize", 0, 0, 0, 1, 0, 0},
    {"multiply_relinearize_rotate", 4, 0, 0, 1, 4, 0},
    {"two_multiplications", 0, 0, 0, 2, 0, 0},
    {"modulus_switch", 8, 0, 0, 1, 1, 1},
  };

  for (const Scenario &scenario : scenarios)
  {
    Aggregate aggregate;
    for (int trial = 0; trial < arguments.trials; ++trial)
    {
      seal::KeyGenerator key_generator(context);
      seal::PublicKey public_key;
      seal::RelinKeys relin_keys;
      seal::GaloisKeys galois_keys;
      key_generator.create_public_key(public_key);
      key_generator.create_relin_keys(relin_keys);
      key_generator.create_galois_keys(std::vector<int>{1}, galois_keys);
      seal::Encryptor encryptor(context, public_key);
      seal::Evaluator evaluator(context);
      seal::Decryptor decryptor(context, key_generator.secret_key());
      seal::BatchEncoder encoder(context);
      std::vector<std::uint64_t> values(encoder.slot_count(), 1);
      seal::Plaintext plain_one;
      encoder.encode(values, plain_one);
      seal::Ciphertext input;
      seal::Ciphertext result;
      encryptor.encrypt(plain_one, input);
      encryptor.encrypt(plain_one, result);

      auto expression = ufhe::seal_backend::BFVNoiseExpression::fresh();
      auto fresh_input = ufhe::seal_backend::BFVNoiseExpression::fresh();
      const auto plain_bound = ufhe::seal_backend::BFVPlaintextBound::from_plaintext(
        plain_one, parms.plain_modulus().value());
      std::uint64_t expected = 1;

      for (int operation = 0; operation < scenario.additions; ++operation)
      {
        evaluator.add_inplace(result, input);
        expression = ufhe::seal_backend::BFVNoiseExpression::add(expression, fresh_input);
        expected = (expected + 1) % parms.plain_modulus().value();
      }
      for (int operation = 0; operation < scenario.plain_additions; ++operation)
      {
        evaluator.add_plain_inplace(result, plain_one);
        expression = ufhe::seal_backend::BFVNoiseExpression::add_plain(expression, plain_bound);
        expected = (expected + 1) % parms.plain_modulus().value();
      }
      for (int operation = 0; operation < scenario.plain_multiplications; ++operation)
      {
        evaluator.multiply_plain_inplace(result, plain_one);
        expression = ufhe::seal_backend::BFVNoiseExpression::multiply_plain(expression, plain_bound);
      }
      for (int operation = 0; operation < scenario.multiplications; ++operation)
      {
        evaluator.multiply_inplace(result, input);
        expression = ufhe::seal_backend::BFVNoiseExpression::multiply(expression, fresh_input);
        evaluator.relinearize_inplace(result, relin_keys);
        expression = ufhe::seal_backend::BFVNoiseExpression::relinearize(expression);
      }
      for (int operation = 0; operation < scenario.rotations; ++operation)
      {
        evaluator.rotate_rows_inplace(result, 1, galois_keys);
        expression = ufhe::seal_backend::BFVNoiseExpression::rotate(expression);
      }
      for (int operation = 0; operation < scenario.modulus_switches; ++operation)
      {
        evaluator.mod_switch_to_next_inplace(result);
        expression = ufhe::seal_backend::BFVNoiseExpression::mod_switch(expression);
      }

      auto estimate = estimator.BFV_noise_bound(expression);
      int actual_budget = decryptor.invariant_noise_budget(result);
      bool correct = plaintext_matches(decryptor, encoder, result, expected, encoder.slot_count());
      accumulate(aggregate, actual_budget, estimate, correct);
    }
    write_row(csv, scenario, arguments.trials, allocated_initial_noise_budget_bits, aggregate);
  }

  return 0;
}
