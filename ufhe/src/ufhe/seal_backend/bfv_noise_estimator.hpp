#pragma once

#include "seal/context.h"
#include "seal/plaintext.h"
#include <cstddef>
#include <cstdint>
#include <memory>

namespace ufhe
{
namespace seal_backend
{
  struct BFVPlaintextBound
  {
    std::uint64_t coefficient_bound = 0;
    std::size_t nonzero_coefficient_count = 0;
    long double coefficient_l1_norm_bound = 0.0L;

    static BFVPlaintextBound from_plaintext(const seal::Plaintext &plain, std::uint64_t plain_modulus);
  };

  enum class BFVNoiseOperation
  {
    fresh,
    negate,
    add,
    sub,
    add_plain,
    sub_plain,
    multiply_plain,
    multiply,
    relinearize,
    rotate,
    mod_switch
  };

  class BFVNoiseExpression
  {
  public:
    using Ptr = std::shared_ptr<const BFVNoiseExpression>;

    static Ptr fresh();

    static Ptr negate(Ptr operand);

    static Ptr add(Ptr lhs, Ptr rhs);

    static Ptr sub(Ptr lhs, Ptr rhs);

    static Ptr add_plain(Ptr operand, BFVPlaintextBound plain);

    static Ptr sub_plain(Ptr operand, BFVPlaintextBound plain);

    static Ptr multiply_plain(Ptr operand, BFVPlaintextBound plain);

    static Ptr multiply(Ptr lhs, Ptr rhs);

    static Ptr relinearize(Ptr operand);

    static Ptr rotate(Ptr operand);

    static Ptr mod_switch(Ptr operand);

  private:
    BFVNoiseExpression(BFVNoiseOperation operation, Ptr lhs, Ptr rhs, BFVPlaintextBound plain);

    BFVNoiseOperation operation_;
    Ptr lhs_;
    Ptr rhs_;
    BFVPlaintextBound plain_;

    friend class BFVNoiseEstimator;
  };

  struct BFVNoiseEstimate
  {
    long double invariant_noise_bound = 0.0L;
    int remaining_noise_budget_lower_bound_bits = 0;
    std::size_t ciphertext_size = 0;
    std::size_t modulus_level = 0;
    bool decryptable = false;
  };

  class BFVNoiseEstimator
  {
  public:
    explicit BFVNoiseEstimator(const seal::SEALContext &context, std::uint64_t error_coefficient_bound = 21);

    BFVNoiseEstimate BFV_noise_bound(const BFVNoiseExpression::Ptr &expression) const;

  private:
    struct State;

    State evaluate(const BFVNoiseExpression::Ptr &expression) const;

    const seal::SEALContext &context_;
    std::uint64_t error_coefficient_bound_;
  };
}
}
