package main

import (
	"fmt"
	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/schemes/ckks"
)

type Config struct {
	LogN int
	L    int
	Name string
	Q    []int
	P    []int
}

func main() {
	configs := []Config{
		{LogN: 13, L: 4, Name: "Small (N=8192, 4 primes)", Q: []int{55, 40}, P: []int{45, 45}},
		{LogN: 14, L: 6, Name: "Medium (N=16384, 6 primes)", Q: []int{55, 40, 40, 40}, P: []int{45, 45}},
		{LogN: 15, L: 15, Name: "Huge (N=32768, 15 primes)", Q: []int{60, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 60}, P: []int{60, 60}},
	}

	fmt.Printf("%-30s | %-20s | %-20s | %-15s\n", "Configuration", "SEAL Formula", "Lattigo Size", "Multiplier")
	fmt.Println("---------------------------------------------------------------------------------------------------")

	for _, c := range configs {
		paramLit := ckks.ParametersLiteral{
			LogN:            c.LogN,
			LogQ:            c.Q,
			LogP:            c.P,
			LogDefaultScale: 40,
		}
		params, err := ckks.NewParametersFromLiteral(paramLit)
		if err != nil {
			panic(err)
		}

		kgen := rlwe.NewKeyGenerator(params)
		sk := kgen.GenSecretKeyNew()

		gk := kgen.GenGaloisKeyNew(params.GaloisElement(1), sk)
		
		data, _ := gk.MarshalBinary()
		lattigoSize := float64(len(data)) / (1024 * 1024)
		
		// Theoretical formula: 2 * (L+1) * L * N * 8 bytes
		N := 1 << c.LogN
		theoretical := float64(2 * (c.L + 1) * c.L * N * 8) / (1024 * 1024)
		
		multiplier := lattigoSize / theoretical

		fmt.Printf("%-30s | %6.2f MB             | %6.2f MB             | %.3f\n", c.Name, theoretical, lattigoSize, multiplier)
	}
}
