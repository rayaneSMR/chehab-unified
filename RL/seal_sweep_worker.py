import resource
import sys

import tenseal as ts


def run_workload(benchmark_type, degree, prime_count, argument):
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=degree,
        coeff_mod_bit_sizes=[60] + [40] * (prime_count - 2) + [60],
    )
    context.global_scale = 2**40
    if benchmark_type in (2, 3):
        context.generate_relin_keys()

    if benchmark_type == 1:
        encrypted_inputs = [
            ts.ckks_vector(context, [1.0]) for _ in range(argument)
        ]
        result = encrypted_inputs[0]
        for encrypted_input in encrypted_inputs[1:]:
            result = result + encrypted_input
        return result

    if benchmark_type == 2:
        encrypted_inputs = [
            ts.ckks_vector(context, [1.0]) for _ in range(2 * argument)
        ]
        products = [
            encrypted_inputs[i] * encrypted_inputs[i + 1]
            for i in range(0, 2 * argument, 2)
        ]
        return products

    if benchmark_type == 3:
        encrypted_inputs = [
            ts.ckks_vector(context, [1.0]) for _ in range(argument)
        ]
        products = [
            encrypted_inputs[i] * encrypted_inputs[i + 1]
            for i in range(0, argument, 2)
        ]
        result = products[0]
        for product in products[1:]:
            result = result + product
        return result

    raise ValueError(f"Unsupported benchmark type: {benchmark_type}")


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def main():
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: seal_sweep_worker.py <type> <degree> <prime-count> <argument>"
        )
    benchmark_type, degree, prime_count, argument = map(int, sys.argv[1:])
    result = run_workload(benchmark_type, degree, prime_count, argument)
    if result is None:
        raise RuntimeError("Benchmark did not produce a ciphertext")
    print(peak_rss_bytes())


if __name__ == "__main__":
    main()
