package main

import (
	"fmt"
	"os"
	"strings"
	"strconv"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
	"github.com/tuneinsight/lattigo/v5/core/rlwe"
)

func getRSSKB() int {
	data, _ := os.ReadFile("/proc/self/status")
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "VmRSS:") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				val, _ := strconv.Atoi(parts[1])
				return val
			}
		}
	}
	return 0
}

func main() {
	fmt.Printf("1. Baseline RSS: %d kB\n", getRSSKB())

	params, _ := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            14,
		LogQ:            []int{60, 40, 40, 40, 40, 40, 40}, // nQ = 7
		LogP:            []int{60},                         // nP = 1
		LogDefaultScale: 40,
	})
	
	fmt.Printf("2. Context (Params) RSS: %d kB\n", getRSSKB())

	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()

	// Relinearization Key
	rlk := kgen.GenRelinearizationKeyNew(sk)
	_ = rlk
	fmt.Printf("3. +RelinKey RSS: %d kB\n", getRSSKB())

	// 1 Galois Key
	gks1 := kgen.GenGaloisKeysNew([]uint64{3}, sk)
	_ = gks1
	fmt.Printf("4. +1 GaloisKey RSS: %d kB\n", getRSSKB())

	// 10 Galois Keys
	gks10 := kgen.GenGaloisKeysNew([]uint64{5, 7, 9, 11, 13, 15, 17, 19, 21, 23}, sk)
	_ = gks10
	fmt.Printf("5. +10 GaloisKeys RSS: %d kB\n", getRSSKB())

	// Ciphertexts
	encoder := hefloat.NewEncoder(params)
	encryptor := rlwe.NewEncryptor(params, sk)
	
	values := make([]float64, params.MaxSlots())
	for i := range values {
		values[i] = 1.0
	}
	pt := hefloat.NewPlaintext(params, params.MaxLevel())
	encoder.Encode(values, pt)

	var cts []*rlwe.Ciphertext
	for i := 0; i < 100; i++ {
		ct, _ := encryptor.EncryptNew(pt)
		cts = append(cts, ct)
	}
	fmt.Printf("6. +100 Ciphertexts RSS: %d kB\n", getRSSKB())
}
