package main

import (
	"fmt"
	"runtime"
	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/schemes/ckks"
)

func main() {
	runtime.GC()
	var m0 runtime.MemStats
	runtime.ReadMemStats(&m0)

	logN := 15
	logQ := make([]int, 13)
	logQ[0] = 60
	for i := 1; i <= 11; i++ {
		logQ[i] = 45
	}
	logQ[12] = 60
	logP := []int{60, 60}

	paramLit := ckks.ParametersLiteral{
		LogN:            logN,
		LogQ:            logQ,
		LogP:            logP,
		LogDefaultScale: 45,
	}
	params, _ := ckks.NewParametersFromLiteral(paramLit)
	
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()

	runtime.GC()
	var m1 runtime.MemStats
	runtime.ReadMemStats(&m1)

	gk := kgen.GenGaloisKeyNew(params.GaloisElement(1), sk)
	_ = gk

	runtime.GC()
	var m2 runtime.MemStats
	runtime.ReadMemStats(&m2)

	data, _ := gk.MarshalBinary()
	
	fmt.Printf("Serialized Size: %.2f MB\n", float64(len(data))/(1024*1024))
	fmt.Printf("Heap for 1 Key : %.2f MB\n", float64(m2.HeapAlloc-m1.HeapAlloc)/(1024*1024))
}
