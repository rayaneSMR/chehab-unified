#include "ufhe/seal_backend/bfv_noise_estimator.hpp"

#include "seal/seal.h"
#include <cctype>
#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace
{
  struct Arguments
  {
    std::size_t poly_modulus_degree = 0;
    std::uint64_t plain_modulus = 0;
    std::vector<std::uint64_t> coeff_modulus;
    std::vector<int> coeff_modulus_bits;
  };

  struct Node
  {
    bool atom = false;
    std::string value;
    std::vector<Node> args;
  };

  struct Value
  {
    enum class Type
    {
      plain,
      cipher,
      vector
    };

    Type type = Type::plain;
    std::uint64_t plain_value = 0;
    ufhe::seal_backend::BFVNoiseExpression::Ptr cipher_expression;
    std::vector<Value> elements;
  };

  std::vector<std::string> tokenize(const std::string &input)
  {
    std::vector<std::string> tokens;
    std::string token;
    for (char character : input)
    {
      if (character == '(' || character == ')')
      {
        if (!token.empty())
        {
          tokens.push_back(std::move(token));
          token.clear();
        }
        tokens.emplace_back(1, character);
      }
      else if (std::isspace(static_cast<unsigned char>(character)))
      {
        if (!token.empty())
        {
          tokens.push_back(std::move(token));
          token.clear();
        }
      }
      else
      {
        token += character;
      }
    }
    if (!token.empty())
      tokens.push_back(std::move(token));
    return tokens;
  }

  Node parse_node(const std::vector<std::string> &tokens, std::size_t &index)
  {
    if (index >= tokens.size())
      throw std::invalid_argument("unexpected end of expression");
    if (tokens[index] != "(")
      return {true, tokens[index++], {}};
    ++index;
    if (index >= tokens.size() || tokens[index] == ")")
      throw std::invalid_argument("missing operation");
    Node result;
    result.value = tokens[index++];
    while (index < tokens.size() && tokens[index] != ")")
      result.args.push_back(parse_node(tokens, index));
    if (index >= tokens.size())
      throw std::invalid_argument("missing closing parenthesis");
    ++index;
    return result;
  }

  std::uint64_t parse_unsigned(const std::string &value, const char *name)
  {
    std::size_t consumed = 0;
    std::uint64_t result = std::stoull(value, &consumed);
    if (consumed != value.size())
      throw std::invalid_argument(std::string("invalid ") + name);
    return result;
  }

  std::vector<std::uint64_t> parse_moduli(const std::string &value)
  {
    std::vector<std::uint64_t> result;
    std::size_t begin = 0;
    while (begin < value.size())
    {
      std::size_t end = value.find(',', begin);
      std::string item = value.substr(begin, end == std::string::npos ? std::string::npos : end - begin);
      if (item.empty())
        throw std::invalid_argument("invalid coefficient modulus");
      result.push_back(parse_unsigned(item, "coefficient modulus"));
      if (end == std::string::npos)
        break;
      begin = end + 1;
    }
    return result;
  }

  std::vector<int> parse_modulus_bits(const std::string &value)
  {
    std::vector<int> result;
    std::size_t begin = 0;
    while (begin < value.size())
    {
      std::size_t end = value.find(',', begin);
      std::string item = value.substr(begin, end == std::string::npos ? std::string::npos : end - begin);
      if (item.empty())
        throw std::invalid_argument("invalid coefficient modulus bit count");
      std::size_t consumed = 0;
      int bits = std::stoi(item, &consumed);
      if (consumed != item.size() || bits < 2 || bits > 60)
        throw std::invalid_argument("invalid coefficient modulus bit count");
      result.push_back(bits);
      if (end == std::string::npos)
        break;
      begin = end + 1;
    }
    return result;
  }

  Arguments parse_arguments(int argc, char **argv)
  {
    Arguments arguments;
    for (int index = 1; index < argc; ++index)
    {
      std::string argument = argv[index];
      if (argument == "--poly-modulus-degree" && index + 1 < argc)
        arguments.poly_modulus_degree = static_cast<std::size_t>(parse_unsigned(argv[++index], "polynomial modulus degree"));
      else if (argument == "--plain-modulus" && index + 1 < argc)
        arguments.plain_modulus = parse_unsigned(argv[++index], "plaintext modulus");
      else if (argument == "--coeff-modulus" && index + 1 < argc)
        arguments.coeff_modulus = parse_moduli(argv[++index]);
      else if (argument == "--coeff-modulus-bits" && index + 1 < argc)
        arguments.coeff_modulus_bits = parse_modulus_bits(argv[++index]);
      else
        throw std::invalid_argument("usage: bfv_noise_bound_cli --poly-modulus-degree degree --plain-modulus modulus --coeff-modulus q0,q1,...");
    }
    if (!arguments.poly_modulus_degree || !arguments.plain_modulus ||
        (arguments.coeff_modulus.empty() == arguments.coeff_modulus_bits.empty()))
      throw std::invalid_argument("all SEAL BFV parameters are required");
    return arguments;
  }

  bool is_integer(const std::string &value)
  {
    if (value.empty())
      return false;
    std::size_t index = value[0] == '-' || value[0] == '+' ? 1 : 0;
    if (index == value.size())
      return false;
    for (; index < value.size(); ++index)
    {
      if (!std::isdigit(static_cast<unsigned char>(value[index])))
        return false;
    }
    return true;
  }

  std::uint64_t centered_modulo(std::int64_t value, std::uint64_t modulus)
  {
    std::int64_t remainder = value % static_cast<std::int64_t>(modulus);
    if (remainder < 0)
      remainder += static_cast<std::int64_t>(modulus);
    return static_cast<std::uint64_t>(remainder);
  }

  Value make_plain(std::uint64_t value)
  {
    Value result;
    result.type = Value::Type::plain;
    result.plain_value = value;
    return result;
  }

  Value make_cipher(ufhe::seal_backend::BFVNoiseExpression::Ptr expression)
  {
    Value result;
    result.type = Value::Type::cipher;
    result.cipher_expression = std::move(expression);
    return result;
  }

  Value make_vector(std::vector<Value> elements)
  {
    Value result;
    result.type = Value::Type::vector;
    result.elements = std::move(elements);
    return result;
  }

  std::uint64_t add_mod(std::uint64_t lhs, std::uint64_t rhs, std::uint64_t modulus)
  {
    return lhs >= modulus - rhs ? lhs - (modulus - rhs) : lhs + rhs;
  }

  std::uint64_t multiply_mod(std::uint64_t lhs, std::uint64_t rhs, std::uint64_t modulus)
  {
    std::uint64_t result = 0;
    while (rhs)
    {
      if (rhs & 1)
        result = add_mod(result, lhs, modulus);
      rhs >>= 1;
      if (rhs)
        lhs = add_mod(lhs, lhs, modulus);
    }
    return result;
  }

  class ExpressionBuilder
  {
  public:
    ExpressionBuilder(const seal::SEALContext &context, std::uint64_t plain_modulus)
      : encoder_(context), plain_modulus_(plain_modulus)
    {}

    Value build(const Node &node)
    {
      if (node.atom)
      {
        if (is_integer(node.value))
          return make_plain(centered_modulo(std::stoll(node.value), plain_modulus_));
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::fresh());
      }
      if (node.value == "Vec")
      {
        std::vector<Value> elements;
        elements.reserve(node.args.size());
        for (const Node &argument : node.args)
          elements.push_back(build(argument));
        return make_vector(std::move(elements));
      }
      if (node.value == "-" || node.value == "Neg" || node.value == "VecNeg")
      {
        if (node.args.size() == 1)
          return negate(build(node.args.front()));
        if (node.value == "-")
          return fold_binary(node.args, "-");
        throw std::invalid_argument("invalid negation arity");
      }
      if (node.value == "<<")
      {
        if (node.args.size() != 2)
          throw std::invalid_argument("invalid rotation arity");
        return rotate(build(node.args.front()));
      }
      if (node.value == "+" || node.value == "Add" || node.value == "VecAdd")
        return fold_binary(node.args, "+");
      if (node.value == "*" || node.value == "Mul" || node.value == "VecMul")
        return fold_binary(node.args, "*");
      if (node.value == "Minus" || node.value == "VecMinus")
        return fold_binary(node.args, "-");
      throw std::invalid_argument("unsupported FHE expression operation: " + node.value);
    }

  private:
    ufhe::seal_backend::BFVPlaintextBound plain_bound(std::uint64_t value) const
    {
      seal::Plaintext plain;
      encoder_.encode(std::vector<std::uint64_t>(encoder_.slot_count(), value), plain);
      return ufhe::seal_backend::BFVPlaintextBound::from_plaintext(plain, plain_modulus_);
    }

    Value fold_binary(const std::vector<Node> &nodes, const std::string &operation)
    {
      if (nodes.size() < 2)
        throw std::invalid_argument("binary operation requires at least two operands");
      Value result = build(nodes.front());
      for (std::size_t index = 1; index < nodes.size(); ++index)
        result = binary(operation, std::move(result), build(nodes[index]));
      return result;
    }

    Value binary(const std::string &operation, Value lhs, Value rhs)
    {
      if (lhs.type == Value::Type::vector || rhs.type == Value::Type::vector)
      {
        std::size_t element_count = lhs.type == Value::Type::vector ? lhs.elements.size() : rhs.elements.size();
        if (lhs.type == Value::Type::vector && rhs.type == Value::Type::vector && lhs.elements.size() != rhs.elements.size())
          throw std::invalid_argument("vector operation requires equally sized vector operands");
        std::vector<Value> elements;
        elements.reserve(element_count);
        for (std::size_t index = 0; index < element_count; ++index)
        {
          Value lhs_element = lhs.type == Value::Type::vector ? lhs.elements[index] : lhs;
          Value rhs_element = rhs.type == Value::Type::vector ? rhs.elements[index] : rhs;
          elements.push_back(binary(operation, std::move(lhs_element), std::move(rhs_element)));
        }
        return make_vector(std::move(elements));
      }
      if (lhs.type == Value::Type::plain && rhs.type == Value::Type::plain)
      {
        if (operation == "+")
          return make_plain((lhs.plain_value + rhs.plain_value) % plain_modulus_);
        if (operation == "-")
          return make_plain((lhs.plain_value + plain_modulus_ - rhs.plain_value) % plain_modulus_);
        return make_plain(multiply_mod(lhs.plain_value, rhs.plain_value, plain_modulus_));
      }
      if (operation == "*")
      {
        if (lhs.type == Value::Type::cipher && rhs.type == Value::Type::cipher)
          return make_cipher(ufhe::seal_backend::BFVNoiseExpression::relinearize(
            ufhe::seal_backend::BFVNoiseExpression::multiply(lhs.cipher_expression, rhs.cipher_expression)));
        if (lhs.type == Value::Type::cipher)
          return make_cipher(ufhe::seal_backend::BFVNoiseExpression::multiply_plain(lhs.cipher_expression, plain_bound(rhs.plain_value)));
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::multiply_plain(rhs.cipher_expression, plain_bound(lhs.plain_value)));
      }
      if (lhs.type == Value::Type::cipher && rhs.type == Value::Type::cipher)
      {
        if (operation == "+")
          return make_cipher(ufhe::seal_backend::BFVNoiseExpression::add(lhs.cipher_expression, rhs.cipher_expression));
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::sub(lhs.cipher_expression, rhs.cipher_expression));
      }
      if (lhs.type == Value::Type::cipher)
      {
        if (operation == "+")
          return make_cipher(ufhe::seal_backend::BFVNoiseExpression::add_plain(lhs.cipher_expression, plain_bound(rhs.plain_value)));
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::sub_plain(lhs.cipher_expression, plain_bound(rhs.plain_value)));
      }
      if (operation == "+")
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::add_plain(rhs.cipher_expression, plain_bound(lhs.plain_value)));
      return make_cipher(ufhe::seal_backend::BFVNoiseExpression::sub_plain(
        ufhe::seal_backend::BFVNoiseExpression::negate(rhs.cipher_expression), plain_bound(lhs.plain_value)));
    }

    Value negate(Value value)
    {
      if (value.type == Value::Type::plain)
        return make_plain(value.plain_value == 0 ? 0 : plain_modulus_ - value.plain_value);
      if (value.type == Value::Type::cipher)
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::negate(value.cipher_expression));
      for (Value &element : value.elements)
        element = negate(std::move(element));
      return value;
    }

    Value rotate(Value value)
    {
      if (value.type == Value::Type::cipher)
        return make_cipher(ufhe::seal_backend::BFVNoiseExpression::rotate(value.cipher_expression));
      if (value.type == Value::Type::vector)
      {
        for (Value &element : value.elements)
          element = rotate(std::move(element));
      }
      return value;
    }

    seal::BatchEncoder encoder_;
    std::uint64_t plain_modulus_;
  };

  void collect_ciphertexts(const Value &value, std::vector<ufhe::seal_backend::BFVNoiseExpression::Ptr> &expressions)
  {
    if (value.type == Value::Type::cipher)
    {
      expressions.push_back(value.cipher_expression);
      return;
    }
    if (value.type == Value::Type::vector)
    {
      for (const Value &element : value.elements)
        collect_ciphertexts(element, expressions);
    }
  }
}

int main(int argc, char **argv)
{
  try
  {
    Arguments arguments = parse_arguments(argc, argv);
    std::string expression((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    std::vector<std::string> tokens = tokenize(expression);
    std::size_t index = 0;
    Node root = parse_node(tokens, index);
    if (index != tokens.size())
      throw std::invalid_argument("unexpected trailing expression tokens");

    seal::EncryptionParameters parameters(seal::scheme_type::bfv);
    parameters.set_poly_modulus_degree(arguments.poly_modulus_degree);
    if (arguments.coeff_modulus.empty())
    {
      parameters.set_coeff_modulus(seal::CoeffModulus::Create(
        arguments.poly_modulus_degree, arguments.coeff_modulus_bits));
    }
    else
    {
      std::vector<seal::Modulus> moduli;
      moduli.reserve(arguments.coeff_modulus.size());
      for (std::uint64_t modulus : arguments.coeff_modulus)
        moduli.emplace_back(modulus);
      parameters.set_coeff_modulus(moduli);
    }
    parameters.set_plain_modulus(arguments.plain_modulus);
    seal::SEALContext context(parameters);
    if (!context.parameters_set())
      throw std::invalid_argument("invalid SEAL BFV parameters");

    ExpressionBuilder builder(context, arguments.plain_modulus);
    Value value = builder.build(root);
    std::vector<ufhe::seal_backend::BFVNoiseExpression::Ptr> ciphertexts;
    collect_ciphertexts(value, ciphertexts);
    ufhe::seal_backend::BFVNoiseEstimator estimator(context);
    int remaining_bits = std::numeric_limits<int>::max();
    bool decryptable = true;
    for (const auto &ciphertext : ciphertexts)
    {
      auto estimate = estimator.BFV_noise_bound(ciphertext);
      remaining_bits = std::min(remaining_bits, estimate.remaining_noise_budget_lower_bound_bits);
      decryptable = decryptable && estimate.decryptable;
    }
    std::cout << "{\"remaining_noise_budget_bits\":" << remaining_bits
              << ",\"decryptable\":" << (decryptable ? "true" : "false") << "}\n";
    return 0;
  }
  catch (const std::exception &error)
  {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
