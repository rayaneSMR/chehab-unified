import sys

import tenseal as ts


def run_workload(benchmark_type, degree, prime_count, argument, phase="evaluation"):
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=degree,
        coeff_mod_bit_sizes=[60] + [40] * (prime_count - 2) + [60],
    )
    context.global_scale = 2**40
    if benchmark_type in (2, 3):
        context.generate_relin_keys()
    if benchmark_type == 3:
        context.generate_galois_keys()
    if phase == "keys":
        return context

    if benchmark_type == 1:
        encrypted_inputs = [
            ts.ckks_vector(context, [1.0]) for _ in range(argument)
        ]
        if phase == "inputs":
            return encrypted_inputs
        result = encrypted_inputs[0]
        for encrypted_input in encrypted_inputs[1:]:
            result = result + encrypted_input
        return result

    if benchmark_type == 2:
        encrypted_inputs = [
            ts.ckks_vector(context, [1.0]) for _ in range(2 * argument)
        ]
        if phase == "inputs":
            return encrypted_inputs
        products = [
            encrypted_inputs[i] * encrypted_inputs[i + 1]
            for i in range(0, 2 * argument, 2)
        ]
        return products

    if benchmark_type == 3:
        encrypted_inputs = [
            ts.ckks_vector(context, [1.0] * argument) for _ in range(2)
        ]
        if phase == "inputs":
            return encrypted_inputs
        return encrypted_inputs[0].dot(encrypted_inputs[1])

    raise ValueError(f"Unsupported benchmark type: {benchmark_type}")


def main():
    if len(sys.argv) not in (5, 6):
        raise SystemExit(
            "usage: seal_sweep_worker.py <type> <degree> <prime-count> "
            "<argument> [baseline|keys|inputs|evaluation]"
        )
    benchmark_type, degree, prime_count, argument = map(int, sys.argv[1:5])
    phase = sys.argv[5] if len(sys.argv) == 6 else "evaluation"
    if phase not in {"baseline", "keys", "inputs", "evaluation"}:
        raise SystemExit(f"unsupported measurement phase: {phase}")
    if phase == "baseline":
        return
    result = run_workload(benchmark_type, degree, prime_count, argument, phase)
    if result is None:
        raise RuntimeError("Benchmark did not produce a ciphertext")


if __name__ == "__main__":
    main()
