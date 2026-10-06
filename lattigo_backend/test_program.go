package main

import (
	"fmt"
	"os"
	"strconv"
	"runtime"
	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/schemes/ckks"
)

func main() {
	if len(os.Args) < 4 {
		fmt.Println("Usage: runner <LogN> <L> <NumKeys>")
		os.Exit(1)
	}
	
	logN, _ := strconv.Atoi(os.Args[1])
	L, _ := strconv.Atoi(os.Args[2])
	numKeys, _ := strconv.Atoi(os.Args[3])

	// L primes total. P is always 2 primes, Q is the rest.
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
	params, _ := ckks.NewParametersFromLiteral(paramLit)
	
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()

	var galoisElements []uint64
	for i := 1; i <= numKeys; i++ {
		galoisElements = append(galoisElements, params.GaloisElement(i))
	}

	gks := kgen.GenGaloisKeysNew(galoisElements, sk)
	_ = gks

	// Output memory
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	fmt.Printf("HEAP_ALLOC:%d\n", m.HeapAlloc)
}
