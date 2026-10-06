import math

def key_bytes(backend: str, N: int, nQ: int, nP: int) -> int:
    """
    Returns the size of a single Galois Key or Relinearization Key in bytes.
    """
    backend = backend.lower()
    if backend == "lattigo":
        # Lattigo v5 formula: ceil(|Q|/|P|) * 2 * (|Q|+|P|) * N * 8
        digits = math.ceil(nQ / nP)
        return digits * 2 * (nQ + nP) * N * 8
    elif backend == "seal":
        # SEAL formula (based on native/src/seal/keygenerator.cpp):
        # destination.resize(decomp_mod_count) where decomp_mod_count = nQ
        # Each component is a PublicKey (2 polynomials) of size (nQ + nP) limbs
        digits = nQ
        return digits * 2 * (nQ + nP) * N * 8
    else:
        raise ValueError(f"Unknown backend: {backend}")

def ct_bytes(backend: str, level: int, N: int, nQ: int, nP: int) -> int:
    """
    Returns the size of a Ciphertext at the given level in bytes.
    level: The number of primes dropped (0 means base level with all nQ primes).
    """
    backend = backend.lower()
    remaining_primes = nQ - level if level < nQ else 1
    
    if backend == "lattigo":
        return 2 * remaining_primes * N * 8
    elif backend == "seal":
        return 2 * remaining_primes * N * 8
    else:
        raise ValueError(f"Unknown backend: {backend}")

def sk_bytes(backend: str, N: int, nQ: int, nP: int) -> int:
    # Lattigo SK is one polynomial in Q and P
    return (nQ + nP) * N * 8

def pk_bytes(backend: str, N: int, nQ: int, nP: int) -> int:
    # Lattigo PK is two polynomials in Q and P
    return 2 * (nQ + nP) * N * 8

def pt_bytes(backend: str, level: int, N: int, nQ: int, nP: int) -> int:
    # Plaintext is one polynomial in Q (at the given level)
    remaining_primes = nQ - level if level < nQ else 1
    return remaining_primes * N * 8

def test_lattigo_key_size():
    # Test unitaire : une clé à N=2¹⁴, |Q|=4, |P|=2 Lattigo doit donner 
    # 2 × 2 × 6 × 16384 × 8 = 3145728 bytes (3.14 MB)
    # (Note: Kimi incorrectly calculated this as 6.29 MB in the prompt)
    b = key_bytes("lattigo", 16384, 4, 2)
    assert b == 3145728, f"Expected 3145728, got {b}"
    print(f"Test passed! Lattigo key size is {b} bytes ({b / 1000**2:.2f} MB / {b / 1024**2:.2f} MiB)")

if __name__ == "__main__":
    test_lattigo_key_size()
