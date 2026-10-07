package main

import (
	"fmt"
	"os"
	"strconv"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/schemes/ckks"
)

func runCiphertextAddition(params ckks.Parameters, size int, phase string) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	if phase == "keys" {
		return
	}
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
	if phase == "inputs" {
		return
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

func runBatchedMultiplications(params ckks.Parameters, count int, phase string) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	if phase == "keys" {
		return
	}
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
	if phase == "inputs" {
		return
	}

	results := make([]*rlwe.Ciphertext, count)
	for i := range results {
		var err error
		results[i], err = eval.MulRelinNew(left[i], right[i])
		if err != nil {
			panic(err)
		}
		if err = eval.Rescale(results[i], results[i]); err != nil {
			panic(err)
		}
	}
	_ = results
}

func runDotProduct(params ckks.Parameters, size int, phase string) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	rotationSteps := make([]int, 0)
	for step := 1; step < size; step *= 2 {
		rotationSteps = append(rotationSteps, step)
	}
	galoisElements := make([]uint64, len(rotationSteps))
	for i, step := range rotationSteps {
		galoisElements[i] = params.GaloisElement(step)
	}
	galoisKeys := kgen.GenGaloisKeysNew(galoisElements, sk)
	if phase == "keys" {
		return
	}
	eval := ckks.NewEvaluator(
		params,
		rlwe.NewMemEvaluationKeySet(rlk, galoisKeys...),
	)
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())

	ciphertexts := make([]*rlwe.Ciphertext, 2)
	for i := range ciphertexts {
		var err error
		ciphertexts[i], err = encryptor.EncryptNew(pt)
		if err != nil {
			panic(err)
		}
	}
	if phase == "inputs" {
		return
	}

	result, err := eval.MulRelinNew(ciphertexts[0], ciphertexts[1])
	if err != nil {
		panic(err)
	}
	if err = eval.Rescale(result, result); err != nil {
		panic(err)
	}
	for i := len(rotationSteps) - 1; i >= 0; i-- {
		step := rotationSteps[i]
		rotated, err := eval.RotateNew(result, step)
		if err != nil {
			panic(err)
		}
		result, err = eval.AddNew(result, rotated)
		if err != nil {
			panic(err)
		}
	}
	_ = result
}

func runDeepPolynomial(params ckks.Parameters, depth int, phase string) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	if phase == "keys" {
		return
	}
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(rlk))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	ct, err := encryptor.EncryptNew(pt)
	if err != nil {
		panic(err)
	}
	if phase == "inputs" {
		return
	}
	result := ct
	for range depth {
		result, err = eval.MulRelinNew(result, result)
		if err != nil {
			panic(err)
		}
		if err = eval.Rescale(result, result); err != nil {
			panic(err)
		}
	}
}

func runRotationConvolution(params ckks.Parameters, imageSize int, phase string) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rotations := make([]int, 0, 9)
	rotationKeyElements := make([]uint64, 0, 8)
	for row := 0; row < 3; row++ {
		for col := 0; col < 3; col++ {
			step := row*imageSize + col
			rotations = append(rotations, step)
			if step != 0 {
				rotationKeyElements = append(
					rotationKeyElements,
					params.GaloisElement(step),
				)
			}
		}
	}
	galoisKeys := kgen.GenGaloisKeysNew(rotationKeyElements, sk)
	if phase == "keys" {
		return
	}
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(nil, galoisKeys...))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	input, err := encryptor.EncryptNew(pt)
	if err != nil {
		panic(err)
	}
	if phase == "inputs" {
		return
	}
	var result *rlwe.Ciphertext
	for i, step := range rotations {
		rotated := input
		if step != 0 {
			rotated, err = eval.RotateNew(input, step)
			if err != nil {
				panic(err)
			}
		}
		term, err := eval.MulNew(rotated, 1.0/9.0)
		if err != nil {
			panic(err)
		}
		if i == 0 {
			result = term
		} else {
			result, err = eval.AddNew(result, term)
			if err != nil {
				panic(err)
			}
		}
	}
	_ = result
}

func runHighChurn(params ckks.Parameters, operationCount int, phase string) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	if phase == "keys" {
		return
	}
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(rlk))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	left, err := encryptor.EncryptNew(pt)
	if err != nil {
		panic(err)
	}
	right, err := encryptor.EncryptNew(pt)
	if err != nil {
		panic(err)
	}
	if phase == "inputs" {
		return
	}
	result, err := eval.MulRelinNew(left, right)
	if err != nil {
		panic(err)
	}
	for range operationCount {
		result, err = eval.AddNew(result, right)
		if err != nil {
			panic(err)
		}
	}
}

func main() {
	if len(os.Args) < 5 {
		os.Exit(1)
	}

	benchType, _ := strconv.Atoi(os.Args[1])
	logN, _ := strconv.Atoi(os.Args[2])
	L, _ := strconv.Atoi(os.Args[3])
	paramArg, _ := strconv.Atoi(os.Args[4])
	phase := "evaluation"
	if len(os.Args) > 5 {
		phase = os.Args[5]
	}
	if phase != "baseline" && phase != "keys" && phase != "inputs" && phase != "evaluation" {
		fmt.Fprintf(os.Stderr, "unsupported measurement phase: %s\n", phase)
		os.Exit(1)
	}

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

	if phase == "baseline" {
		return
	}
	if benchType == 1 {
		runCiphertextAddition(params, paramArg, phase)
	} else if benchType == 2 {
		runBatchedMultiplications(params, paramArg, phase)
	} else if benchType == 3 {
		runDotProduct(params, paramArg, phase)
	} else if benchType == 4 {
		runDeepPolynomial(params, paramArg, phase)
	} else if benchType == 5 {
		runRotationConvolution(params, paramArg, phase)
	} else if benchType == 6 {
		runHighChurn(params, paramArg, phase)
	} else {
		fmt.Fprintf(os.Stderr, "unsupported benchmark type: %d\n", benchType)
		os.Exit(1)
	}

}
