#include "ufhe/seal_backend/bfv_noise_estimator.hpp"

#include "seal/seal.h"

int main()
{
  seal::EncryptionParameters parms(seal::scheme_type::bfv);
  parms.set_poly_modulus_degree(4096);
  parms.set_coeff_modulus(seal::CoeffModulus::Create(4096, {36, 36, 36}));
  parms.set_plain_modulus(seal::PlainModulus::Batching(4096, 20));
  seal::SEALContext context(parms);

  ufhe::seal_backend::BFVNoiseEstimator estimator(context);
  auto input = ufhe::seal_backend::BFVNoiseExpression::fresh();
  auto expression = ufhe::seal_backend::BFVNoiseExpression::add(input, input);
  auto estimate = estimator.BFV_noise_bound(expression);

  seal::KeyGenerator key_generator(context);
  seal::PublicKey public_key;
  key_generator.create_public_key(public_key);
  seal::Encryptor encryptor(context, public_key);
  seal::Evaluator evaluator(context);
  seal::Decryptor decryptor(context, key_generator.secret_key());
  seal::Plaintext plain("1");
  seal::Ciphertext lhs;
  seal::Ciphertext rhs;
  encryptor.encrypt(plain, lhs);
  encryptor.encrypt(plain, rhs);
  evaluator.add_inplace(lhs, rhs);

  return estimate.decryptable && estimate.remaining_noise_budget_lower_bound_bits > 0 &&
                 decryptor.invariant_noise_budget(lhs) > 0
             ? 0
             : 1;
}
