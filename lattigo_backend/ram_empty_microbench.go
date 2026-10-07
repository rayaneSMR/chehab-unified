package main

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
)

var (
	keepParams   hefloat.Parameters
	keepSecret   *rlwe.SecretKey
	keepPublic   *rlwe.PublicKey
	keepRelin    *rlwe.RelinearizationKey
	keepGalois   []*rlwe.GaloisKey
	keepKeySet   *rlwe.MemEvaluationKeySet
	keepEncoder  *hefloat.Encoder
	keepEncrypt  *rlwe.Encryptor
	keepDecrypt  *rlwe.Decryptor
	keepEvaluator *hefloat.Evaluator
	keepPlaintext *rlwe.Plaintext
	keepCiphertext *rlwe.Ciphertext
)

func reportPhase(name string) {
	status, err := os.ReadFile("/proc/self/status")
	if err != nil {
		panic(err)
	}
	rss, hwm := "unknown", "unknown"
	for _, line := range strings.Split(string(status), "\n") {
		if strings.HasPrefix(line, "VmRSS:") {
			rss = strings.TrimSpace(strings.TrimPrefix(line, "VmRSS:"))
		}
		if strings.HasPrefix(line, "VmHWM:") {
			hwm = strings.TrimSpace(strings.TrimPrefix(line, "VmHWM:"))
		}
	}
	var stats runtime.MemStats
	runtime.ReadMemStats(&stats)
	fmt.Printf(
		"MEM_PHASE %s vmrss=%s vmhwm=%s heap_alloc=%d heap_inuse=%d heap_sys=%d num_gc=%d total_alloc=%d\n",
		name, rss, hwm, stats.HeapAlloc, stats.HeapInuse, stats.HeapSys,
		stats.NumGC, stats.TotalAlloc,
	)
}

func main() {
	if len(os.Args) != 3 {
		panic("usage: ram_empty_microbench <N> <L>")
	}
	n, err := strconv.Atoi(os.Args[1])
	if err != nil {
		panic(err)
	}
	totalPrimes, err := strconv.Atoi(os.Args[2])
	if err != nil {
		panic(err)
	}
	if n < 1<<10 || n&(n-1) != 0 || totalPrimes <= 2 {
		panic("N must be a power of two >= 1024 and L must exceed 2")
	}

	reportPhase("baseline")
	logQ := make([]int, totalPrimes-2)
	for i := range logQ {
		logQ[i] = 40
	}
	logQ[0] = 55
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            log2(n),
		LogQ:            logQ,
		LogP:            []int{45, 45},
		LogDefaultScale: 40,
	})
	if err != nil {
		panic(err)
	}
	keepParams = params
	reportPhase("parameters")

	keyGenerator := rlwe.NewKeyGenerator(params)
	keepSecret = keyGenerator.GenSecretKeyNew()
	keepPublic = keyGenerator.GenPublicKeyNew(keepSecret)
	keepRelin = keyGenerator.GenRelinearizationKeyNew(keepSecret)
	keepGalois = keyGenerator.GenGaloisKeysNew(
		[]uint64{params.GaloisElement(1)},
		keepSecret,
	)
	keepKeySet = rlwe.NewMemEvaluationKeySet(keepRelin, keepGalois...)
	reportPhase("keys")

	keepEncoder = hefloat.NewEncoder(params)
	keepEncrypt = rlwe.NewEncryptor(params, keepPublic)
	keepDecrypt = rlwe.NewDecryptor(params, keepSecret)
	keepEvaluator = hefloat.NewEvaluator(params, keepKeySet)
	reportPhase("helpers")

	keepPlaintext = hefloat.NewPlaintext(params, params.MaxLevel())
	values := make([]float64, params.MaxSlots())
	for i := range values {
		values[i] = 1
	}
	if err := keepEncoder.Encode(values, keepPlaintext); err != nil {
		panic(err)
	}
	keepCiphertext, err = keepEncrypt.EncryptNew(keepPlaintext)
	if err != nil {
		panic(err)
	}
	reportPhase("one_input")
}

func log2(value int) int {
	var log int
	for value > 1 {
		value >>= 1
		log++
	}
	return log
}
