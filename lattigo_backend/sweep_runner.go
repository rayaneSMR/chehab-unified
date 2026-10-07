package main

import (
	"fmt"
	"os"
	"strconv"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/schemes/ckks"
)

func runCiphertextAddition(params ckks.Parameters, size int) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	encryptor := rlwe.NewEncryptor(params, sk)
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(nil))
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	ciphertexts := make([]*rlwe.Ciphertext, size)
	for i := range ciphertexts {
		var err error
		ciphertexts[i], err = encryptor.EncryptNew(pt)
		if err != nil {
			panic(err)
		}
	}
	result := ciphertexts[0]
	for _, ciphertext := range ciphertexts[1:] {
		var err error
		result, err = eval.AddNew(result, ciphertext)
		if err != nil {
			panic(err)
		}
	}
	_ = result
}

func runBatchedMultiplications(params ckks.Parameters, count int) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(rlk))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())

	left := make([]*rlwe.Ciphertext, count)
	right := make([]*rlwe.Ciphertext, count)
	for i := 0; i < count; i++ {
		var err error
		left[i], err = encryptor.EncryptNew(pt)
		if err != nil {
			panic(err)
		}
		right[i], err = encryptor.EncryptNew(pt)
		if err != nil {
			panic(err)
		}
	}

	results := make([]*rlwe.Ciphertext, count)
	for i := range results {
		var err error
		results[i], err = eval.MulRelinNew(left[i], right[i])
		if err != nil {
			panic(err)
		}
	}
	_ = results
}

func runDotProduct(params ckks.Parameters, size int) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(rlk))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())

	ciphertexts := make([]*rlwe.Ciphertext, size)
	for i := range ciphertexts {
		var err error
		ciphertexts[i], err = encryptor.EncryptNew(pt)
		if err != nil {
			panic(err)
		}
	}

	result, err := eval.MulRelinNew(ciphertexts[0], ciphertexts[1])
	if err != nil {
		panic(err)
	}
	for i := 2; i < size; i += 2 {
		product, err := eval.MulRelinNew(ciphertexts[i], ciphertexts[i+1])
		if err != nil {
			panic(err)
		}
		result, err = eval.AddNew(result, product)
		if err != nil {
			panic(err)
		}
	}
	_ = result
}

func main() {
	if len(os.Args) < 5 {
		os.Exit(1)
	}

	benchType, _ := strconv.Atoi(os.Args[1])
	logN, _ := strconv.Atoi(os.Args[2])
	L, _ := strconv.Atoi(os.Args[3])
	paramArg, _ := strconv.Atoi(os.Args[4])

	if L < 3 {
		L = 3
	}
	numQ := L - 2

	logQ := make([]int, numQ)
	logQ[0] = 60
	for i := 1; i < numQ-1; i++ {
		logQ[i] = 45
	}
	logQ[numQ-1] = 60
	logP := []int{60, 60}

	paramLit := ckks.ParametersLiteral{
		LogN:            logN,
		LogQ:            logQ,
		LogP:            logP,
		LogDefaultScale: 40,
	}
	params, err := ckks.NewParametersFromLiteral(paramLit)
	if err != nil {
		fmt.Printf("ERROR: %v\n", err)
		os.Exit(1)
	}

	if benchType == 1 {
		runCiphertextAddition(params, paramArg)
	} else if benchType == 2 {
		runBatchedMultiplications(params, paramArg)
	} else if benchType == 3 {
		runDotProduct(params, paramArg)
	} else {
		fmt.Fprintf(os.Stderr, "unsupported benchmark type: %d\n", benchType)
		os.Exit(1)
	}

}
