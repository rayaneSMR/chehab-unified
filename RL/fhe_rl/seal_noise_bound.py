import json
import os
import subprocess
from dataclasses import dataclass


class BFVNoiseBoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class BFVNoiseBoundCertificate:
    remaining_noise_budget_bits: int
    decryptable: bool


class BFVNoiseBoundVerifier:
    def __init__(self, executable, poly_modulus_degree, plain_modulus, coeff_modulus=None, coeff_modulus_bits=None):
        if not executable:
            raise BFVNoiseBoundError("a BFV noise-bound executable is required")
        if not os.path.isfile(executable):
            raise BFVNoiseBoundError(f"BFV noise-bound executable was not found: {executable}")
        if int(poly_modulus_degree) <= 0 or int(plain_modulus) <= 1:
            raise BFVNoiseBoundError("valid BFV polynomial and plaintext moduli are required")
        if bool(coeff_modulus) == bool(coeff_modulus_bits):
            raise BFVNoiseBoundError("provide either exact BFV coefficient moduli or their SEAL construction bit sizes")
        self.executable = os.fspath(executable)
        self.poly_modulus_degree = int(poly_modulus_degree)
        self.plain_modulus = int(plain_modulus)
        self.coeff_modulus = tuple(int(modulus) for modulus in coeff_modulus) if coeff_modulus else None
        self.coeff_modulus_bits = tuple(int(bits) for bits in coeff_modulus_bits) if coeff_modulus_bits else None

    @classmethod
    def from_environment(cls):
        executable = os.environ.get("FHE_BFV_NOISE_BOUND_EXECUTABLE")
        poly_modulus_degree = os.environ.get("FHE_BFV_POLY_MODULUS_DEGREE")
        plain_modulus = os.environ.get("FHE_BFV_PLAIN_MODULUS")
        coeff_modulus = os.environ.get("FHE_BFV_COEFF_MODULUS")
        coeff_modulus_bits = os.environ.get("FHE_BFV_COEFF_MODULUS_BITS")
        if not executable or not poly_modulus_degree or not plain_modulus or bool(coeff_modulus) == bool(coeff_modulus_bits):
            raise BFVNoiseBoundError(
                "set FHE_BFV_NOISE_BOUND_EXECUTABLE, FHE_BFV_POLY_MODULUS_DEGREE, "
                "FHE_BFV_PLAIN_MODULUS, and exactly one of FHE_BFV_COEFF_MODULUS or "
                "FHE_BFV_COEFF_MODULUS_BITS before using the BFV rollback certificate"
            )
        return cls(
            executable,
            poly_modulus_degree,
            plain_modulus,
            coeff_modulus.split(",") if coeff_modulus else None,
            coeff_modulus_bits.split(",") if coeff_modulus_bits else None,
        )

    def BFV_noise_bound(self, expression):
        command = [
            self.executable,
            "--poly-modulus-degree",
            str(self.poly_modulus_degree),
            "--plain-modulus",
            str(self.plain_modulus),
        ]
        if self.coeff_modulus:
            command.extend(["--coeff-modulus", ",".join(str(modulus) for modulus in self.coeff_modulus)])
        else:
            command.extend(["--coeff-modulus-bits", ",".join(str(bits) for bits in self.coeff_modulus_bits)])
        completed = subprocess.run(
            command,
            input=expression,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "unknown native verifier failure"
            raise BFVNoiseBoundError(f"BFV noise-bound verification failed: {message}")
        try:
            result = json.loads(completed.stdout)
            remaining_bits = int(result["remaining_noise_budget_bits"])
            decryptable = bool(result["decryptable"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise BFVNoiseBoundError("BFV noise-bound verifier returned an invalid result") from error
        return BFVNoiseBoundCertificate(remaining_bits, decryptable)
