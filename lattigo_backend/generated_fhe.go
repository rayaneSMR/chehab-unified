package main

import (
	"fmt"
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
	c64 := encryptedInputs["c26"]
	_ = c64
	c63 := encryptedInputs["c26"]
	_ = c63
	c62 := encryptedInputs["c11"]
	_ = c62
	c61 := encryptedInputs["c11"]
	_ = c61
	c60 := encryptedInputs["c27"]
	_ = c60
	c29 := encryptedInputs["c29"]
	_ = c29
	c28 := encryptedInputs["c2"]
	_ = c28
	c27 := encryptedInputs["c2"]
	_ = c27
	c26 := encryptedInputs["c9"]
	_ = c26
	c25 := encryptedInputs["c9"]
	_ = c25
	c24 := encryptedInputs["c13"]
	_ = c24
	c23 := encryptedInputs["c13"]
	_ = c23
	c22 := encryptedInputs["c4"]
	_ = c22
	c21 := encryptedInputs["c4"]
	_ = c21
	c20 := encryptedInputs["c6"]
	_ = c20
	c19 := encryptedInputs["c6"]
	_ = c19
	c18 := encryptedInputs["c8"]
	_ = c18
	c17 := encryptedInputs["c8"]
	_ = c17
	c16 := encryptedInputs["c12"]
	_ = c16
	c15 := encryptedInputs["c12"]
	_ = c15
	c14 := encryptedInputs["c20"]
	_ = c14
	c1 := encryptedInputs["c31"]
	_ = c1
	c2 := encryptedInputs["c31"]
	_ = c2
	c3 := encryptedInputs["c30"]
	_ = c3
	c4 := encryptedInputs["c30"]
	_ = c4
	c5 := encryptedInputs["c28"]
	_ = c5
	c6 := encryptedInputs["c28"]
	_ = c6
	c7 := encryptedInputs["c25"]
	_ = c7
	c8 := encryptedInputs["c25"]
	_ = c8
	c9 := encryptedInputs["c7"]
	_ = c9
	c10 := encryptedInputs["c7"]
	_ = c10
	c11 := encryptedInputs["c5"]
	_ = c11
	c12 := encryptedInputs["c5"]
	_ = c12
	c13 := encryptedInputs["c20"]
	_ = c13
	c30 := encryptedInputs["c29"]
	_ = c30
	c31 := encryptedInputs["c1"]
	_ = c31
	c32 := encryptedInputs["c1"]
	_ = c32
	c33 := encryptedInputs["c16"]
	_ = c33
	c34 := encryptedInputs["c16"]
	_ = c34
	c35 := encryptedInputs["c0"]
	_ = c35
	c36 := encryptedInputs["c0"]
	_ = c36
	c37 := encryptedInputs["c21"]
	_ = c37
	c38 := encryptedInputs["c21"]
	_ = c38
	c39 := encryptedInputs["c15"]
	_ = c39
	c40 := encryptedInputs["c15"]
	_ = c40
	c41 := encryptedInputs["c23"]
	_ = c41
	c42 := encryptedInputs["c23"]
	_ = c42
	c43 := encryptedInputs["c24"]
	_ = c43
	c44 := encryptedInputs["c24"]
	_ = c44
	c45 := encryptedInputs["c10"]
	_ = c45
	c46 := encryptedInputs["c10"]
	_ = c46
	c47 := encryptedInputs["c14"]
	_ = c47
	c48 := encryptedInputs["c14"]
	_ = c48
	c49 := encryptedInputs["c17"]
	_ = c49
	c50 := encryptedInputs["c17"]
	_ = c50
	c51 := encryptedInputs["c3"]
	_ = c51
	c52 := encryptedInputs["c3"]
	_ = c52
	c53 := encryptedInputs["c19"]
	_ = c53
	c54 := encryptedInputs["c19"]
	_ = c54
	c55 := encryptedInputs["c22"]
	_ = c55
	c56 := encryptedInputs["c22"]
	_ = c56
	c57 := encryptedInputs["c18"]
	_ = c57
	c58 := encryptedInputs["c18"]
	_ = c58
	c59 := encryptedInputs["c27"]
	_ = c59

	// FHE Operations
	c2, _ = eval.MulRelinNew(c2, c4)
	_ = eval.Rescale(c2, c2)
	c6, _ = eval.MulRelinNew(c6, c30)
	_ = eval.Rescale(c6, c6)
	c57, _ = eval.MulRelinNew(c2, c6)
	_ = eval.Rescale(c57, c57)
	c59, _ = eval.MulRelinNew(c59, c63)
	_ = eval.Rescale(c59, c59)
	c8, _ = eval.MulRelinNew(c8, c44)
	_ = eval.Rescale(c8, c8)
	c55, _ = eval.MulRelinNew(c59, c8)
	_ = eval.Rescale(c55, c55)
	c7, _ = eval.MulRelinNew(c57, c55)
	_ = eval.Rescale(c7, c7)
	c42, _ = eval.MulRelinNew(c42, c56)
	_ = eval.Rescale(c42, c42)
	c13, _ = eval.MulRelinNew(c13, c38)
	_ = eval.Rescale(c13, c13)
	c56, _ = eval.MulRelinNew(c42, c13)
	_ = eval.Rescale(c56, c56)
	c54, _ = eval.MulRelinNew(c54, c58)
	_ = eval.Rescale(c54, c54)
	c34, _ = eval.MulRelinNew(c34, c50)
	_ = eval.Rescale(c34, c34)
	c58, _ = eval.MulRelinNew(c54, c34)
	_ = eval.Rescale(c58, c58)
	c1, _ = eval.MulRelinNew(c56, c58)
	_ = eval.Rescale(c1, c1)
	c60, _ = eval.AddNew(c7, c1)
	c40, _ = eval.MulRelinNew(c40, c48)
	_ = eval.Rescale(c40, c40)
	c15, _ = eval.MulRelinNew(c15, c23)
	_ = eval.Rescale(c15, c15)
	c14, _ = eval.MulRelinNew(c40, c15)
	_ = eval.Rescale(c14, c14)
	c46, _ = eval.MulRelinNew(c46, c61)
	_ = eval.Rescale(c46, c46)
	c17, _ = eval.MulRelinNew(c17, c25)
	_ = eval.Rescale(c17, c17)
	c16, _ = eval.MulRelinNew(c46, c17)
	_ = eval.Rescale(c16, c16)
	c18, _ = eval.MulRelinNew(c14, c16)
	_ = eval.Rescale(c18, c18)
	c10, _ = eval.MulRelinNew(c10, c19)
	_ = eval.Rescale(c10, c10)
	c12, _ = eval.MulRelinNew(c12, c21)
	_ = eval.Rescale(c12, c12)
	c19, _ = eval.MulRelinNew(c10, c12)
	_ = eval.Rescale(c19, c19)
	c27, _ = eval.MulRelinNew(c27, c52)
	_ = eval.Rescale(c27, c27)
	c32, _ = eval.MulRelinNew(c32, c36)
	_ = eval.Rescale(c32, c32)
	c20, _ = eval.MulRelinNew(c27, c32)
	_ = eval.Rescale(c20, c20)
	c21, _ = eval.MulRelinNew(c19, c20)
	_ = eval.Rescale(c21, c21)
	c64, _ = eval.AddNew(c18, c21)
	c60, _ = eval.MulRelinNew(c60, c64)
	_ = eval.Rescale(c60, c60)

	// Store outputs
	encryptedOutputs["c32"] = c60
}


func main() {
	// CKKS Parameters (generated from CKKSParamSelector)
	// LogN=14 (n=16384, slots=8192)
	// MaxLevel=5, LogScale=40
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            14,
		LogQ:            []int{55, 40, 40, 40, 40, 40},
		LogP:            []int{45, 45},
		LogDefaultScale: 40,
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

	keys_time := time.Now()
	gks := kgen.GenGaloisKeysNew(galoisElements, sk)
	keys_elapsed := time.Since(keys_time).Seconds() * 1000.0

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

	// Input/Output maps
	encryptedInputs := make(map[string]*rlwe.Ciphertext)
	encodedInputs := make(map[string]*rlwe.Plaintext)
	encryptedOutputs := make(map[string]*rlwe.Ciphertext)
	encodedOutputs := make(map[string]*rlwe.Plaintext)

	// Prepare encrypted inputs
	values := make([]float64, params.MaxSlots())
	for i := range values { values[i] = float64(i) }
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c0"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c1"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c10"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c11"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c12"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c13"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c14"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c15"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c16"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c17"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c18"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c19"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c2"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c20"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c21"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c22"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c23"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c24"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c25"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c26"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c27"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c28"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c29"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c3"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c30"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c31"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c4"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c5"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c6"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c7"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c8"] = ct
	}
	{
		pt := hefloat.NewPlaintext(params, params.MaxLevel())
		encoder.Encode(values, pt)
		ct, _ := enc.EncryptNew(pt)
		encryptedInputs["c9"] = ct
	}

	// Run computation
	t := time.Now()
	fhe(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, encoder, enc, eval, params)
	elapsed := time.Since(t).Seconds() * 1000.0

	// Decrypt and print results
	for name, ct := range encryptedOutputs {
		pt := dec.DecryptNew(ct)
		values := make([]float64, params.MaxSlots())
		encoder.Decode(pt, values)
		fmt.Printf("%s: [%.4f, %.4f, %.4f, ...]\n", name, values[0], values[1], values[2])
	}

	_ = encodedOutputs
	fmt.Printf("circuit_execution_time_(ms): %f\n", elapsed)
	fmt.Printf("galois_keys_generation_time_(ms): %f\n", keys_elapsed)
	fmt.Printf("total_execution_time_(ms): %f\n", elapsed+keys_elapsed)
	fmt.Println("CKKS computation completed!")
}
