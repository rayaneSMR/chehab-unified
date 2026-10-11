// v3_size_oracle: library-driven size oracle for the V3 peak-RAM estimator.
//
// For each (logN, nQ, nP) triple it allocates EMPTY Lattigo objects (zero
// values, no key generation / encryption) and emits BinarySize() to stdout
// as CSV: kind,logN,nQ,nP,bytes.
//
// Build (single file, never built together with other mains):
//   go build -mod=readonly -o v3_size_oracle v3_size_oracle.go
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
)

type paramSet struct {
	logN int
	nQ   int
	nP   int
}

// defaultSets covers every (N, L) used by the compiled CHEHAB corpus plus
// a few neighbours for generality (L = nQ + nP).
var defaultSets = []paramSet{
	{13, 4, 2},
	{14, 4, 2}, // corpus L=6
	{14, 5, 2}, // corpus L=7
	{14, 6, 2}, // corpus L=8
	{14, 7, 2}, // corpus L=9
	{14, 8, 2}, // corpus L=10
	{14, 4, 1}, // nP=1 neighbour
	{15, 10, 2}, // corpus L=12
}

func makeParams(set paramSet) hefloat.Parameters {
	logQ := make([]int, set.nQ)
	for i := range logQ {
		logQ[i] = 40
	}
	if set.nQ > 0 {
		logQ[0] = 55
	}
	logP := make([]int, set.nP)
	for i := range logP {
		logP[i] = 45
	}
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            set.logN,
		LogQ:            logQ,
		LogP:            logP,
		LogDefaultScale: 40,
	})
	if err != nil {
		panic(err)
	}
	return params
}

func emit(kind string, set paramSet, bytes int) {
	fmt.Printf("%s,%d,%d,%d,%d\n", kind, set.logN, set.nQ, set.nP, bytes)
}

func main() {
	sets := defaultSets
	if len(os.Args) > 1 {
		sets = nil
		for _, arg := range os.Args[1:] {
			parts := strings.Split(arg, ",")
			if len(parts) != 3 {
				panic("usage: v3_size_oracle [logN,nQ,nP ...]")
			}
			logN, _ := strconv.Atoi(parts[0])
			nQ, _ := strconv.Atoi(parts[1])
			nP, _ := strconv.Atoi(parts[2])
			sets = append(sets, paramSet{logN, nQ, nP})
		}
	}

	fmt.Println("kind,logN,nQ,nP,bytes")
	for _, set := range sets {
		params := makeParams(set)

		sk := rlwe.NewSecretKey(params)
		emit("secret_key", set, sk.BinarySize())

		pk := rlwe.NewPublicKey(params)
		emit("public_key", set, pk.BinarySize())

		rk := rlwe.NewRelinearizationKey(params)
		emit("relinearization_key", set, rk.BinarySize())

		gk := rlwe.NewGaloisKey(params)
		emit("galois_key", set, gk.BinarySize())

		ct := rlwe.NewCiphertext(params, 1)
		emit("ciphertext_deg1", set, ct.BinarySize())

		pt := rlwe.NewPlaintext(params, params.MaxLevel())
		emit("plaintext_max_level", set, pt.BinarySize())
	}
}
