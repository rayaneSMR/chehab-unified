package main

import (
	"fmt"
	"os"
	"strconv"
	"runtime"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/schemes/ckks"
)

func runDeepPoly(params ckks.Parameters, depth int) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	_ = kgen.GenRelinearizationKeyNew(sk)
	// We just allocate the keys to measure memory.
	// For actual execution memory, ciphertexts also matter, but we'll just allocate keys and dummy ciphertexts.
	
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(kgen.GenRelinearizationKeyNew(sk)))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	c1, _ := encryptor.EncryptNew(pt)
	for i := 0; i < depth; i++ {
		c1, _ = eval.MulRelinNew(c1, c1)
	}
}

func runDotProduct(params ckks.Parameters, size int) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	rlk := kgen.GenRelinearizationKeyNew(sk)
	
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(rlk))
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	
	// Create size ciphertexts
	cts := make([]*rlwe.Ciphertext, size)
	for i := 0; i < size; i++ {
		cts[i], _ = encryptor.EncryptNew(pt)
	}
	
	res, _ := encryptor.EncryptNew(pt)
	for i := 0; i < size/2; i++ {
		m, _ := eval.MulRelinNew(cts[i*2], cts[i*2+1])
		eval.Add(res, m, res)
	}
}

func runConv(params ckks.Parameters, layers int) {
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	
	// Rotations for 3x3 kernel over 'layers'
	rotSet := make(map[int]bool)
	currentWidth := 32
	for l := 0; l < layers; l++ {
		for ki := 0; ki < 3; ki++ {
			for kj := 0; kj < 3; kj++ {
				rot := ki*currentWidth + kj
				if rot != 0 {
					rotSet[rot] = true
				}
			}
		}
		currentWidth -= 2
	}
	
	var galEls []uint64
	for r := range rotSet {
		galEls = append(galEls, params.GaloisElement(r))
	}
	
	gks := kgen.GenGaloisKeysNew(galEls, sk)
	_ = gks
	encryptor := rlwe.NewEncryptor(params, sk)
	pt := ckks.NewPlaintext(params, params.MaxLevel())
	
	eval := ckks.NewEvaluator(params, rlwe.NewMemEvaluationKeySet(nil, gks...))
	// Simulate ciphertexts
	c, _ := encryptor.EncryptNew(pt)
	for r := range rotSet {
		eval.RotateNew(c, r)
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
	
	if L < 3 { L = 3 }
	numQ := L - 2
	
	logQ := make([]int, numQ)
	logQ[0] = 60
	for i := 1; i < numQ-1; i++ { logQ[i] = 45 }
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
		runDeepPoly(params, paramArg)
	} else if benchType == 2 {
		runDotProduct(params, paramArg)
	} else if benchType == 3 {
		runConv(params, paramArg)
	}
	
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	// Do not print anything else, just the exit so time -v catches it.
}
