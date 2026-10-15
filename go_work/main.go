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
	"syscall"
	"time"

	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he/hefloat"
)

func getRotationSteps() []int {
	return []int{}
}

func fhe(
	encryptedInputs map[string]*rlwe.Ciphertext,
	encodedInputs map[string]*rlwe.Plaintext,
	encryptedOutputs map[string]*rlwe.Ciphertext,
	encodedOutputs map[string]*rlwe.Plaintext,
	encoder *hefloat.Encoder,
	enc *rlwe.Encryptor,
	eval *hefloat.Evaluator,
	params hefloat.Parameters,
) {
	c38 := encryptedInputs["c11"]
	_ = c38
	c37 := encryptedInputs["c11"]
	_ = c37
	c36 := encryptedInputs["c10"]
	_ = c36
	c35 := encryptedInputs["c10"]
	_ = c35
	c34 := encryptedInputs["c6"]
	_ = c34
	c33 := encryptedInputs["c6"]
	_ = c33
	c32 := encryptedInputs["c3"]
	_ = c32
	c31 := encryptedInputs["c3"]
	_ = c31
	c30 := encryptedInputs["c7"]
	_ = c30
	c13 := encryptedInputs["c1"]
	_ = c13
	c12 := encryptedInputs["c16"]
	_ = c12
	c11 := encryptedInputs["c16"]
	_ = c11
	c10 := encryptedInputs["c0"]
	_ = c10
	c9 := encryptedInputs["c0"]
	_ = c9
	c8 := encryptedInputs["c14"]
	_ = c8
	c7 := encryptedInputs["c14"]
	_ = c7
	c6 := encryptedInputs["c15"]
	_ = c6
	c5 := encryptedInputs["c15"]
	_ = c5
	c4 := encryptedInputs["c17"]
	_ = c4
	c3 := encryptedInputs["c17"]
	_ = c3
	c2 := encryptedInputs["c18"]
	_ = c2
	c1 := encryptedInputs["c18"]
	_ = c1
	c14 := encryptedInputs["c1"]
	_ = c14
	c15 := encryptedInputs["c2"]
	_ = c15
	c16 := encryptedInputs["c2"]
	_ = c16
	c17 := encryptedInputs["c9"]
	_ = c17
	c18 := encryptedInputs["c9"]
	_ = c18
	c19 := encryptedInputs["c13"]
	_ = c19
	c20 := encryptedInputs["c13"]
	_ = c20
	c21 := encryptedInputs["c4"]
	_ = c21
	c22 := encryptedInputs["c4"]
	_ = c22
	c23 := encryptedInputs["c8"]
	_ = c23
	c24 := encryptedInputs["c8"]
	_ = c24
	c25 := encryptedInputs["c12"]
	_ = c25
	c26 := encryptedInputs["c12"]
	_ = c26
	c27 := encryptedInputs["c5"]
	_ = c27
	c28 := encryptedInputs["c5"]
	_ = c28
	c29 := encryptedInputs["c7"]
	_ = c29

	// FHE Operations
	c3, _ = eval.MulRelinNew(c3, c18)
	_ = eval.Rescale(c3, c3)
	c27, _ = eval.MulRelinNew(c5, c29)
	_ = eval.Rescale(c27, c27)
	c25, _ = eval.AddNew(c3, c27)
	c23, _ = eval.MulRelinNew(c26, c28)
	_ = eval.Rescale(c23, c23)
	c21, _ = eval.MulRelinNew(c24, c31)
	_ = eval.Rescale(c21, c21)
	c13, _ = eval.AddNew(c23, c21)
	c25, _ = eval.AddNew(c25, c13)
	c25, _ = eval.AddNew(c14, c25)
	c25, _ = eval.MulRelinNew(c25, c25)
	_ = eval.Rescale(c25, c25)
	c1, _ = eval.MulRelinNew(c1, c25)
	_ = eval.Rescale(c1, c1)
	c5, _ = eval.MulRelinNew(c5, c18)
	_ = eval.Rescale(c5, c5)
	c7, _ = eval.MulRelinNew(c7, c29)
	_ = eval.Rescale(c7, c7)
	c13, _ = eval.AddNew(c5, c7)
	c30, _ = eval.MulRelinNew(c24, c28)
	_ = eval.Rescale(c30, c30)
	c2, _ = eval.MulRelinNew(c31, c33)
	_ = eval.Rescale(c2, c2)
	c32, _ = eval.AddNew(c30, c2)
	c13, _ = eval.AddNew(c13, c32)
	c13, _ = eval.AddNew(c14, c13)
	c13, _ = eval.MulRelinNew(c13, c13)
	_ = eval.Rescale(c13, c13)
	c11, _ = eval.MulRelinNew(c11, c13)
	_ = eval.Rescale(c11, c11)
	c32, _ = eval.AddNew(c1, c11)
	c26, _ = eval.MulRelinNew(c18, c26)
	_ = eval.Rescale(c26, c26)
	c4, _ = eval.MulRelinNew(c24, c29)
	_ = eval.Rescale(c4, c4)
	c34, _ = eval.AddNew(c26, c4)
	c37, _ = eval.MulRelinNew(c28, c37)
	_ = eval.Rescale(c37, c37)
	c6, _ = eval.MulRelinNew(c22, c31)
	_ = eval.Rescale(c6, c6)
	c10, _ = eval.AddNew(c37, c6)
	c34, _ = eval.AddNew(c34, c10)
	c34, _ = eval.AddNew(c14, c34)
	c34, _ = eval.MulRelinNew(c34, c34)
	_ = eval.Rescale(c34, c34)
	c20, _ = eval.MulRelinNew(c20, c34)
	_ = eval.Rescale(c20, c20)
	c18, _ = eval.MulRelinNew(c18, c24)
	_ = eval.Rescale(c18, c18)
	c29, _ = eval.MulRelinNew(c29, c33)
	_ = eval.Rescale(c29, c29)
	c10, _ = eval.AddNew(c18, c29)
	c22, _ = eval.MulRelinNew(c22, c28)
	_ = eval.Rescale(c22, c22)
	c16, _ = eval.MulRelinNew(c16, c31)
	_ = eval.Rescale(c16, c16)
	c28, _ = eval.AddNew(c22, c16)
	c10, _ = eval.AddNew(c10, c28)
	c14, _ = eval.AddNew(c14, c10)
	c14, _ = eval.MulRelinNew(c14, c14)
	_ = eval.Rescale(c14, c14)
	c35, _ = eval.MulRelinNew(c35, c14)
	_ = eval.Rescale(c35, c35)
	c10, _ = eval.AddNew(c20, c35)
	c32, _ = eval.AddNew(c32, c10)
	c9, _ = eval.AddNew(c9, c32)
	c9, _ = eval.MulRelinNew(c9, c9)
	_ = eval.Rescale(c9, c9)

	// Store outputs
	encryptedOutputs["c19"] = c9
}


func getMaxRSS() uint64 {
	var ru syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &ru); err == nil {
		// Linux reports ru.Maxrss in kilobytes.
		return uint64(ru.Maxrss) * 1024
	}
	return 0
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
	// LogN=14 (n=16384, slots=8192)
	// MaxLevel=5, LogScale=40
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            14,
		LogQ:            []int{55, 40, 40, 40, 40, 40},
		LogP:            []int{50, 50},
		LogDefaultScale: 40,
	})
	if err != nil {
		panic(err)
	}

	// Key Generation
	keygenStart := time.Now()
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

	gks := kgen.GenGaloisKeysNew(galoisElements, sk)

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
	keys_elapsed := float64(time.Since(keygenStart).Microseconds()) / 1000.0

	// Deterministic inputs and timing setup.
	repetitions := flag.Int("repetitions", 1, "number of encrypted inference repetitions")
	flag.Parse()
	if *repetitions < 1 { panic("repetitions must be positive") }
	encryptedInputs := make(map[string]*rlwe.Ciphertext)
	encodedInputs := make(map[string]*rlwe.Plaintext)
	encryptedOutputs := make(map[string]*rlwe.Ciphertext)
	encodedOutputs := make(map[string]*rlwe.Plaintext)
	encryptStart := time.Now()
	values := make([]float64, params.MaxSlots())
	for i := range values { values[i] = float64((i % 17) + 1) / 17.0 }
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c0"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c1"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c10"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c11"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c12"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c13"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c14"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c15"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c16"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c17"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c18"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c2"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c3"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c4"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c5"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c6"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c7"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c8"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		if err := encoder.Encode(values, pt); err != nil { panic(err) }
		ct, err := enc.EncryptNew(pt)
		if err != nil { panic(err) }
		encryptedInputs["c9"] = ct
	}

	encryptMillis := float64(time.Since(encryptStart).Microseconds()) / 1000.0
	precisionChecked := false
	ref_38 := append([]float64(nil), values...)
	ref_37 := append([]float64(nil), values...)
	ref_36 := append([]float64(nil), values...)
	ref_35 := append([]float64(nil), values...)
	ref_34 := append([]float64(nil), values...)
	ref_33 := append([]float64(nil), values...)
	ref_32 := append([]float64(nil), values...)
	ref_31 := append([]float64(nil), values...)
	ref_30 := append([]float64(nil), values...)
	ref_13 := append([]float64(nil), values...)
	ref_12 := append([]float64(nil), values...)
	ref_11 := append([]float64(nil), values...)
	ref_10 := append([]float64(nil), values...)
	ref_9 := append([]float64(nil), values...)
	ref_8 := append([]float64(nil), values...)
	ref_7 := append([]float64(nil), values...)
	ref_6 := append([]float64(nil), values...)
	ref_5 := append([]float64(nil), values...)
	ref_4 := append([]float64(nil), values...)
	ref_3 := append([]float64(nil), values...)
	ref_2 := append([]float64(nil), values...)
	ref_1 := append([]float64(nil), values...)
	ref_14 := append([]float64(nil), values...)
	ref_15 := append([]float64(nil), values...)
	ref_16 := append([]float64(nil), values...)
	ref_17 := append([]float64(nil), values...)
	ref_18 := append([]float64(nil), values...)
	ref_19 := append([]float64(nil), values...)
	ref_20 := append([]float64(nil), values...)
	ref_21 := append([]float64(nil), values...)
	ref_22 := append([]float64(nil), values...)
	ref_23 := append([]float64(nil), values...)
	ref_24 := append([]float64(nil), values...)
	ref_25 := append([]float64(nil), values...)
	ref_26 := append([]float64(nil), values...)
	ref_27 := append([]float64(nil), values...)
	ref_28 := append([]float64(nil), values...)
	ref_29 := append([]float64(nil), values...)
	ref_40 := make([]float64, len(ref_3))
	for i := range ref_40 { ref_40[i] = ref_3[i] * ref_18[i] }
	ref_41 := make([]float64, len(ref_5))
	for i := range ref_41 { ref_41[i] = ref_5[i] * ref_29[i] }
	ref_42 := make([]float64, len(ref_40))
	for i := range ref_42 { ref_42[i] = ref_40[i] + ref_41[i] }
	ref_43 := make([]float64, len(ref_26))
	for i := range ref_43 { ref_43[i] = ref_26[i] * ref_28[i] }
	ref_44 := make([]float64, len(ref_24))
	for i := range ref_44 { ref_44[i] = ref_24[i] * ref_31[i] }
	ref_45 := make([]float64, len(ref_43))
	for i := range ref_45 { ref_45[i] = ref_43[i] + ref_44[i] }
	ref_46 := make([]float64, len(ref_42))
	for i := range ref_46 { ref_46[i] = ref_42[i] + ref_45[i] }
	ref_47 := make([]float64, len(ref_14))
	for i := range ref_47 { ref_47[i] = ref_14[i] + ref_46[i] }
	ref_48 := make([]float64, len(ref_47))
	for i := range ref_48 { ref_48[i] = ref_47[i] * ref_47[i] }
	ref_49 := make([]float64, len(ref_1))
	for i := range ref_49 { ref_49[i] = ref_1[i] * ref_48[i] }
	ref_50 := make([]float64, len(ref_5))
	for i := range ref_50 { ref_50[i] = ref_5[i] * ref_18[i] }
	ref_51 := make([]float64, len(ref_7))
	for i := range ref_51 { ref_51[i] = ref_7[i] * ref_29[i] }
	ref_52 := make([]float64, len(ref_50))
	for i := range ref_52 { ref_52[i] = ref_50[i] + ref_51[i] }
	ref_53 := make([]float64, len(ref_24))
	for i := range ref_53 { ref_53[i] = ref_24[i] * ref_28[i] }
	ref_54 := make([]float64, len(ref_31))
	for i := range ref_54 { ref_54[i] = ref_31[i] * ref_33[i] }
	ref_55 := make([]float64, len(ref_53))
	for i := range ref_55 { ref_55[i] = ref_53[i] + ref_54[i] }
	ref_56 := make([]float64, len(ref_52))
	for i := range ref_56 { ref_56[i] = ref_52[i] + ref_55[i] }
	ref_57 := make([]float64, len(ref_14))
	for i := range ref_57 { ref_57[i] = ref_14[i] + ref_56[i] }
	ref_58 := make([]float64, len(ref_57))
	for i := range ref_58 { ref_58[i] = ref_57[i] * ref_57[i] }
	ref_59 := make([]float64, len(ref_11))
	for i := range ref_59 { ref_59[i] = ref_11[i] * ref_58[i] }
	ref_60 := make([]float64, len(ref_49))
	for i := range ref_60 { ref_60[i] = ref_49[i] + ref_59[i] }
	ref_61 := make([]float64, len(ref_18))
	for i := range ref_61 { ref_61[i] = ref_18[i] * ref_26[i] }
	ref_62 := make([]float64, len(ref_24))
	for i := range ref_62 { ref_62[i] = ref_24[i] * ref_29[i] }
	ref_63 := make([]float64, len(ref_61))
	for i := range ref_63 { ref_63[i] = ref_61[i] + ref_62[i] }
	ref_64 := make([]float64, len(ref_28))
	for i := range ref_64 { ref_64[i] = ref_28[i] * ref_37[i] }
	ref_65 := make([]float64, len(ref_22))
	for i := range ref_65 { ref_65[i] = ref_22[i] * ref_31[i] }
	ref_66 := make([]float64, len(ref_64))
	for i := range ref_66 { ref_66[i] = ref_64[i] + ref_65[i] }
	ref_67 := make([]float64, len(ref_63))
	for i := range ref_67 { ref_67[i] = ref_63[i] + ref_66[i] }
	ref_68 := make([]float64, len(ref_14))
	for i := range ref_68 { ref_68[i] = ref_14[i] + ref_67[i] }
	ref_69 := make([]float64, len(ref_68))
	for i := range ref_69 { ref_69[i] = ref_68[i] * ref_68[i] }
	ref_70 := make([]float64, len(ref_20))
	for i := range ref_70 { ref_70[i] = ref_20[i] * ref_69[i] }
	ref_71 := make([]float64, len(ref_18))
	for i := range ref_71 { ref_71[i] = ref_18[i] * ref_24[i] }
	ref_72 := make([]float64, len(ref_29))
	for i := range ref_72 { ref_72[i] = ref_29[i] * ref_33[i] }
	ref_73 := make([]float64, len(ref_71))
	for i := range ref_73 { ref_73[i] = ref_71[i] + ref_72[i] }
	ref_74 := make([]float64, len(ref_22))
	for i := range ref_74 { ref_74[i] = ref_22[i] * ref_28[i] }
	ref_75 := make([]float64, len(ref_16))
	for i := range ref_75 { ref_75[i] = ref_16[i] * ref_31[i] }
	ref_76 := make([]float64, len(ref_74))
	for i := range ref_76 { ref_76[i] = ref_74[i] + ref_75[i] }
	ref_77 := make([]float64, len(ref_73))
	for i := range ref_77 { ref_77[i] = ref_73[i] + ref_76[i] }
	ref_78 := make([]float64, len(ref_14))
	for i := range ref_78 { ref_78[i] = ref_14[i] + ref_77[i] }
	ref_79 := make([]float64, len(ref_78))
	for i := range ref_79 { ref_79[i] = ref_78[i] * ref_78[i] }
	ref_80 := make([]float64, len(ref_35))
	for i := range ref_80 { ref_80[i] = ref_35[i] * ref_79[i] }
	ref_81 := make([]float64, len(ref_70))
	for i := range ref_81 { ref_81[i] = ref_70[i] + ref_80[i] }
	ref_82 := make([]float64, len(ref_60))
	for i := range ref_82 { ref_82[i] = ref_60[i] + ref_81[i] }
	ref_83 := make([]float64, len(ref_9))
	for i := range ref_83 { ref_83[i] = ref_9[i] + ref_82[i] }
	ref_84 := make([]float64, len(ref_83))
	for i := range ref_84 { ref_84[i] = ref_83[i] * ref_83[i] }
	expectedOutputs := make(map[string][]float64)
	expectedOutputs["c19"] = ref_84
	_ = ref_84
	_ = ref_83
	_ = ref_82
	_ = ref_81
	_ = ref_80
	_ = ref_79
	_ = ref_78
	_ = ref_77
	_ = ref_76
	_ = ref_75
	_ = ref_74
	_ = ref_73
	_ = ref_72
	_ = ref_71
	_ = ref_70
	_ = ref_69
	_ = ref_68
	_ = ref_67
	_ = ref_66
	_ = ref_65
	_ = ref_64
	_ = ref_63
	_ = ref_62
	_ = ref_61
	_ = ref_20
	_ = ref_19
	_ = ref_18
	_ = ref_17
	_ = ref_16
	_ = ref_15
	_ = ref_14
	_ = ref_9
	_ = ref_38
	_ = ref_12
	_ = ref_8
	_ = ref_37
	_ = ref_11
	_ = ref_7
	_ = ref_36
	_ = ref_10
	_ = ref_6
	_ = ref_35
	_ = ref_5
	_ = ref_34
	_ = ref_4
	_ = ref_33
	_ = ref_3
	_ = ref_32
	_ = ref_2
	_ = ref_31
	_ = ref_1
	_ = ref_60
	_ = ref_30
	_ = ref_13
	_ = ref_21
	_ = ref_22
	_ = ref_23
	_ = ref_24
	_ = ref_25
	_ = ref_26
	_ = ref_27
	_ = ref_28
	_ = ref_29
	_ = ref_40
	_ = ref_41
	_ = ref_42
	_ = ref_43
	_ = ref_44
	_ = ref_45
	_ = ref_46
	_ = ref_47
	_ = ref_48
	_ = ref_49
	_ = ref_50
	_ = ref_51
	_ = ref_52
	_ = ref_53
	_ = ref_54
	_ = ref_55
	_ = ref_56
	_ = ref_57
	_ = ref_58
	_ = ref_59
	precisionChecked = true

	computeStart := time.Now()
	for i := 0; i < *repetitions; i++ {
			fhe(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, encoder, enc, eval, params)
	}
	computeMillis := float64(time.Since(computeStart).Microseconds()) / 1000.0 / float64(*repetitions)
	decryptStart := time.Now()
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
	decryptMillis := float64(time.Since(decryptStart).Microseconds()) / 1000.0
	levelsEnd := -1
	for _, ct := range encryptedOutputs { levelsEnd = ct.Level(); break }
	maxAbsErrorJSON := "null"
	if precisionChecked { maxAbsErrorJSON = fmt.Sprintf("%.12g", maxAbsError) }
	fmt.Printf("BENCHMARK_METRICS {\"repetitions\":%d,\"encrypt_ms\":%.3f,\"compute_ms\":%.3f,\"decrypt_ms\":%.3f,\"galois_keys\":%d,\"bootstrap_count\":0,\"level_start\":%d,\"level_end\":%d,\"max_abs_error\":%s,\"precision_checked\":%t}\n",
		*repetitions, encryptMillis, computeMillis, decryptMillis, len(galoisElements), params.MaxLevel(), levelsEnd, maxAbsErrorJSON, precisionChecked)
	_ = encodedOutputs
	elapsed := computeMillis
	fmt.Printf("circuit_execution_time_(ms): %f\n", elapsed)
	fmt.Printf("galois_keys_generation_time_(ms): %f\n", keys_elapsed)
	fmt.Printf("total_execution_time_(ms): %f\n", elapsed+keys_elapsed)
	fmt.Println("CKKS computation completed!")

	sampler.Stop()
	fmt.Printf("peak_ram_memory_(MB): %f\n", float64(sampler.peakUsed.Load())/(1024.0*1024.0))
	fmt.Printf("max_rss_(MB): %f\n", float64(getMaxRSS())/(1024.0*1024.0))
}
