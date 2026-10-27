#include "ufhe/seal_backend/bfv_noise_estimator.hpp"

#include "seal/seal.h"
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace
{
  using Expression = ufhe::seal_backend::BFVNoiseExpression::Ptr;

  struct Arguments
  {
    std::string output = "bfv_noise_bound_workloads.csv";
    int trials = 5;
  };

  struct Measurement
  {
    std::string benchmark;
    std::size_t vector_size = 0;
    std::size_t poly_modulus_degree = 0;
    int allocated_initial_noise_budget_bits = 0;
    int actual_remaining_noise_budget_bits = 0;
    ufhe::seal_backend::BFVNoiseEstimate estimate;
  };

  struct Aggregate
  {
    Measurement metadata;
    long long actual_remaining_noise_budget_bits_sum = 0;
    long long certified_remaining_noise_budget_bits_sum = 0;
    long double invariant_noise_bound_sum = 0.0L;
    bool all_certificates_decryptable = true;
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
        throw std::invalid_argument("usage: bfv_noise_bound_workloads [--output file] [--trials count]");
    }
    if (arguments.trials < 1)
      throw std::invalid_argument("trials must be positive");
    return arguments;
  }

  seal::EncryptionParameters make_parameters(const std::vector<int> &coeff_modulus_bits)
  {
    constexpr std::size_t poly_modulus_degree = 16384;
    seal::EncryptionParameters parameters(seal::scheme_type::bfv);
    parameters.set_poly_modulus_degree(poly_modulus_degree);
    parameters.set_coeff_modulus(seal::CoeffModulus::Create(poly_modulus_degree, coeff_modulus_bits));
    parameters.set_plain_modulus(seal::PlainModulus::Batching(poly_modulus_degree, 20));
    return parameters;
  }

  seal::Plaintext encode_constant(const seal::BatchEncoder &encoder, std::uint64_t value)
  {
    seal::Plaintext plain;
    encoder.encode(std::vector<std::uint64_t>(encoder.slot_count(), value), plain);
    return plain;
  }

  struct TrackedCiphertext
  {
    seal::Ciphertext ciphertext;
    Expression expression;
  };

  TrackedCiphertext encrypt_one(const seal::BatchEncoder &encoder, seal::Encryptor &encryptor)
  {
    TrackedCiphertext result;
    encryptor.encrypt(encode_constant(encoder, 1), result.ciphertext);
    result.expression = ufhe::seal_backend::BFVNoiseExpression::fresh();
    return result;
  }

  TrackedCiphertext add(TrackedCiphertext lhs, const TrackedCiphertext &rhs, seal::Evaluator &evaluator)
  {
    evaluator.add_inplace(lhs.ciphertext, rhs.ciphertext);
    lhs.expression = ufhe::seal_backend::BFVNoiseExpression::add(lhs.expression, rhs.expression);
    return lhs;
  }

  TrackedCiphertext sub(TrackedCiphertext lhs, const TrackedCiphertext &rhs, seal::Evaluator &evaluator)
  {
    evaluator.sub_inplace(lhs.ciphertext, rhs.ciphertext);
    lhs.expression = ufhe::seal_backend::BFVNoiseExpression::sub(lhs.expression, rhs.expression);
    return lhs;
  }

  TrackedCiphertext multiply(
    TrackedCiphertext lhs, const TrackedCiphertext &rhs, seal::Evaluator &evaluator, const seal::RelinKeys &relin_keys)
  {
    evaluator.multiply_inplace(lhs.ciphertext, rhs.ciphertext);
    evaluator.relinearize_inplace(lhs.ciphertext, relin_keys);
    lhs.expression = ufhe::seal_backend::BFVNoiseExpression::relinearize(
      ufhe::seal_backend::BFVNoiseExpression::multiply(lhs.expression, rhs.expression));
    return lhs;
  }

  TrackedCiphertext rotate(
    TrackedCiphertext value, int steps, seal::Evaluator &evaluator, const seal::GaloisKeys &galois_keys)
  {
    if (steps)
    {
      evaluator.rotate_rows_inplace(value.ciphertext, steps, galois_keys);
      value.expression = ufhe::seal_backend::BFVNoiseExpression::rotate(value.expression);
    }
    return value;
  }

  TrackedCiphertext multiply_scalar(
    TrackedCiphertext value, std::int64_t scalar, const seal::BatchEncoder &encoder,
    const seal::EncryptionParameters &parameters, seal::Evaluator &evaluator)
  {
    std::uint64_t modulus = parameters.plain_modulus().value();
    std::int64_t reduced = scalar % static_cast<std::int64_t>(modulus);
    if (reduced < 0)
      reduced += static_cast<std::int64_t>(modulus);
    seal::Plaintext plain = encode_constant(encoder, static_cast<std::uint64_t>(reduced));
    evaluator.multiply_plain_inplace(value.ciphertext, plain);
    value.expression = ufhe::seal_backend::BFVNoiseExpression::multiply_plain(
      value.expression,
      ufhe::seal_backend::BFVPlaintextBound::from_plaintext(plain, modulus));
    return value;
  }

  template <typename Program>
  Measurement run_pattern(
    const std::string &name, std::size_t vector_size, const std::vector<int> &rotation_steps, Program program)
  {
    auto parameters = make_parameters({50, 50, 50, 50, 50, 50, 50, 50});
    seal::SEALContext context(parameters);
    seal::KeyGenerator key_generator(context);
    seal::PublicKey public_key;
    seal::RelinKeys relin_keys;
    seal::GaloisKeys galois_keys;
    key_generator.create_public_key(public_key);
    key_generator.create_relin_keys(relin_keys);
    key_generator.create_galois_keys(rotation_steps, galois_keys);
    seal::Encryptor encryptor(context, public_key);
    seal::Evaluator evaluator(context);
    seal::Decryptor decryptor(context, key_generator.secret_key());
    seal::BatchEncoder encoder(context);
    ufhe::seal_backend::BFVNoiseEstimator estimator(context);
    TrackedCiphertext result = program(parameters, encoder, encryptor, evaluator, relin_keys, galois_keys);
    return {name, vector_size, parameters.poly_modulus_degree(),
            context.first_context_data()->total_coeff_modulus_bit_count() - parameters.plain_modulus().bit_count(),
            decryptor.invariant_noise_budget(result.ciphertext), estimator.BFV_noise_bound(result.expression)};
  }

  TrackedCiphertext linear_filter(
    const std::vector<std::pair<int, std::int64_t>> &terms, const seal::EncryptionParameters &parameters,
    const seal::BatchEncoder &encoder, seal::Encryptor &encryptor, seal::Evaluator &evaluator,
    const seal::GaloisKeys &galois_keys)
  {
    TrackedCiphertext input = encrypt_one(encoder, encryptor);
    bool first = true;
    TrackedCiphertext result;
    for (const auto &[steps, coefficient] : terms)
    {
      if (!coefficient)
        continue;
      TrackedCiphertext term = rotate(input, steps, evaluator, galois_keys);
      term = multiply_scalar(term, coefficient, encoder, parameters, evaluator);
      if (first)
      {
        result = std::move(term);
        first = false;
      }
      else
        result = add(std::move(result), term, evaluator);
    }
    return result;
  }

  Measurement run_linear_filter(
    const std::string &name, std::size_t width, const std::vector<std::pair<int, std::int64_t>> &terms)
  {
    std::vector<int> rotation_steps;
    for (const auto &[steps, coefficient] : terms)
      if (steps && coefficient)
        rotation_steps.push_back(steps);
    return run_pattern(
      name, width, rotation_steps,
      [&](const seal::EncryptionParameters &parameters, const seal::BatchEncoder &encoder, seal::Encryptor &encryptor,
          seal::Evaluator &evaluator, const seal::RelinKeys &, const seal::GaloisKeys &galois_keys) {
        return linear_filter(terms, parameters, encoder, encryptor, evaluator, galois_keys);
      });
  }

  Measurement run_square_sum(const std::string &name)
  {
    constexpr int vector_size = 64;
    return run_pattern(
      name, vector_size, {32, 16, 8, 4, 2, 1},
      [&](const seal::EncryptionParameters &, const seal::BatchEncoder &encoder, seal::Encryptor &encryptor,
          seal::Evaluator &evaluator, const seal::RelinKeys &relin_keys, const seal::GaloisKeys &galois_keys) {
        TrackedCiphertext difference = sub(encrypt_one(encoder, encryptor), encrypt_one(encoder, encryptor), evaluator);
        TrackedCiphertext result = multiply(difference, difference, evaluator, relin_keys);
        for (int step = vector_size / 2; step >= 1; step /= 2)
        {
          TrackedCiphertext rotated = rotate(result, step, evaluator, galois_keys);
          result = add(std::move(result), rotated, evaluator);
        }
        return result;
      });
  }

  void sum_vector(
    seal::Ciphertext &ciphertext, Expression &expression, int size, seal::Evaluator &evaluator,
    const seal::GaloisKeys &galois_keys)
  {
    for (int step = size / 2; step >= 1; step /= 2)
    {
      seal::Ciphertext rotated;
      evaluator.rotate_rows(ciphertext, step, galois_keys, rotated);
      evaluator.add_inplace(ciphertext, rotated);
      expression = ufhe::seal_backend::BFVNoiseExpression::add(
        expression, ufhe::seal_backend::BFVNoiseExpression::rotate(expression));
    }
  }

  Measurement run_dot_product()
  {
    constexpr int vector_size = 64;
    auto parameters = make_parameters({50, 50, 50, 50, 50, 50, 50, 50});
    seal::SEALContext context(parameters);
    seal::KeyGenerator key_generator(context);
    seal::PublicKey public_key;
    seal::GaloisKeys galois_keys;
    key_generator.create_public_key(public_key);
    std::vector<int> rotation_steps;
    for (int step = 1; step < vector_size; ++step)
      rotation_steps.push_back(step);
    key_generator.create_galois_keys(rotation_steps, galois_keys);
    seal::Encryptor encryptor(context, public_key);
    seal::Evaluator evaluator(context);
    seal::Decryptor decryptor(context, key_generator.secret_key());
    seal::BatchEncoder encoder(context);
    ufhe::seal_backend::BFVNoiseEstimator estimator(context);

    seal::Plaintext plain_one = encode_constant(encoder, 1);
    seal::Plaintext plain_zero = encode_constant(encoder, 0);
    auto public_plain_bound = ufhe::seal_backend::BFVPlaintextBound::from_plaintext(
      plain_one, parameters.plain_modulus().value());
    seal::Ciphertext input;
    seal::Ciphertext sum;
    seal::Ciphertext product;
    encryptor.encrypt(plain_one, input);
    encryptor.encrypt(plain_zero, sum);
    evaluator.multiply_plain(input, plain_one, product);

    Expression product_expression = ufhe::seal_backend::BFVNoiseExpression::multiply_plain(
      ufhe::seal_backend::BFVNoiseExpression::fresh(), public_plain_bound);
    Expression sum_expression = ufhe::seal_backend::BFVNoiseExpression::fresh();
    for (int step = 0; step < vector_size; ++step)
    {
      if (step == 0)
      {
        evaluator.add_inplace(sum, product);
        sum_expression = ufhe::seal_backend::BFVNoiseExpression::add(sum_expression, product_expression);
      }
      else
      {
        seal::Ciphertext rotated;
        evaluator.rotate_rows(product, step, galois_keys, rotated);
        evaluator.add_inplace(sum, rotated);
        sum_expression = ufhe::seal_backend::BFVNoiseExpression::add(
          sum_expression, ufhe::seal_backend::BFVNoiseExpression::rotate(product_expression));
      }
    }

    return {"dot_product", vector_size, parameters.poly_modulus_degree(),
            context.first_context_data()->total_coeff_modulus_bit_count() - parameters.plain_modulus().bit_count(),
            decryptor.invariant_noise_budget(sum),
            estimator.BFV_noise_bound(sum_expression)};
  }

  Measurement run_hamming_distance()
  {
    constexpr int vector_size = 64;
    auto parameters = make_parameters({50, 50, 50, 50, 50, 50, 50, 50});
    seal::SEALContext context(parameters);
    seal::KeyGenerator key_generator(context);
    seal::PublicKey public_key;
    seal::RelinKeys relin_keys;
    seal::GaloisKeys galois_keys;
    key_generator.create_public_key(public_key);
    key_generator.create_relin_keys(relin_keys);
    key_generator.create_galois_keys(std::vector<int>{32, 16, 8, 4, 2, 1}, galois_keys);
    seal::Encryptor encryptor(context, public_key);
    seal::Evaluator evaluator(context);
    seal::Decryptor decryptor(context, key_generator.secret_key());
    seal::BatchEncoder encoder(context);
    ufhe::seal_backend::BFVNoiseEstimator estimator(context);

    seal::Plaintext plain_one = encode_constant(encoder, 1);
    seal::Plaintext plain_two = encode_constant(encoder, 2);
    auto two_bound = ufhe::seal_backend::BFVPlaintextBound::from_plaintext(
      plain_two, parameters.plain_modulus().value());
    seal::Ciphertext left;
    seal::Ciphertext right;
    seal::Ciphertext sum;
    seal::Ciphertext product;
    encryptor.encrypt(plain_one, left);
    encryptor.encrypt(plain_one, right);
    evaluator.add(left, right, sum);
    evaluator.multiply(left, right, product);
    evaluator.relinearize_inplace(product, relin_keys);
    evaluator.multiply_plain_inplace(product, plain_two);
    evaluator.sub_inplace(sum, product);

    Expression left_expression = ufhe::seal_backend::BFVNoiseExpression::fresh();
    Expression right_expression = ufhe::seal_backend::BFVNoiseExpression::fresh();
    Expression sum_expression = ufhe::seal_backend::BFVNoiseExpression::add(left_expression, right_expression);
    Expression product_expression = ufhe::seal_backend::BFVNoiseExpression::multiply(left_expression, right_expression);
    product_expression = ufhe::seal_backend::BFVNoiseExpression::relinearize(product_expression);
    product_expression = ufhe::seal_backend::BFVNoiseExpression::multiply_plain(product_expression, two_bound);
    sum_expression = ufhe::seal_backend::BFVNoiseExpression::sub(sum_expression, product_expression);
    sum_vector(sum, sum_expression, vector_size, evaluator, galois_keys);

    return {"hamming_dist", vector_size, parameters.poly_modulus_degree(),
            context.first_context_data()->total_coeff_modulus_bit_count() - parameters.plain_modulus().bit_count(),
            decryptor.invariant_noise_budget(sum),
            estimator.BFV_noise_bound(sum_expression)};
  }

  Measurement run_matrix_multiply()
  {
    constexpr int matrix_size = 4;
    auto parameters = make_parameters({50, 50, 50, 50, 50, 50, 50, 50});
    seal::SEALContext context(parameters);
    seal::KeyGenerator key_generator(context);
    seal::PublicKey public_key;
    seal::RelinKeys relin_keys;
    seal::GaloisKeys galois_keys;
    key_generator.create_public_key(public_key);
    key_generator.create_relin_keys(relin_keys);
    key_generator.create_galois_keys(std::vector<int>{2, 1}, galois_keys);
    seal::Encryptor encryptor(context, public_key);
    seal::Evaluator evaluator(context);
    seal::Decryptor decryptor(context, key_generator.secret_key());
    seal::BatchEncoder encoder(context);
    ufhe::seal_backend::BFVNoiseEstimator estimator(context);

    seal::Plaintext plain_one = encode_constant(encoder, 1);
    seal::Ciphertext row;
    Expression row_expression;
    for (int column = 0; column < matrix_size; ++column)
    {
      seal::Ciphertext left;
      seal::Ciphertext right;
      seal::Ciphertext product;
      encryptor.encrypt(plain_one, left);
      encryptor.encrypt(plain_one, right);
      evaluator.multiply(left, right, product);
      evaluator.relinearize_inplace(product, relin_keys);
      Expression product_expression = ufhe::seal_backend::BFVNoiseExpression::relinearize(
        ufhe::seal_backend::BFVNoiseExpression::multiply(
          ufhe::seal_backend::BFVNoiseExpression::fresh(), ufhe::seal_backend::BFVNoiseExpression::fresh()));
      sum_vector(product, product_expression, matrix_size, evaluator, galois_keys);

      std::vector<std::uint64_t> mask_values(encoder.slot_count(), 0);
      mask_values[static_cast<std::size_t>(column)] = 1;
      seal::Plaintext mask;
      encoder.encode(mask_values, mask);
      evaluator.multiply_plain_inplace(product, mask);
      product_expression = ufhe::seal_backend::BFVNoiseExpression::multiply_plain(
        product_expression, ufhe::seal_backend::BFVPlaintextBound::from_plaintext(
                              mask, parameters.plain_modulus().value()));

      if (column == 0)
      {
        row = std::move(product);
        row_expression = product_expression;
      }
      else
      {
        evaluator.add_inplace(row, product);
        row_expression = ufhe::seal_backend::BFVNoiseExpression::add(row_expression, product_expression);
      }
    }

    return {"matrix_mul", matrix_size, parameters.poly_modulus_degree(),
            context.first_context_data()->total_coeff_modulus_bit_count() - parameters.plain_modulus().bit_count(),
            decryptor.invariant_noise_budget(row),
            estimator.BFV_noise_bound(row_expression)};
  }

  Measurement run_quadratic_filter(
    const std::string &name, std::size_t width, const std::vector<std::pair<int, std::int64_t>> &first_terms,
    const std::vector<std::pair<int, std::int64_t>> &second_terms)
  {
    std::vector<int> rotation_steps;
    for (const auto &[steps, coefficient] : first_terms)
      if (steps && coefficient)
        rotation_steps.push_back(steps);
    for (const auto &[steps, coefficient] : second_terms)
      if (steps && coefficient)
        rotation_steps.push_back(steps);
    return run_pattern(
      name, width, rotation_steps,
      [&](const seal::EncryptionParameters &parameters, const seal::BatchEncoder &encoder, seal::Encryptor &encryptor,
          seal::Evaluator &evaluator, const seal::RelinKeys &relin_keys, const seal::GaloisKeys &galois_keys) {
        TrackedCiphertext first = linear_filter(first_terms, parameters, encoder, encryptor, evaluator, galois_keys);
        TrackedCiphertext second = linear_filter(second_terms, parameters, encoder, encryptor, evaluator, galois_keys);
        first = multiply(first, first, evaluator, relin_keys);
        second = multiply(second, second, evaluator, relin_keys);
        return add(std::move(first), second, evaluator);
      });
  }

  Measurement run_poly_regression()
  {
    return run_pattern(
      "poly_reg", 1, {},
      [&](const seal::EncryptionParameters &, const seal::BatchEncoder &encoder, seal::Encryptor &encryptor,
          seal::Evaluator &evaluator, const seal::RelinKeys &relin_keys, const seal::GaloisKeys &) {
        TrackedCiphertext c0 = encrypt_one(encoder, encryptor);
        TrackedCiphertext c1 = encrypt_one(encoder, encryptor);
        TrackedCiphertext c2 = encrypt_one(encoder, encryptor);
        TrackedCiphertext c3 = encrypt_one(encoder, encryptor);
        TrackedCiphertext c4 = encrypt_one(encoder, encryptor);
        TrackedCiphertext squared = multiply(c0, c0, evaluator, relin_keys);
        TrackedCiphertext cubic_term = multiply(squared, c4, evaluator, relin_keys);
        TrackedCiphertext linear_term = multiply(c0, c3, evaluator, relin_keys);
        TrackedCiphertext polynomial = add(add(std::move(cubic_term), linear_term, evaluator), c2, evaluator);
        return sub(c1, polynomial, evaluator);
      });
  }

  Measurement run_linear_regression()
  {
    return run_pattern(
      "lin_reg", 1, {},
      [&](const seal::EncryptionParameters &parameters, const seal::BatchEncoder &encoder, seal::Encryptor &encryptor,
          seal::Evaluator &evaluator, const seal::RelinKeys &, const seal::GaloisKeys &) {
        TrackedCiphertext value = multiply_scalar(encrypt_one(encoder, encryptor), 5, encoder, parameters, evaluator);
        return add(std::move(value), encrypt_one(encoder, encryptor), evaluator);
      });
  }

  TrackedCiphertext condition(
    TrackedCiphertext value, TrackedCiphertext if_true, TrackedCiphertext if_false,
    const seal::EncryptionParameters &parameters, const seal::BatchEncoder &encoder, seal::Evaluator &evaluator,
    const seal::RelinKeys &relin_keys)
  {
    TrackedCiphertext true_term = multiply(value, if_true, evaluator, relin_keys);
    evaluator.negate_inplace(value.ciphertext);
    value.expression = ufhe::seal_backend::BFVNoiseExpression::negate(value.expression);
    seal::Plaintext one = encode_constant(encoder, 1);
    evaluator.add_plain_inplace(value.ciphertext, one);
    value.expression = ufhe::seal_backend::BFVNoiseExpression::add_plain(
      value.expression, ufhe::seal_backend::BFVPlaintextBound::from_plaintext(one, parameters.plain_modulus().value()));
    TrackedCiphertext false_term = multiply(value, if_false, evaluator, relin_keys);
    return add(std::move(true_term), false_term, evaluator);
  }

  Measurement run_selection(const std::string &name)
  {
    return run_pattern(
      name, 3, {},
      [&](const seal::EncryptionParameters &parameters, const seal::BatchEncoder &encoder, seal::Encryptor &encryptor,
          seal::Evaluator &evaluator, const seal::RelinKeys &relin_keys, const seal::GaloisKeys &) {
        TrackedCiphertext c12 = encrypt_one(encoder, encryptor);
        TrackedCiphertext c13 = encrypt_one(encoder, encryptor);
        TrackedCiphertext c23 = encrypt_one(encoder, encryptor);
        TrackedCiphertext o1 = encrypt_one(encoder, encryptor);
        TrackedCiphertext o2 = encrypt_one(encoder, encryptor);
        TrackedCiphertext o3 = encrypt_one(encoder, encryptor);
        TrackedCiphertext left = condition(c13, o1, o3, parameters, encoder, evaluator, relin_keys);
        TrackedCiphertext right = condition(c23, o2, o3, parameters, encoder, evaluator, relin_keys);
        return condition(c12, left, right, parameters, encoder, evaluator, relin_keys);
      });
  }

  void accumulate(Aggregate &aggregate, const Measurement &measurement)
  {
    aggregate.metadata = measurement;
    aggregate.actual_remaining_noise_budget_bits_sum += measurement.actual_remaining_noise_budget_bits;
    aggregate.certified_remaining_noise_budget_bits_sum += measurement.estimate.remaining_noise_budget_lower_bound_bits;
    aggregate.invariant_noise_bound_sum += measurement.estimate.invariant_noise_bound;
    aggregate.all_certificates_decryptable = aggregate.all_certificates_decryptable && measurement.estimate.decryptable;
  }

  void write_row(std::ofstream &csv, const Aggregate &aggregate, int trials)
  {
    int mean_actual_remaining_noise_budget_bits =
      static_cast<int>(aggregate.actual_remaining_noise_budget_bits_sum / trials);
    int mean_certified_remaining_noise_budget_bits =
      static_cast<int>(aggregate.certified_remaining_noise_budget_bits_sum / trials);
    int difference_bits = mean_actual_remaining_noise_budget_bits - mean_certified_remaining_noise_budget_bits;
    long double difference_percent_of_initial_budget =
      100.0L * static_cast<long double>(difference_bits) /
      static_cast<long double>(aggregate.metadata.allocated_initial_noise_budget_bits);
    csv << aggregate.metadata.benchmark << ',' << trials << ',' << aggregate.metadata.vector_size << ','
        << aggregate.metadata.poly_modulus_degree << ',' << aggregate.metadata.allocated_initial_noise_budget_bits << ','
        << mean_actual_remaining_noise_budget_bits << ',' << mean_certified_remaining_noise_budget_bits << ','
        << difference_bits << ',' << std::setprecision(18) << static_cast<double>(difference_percent_of_initial_budget)
        << ',' << static_cast<double>(aggregate.invariant_noise_bound_sum / trials) << ','
        << (aggregate.all_certificates_decryptable ? 1 : 0) << '\n';
  }
}

int main(int argc, char **argv)
{
  Arguments arguments = parse_arguments(argc, argv);
  std::ofstream csv(arguments.output);
  if (!csv)
    throw std::runtime_error("failed to open output CSV");

  csv << "benchmark,trials,vector_size,poly_modulus_degree,allocated_initial_noise_budget_bits,"
         "mean_actual_remaining_noise_budget_bits,mean_certified_remaining_noise_budget_bits,difference_bits,"
         "difference_percent_of_initial_budget,mean_invariant_noise_bound,all_certificates_decryptable\n";
  std::map<std::string, Aggregate> aggregates;
  for (int trial = 0; trial < arguments.trials; ++trial)
  {
    std::vector<Measurement> measurements;
    measurements.push_back(run_dot_product());
    measurements.push_back(run_hamming_distance());
    measurements.push_back(run_matrix_multiply());
    Measurement cryptonets = run_matrix_multiply();
    cryptonets.benchmark = "cryptonets";
    measurements.push_back(std::move(cryptonets));
    measurements.push_back(run_linear_regression());
    measurements.push_back(run_poly_regression());
    measurements.push_back(run_square_sum("l2_distance"));
    measurements.push_back(run_square_sum("discrete_cosin_transform"));
    measurements.push_back(run_square_sum("poly_derivative"));
    measurements.push_back(run_linear_filter(
      "box_blur", 8, {{-9, 1}, {-8, 1}, {-7, 1}, {-1, 1}, {0, 1}, {1, 1}, {7, 1}, {8, 1}, {9, 1}}));
    measurements.push_back(run_linear_filter(
      "gx_kernel", 8, {{-9, -1}, {-7, 1}, {-1, -2}, {1, 2}, {7, -1}, {9, 1}}));
    measurements.push_back(run_linear_filter(
      "gy_kernel", 8, {{-9, -1}, {-8, -2}, {-7, -1}, {7, 1}, {8, 2}, {9, 1}}));
    measurements.push_back(run_quadratic_filter(
      "roberts_cross", 8, {{0, 1}, {9, -1}}, {{1, 1}, {8, -1}}));
    measurements.push_back(run_quadratic_filter(
      "sobel", 8, {{-9, -1}, {-7, 1}, {-1, -2}, {1, 2}, {7, -1}, {9, 1}},
      {{-9, -1}, {-8, -2}, {-7, -1}, {7, 1}, {8, 2}, {9, 1}}));
    measurements.push_back(run_selection("max"));
    measurements.push_back(run_selection("sort"));
    for (const Measurement &measurement : measurements)
      accumulate(aggregates[measurement.benchmark], measurement);
  }
  for (const auto &[name, aggregate] : aggregates)
    write_row(csv, aggregate, arguments.trials);

  return 0;
}
