package main

import (
	"fmt"
	"runtime"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
)

func main() {
	// 1. Force GC to get a clean baseline
	runtime.GC()
	var m0 runtime.MemStats
	runtime.ReadMemStats(&m0)

	// 2. Setup parameters
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            14,
		LogQ:            []int{55, 40, 40, 40}, // L=4
		LogP:            []int{45, 45},         // P=2
		LogDefaultScale: 40,
	})
	if err != nil {
		panic(err)
	}

	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()

	runtime.GC()
	var m1 runtime.MemStats
	runtime.ReadMemStats(&m1)

	// 3. Generate ONE Galois Key
	gk := kgen.GenGaloisKeyNew(params.GaloisElement(1), sk)
	_ = gk

	runtime.GC()
	var m2 runtime.MemStats
	runtime.ReadMemStats(&m2)

	// 4. Generate 10 Galois Keys to average out overheads
	gks := make([]*rlwe.GaloisKey, 10)
	for i := 0; i < 10; i++ {
		gks[i] = kgen.GenGaloisKeyNew(params.GaloisElement(i+2), sk)
	}
	
	runtime.GC()
	var m3 runtime.MemStats
	runtime.ReadMemStats(&m3)

	// 5. Serialize one key to get its byte size
	data, err := gk.MarshalBinary()
	if err != nil {
		panic(err)
	}

	// 6. Calculate theoretical sizes
	// N := 1 << 14
	// In Lattigo v5, Q has 4 primes, P has 2 primes. Total L = 6. 
	// But let's look at the actual key size
	
	fmt.Printf("=== Lattigo Key Size Analysis ===\n")
	fmt.Printf("Serialized Key Size (MarshalBinary) : %.2f MB\n", float64(len(data))/(1024*1024))
	fmt.Printf("Heap allocated for 1 Key            : %.2f MB\n", float64(m2.HeapAlloc-m1.HeapAlloc)/(1024*1024))
	fmt.Printf("Heap allocated for 10 Keys          : %.2f MB\n", float64(m3.HeapAlloc-m2.HeapAlloc)/(1024*1024))
	fmt.Printf("Average Heap per Key (from 10)      : %.2f MB\n", float64(m3.HeapAlloc-m2.HeapAlloc)/(10*1024*1024))
	
	fmt.Println("---")
	fmt.Printf("Base Context Heap (m1-m0)           : %.2f MB\n", float64(m1.HeapAlloc-m0.HeapAlloc)/(1024*1024))
}
