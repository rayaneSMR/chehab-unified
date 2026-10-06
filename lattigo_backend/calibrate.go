package main

import (
	"fmt"
	"os"
	"strconv"
	"runtime"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: calibrate <num_keys>")
		os.Exit(1)
	}
	
	numKeys, err := strconv.Atoi(os.Args[1])
	if err != nil {
		panic(err)
	}

	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            14,
		LogQ:            []int{55, 40, 40, 40}, // 4 primes in Q
		LogP:            []int{45, 45},         // 2 primes in P (so L=4, extended L=6 technically, wait: P+Q is 6 primes)
		LogDefaultScale: 40,
	})
	if err != nil {
		panic(err)
	}

	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()

	var galoisElements []uint64
	for i := 1; i <= numKeys; i++ {
		galoisElements = append(galoisElements, params.GaloisElement(i))
	}

	// This is the heavy operation
	gks := kgen.GenGaloisKeysNew(galoisElements, sk)
	_ = gks

	// Keep memory resident
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	// We print the HeapAlloc in bytes (just as a reference)
	fmt.Printf("num_keys=%d, heap_alloc_bytes=%d\n", numKeys, m.HeapAlloc)
}
