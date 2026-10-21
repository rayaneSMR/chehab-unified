package main

import (
	"flag"
	"fmt"
	"math"
	"os"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
	"github.com/tuneinsight/lattigo/v5/ring/ringqp"
)

func getRotationSteps() []int {
	return []int{2, 1, 16, 32}
}

var (
	p46 *rlwe.Plaintext
	p39 *rlwe.Plaintext
	p37 *rlwe.Plaintext
	p31 *rlwe.Plaintext
)

func init_constants(params hefloat.Parameters, encoder *hefloat.Encoder) {
	slotCount := params.MaxSlots()
	_ = slotCount
	p46 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0)}
		encoder.Encode(values, p46)
	}
	p39 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0)}
		encoder.Encode(values, p39)
	}
	p37 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0)}
		encoder.Encode(values, p37)
	}
	p31 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0)}
		encoder.Encode(values, p31)
	}
}

func tensor_conv2d(
	encryptedInputs map[string]*rlwe.Ciphertext,
	encodedInputs map[string]*rlwe.Plaintext,
	encryptedOutputs map[string]*rlwe.Ciphertext,
	encodedOutputs map[string]*rlwe.Plaintext,
	encoder *hefloat.Encoder,
	enc *rlwe.Encryptor,
	eval *hefloat.Evaluator,
	params hefloat.Parameters,
) {
	c28 := encryptedInputs["image"]
	_ = c28

	// FHE Operations
	buffDecompQP := make([]ringqp.Poly, params.BaseRNSDecompositionVectorSize(params.MaxLevelQ(), 0))
	for i := range buffDecompQP {
		buffDecompQP[i] = params.RingQP().NewPoly()
	}
	var lastDecompID int = -1
	var c29 *rlwe.Ciphertext
	if lastDecompID != 28 {
		eval.DecomposeNTT(c28.Level(), params.MaxLevelP(), params.PCount(), c28.Value[1], c28.IsNTT, buffDecompQP)
		lastDecompID = 28
	}
	if c29 == nil { c29 = rlwe.NewCiphertext(params, 1, c28.Level()) }
	_ = eval.AutomorphismHoisted(c28.Level(), c28, buffDecompQP, params.GaloisElement(2), c29)
	var c32 *rlwe.Ciphertext
	if c32 == nil || c32.Level() < c29.Level() {
		c32, _ = eval.MulNew(c29, p31)
	} else {
		_ = eval.Mul(c29, p31, c32)
	}
	var c30 *rlwe.Ciphertext
	if lastDecompID != 28 {
		eval.DecomposeNTT(c28.Level(), params.MaxLevelP(), params.PCount(), c28.Value[1], c28.IsNTT, buffDecompQP)
		lastDecompID = 28
	}
	if c30 == nil { c30 = rlwe.NewCiphertext(params, 1, c28.Level()) }
	_ = eval.AutomorphismHoisted(c28.Level(), c28, buffDecompQP, params.GaloisElement(1), c30)
	var c33 *rlwe.Ciphertext
	if c33 == nil || c33.Level() < c30.Level() {
		c33, _ = eval.MulNew(c30, p31)
	} else {
		_ = eval.Mul(c30, p31, c33)
	}
	_ = eval.Add(c32, c33, c32)
	if c33 == nil || c33.Level() < c28.Level() {
		c33, _ = eval.MulNew(c28, p31)
	} else {
		_ = eval.Mul(c28, p31, c33)
	}
	_ = eval.Add(c32, c33, c32)
	if c33 == nil || c33.Level() < c29.Level() {
		c33, _ = eval.MulNew(c29, p37)
	} else {
		_ = eval.Mul(c29, p37, c33)
	}
	var c40 *rlwe.Ciphertext
	if c40 == nil || c40.Level() < c30.Level() {
		c40, _ = eval.MulNew(c30, p39)
	} else {
		_ = eval.Mul(c30, p39, c40)
	}
	_ = eval.Add(c33, c40, c33)
	if c40 == nil || c40.Level() < c28.Level() {
		c40, _ = eval.MulNew(c28, p37)
	} else {
		_ = eval.Mul(c28, p37, c40)
	}
	_ = eval.Add(c33, c40, c33)
	_ = eval.Rotate(c33, 16, c33)
	_ = eval.Add(c32, c33, c32)
	_ = eval.Mul(c29, p46, c29)
	_ = eval.Mul(c30, p46, c30)
	_ = eval.Add(c29, c30, c29)
	_ = eval.Mul(c28, p46, c28)
	_ = eval.Add(c29, c28, c29)
	_ = eval.Rotate(c29, 32, c29)
	_ = eval.Add(c32, c29, c32)
	_ = eval.Rescale(c32, c32)

	// Store outputs
	encryptedOutputs["conv_output"] = c32
}


func getCurrentRSS() uint64 {
	if data, err := os.ReadFile("/proc/self/statm"); err == nil {
		fields := strings.Fields(string(data))
		if len(fields) >= 2 {
			if resident, err := strconv.ParseUint(fields[1], 10, 64); err == nil {
				return resident * uint64(os.Getpagesize())
			}
		}
	}
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return m.Sys
}

type RamMemSampler struct {
	running  atomic.Bool
	peakUsed atomic.Uint64
	done     chan struct{}
}

func newRamMemSampler() *RamMemSampler {
	return &RamMemSampler{
		done: make(chan struct{}),
	}
}

func (s *RamMemSampler) Start() {
	s.peakUsed.Store(0)
	s.running.Store(true)
	go func() {
		defer close(s.done)
		for s.running.Load() {
			used := getCurrentRSS()
			for {
				prev := s.peakUsed.Load()
				if used <= prev {
					break
				}
				if s.peakUsed.CompareAndSwap(prev, used) {
					break
				}
			}
			time.Sleep(100 * time.Microsecond)
		}
	}()
}

func (s *RamMemSampler) Stop() {
	s.running.Store(false)
	<-s.done
}

func main() {
	sampler := newRamMemSampler()
	sampler.Start()

	// CKKS Parameters (generated from CKKSParamSelector)
	// LogN=9 (n=512, slots=256)
	// MaxLevel=1, LogScale=26
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            9,
		LogQ:            []int{29, 26},
		LogP:            []int{29, 29},
		LogDefaultScale: 26,
	})
	if err != nil {
		panic(err)
	}

	// Key Generation
	kgen := rlwe.NewKeyGenerator(params)
	sk := kgen.GenSecretKeyNew()
	pk := kgen.GenPublicKeyNew(sk)
	rlk := kgen.GenRelinearizationKeyNew(sk)

	// Galois keys for rotations
	rotations := getRotationSteps()
	galoisElements := make([]uint64, len(rotations))
	for i, r := range rotations {
		galoisElements[i] = params.GaloisElement(r)
	}

	galoisKeysStart := time.Now()
	gks := kgen.GenGaloisKeysNew(galoisElements, sk)
	keys_elapsed := float64(time.Since(galoisKeysStart).Microseconds()) / 1000.0

	var galois_keys_total_size int
	for _, gk := range gks {
		if b, err := gk.MarshalBinary(); err == nil {
			galois_keys_total_size += len(b)
		}
	}
	fmt.Printf("rotation_keys_size_(MB): %f\n", float64(galois_keys_total_size)/(1024.0*1024.0))

	evk := rlwe.NewMemEvaluationKeySet(rlk, gks...)

	// Encoder, Encryptor, Decryptor, Evaluator
	encoder := hefloat.NewEncoder(params)
	enc := rlwe.NewEncryptor(params, pk)
	dec := rlwe.NewDecryptor(params, sk)
	eval := hefloat.NewEvaluator(params, evk)

	// Deterministic inputs and timing setup.
	repetitions := flag.Int("repetitions", 1, "number of encrypted inference repetitions")
	flag.Parse()
	if *repetitions < 1 { panic("repetitions must be positive") }
	encryptedInputs := make(map[string]*rlwe.Ciphertext)
	encodedInputs := make(map[string]*rlwe.Plaintext)
	encryptedOutputs := make(map[string]*rlwe.Ciphertext)
	encodedOutputs := make(map[string]*rlwe.Plaintext)
	values := make([]float64, params.MaxSlots())
	for i := range values { values[i] = float64((i % 17) + 1) / 17.0 }
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["image"] = ct
	}

	encryptReps := 0
	encryptBenchStart := time.Now()
	for time.Since(encryptBenchStart) < 2*time.Millisecond || encryptReps < *repetitions {
		for range encryptedInputs {
			pt := hefloat.NewPlaintext(params, params.MaxLevel())
			_ = encoder.Encode(values, pt)
			_, _ = enc.EncryptNew(pt)
		}
		encryptReps++
	}
	encryptMillis := 0.0
	if encryptReps > 0 {
		encryptMillis = (float64(time.Since(encryptBenchStart).Nanoseconds()) / 1e6) / float64(encryptReps)
	}
	precisionChecked := false
	ref_28 := append([]float64(nil), values...)
	ref_46 := make([]float64, len(values))
	copy(ref_46, []float64{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0})
	ref_39 := make([]float64, len(values))
	copy(ref_39, []float64{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})
	ref_37 := make([]float64, len(values))
	copy(ref_37, []float64{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})
	ref_31 := make([]float64, len(values))
	copy(ref_31, []float64{-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})
	ref_29 := make([]float64, len(ref_28))
	for i := range ref_29 { ref_29[i] = ref_28[(i + 2 + len(ref_28)) % len(ref_28)] }
	ref_32 := make([]float64, len(ref_29))
	for i := range ref_32 { ref_32[i] = ref_29[i] * ref_31[i] }
	ref_30 := make([]float64, len(ref_28))
	for i := range ref_30 { ref_30[i] = ref_28[(i + 1 + len(ref_28)) % len(ref_28)] }
	ref_33 := make([]float64, len(ref_30))
	for i := range ref_33 { ref_33[i] = ref_30[i] * ref_31[i] }
	ref_34 := make([]float64, len(ref_32))
	for i := range ref_34 { ref_34[i] = ref_32[i] + ref_33[i] }
	ref_35 := make([]float64, len(ref_28))
	for i := range ref_35 { ref_35[i] = ref_28[i] * ref_31[i] }
	ref_36 := make([]float64, len(ref_34))
	for i := range ref_36 { ref_36[i] = ref_34[i] + ref_35[i] }
	ref_38 := make([]float64, len(ref_29))
	for i := range ref_38 { ref_38[i] = ref_29[i] * ref_37[i] }
	ref_40 := make([]float64, len(ref_30))
	for i := range ref_40 { ref_40[i] = ref_30[i] * ref_39[i] }
	ref_41 := make([]float64, len(ref_38))
	for i := range ref_41 { ref_41[i] = ref_38[i] + ref_40[i] }
	ref_42 := make([]float64, len(ref_28))
	for i := range ref_42 { ref_42[i] = ref_28[i] * ref_37[i] }
	ref_43 := make([]float64, len(ref_41))
	for i := range ref_43 { ref_43[i] = ref_41[i] + ref_42[i] }
	ref_44 := make([]float64, len(ref_43))
	for i := range ref_44 { ref_44[i] = ref_43[(i + 16 + len(ref_43)) % len(ref_43)] }
	ref_45 := make([]float64, len(ref_36))
	for i := range ref_45 { ref_45[i] = ref_36[i] + ref_44[i] }
	ref_47 := make([]float64, len(ref_29))
	for i := range ref_47 { ref_47[i] = ref_29[i] * ref_46[i] }
	ref_48 := make([]float64, len(ref_30))
	for i := range ref_48 { ref_48[i] = ref_30[i] * ref_46[i] }
	ref_49 := make([]float64, len(ref_47))
	for i := range ref_49 { ref_49[i] = ref_47[i] + ref_48[i] }
	ref_50 := make([]float64, len(ref_28))
	for i := range ref_50 { ref_50[i] = ref_28[i] * ref_46[i] }
	ref_51 := make([]float64, len(ref_49))
	for i := range ref_51 { ref_51[i] = ref_49[i] + ref_50[i] }
	ref_52 := make([]float64, len(ref_51))
	for i := range ref_52 { ref_52[i] = ref_51[(i + 32 + len(ref_51)) % len(ref_51)] }
	ref_53 := make([]float64, len(ref_45))
	for i := range ref_53 { ref_53[i] = ref_45[i] + ref_52[i] }
	ref_54 := ref_53
	expectedOutputs := make(map[string][]float64)
	expectedOutputs["conv_output"] = ref_54
	precisionChecked = true

	init_constants(params, encoder)
	computeStart := time.Now()
	for i := 0; i < *repetitions; i++ {
			tensor_conv2d(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, encoder, enc, eval, params)
	}
  elapsed := float64(time.Since(computeStart).Nanoseconds()) / 1e6
  computeMillis := elapsed / float64(*repetitions)
	maxAbsError := 0.0
	for name, ct := range encryptedOutputs {
		pt := dec.DecryptNew(ct)
		values := make([]float64, params.MaxSlots())
		if err := encoder.Decode(pt, values); err != nil { panic(err) }
		if precisionChecked {
			for i, expected := range expectedOutputs[name] {
				maxAbsError = math.Max(maxAbsError, math.Abs(values[i]-expected))
			}
		}
		fmt.Printf("%s: [%.4f, %.4f, %.4f, ...]\n", name, values[0], values[1], values[2])
	}
	decryptReps := 0
	decryptStart := time.Now()
	for time.Since(decryptStart) < 2*time.Millisecond || decryptReps < *repetitions {
		for _, ct := range encryptedOutputs {
			pt := dec.DecryptNew(ct)
			vals := make([]float64, params.MaxSlots())
			_ = encoder.Decode(pt, vals)
		}
		decryptReps++
	}
	decryptMillis := 0.0
	if decryptReps > 0 {
		decryptMillis = (float64(time.Since(decryptStart).Nanoseconds()) / 1e6) / float64(decryptReps)
	}
	levelsEnd := -1
	for _, ct := range encryptedOutputs { levelsEnd = ct.Level(); break }
	maxAbsErrorJSON := "null"
	if precisionChecked { maxAbsErrorJSON = fmt.Sprintf("%.12g", maxAbsError) }
	fmt.Printf("BENCHMARK_METRICS {\"repetitions\":%d,\"encrypt_ms\":%.3f,\"compute_ms\":%.3f,\"decrypt_ms\":%.3f,\"galois_keys\":%d,\"bootstrap_count\":0,\"level_start\":%d,\"level_end\":%d,\"max_abs_error\":%s,\"precision_checked\":%t}\n",
		*repetitions, encryptMillis, computeMillis, decryptMillis, len(galoisElements), params.MaxLevel(), levelsEnd, maxAbsErrorJSON, precisionChecked)
	_ = encodedOutputs
	fmt.Printf("circuit_execution_time_(ms): %f\n", elapsed)
	fmt.Printf("galois_keys_generation_time_(ms): %f\n", keys_elapsed)
	fmt.Printf("total_execution_time_(ms): %f\n", elapsed+keys_elapsed)
	fmt.Println("CKKS computation completed!")

	sampler.Stop()
	fmt.Printf("peak_ram_memory_(MB): %f\n", float64(sampler.peakUsed.Load())/(1024.0*1024.0))
}
