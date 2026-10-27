#include "ufhe/seal_backend/bfv_noise_estimator.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace
{
  constexpr long double negative_infinity = -std::numeric_limits<long double>::infinity();

  long double round_up(long double value)
  {
    return std::nextafter(value, std::numeric_limits<long double>::infinity());
  }

  long double log2_up(long double value)
  {
    if (value == 0.0L)
      return negative_infinity;
    return round_up(std::log2(value));
  }

  long double log_add(long double lhs, long double rhs)
  {
    if (lhs == negative_infinity)
      return rhs;
    if (rhs == negative_infinity)
      return lhs;
    long double high = std::max(lhs, rhs);
    long double low = std::min(lhs, rhs);
    return round_up(high + std::log2(1.0L + std::exp2(low - high)));
  }

  long double log_add(long double first, long double second, long double third)
  {
    return log_add(log_add(first, second), third);
  }

  long double log_geometric_sum(std::size_t base, std::size_t terms)
  {
    if (!terms)
      return negative_infinity;
    if (base == 1)
      return log2_up(static_cast<long double>(terms));
    long double log_base = log2_up(static_cast<long double>(base));
    long double numerator = log_base * static_cast<long double>(terms);
    long double correction = std::log2(1.0L - std::exp2(-numerator));
    long double denominator = std::log2(1.0L - std::exp2(-log_base));
    return round_up(numerator + correction - denominator);
  }
}

namespace ufhe
{
namespace seal_backend
{
  BFVPlaintextBound BFVPlaintextBound::from_plaintext(
    const seal::Plaintext &plain, std::uint64_t plain_modulus)
  {
    if (plain_modulus < 2)
      throw std::invalid_argument("plaintext modulus must be at least two");

    BFVPlaintextBound result;
    for (std::size_t index = 0; index < plain.coeff_count(); ++index)
    {
      std::uint64_t coefficient = plain[index];
      if (coefficient >= plain_modulus)
        throw std::invalid_argument("plaintext coefficient is outside the BFV plaintext domain");
      std::uint64_t centered_coefficient = std::min(coefficient, plain_modulus - coefficient);
      if (!centered_coefficient)
        continue;
      result.coefficient_bound = std::max(result.coefficient_bound, centered_coefficient);
      ++result.nonzero_coefficient_count;
      result.coefficient_l1_norm_bound = round_up(
        result.coefficient_l1_norm_bound + static_cast<long double>(centered_coefficient));
    }
    return result;
  }

  BFVNoiseExpression::BFVNoiseExpression(BFVNoiseOperation operation, Ptr lhs, Ptr rhs, BFVPlaintextBound plain)
    : operation_(operation), lhs_(std::move(lhs)), rhs_(std::move(rhs)), plain_(plain)
  {}

  BFVNoiseExpression::Ptr BFVNoiseExpression::fresh()
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::fresh, nullptr, nullptr, {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::negate(Ptr operand)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::negate, std::move(operand), nullptr, {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::add(Ptr lhs, Ptr rhs)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::add, std::move(lhs), std::move(rhs), {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::sub(Ptr lhs, Ptr rhs)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::sub, std::move(lhs), std::move(rhs), {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::add_plain(Ptr operand, BFVPlaintextBound plain)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::add_plain, std::move(operand), nullptr, plain));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::sub_plain(Ptr operand, BFVPlaintextBound plain)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::sub_plain, std::move(operand), nullptr, plain));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::multiply_plain(Ptr operand, BFVPlaintextBound plain)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::multiply_plain, std::move(operand), nullptr, plain));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::multiply(Ptr lhs, Ptr rhs)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::multiply, std::move(lhs), std::move(rhs), {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::relinearize(Ptr operand)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::relinearize, std::move(operand), nullptr, {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::rotate(Ptr operand)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::rotate, std::move(operand), nullptr, {}));
  }

  BFVNoiseExpression::Ptr BFVNoiseExpression::mod_switch(Ptr operand)
  {
    return std::shared_ptr<const BFVNoiseExpression>(
      new BFVNoiseExpression(BFVNoiseOperation::mod_switch, std::move(operand), nullptr, {}));
  }

  struct BFVNoiseEstimator::State
  {
    long double log_noise = negative_infinity;
    std::size_t ciphertext_size = 0;
    std::size_t modulus_level = 0;
  };

  BFVNoiseEstimator::BFVNoiseEstimator(const seal::SEALContext &context, std::uint64_t error_coefficient_bound)
    : context_(context), error_coefficient_bound_(error_coefficient_bound)
  {
    if (!context_.parameters_set())
      throw std::invalid_argument("encryption parameters are not set");
    if (context_.first_context_data()->parms().scheme() != seal::scheme_type::bfv)
      throw std::invalid_argument("BFV noise estimation requires BFV parameters");
    if (!error_coefficient_bound_)
      throw std::invalid_argument("error coefficient bound must be positive");
  }

  BFVNoiseEstimator::State BFVNoiseEstimator::evaluate(const BFVNoiseExpression::Ptr &expression) const
  {
    if (!expression)
      throw std::invalid_argument("noise expression is null");

    const auto &parms = context_.first_context_data()->parms();
    std::size_t n = parms.poly_modulus_degree();
    std::uint64_t t = parms.plain_modulus().value();
    std::uint64_t message_bound = t >> 1;
    std::size_t message_nonzero_count = n;

    auto log_q = [&](std::size_t level) {
      const auto &moduli = parms.coeff_modulus();
      if (level >= moduli.size())
        throw std::invalid_argument("modulus switching exhausted the BFV modulus chain");
      long double result = 0.0L;
      for (std::size_t index = 0; index + level < moduli.size(); ++index)
        result = round_up(result + log2_up(static_cast<long double>(moduli[index].value())));
      return result;
    };

    auto log_rns_key_switch_term = [&](std::size_t level) {
      const auto &moduli = parms.coeff_modulus();
      long double result = negative_infinity;
      for (std::size_t index = 0; index + level < moduli.size(); ++index)
        result = log_add(result, log2_up(static_cast<long double>(moduli[index].value())));
      return result;
    };

    auto validate_plain = [&](const BFVPlaintextBound &plain) {
      if (plain.coefficient_bound > message_bound || plain.nonzero_coefficient_count > n)
        throw std::invalid_argument("plaintext bound exceeds the centered BFV plaintext domain");
    };

    auto evaluate_binary = [&]() {
      State lhs = evaluate(expression->lhs_);
      State rhs = evaluate(expression->rhs_);
      if (lhs.modulus_level != rhs.modulus_level)
        throw std::invalid_argument("ciphertexts must be at the same modulus level");
      return std::pair<State, State>(lhs, rhs);
    };

    switch (expression->operation_)
    {
    case BFVNoiseOperation::fresh:
    {
      long double q = log_q(0);
      long double message_term = log2_up(static_cast<long double>(t)) + log2_up(static_cast<long double>(message_bound)) - q;
      long double encryption_term = log2_up(static_cast<long double>(t)) +
                                    log2_up(static_cast<long double>(error_coefficient_bound_)) +
                                    log2_up(static_cast<long double>(2 * n + 1)) - q;
      return {log_add(message_term, encryption_term), 2, 0};
    }

    case BFVNoiseOperation::negate:
      return evaluate(expression->lhs_);

    case BFVNoiseOperation::add:
    case BFVNoiseOperation::sub:
    {
      auto operands = evaluate_binary();
      return {log_add(operands.first.log_noise, operands.second.log_noise),
              std::max(operands.first.ciphertext_size, operands.second.ciphertext_size),
              operands.first.modulus_level};
    }

    case BFVNoiseOperation::add_plain:
    case BFVNoiseOperation::sub_plain:
    {
      State operand = evaluate(expression->lhs_);
      validate_plain(expression->plain_);
      return operand;
    }

    case BFVNoiseOperation::multiply_plain:
    {
      State operand = evaluate(expression->lhs_);
      validate_plain(expression->plain_);
      long double multiplier = expression->plain_.coefficient_l1_norm_bound > 0.0L
                                 ? log2_up(expression->plain_.coefficient_l1_norm_bound)
                                 : log2_up(static_cast<long double>(expression->plain_.nonzero_coefficient_count)) +
                                     log2_up(static_cast<long double>(expression->plain_.coefficient_bound));
      return {round_up(operand.log_noise + multiplier), operand.ciphertext_size, operand.modulus_level};
    }

    case BFVNoiseOperation::multiply:
    {
      auto operands = evaluate_binary();
      std::size_t lhs_j = operands.first.ciphertext_size - 1;
      std::size_t rhs_j = operands.second.ciphertext_size - 1;
      long double common_message_term = log2_up(static_cast<long double>(message_nonzero_count + n)) +
                                        log2_up(static_cast<long double>(message_bound));
      long double lhs_rounding_term = log2_up(static_cast<long double>(n)) + log2_up(static_cast<long double>(t)) - 1.0L +
                                       log_geometric_sum(n, lhs_j + 1);
      long double rhs_rounding_term = log2_up(static_cast<long double>(n)) + log2_up(static_cast<long double>(t)) - 1.0L +
                                       log_geometric_sum(n, rhs_j + 1);
      long double lhs_coefficient = log_add(common_message_term, lhs_rounding_term);
      long double rhs_coefficient = log_add(common_message_term, rhs_rounding_term);
      long double first_term = round_up(lhs_coefficient + operands.second.log_noise);
      long double second_term = round_up(rhs_coefficient + operands.first.log_noise);
      long double product_term = round_up(log2_up(3.0L) + log2_up(static_cast<long double>(n)) +
                                          operands.first.log_noise + operands.second.log_noise);
      long double final_rounding_term = log2_up(static_cast<long double>(t)) - 1.0L -
                                       log_q(operands.first.modulus_level) +
                                       log_geometric_sum(n, lhs_j + rhs_j + 1);
      return {log_add(log_add(first_term, second_term), product_term, final_rounding_term),
              operands.first.ciphertext_size + operands.second.ciphertext_size - 1,
              operands.first.modulus_level};
    }

    case BFVNoiseOperation::relinearize:
    {
      State operand = evaluate(expression->lhs_);
      if (operand.ciphertext_size < 3)
        throw std::invalid_argument("relinearization requires a ciphertext of size at least three");
      long double key_switch_term = log2_up(static_cast<long double>(t)) - log_q(operand.modulus_level) +
                                    log2_up(static_cast<long double>(operand.ciphertext_size - 2)) +
                                    log2_up(static_cast<long double>(n)) +
                                    log2_up(static_cast<long double>(error_coefficient_bound_)) +
                                    log_rns_key_switch_term(operand.modulus_level);
      return {log_add(operand.log_noise, key_switch_term), 2, operand.modulus_level};
    }

    case BFVNoiseOperation::rotate:
    {
      State operand = evaluate(expression->lhs_);
      long double key_switch_term = log2_up(static_cast<long double>(t)) - log_q(operand.modulus_level) +
                                    log2_up(static_cast<long double>(n)) +
                                    log2_up(static_cast<long double>(error_coefficient_bound_)) +
                                    log_rns_key_switch_term(operand.modulus_level);
      return {log_add(operand.log_noise, key_switch_term), 2, operand.modulus_level};
    }

    case BFVNoiseOperation::mod_switch:
    {
      State operand = evaluate(expression->lhs_);
      std::size_t next_level = operand.modulus_level + 1;
      long double rounding_term = log2_up(static_cast<long double>(t)) - 1.0L - log_q(next_level) +
                                  log_geometric_sum(n, operand.ciphertext_size);
      return {log_add(operand.log_noise, rounding_term), operand.ciphertext_size, next_level};
    }
    }

    throw std::logic_error("unsupported BFV noise operation");
  }

  BFVNoiseEstimate BFVNoiseEstimator::BFV_noise_bound(const BFVNoiseExpression::Ptr &expression) const
  {
    State state = evaluate(expression);
    auto context_data = context_.first_context_data();
    for (std::size_t level = 0; level < state.modulus_level; ++level)
    {
      context_data = context_data->next_context_data();
      if (!context_data)
        throw std::invalid_argument("modulus switching exhausted the BFV modulus chain");
    }

    int noise_bit_count_upper_bound = 0;
    if (state.log_noise != negative_infinity)
    {
      long double log_noise_norm_upper_bound = round_up(
        static_cast<long double>(context_data->total_coeff_modulus_bit_count()) + state.log_noise);
      if (!std::isfinite(log_noise_norm_upper_bound) ||
          log_noise_norm_upper_bound >= static_cast<long double>(std::numeric_limits<int>::max() - 1))
      {
        noise_bit_count_upper_bound = std::numeric_limits<int>::max();
      }
      else
      {
        noise_bit_count_upper_bound = std::max(
          1, static_cast<int>(std::floor(log_noise_norm_upper_bound)) + 1);
      }
    }

    int remaining_bits = std::max(
      0, context_data->total_coeff_modulus_bit_count() - noise_bit_count_upper_bound - 1);
    long double upper_bound = std::exp2(state.log_noise);
    return {upper_bound, remaining_bits, state.ciphertext_size, state.modulus_level, remaining_bits > 0};
  }

}
}
