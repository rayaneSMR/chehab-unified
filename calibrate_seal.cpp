#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include "seal/seal.h"
#include <unistd.h>

using namespace std;
using namespace seal;

size_t get_rss_kb() {
    ifstream status_file("/proc/self/status");
    string line;
    while (getline(status_file, line)) {
        if (line.compare(0, 6, "VmHWM:") == 0) {
            size_t rss;
            sscanf(line.c_str(), "VmHWM: %zu kB", &rss);
            return rss;
        }
    }
    return 0;
}

int main() {
    cout << "1. Baseline RSS: " << get_rss_kb() << " kB" << endl;

    EncryptionParameters parms(scheme_type::ckks);
    size_t poly_modulus_degree = 16384;
    parms.set_poly_modulus_degree(poly_modulus_degree);
    parms.set_coeff_modulus(CoeffModulus::Create(poly_modulus_degree, {60, 40, 40, 40, 40, 40, 40, 60})); 
    
    SEALContext context(parms);
    cout << "2. Context (Params) RSS: " << get_rss_kb() << " kB" << endl;

    KeyGenerator keygen(context);
    SecretKey secret_key = keygen.secret_key();
    
    // Relinearization Key
    RelinKeys relin_keys;
    keygen.create_relin_keys(relin_keys);
    cout << "3. +RelinKey RSS: " << get_rss_kb() << " kB" << endl;

    // 1 Galois Key
    vector<uint32_t> step1 = {3};
    GaloisKeys galois_keys_1;
    keygen.create_galois_keys(step1, galois_keys_1);
    cout << "4. +1 GaloisKey RSS: " << get_rss_kb() << " kB" << endl;

    // 10 Galois Keys
    vector<uint32_t> steps_10 = {5, 7, 9, 11, 13, 15, 17, 19, 21, 23};
    GaloisKeys galois_keys_10;
    keygen.create_galois_keys(steps_10, galois_keys_10);
    cout << "5. +10 GaloisKeys RSS: " << get_rss_kb() << " kB" << endl;

    // Ciphertexts
    CKKSEncoder encoder(context);
    Encryptor encryptor(context, secret_key);
    vector<Ciphertext> cts;
    vector<double> input(poly_modulus_degree / 2, 1.0);
    Plaintext plain;
    encoder.encode(input, pow(2.0, 40), plain);
    for (int i = 0; i < 100; i++) {
        Ciphertext ct;
        encryptor.encrypt(plain, ct);
        cts.push_back(ct);
    }
    cout << "6. +100 Ciphertexts RSS: " << get_rss_kb() << " kB" << endl;

    return 0;
}
