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
	return []int{10, 11, 5, 4, 7, 6, 64, 32, 3, 16, 14, 1, 144, 112, 80, 2, 15, 48, 13, 128, 12, 8, 240, 9, 96}
}

var (
	p1003 *rlwe.Plaintext
	p997 *rlwe.Plaintext
	p994 *rlwe.Plaintext
	p991 *rlwe.Plaintext
	p988 *rlwe.Plaintext
	p978 *rlwe.Plaintext
	p975 *rlwe.Plaintext
	p969 *rlwe.Plaintext
	p963 *rlwe.Plaintext
	p955 *rlwe.Plaintext
	p923 *rlwe.Plaintext
	p1006 *rlwe.Plaintext
	p879 *rlwe.Plaintext
	p866 *rlwe.Plaintext
	p863 *rlwe.Plaintext
	p860 *rlwe.Plaintext
	p985 *rlwe.Plaintext
	p858 *rlwe.Plaintext
	p966 *rlwe.Plaintext
	p839 *rlwe.Plaintext
	p831 *rlwe.Plaintext
	p829 *rlwe.Plaintext
	p942 *rlwe.Plaintext
	p815 *rlwe.Plaintext
	p812 *rlwe.Plaintext
	p809 *rlwe.Plaintext
	p798 *rlwe.Plaintext
	p793 *rlwe.Plaintext
	p790 *rlwe.Plaintext
	p787 *rlwe.Plaintext
	p784 *rlwe.Plaintext
	p755 *rlwe.Plaintext
	p750 *rlwe.Plaintext
	p747 *rlwe.Plaintext
	p744 *rlwe.Plaintext
	p881 *rlwe.Plaintext
	p627 *rlwe.Plaintext
	p624 *rlwe.Plaintext
	p621 *rlwe.Plaintext
	p738 *rlwe.Plaintext
	p611 *rlwe.Plaintext
	p670 *rlwe.Plaintext
	p1000 *rlwe.Plaintext
	p619 *rlwe.Plaintext
	p844 *rlwe.Plaintext
	p590 *rlwe.Plaintext
	p587 *rlwe.Plaintext
	p584 *rlwe.Plaintext
	p757 *rlwe.Plaintext
	p630 *rlwe.Plaintext
	p689 *rlwe.Plaintext
	p520 *rlwe.Plaintext
	p960 *rlwe.Plaintext
	p579 *rlwe.Plaintext
	p824 *rlwe.Plaintext
	p570 *rlwe.Plaintext
	p697 *rlwe.Plaintext
	p741 *rlwe.Plaintext
	p614 *rlwe.Plaintext
	p800 *rlwe.Plaintext
	p673 *rlwe.Plaintext
	p735 *rlwe.Plaintext
	p608 *rlwe.Plaintext
	p921 *rlwe.Plaintext
	p667 *rlwe.Plaintext
	p853 *rlwe.Plaintext
	p599 *rlwe.Plaintext
	p726 *rlwe.Plaintext
	p581 *rlwe.Plaintext
	p554 *rlwe.Plaintext
	p983 *rlwe.Plaintext
	p729 *rlwe.Plaintext
	p602 *rlwe.Plaintext
	p661 *rlwe.Plaintext
	p847 *rlwe.Plaintext
	p593 *rlwe.Plaintext
	p720 *rlwe.Plaintext
	p818 *rlwe.Plaintext
	p564 *rlwe.Plaintext
	p691 *rlwe.Plaintext
	p732 *rlwe.Plaintext
	p605 *rlwe.Plaintext
	p664 *rlwe.Plaintext
	p850 *rlwe.Plaintext
	p596 *rlwe.Plaintext
	p723 *rlwe.Plaintext
	p772 *rlwe.Plaintext
	p645 *rlwe.Plaintext
	p518 *rlwe.Plaintext
	p763 *rlwe.Plaintext
	p636 *rlwe.Plaintext
	p957 *rlwe.Plaintext
	p576 *rlwe.Plaintext
	p821 *rlwe.Plaintext
	p567 *rlwe.Plaintext
	p694 *rlwe.Plaintext
	p760 *rlwe.Plaintext
	p633 *rlwe.Plaintext
	p766 *rlwe.Plaintext
	p512 *rlwe.Plaintext
	p639 *rlwe.Plaintext
	p896 *rlwe.Plaintext
	p769 *rlwe.Plaintext
	p642 *rlwe.Plaintext
	p775 *rlwe.Plaintext
	p648 *rlwe.Plaintext
	p834 *rlwe.Plaintext
	p707 *rlwe.Plaintext
	p778 *rlwe.Plaintext
	p651 *rlwe.Plaintext
	p710 *rlwe.Plaintext
	p781 *rlwe.Plaintext
	p527 *rlwe.Plaintext
	p654 *rlwe.Plaintext
	p713 *rlwe.Plaintext
	p659 *rlwe.Plaintext
	p972 *rlwe.Plaintext
	p718 *rlwe.Plaintext
	p803 *rlwe.Plaintext
	p676 *rlwe.Plaintext
	p806 *rlwe.Plaintext
	p552 *rlwe.Plaintext
	p679 *rlwe.Plaintext
	p557 *rlwe.Plaintext
	p684 *rlwe.Plaintext
	p573 *rlwe.Plaintext
	p700 *rlwe.Plaintext
)

func init_constants(params hefloat.Parameters, encoder *hefloat.Encoder) {
	slotCount := params.MaxSlots()
	_ = slotCount
	p1003 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[245] = float64(0.04)
		values[247] = float64(-0.04)
		values[248] = float64(0.04)
		encoder.Encode(values, p1003)
	}
	p997 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[245] = float64(-0.04)
		values[246] = float64(0.04)
		values[248] = float64(-0.04)
		values[249] = float64(0.04)
		encoder.Encode(values, p997)
	}
	p994 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[248] = float64(-0.04)
		values[249] = float64(0.04)
		encoder.Encode(values, p994)
	}
	p991 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[243] = float64(-0.04)
		values[244] = float64(0.04)
		values[246] = float64(-0.04)
		values[247] = float64(0.04)
		values[249] = float64(-0.04)
		encoder.Encode(values, p991)
	}
	p988 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[249] = float64(-0.04)
		encoder.Encode(values, p988)
	}
	p978 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(-0.04)
		values[17] = float64(0.04)
		values[19] = float64(-0.04)
		values[20] = float64(0.04)
		values[22] = float64(-0.04)
		encoder.Encode(values, p978)
	}
	p975 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[17] = float64(-0.04)
		values[18] = float64(0.04)
		encoder.Encode(values, p975)
	}
	p969 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[17] = float64(-0.04)
		values[18] = float64(0.04)
		values[20] = float64(-0.04)
		values[21] = float64(0.04)
		values[23] = float64(-0.04)
		values[24] = float64(0.04)
		encoder.Encode(values, p969)
	}
	p963 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.04)
		encoder.Encode(values, p963)
	}
	p955 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.04)
		values[18] = float64(-0.04)
		values[19] = float64(0.04)
		encoder.Encode(values, p955)
	}
	p923 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(-0.04)
		values[1] = float64(0.04)
		values[3] = float64(-0.04)
		values[4] = float64(0.04)
		values[6] = float64(-0.04)
		values[7] = float64(0.04)
		values[9] = float64(-0.04)
		encoder.Encode(values, p923)
	}
	p1006 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[242] = float64(0.04)
		values[244] = float64(-0.04)
		values[245] = float64(0.04)
		values[247] = float64(-0.04)
		values[248] = float64(0.04)
		encoder.Encode(values, p1006)
	}
	p879 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(-1)
		values[1] = float64(-1)
		values[2] = float64(-1)
		values[3] = float64(-1)
		values[4] = float64(-1)
		values[7] = float64(-1)
		values[8] = float64(-1)
		values[9] = float64(-1)
		values[10] = float64(-1)
		values[11] = float64(-1)
		values[14] = float64(-1)
		values[15] = float64(-1)
		values[16] = float64(-1)
		values[17] = float64(-1)
		values[18] = float64(-1)
		values[21] = float64(-1)
		values[22] = float64(-1)
		values[23] = float64(-1)
		values[24] = float64(-1)
		values[25] = float64(-1)
		values[28] = float64(-1)
		values[29] = float64(-1)
		values[30] = float64(-1)
		values[31] = float64(-1)
		values[32] = float64(-1)
		encoder.Encode(values, p879)
	}
	p866 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[191] = float64(0.25)
		values[192] = float64(0.25)
		encoder.Encode(values, p866)
	}
	p863 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[190] = float64(0.25)
		values[191] = float64(0.25)
		encoder.Encode(values, p863)
	}
	p860 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[189] = float64(0.25)
		values[190] = float64(0.25)
		encoder.Encode(values, p860)
	}
	p985 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[248] = float64(0.04)
		encoder.Encode(values, p985)
	}
	p858 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[192] = float64(0.25)
		encoder.Encode(values, p858)
	}
	p966 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(-0.04)
		encoder.Encode(values, p966)
	}
	p839 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[172] = float64(0.25)
		values[173] = float64(0.25)
		encoder.Encode(values, p839)
	}
	p831 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[171] = float64(0.25)
		values[172] = float64(0.25)
		encoder.Encode(values, p831)
	}
	p829 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[170] = float64(0.25)
		encoder.Encode(values, p829)
	}
	p942 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[1] = float64(-0.04)
		values[2] = float64(0.04)
		values[4] = float64(-0.04)
		values[5] = float64(0.04)
		values[7] = float64(-0.04)
		values[8] = float64(0.04)
		encoder.Encode(values, p942)
	}
	p815 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[148] = float64(0.25)
		values[149] = float64(0.25)
		encoder.Encode(values, p815)
	}
	p812 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[149] = float64(0.25)
		values[150] = float64(0.25)
		encoder.Encode(values, p812)
	}
	p809 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[150] = float64(0.25)
		values[151] = float64(0.25)
		encoder.Encode(values, p809)
	}
	p798 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[153] = float64(0.25)
		values[154] = float64(0.25)
		encoder.Encode(values, p798)
	}
	p793 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[124] = float64(0.25)
		encoder.Encode(values, p793)
	}
	p790 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[124] = float64(0.25)
		values[125] = float64(0.25)
		encoder.Encode(values, p790)
	}
	p787 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[125] = float64(0.25)
		values[126] = float64(0.25)
		encoder.Encode(values, p787)
	}
	p784 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[126] = float64(0.25)
		values[127] = float64(0.25)
		encoder.Encode(values, p784)
	}
	p755 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[136] = float64(0.25)
		values[137] = float64(0.25)
		encoder.Encode(values, p755)
	}
	p750 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[103] = float64(0.25)
		values[104] = float64(0.25)
		encoder.Encode(values, p750)
	}
	p747 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[104] = float64(0.25)
		values[105] = float64(0.25)
		encoder.Encode(values, p747)
	}
	p744 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[105] = float64(0.25)
		values[106] = float64(0.25)
		encoder.Encode(values, p744)
	}
	p881 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(8)
		values[1] = float64(8)
		values[2] = float64(8)
		values[3] = float64(8)
		values[4] = float64(8)
		values[7] = float64(8)
		values[8] = float64(8)
		values[9] = float64(8)
		values[10] = float64(8)
		values[11] = float64(8)
		values[14] = float64(8)
		values[15] = float64(8)
		values[16] = float64(8)
		values[17] = float64(8)
		values[18] = float64(8)
		values[21] = float64(8)
		values[22] = float64(8)
		values[23] = float64(8)
		values[24] = float64(8)
		values[25] = float64(8)
		values[28] = float64(8)
		values[29] = float64(8)
		values[30] = float64(8)
		values[31] = float64(8)
		values[32] = float64(8)
		encoder.Encode(values, p881)
	}
	p627 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[41] = float64(0.25)
		values[42] = float64(0.25)
		encoder.Encode(values, p627)
	}
	p624 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[42] = float64(0.25)
		values[43] = float64(0.25)
		encoder.Encode(values, p624)
	}
	p621 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[43] = float64(0.25)
		values[44] = float64(0.25)
		encoder.Encode(values, p621)
	}
	p738 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[107] = float64(0.25)
		values[108] = float64(0.25)
		encoder.Encode(values, p738)
	}
	p611 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[20] = float64(0.25)
		values[21] = float64(0.25)
		encoder.Encode(values, p611)
	}
	p670 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[68] = float64(0.25)
		values[69] = float64(0.25)
		encoder.Encode(values, p670)
	}
	p1000 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[242] = float64(-0.04)
		values[243] = float64(0.04)
		values[245] = float64(-0.04)
		values[246] = float64(0.04)
		values[248] = float64(-0.04)
		values[249] = float64(0.04)
		encoder.Encode(values, p1000)
	}
	p619 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[44] = float64(0.25)
		values[45] = float64(0.25)
		encoder.Encode(values, p619)
	}
	p844 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[173] = float64(0.25)
		values[174] = float64(0.25)
		encoder.Encode(values, p844)
	}
	p590 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[24] = float64(0.25)
		values[25] = float64(0.25)
		encoder.Encode(values, p590)
	}
	p587 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[25] = float64(0.25)
		values[26] = float64(0.25)
		encoder.Encode(values, p587)
	}
	p584 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[26] = float64(0.25)
		values[27] = float64(0.25)
		encoder.Encode(values, p584)
	}
	p757 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[135] = float64(0.25)
		values[136] = float64(0.25)
		encoder.Encode(values, p757)
	}
	p630 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[40] = float64(0.25)
		values[41] = float64(0.25)
		encoder.Encode(values, p630)
	}
	p689 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[91] = float64(0.25)
		encoder.Encode(values, p689)
	}
	p520 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(8), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0)}
		encoder.Encode(values, p520)
	}
	p960 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.04)
		values[18] = float64(-0.04)
		values[19] = float64(0.04)
		values[21] = float64(-0.04)
		values[22] = float64(0.04)
		encoder.Encode(values, p960)
	}
	p579 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[28] = float64(0.25)
		values[29] = float64(0.25)
		encoder.Encode(values, p579)
	}
	p824 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[154] = float64(0.25)
		values[155] = float64(0.25)
		encoder.Encode(values, p824)
	}
	p570 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[3] = float64(0.25)
		values[4] = float64(0.25)
		encoder.Encode(values, p570)
	}
	p697 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[85] = float64(0.25)
		encoder.Encode(values, p697)
	}
	p741 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[106] = float64(0.25)
		values[107] = float64(0.25)
		encoder.Encode(values, p741)
	}
	p614 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[29] = float64(0.25)
		encoder.Encode(values, p614)
	}
	p800 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[153] = float64(0.25)
		encoder.Encode(values, p800)
	}
	p673 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[62] = float64(0.25)
		encoder.Encode(values, p673)
	}
	p735 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[108] = float64(0.25)
		values[109] = float64(0.25)
		encoder.Encode(values, p735)
	}
	p608 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[19] = float64(0.25)
		values[20] = float64(0.25)
		encoder.Encode(values, p608)
	}
	p921 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.04)
		values[2] = float64(-0.04)
		values[3] = float64(0.04)
		values[5] = float64(-0.04)
		values[6] = float64(0.04)
		values[8] = float64(-0.04)
		values[9] = float64(0.04)
		encoder.Encode(values, p921)
	}
	p667 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[67] = float64(0.25)
		values[68] = float64(0.25)
		encoder.Encode(values, p667)
	}
	p853 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[176] = float64(0.25)
		encoder.Encode(values, p853)
	}
	p599 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[21] = float64(0.25)
		values[22] = float64(0.25)
		encoder.Encode(values, p599)
	}
	p726 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[111] = float64(0.25)
		values[112] = float64(0.25)
		encoder.Encode(values, p726)
	}
	p581 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[27] = float64(0.25)
		values[28] = float64(0.25)
		encoder.Encode(values, p581)
	}
	p554 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.25)
		encoder.Encode(values, p554)
	}
	p983 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[246] = float64(-0.04)
		values[247] = float64(0.04)
		values[249] = float64(-0.04)
		encoder.Encode(values, p983)
	}
	p729 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[110] = float64(0.25)
		values[111] = float64(0.25)
		encoder.Encode(values, p729)
	}
	p602 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[17] = float64(0.25)
		values[18] = float64(0.25)
		encoder.Encode(values, p602)
	}
	p661 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[65] = float64(0.25)
		values[66] = float64(0.25)
		encoder.Encode(values, p661)
	}
	p847 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[174] = float64(0.25)
		values[175] = float64(0.25)
		encoder.Encode(values, p847)
	}
	p593 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[23] = float64(0.25)
		values[24] = float64(0.25)
		encoder.Encode(values, p593)
	}
	p720 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[113] = float64(0.25)
		values[114] = float64(0.25)
		encoder.Encode(values, p720)
	}
	p818 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[147] = float64(0.25)
		values[148] = float64(0.25)
		encoder.Encode(values, p818)
	}
	p564 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[1] = float64(0.25)
		values[2] = float64(0.25)
		encoder.Encode(values, p564)
	}
	p691 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[87] = float64(0.25)
		values[88] = float64(0.25)
		encoder.Encode(values, p691)
	}
	p732 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[109] = float64(0.25)
		values[110] = float64(0.25)
		encoder.Encode(values, p732)
	}
	p605 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[18] = float64(0.25)
		values[19] = float64(0.25)
		encoder.Encode(values, p605)
	}
	p664 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[66] = float64(0.25)
		values[67] = float64(0.25)
		encoder.Encode(values, p664)
	}
	p850 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[175] = float64(0.25)
		values[176] = float64(0.25)
		encoder.Encode(values, p850)
	}
	p596 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[22] = float64(0.25)
		values[23] = float64(0.25)
		encoder.Encode(values, p596)
	}
	p723 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[112] = float64(0.25)
		values[113] = float64(0.25)
		encoder.Encode(values, p723)
	}
	p772 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[130] = float64(0.25)
		values[131] = float64(0.25)
		encoder.Encode(values, p772)
	}
	p645 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[47] = float64(0.25)
		values[48] = float64(0.25)
		encoder.Encode(values, p645)
	}
	p518 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0)}
		encoder.Encode(values, p518)
	}
	p763 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[133] = float64(0.25)
		values[134] = float64(0.25)
		encoder.Encode(values, p763)
	}
	p636 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[39] = float64(0.25)
		encoder.Encode(values, p636)
	}
	p957 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(-0.04)
		values[17] = float64(0.04)
		values[19] = float64(-0.04)
		encoder.Encode(values, p957)
	}
	p576 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[5] = float64(0.25)
		values[6] = float64(0.25)
		encoder.Encode(values, p576)
	}
	p821 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[147] = float64(0.25)
		encoder.Encode(values, p821)
	}
	p567 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[2] = float64(0.25)
		values[3] = float64(0.25)
		encoder.Encode(values, p567)
	}
	p694 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[86] = float64(0.25)
		values[87] = float64(0.25)
		encoder.Encode(values, p694)
	}
	p760 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[134] = float64(0.25)
		values[135] = float64(0.25)
		encoder.Encode(values, p760)
	}
	p633 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[39] = float64(0.25)
		values[40] = float64(0.25)
		encoder.Encode(values, p633)
	}
	p766 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[132] = float64(0.25)
		values[133] = float64(0.25)
		encoder.Encode(values, p766)
	}
	p512 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0)}
		encoder.Encode(values, p512)
	}
	p639 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[45] = float64(0.25)
		values[46] = float64(0.25)
		encoder.Encode(values, p639)
	}
	p896 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(-1)
		values[17] = float64(-1)
		values[18] = float64(-1)
		values[19] = float64(-1)
		values[20] = float64(-1)
		values[23] = float64(-1)
		values[24] = float64(-1)
		values[25] = float64(-1)
		values[26] = float64(-1)
		values[27] = float64(-1)
		values[30] = float64(-1)
		values[31] = float64(-1)
		values[32] = float64(-1)
		values[33] = float64(-1)
		values[34] = float64(-1)
		values[37] = float64(-1)
		values[38] = float64(-1)
		values[39] = float64(-1)
		values[40] = float64(-1)
		values[41] = float64(-1)
		values[44] = float64(-1)
		values[45] = float64(-1)
		values[46] = float64(-1)
		values[47] = float64(-1)
		values[48] = float64(-1)
		encoder.Encode(values, p896)
	}
	p769 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[131] = float64(0.25)
		values[132] = float64(0.25)
		encoder.Encode(values, p769)
	}
	p642 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[46] = float64(0.25)
		values[47] = float64(0.25)
		encoder.Encode(values, p642)
	}
	p775 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[129] = float64(0.25)
		values[130] = float64(0.25)
		encoder.Encode(values, p775)
	}
	p648 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[48] = float64(0.25)
		values[49] = float64(0.25)
		encoder.Encode(values, p648)
	}
	p834 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[170] = float64(0.25)
		values[171] = float64(0.25)
		encoder.Encode(values, p834)
	}
	p707 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[88] = float64(0.25)
		values[89] = float64(0.25)
		encoder.Encode(values, p707)
	}
	p778 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[128] = float64(0.25)
		values[129] = float64(0.25)
		encoder.Encode(values, p778)
	}
	p651 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[49] = float64(0.25)
		values[50] = float64(0.25)
		encoder.Encode(values, p651)
	}
	p710 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[89] = float64(0.25)
		values[90] = float64(0.25)
		encoder.Encode(values, p710)
	}
	p781 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[127] = float64(0.25)
		values[128] = float64(0.25)
		encoder.Encode(values, p781)
	}
	p527 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := []float64{float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(-1), float64(0), float64(0)}
		encoder.Encode(values, p527)
	}
	p654 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[50] = float64(0.25)
		values[51] = float64(0.25)
		encoder.Encode(values, p654)
	}
	p713 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[90] = float64(0.25)
		values[91] = float64(0.25)
		encoder.Encode(values, p713)
	}
	p659 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[64] = float64(0.25)
		values[65] = float64(0.25)
		encoder.Encode(values, p659)
	}
	p972 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[17] = float64(-0.04)
		values[18] = float64(0.04)
		values[20] = float64(-0.04)
		values[21] = float64(0.04)
		encoder.Encode(values, p972)
	}
	p718 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[114] = float64(0.25)
		encoder.Encode(values, p718)
	}
	p803 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[152] = float64(0.25)
		values[153] = float64(0.25)
		encoder.Encode(values, p803)
	}
	p676 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[62] = float64(0.25)
		values[63] = float64(0.25)
		encoder.Encode(values, p676)
	}
	p806 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[151] = float64(0.25)
		values[152] = float64(0.25)
		encoder.Encode(values, p806)
	}
	p552 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[6] = float64(0.25)
		encoder.Encode(values, p552)
	}
	p679 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[63] = float64(0.25)
		values[64] = float64(0.25)
		encoder.Encode(values, p679)
	}
	p557 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.25)
		values[1] = float64(0.25)
		encoder.Encode(values, p557)
	}
	p684 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[68] = float64(0.25)
		encoder.Encode(values, p684)
	}
	p573 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[4] = float64(0.25)
		values[5] = float64(0.25)
		encoder.Encode(values, p573)
	}
	p700 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[85] = float64(0.25)
		values[86] = float64(0.25)
		encoder.Encode(values, p700)
	}
}

func tensor_full_dnn(
	encryptedInputs map[string]*rlwe.Ciphertext,
	encodedInputs map[string]*rlwe.Plaintext,
	encryptedOutputs map[string]*rlwe.Ciphertext,
	encodedOutputs map[string]*rlwe.Plaintext,
	encoder *hefloat.Encoder,
	enc *rlwe.Encryptor,
	eval *hefloat.Evaluator,
	params hefloat.Parameters,
) {
	c509 := encryptedInputs["image"]
	_ = c509

	// FHE Operations
	buffDecompQP := make([]ringqp.Poly, params.BaseRNSDecompositionVectorSize(params.MaxLevelQ(), 0))
	for i := range buffDecompQP {
		buffDecompQP[i] = params.RingQP().NewPoly()
	}
	var lastDecompID int = -1
	var c510 *rlwe.Ciphertext
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c510 == nil { c510 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(2), c510)
	var c513 *rlwe.Ciphertext
	if c513 == nil || c513.Level() < c510.Level() {
		c513, _ = eval.MulNew(c510, p512)
	} else {
		_ = eval.Mul(c510, p512, c513)
	}
	var c511 *rlwe.Ciphertext
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c511 == nil { c511 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(1), c511)
	var c514 *rlwe.Ciphertext
	if c514 == nil || c514.Level() < c511.Level() {
		c514, _ = eval.MulNew(c511, p512)
	} else {
		_ = eval.Mul(c511, p512, c514)
	}
	_ = eval.Add(c513, c514, c513)
	if c514 == nil || c514.Level() < c509.Level() {
		c514, _ = eval.MulNew(c509, p512)
	} else {
		_ = eval.Mul(c509, p512, c514)
	}
	_ = eval.Add(c513, c514, c513)
	if c514 == nil || c514.Level() < c510.Level() {
		c514, _ = eval.MulNew(c510, p518)
	} else {
		_ = eval.Mul(c510, p518, c514)
	}
	var c521 *rlwe.Ciphertext
	if c521 == nil || c521.Level() < c511.Level() {
		c521, _ = eval.MulNew(c511, p520)
	} else {
		_ = eval.Mul(c511, p520, c521)
	}
	_ = eval.Add(c514, c521, c514)
	if c521 == nil || c521.Level() < c509.Level() {
		c521, _ = eval.MulNew(c509, p518)
	} else {
		_ = eval.Mul(c509, p518, c521)
	}
	_ = eval.Add(c514, c521, c514)
	_ = eval.Rotate(c514, 16, c514)
	_ = eval.Add(c513, c514, c513)
	_ = eval.Mul(c510, p527, c510)
	_ = eval.Mul(c511, p527, c511)
	_ = eval.Add(c510, c511, c510)
	_ = eval.Mul(c509, p527, c509)
	_ = eval.Add(c510, c509, c510)
	_ = eval.Rotate(c510, 32, c510)
	_ = eval.Add(c513, c510, c513)
	_ = eval.Rescale(c513, c513)
	_ = eval.MulRelin(c513, c513, c513)
	_ = eval.Rescale(c513, c513)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c510 == nil { c510 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(7), c510)
	if c509 == nil || c509.Level() < c510.Level() {
		c509, _ = eval.MulNew(c510, p552)
	} else {
		_ = eval.Mul(c510, p552, c509)
	}
	if c511 == nil || c511.Level() < c513.Level() {
		c511, _ = eval.MulNew(c513, p554)
	} else {
		_ = eval.Mul(c513, p554, c511)
	}
	_ = eval.Add(c509, c511, c509)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c511 == nil { c511 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(1), c511)
	if c514 == nil || c514.Level() < c511.Level() {
		c514, _ = eval.MulNew(c511, p557)
	} else {
		_ = eval.Mul(c511, p557, c514)
	}
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c521 == nil { c521 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(14), c521)
	var c560 *rlwe.Ciphertext
	if c560 == nil || c560.Level() < c521.Level() {
		c560, _ = eval.MulNew(c521, p554)
	} else {
		_ = eval.Mul(c521, p554, c560)
	}
	_ = eval.Add(c514, c560, c514)
	_ = eval.Add(c509, c514, c509)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c514 == nil { c514 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(15), c514)
	if c560 == nil || c560.Level() < c514.Level() {
		c560, _ = eval.MulNew(c514, p557)
	} else {
		_ = eval.Mul(c514, p557, c560)
	}
	var c541 *rlwe.Ciphertext
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c541 == nil { c541 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(2), c541)
	var c565 *rlwe.Ciphertext
	if c565 == nil || c565.Level() < c541.Level() {
		c565, _ = eval.MulNew(c541, p564)
	} else {
		_ = eval.Mul(c541, p564, c565)
	}
	_ = eval.Add(c560, c565, c560)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c565 == nil { c565 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(3), c565)
	var c568 *rlwe.Ciphertext
	if c568 == nil || c568.Level() < c565.Level() {
		c568, _ = eval.MulNew(c565, p567)
	} else {
		_ = eval.Mul(c565, p567, c568)
	}
	var c543 *rlwe.Ciphertext
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c543 == nil { c543 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(4), c543)
	var c571 *rlwe.Ciphertext
	if c571 == nil || c571.Level() < c543.Level() {
		c571, _ = eval.MulNew(c543, p570)
	} else {
		_ = eval.Mul(c543, p570, c571)
	}
	_ = eval.Add(c568, c571, c568)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c571 == nil { c571 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(5), c571)
	var c574 *rlwe.Ciphertext
	if c574 == nil || c574.Level() < c571.Level() {
		c574, _ = eval.MulNew(c571, p573)
	} else {
		_ = eval.Mul(c571, p573, c574)
	}
	var c545 *rlwe.Ciphertext
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c545 == nil { c545 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(6), c545)
	var c577 *rlwe.Ciphertext
	if c577 == nil || c577.Level() < c545.Level() {
		c577, _ = eval.MulNew(c545, p576)
	} else {
		_ = eval.Mul(c545, p576, c577)
	}
	_ = eval.Add(c574, c577, c574)
	_ = eval.Add(c568, c574, c568)
	_ = eval.Add(c560, c568, c560)
	_ = eval.Add(c509, c560, c509)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c568 == nil { c568 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(11), c568)
	if c577 == nil || c577.Level() < c568.Level() {
		c577, _ = eval.MulNew(c568, p579)
	} else {
		_ = eval.Mul(c568, p579, c577)
	}
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c560 == nil { c560 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(10), c560)
	if c574 == nil || c574.Level() < c560.Level() {
		c574, _ = eval.MulNew(c560, p581)
	} else {
		_ = eval.Mul(c560, p581, c574)
	}
	_ = eval.Add(c577, c574, c577)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c574 == nil { c574 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(9), c574)
	var c585 *rlwe.Ciphertext
	if c585 == nil || c585.Level() < c574.Level() {
		c585, _ = eval.MulNew(c574, p584)
	} else {
		_ = eval.Mul(c574, p584, c585)
	}
	var c549 *rlwe.Ciphertext
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c549 == nil { c549 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(8), c549)
	var c588 *rlwe.Ciphertext
	if c588 == nil || c588.Level() < c549.Level() {
		c588, _ = eval.MulNew(c549, p587)
	} else {
		_ = eval.Mul(c549, p587, c588)
	}
	_ = eval.Add(c585, c588, c585)
	_ = eval.Add(c577, c585, c577)
	if c588 == nil || c588.Level() < c510.Level() {
		c588, _ = eval.MulNew(c510, p590)
	} else {
		_ = eval.Mul(c510, p590, c588)
	}
	if c585 == nil || c585.Level() < c545.Level() {
		c585, _ = eval.MulNew(c545, p593)
	} else {
		_ = eval.Mul(c545, p593, c585)
	}
	_ = eval.Add(c588, c585, c588)
	if c585 == nil || c585.Level() < c571.Level() {
		c585, _ = eval.MulNew(c571, p596)
	} else {
		_ = eval.Mul(c571, p596, c585)
	}
	var c600 *rlwe.Ciphertext
	if c600 == nil || c600.Level() < c543.Level() {
		c600, _ = eval.MulNew(c543, p599)
	} else {
		_ = eval.Mul(c543, p599, c600)
	}
	_ = eval.Add(c585, c600, c585)
	_ = eval.Add(c588, c585, c588)
	_ = eval.Add(c577, c588, c577)
	if c588 == nil || c588.Level() < c513.Level() {
		c588, _ = eval.MulNew(c513, p602)
	} else {
		_ = eval.Mul(c513, p602, c588)
	}
	if c585 == nil || c585.Level() < c511.Level() {
		c585, _ = eval.MulNew(c511, p605)
	} else {
		_ = eval.Mul(c511, p605, c585)
	}
	_ = eval.Add(c588, c585, c588)
	if c585 == nil || c585.Level() < c541.Level() {
		c585, _ = eval.MulNew(c541, p608)
	} else {
		_ = eval.Mul(c541, p608, c585)
	}
	if c600 == nil || c600.Level() < c565.Level() {
		c600, _ = eval.MulNew(c565, p611)
	} else {
		_ = eval.Mul(c565, p611, c600)
	}
	_ = eval.Add(c585, c600, c585)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c600 == nil { c600 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(12), c600)
	var c615 *rlwe.Ciphertext
	if c615 == nil || c615.Level() < c600.Level() {
		c615, _ = eval.MulNew(c600, p614)
	} else {
		_ = eval.Mul(c600, p614, c615)
	}
	_ = eval.Add(c585, c615, c585)
	_ = eval.Add(c588, c585, c588)
	_ = eval.Add(c577, c588, c577)
	_ = eval.Rotate(c577, 16, c577)
	_ = eval.Add(c509, c577, c509)
	if c577 == nil || c577.Level() < c574.Level() {
		c577, _ = eval.MulNew(c574, p619)
	} else {
		_ = eval.Mul(c574, p619, c577)
	}
	if c585 == nil || c585.Level() < c549.Level() {
		c585, _ = eval.MulNew(c549, p621)
	} else {
		_ = eval.Mul(c549, p621, c585)
	}
	_ = eval.Add(c577, c585, c577)
	if c585 == nil || c585.Level() < c510.Level() {
		c585, _ = eval.MulNew(c510, p624)
	} else {
		_ = eval.Mul(c510, p624, c585)
	}
	if c615 == nil || c615.Level() < c545.Level() {
		c615, _ = eval.MulNew(c545, p627)
	} else {
		_ = eval.Mul(c545, p627, c615)
	}
	_ = eval.Add(c585, c615, c585)
	_ = eval.Add(c577, c585, c577)
	if c588 == nil || c588.Level() < c571.Level() {
		c588, _ = eval.MulNew(c571, p630)
	} else {
		_ = eval.Mul(c571, p630, c588)
	}
	if c585 == nil || c585.Level() < c543.Level() {
		c585, _ = eval.MulNew(c543, p633)
	} else {
		_ = eval.Mul(c543, p633, c585)
	}
	_ = eval.Add(c588, c585, c588)
	if c585 == nil || c585.Level() < c565.Level() {
		c585, _ = eval.MulNew(c565, p636)
	} else {
		_ = eval.Mul(c565, p636, c585)
	}
	if c615 == nil || c615.Level() < c560.Level() {
		c615, _ = eval.MulNew(c560, p639)
	} else {
		_ = eval.Mul(c560, p639, c615)
	}
	_ = eval.Add(c585, c615, c585)
	_ = eval.Add(c588, c585, c588)
	_ = eval.Add(c577, c588, c577)
	if c585 == nil || c585.Level() < c568.Level() {
		c585, _ = eval.MulNew(c568, p642)
	} else {
		_ = eval.Mul(c568, p642, c585)
	}
	if c615 == nil || c615.Level() < c600.Level() {
		c615, _ = eval.MulNew(c600, p645)
	} else {
		_ = eval.Mul(c600, p645, c615)
	}
	_ = eval.Add(c585, c615, c585)
	if lastDecompID != 513 {
		eval.DecomposeNTT(c513.Level(), params.MaxLevelP(), params.PCount(), c513.Value[1], c513.IsNTT, buffDecompQP)
		lastDecompID = 513
	}
	if c615 == nil { c615 = rlwe.NewCiphertext(params, 1, c513.Level()) }
	_ = eval.AutomorphismHoisted(c513.Level(), c513, buffDecompQP, params.GaloisElement(13), c615)
	if c588 == nil || c588.Level() < c615.Level() {
		c588, _ = eval.MulNew(c615, p648)
	} else {
		_ = eval.Mul(c615, p648, c588)
	}
	var c652 *rlwe.Ciphertext
	if c652 == nil || c652.Level() < c521.Level() {
		c652, _ = eval.MulNew(c521, p651)
	} else {
		_ = eval.Mul(c521, p651, c652)
	}
	_ = eval.Add(c588, c652, c588)
	if c652 == nil || c652.Level() < c514.Level() {
		c652, _ = eval.MulNew(c514, p654)
	} else {
		_ = eval.Mul(c514, p654, c652)
	}
	_ = eval.Add(c588, c652, c588)
	_ = eval.Add(c585, c588, c585)
	_ = eval.Add(c577, c585, c577)
	_ = eval.Rotate(c577, 32, c577)
	if c585 == nil || c585.Level() < c568.Level() {
		c585, _ = eval.MulNew(c568, p659)
	} else {
		_ = eval.Mul(c568, p659, c585)
	}
	if c588 == nil || c588.Level() < c600.Level() {
		c588, _ = eval.MulNew(c600, p661)
	} else {
		_ = eval.Mul(c600, p661, c588)
	}
	_ = eval.Add(c585, c588, c585)
	if c588 == nil || c588.Level() < c615.Level() {
		c588, _ = eval.MulNew(c615, p664)
	} else {
		_ = eval.Mul(c615, p664, c588)
	}
	if c652 == nil || c652.Level() < c521.Level() {
		c652, _ = eval.MulNew(c521, p667)
	} else {
		_ = eval.Mul(c521, p667, c652)
	}
	_ = eval.Add(c588, c652, c588)
	_ = eval.Add(c585, c588, c585)
	if c652 == nil || c652.Level() < c514.Level() {
		c652, _ = eval.MulNew(c514, p670)
	} else {
		_ = eval.Mul(c514, p670, c652)
	}
	if c588 == nil || c588.Level() < c549.Level() {
		c588, _ = eval.MulNew(c549, p673)
	} else {
		_ = eval.Mul(c549, p673, c588)
	}
	_ = eval.Add(c652, c588, c652)
	if c588 == nil || c588.Level() < c574.Level() {
		c588, _ = eval.MulNew(c574, p676)
	} else {
		_ = eval.Mul(c574, p676, c588)
	}
	var c680 *rlwe.Ciphertext
	if c680 == nil || c680.Level() < c560.Level() {
		c680, _ = eval.MulNew(c560, p679)
	} else {
		_ = eval.Mul(c560, p679, c680)
	}
	_ = eval.Add(c588, c680, c588)
	if c680 == nil || c680.Level() < c513.Level() {
		c680, _ = eval.MulNew(c513, p667)
	} else {
		_ = eval.Mul(c513, p667, c680)
	}
	var c685 *rlwe.Ciphertext
	if c685 == nil || c685.Level() < c511.Level() {
		c685, _ = eval.MulNew(c511, p684)
	} else {
		_ = eval.Mul(c511, p684, c685)
	}
	_ = eval.Add(c680, c685, c680)
	_ = eval.Add(c588, c680, c588)
	_ = eval.Add(c652, c588, c652)
	_ = eval.Add(c585, c652, c585)
	_ = eval.Rotate(c585, 48, c585)
	_ = eval.Add(c577, c585, c577)
	_ = eval.Add(c509, c577, c509)
	if c577 == nil || c577.Level() < c545.Level() {
		c577, _ = eval.MulNew(c545, p689)
	} else {
		_ = eval.Mul(c545, p689, c577)
	}
	if c652 == nil || c652.Level() < c541.Level() {
		c652, _ = eval.MulNew(c541, p691)
	} else {
		_ = eval.Mul(c541, p691, c652)
	}
	_ = eval.Add(c577, c652, c577)
	if c588 == nil || c588.Level() < c514.Level() {
		c588, _ = eval.MulNew(c514, p694)
	} else {
		_ = eval.Mul(c514, p694, c588)
	}
	if c680 == nil || c680.Level() < c615.Level() {
		c680, _ = eval.MulNew(c615, p697)
	} else {
		_ = eval.Mul(c615, p697, c680)
	}
	_ = eval.Add(c588, c680, c588)
	_ = eval.Add(c577, c588, c577)
	if c588 == nil || c588.Level() < c513.Level() {
		c588, _ = eval.MulNew(c513, p700)
	} else {
		_ = eval.Mul(c513, p700, c588)
	}
	if c680 == nil || c680.Level() < c521.Level() {
		c680, _ = eval.MulNew(c521, p700)
	} else {
		_ = eval.Mul(c521, p700, c680)
	}
	_ = eval.Add(c588, c680, c588)
	if c680 == nil || c680.Level() < c511.Level() {
		c680, _ = eval.MulNew(c511, p694)
	} else {
		_ = eval.Mul(c511, p694, c680)
	}
	if c652 == nil || c652.Level() < c565.Level() {
		c652, _ = eval.MulNew(c565, p707)
	} else {
		_ = eval.Mul(c565, p707, c652)
	}
	_ = eval.Add(c680, c652, c680)
	if c652 == nil || c652.Level() < c543.Level() {
		c652, _ = eval.MulNew(c543, p710)
	} else {
		_ = eval.Mul(c543, p710, c652)
	}
	if c685 == nil || c685.Level() < c571.Level() {
		c685, _ = eval.MulNew(c571, p713)
	} else {
		_ = eval.Mul(c571, p713, c685)
	}
	_ = eval.Add(c652, c685, c652)
	_ = eval.Add(c680, c652, c680)
	_ = eval.Add(c588, c680, c588)
	_ = eval.Add(c577, c588, c577)
	_ = eval.Rotate(c577, 64, c577)
	if c588 == nil || c588.Level() < c568.Level() {
		c588, _ = eval.MulNew(c568, p718)
	} else {
		_ = eval.Mul(c568, p718, c588)
	}
	if c680 == nil || c680.Level() < c560.Level() {
		c680, _ = eval.MulNew(c560, p720)
	} else {
		_ = eval.Mul(c560, p720, c680)
	}
	_ = eval.Add(c588, c680, c588)
	if c652 == nil || c652.Level() < c574.Level() {
		c652, _ = eval.MulNew(c574, p723)
	} else {
		_ = eval.Mul(c574, p723, c652)
	}
	if c680 == nil || c680.Level() < c549.Level() {
		c680, _ = eval.MulNew(c549, p726)
	} else {
		_ = eval.Mul(c549, p726, c680)
	}
	_ = eval.Add(c652, c680, c652)
	_ = eval.Add(c588, c652, c588)
	if c652 == nil || c652.Level() < c510.Level() {
		c652, _ = eval.MulNew(c510, p729)
	} else {
		_ = eval.Mul(c510, p729, c652)
	}
	if c680 == nil || c680.Level() < c545.Level() {
		c680, _ = eval.MulNew(c545, p732)
	} else {
		_ = eval.Mul(c545, p732, c680)
	}
	_ = eval.Add(c652, c680, c652)
	if c680 == nil || c680.Level() < c571.Level() {
		c680, _ = eval.MulNew(c571, p735)
	} else {
		_ = eval.Mul(c571, p735, c680)
	}
	if c685 == nil || c685.Level() < c543.Level() {
		c685, _ = eval.MulNew(c543, p738)
	} else {
		_ = eval.Mul(c543, p738, c685)
	}
	_ = eval.Add(c680, c685, c680)
	_ = eval.Add(c652, c680, c652)
	if c680 == nil || c680.Level() < c565.Level() {
		c680, _ = eval.MulNew(c565, p741)
	} else {
		_ = eval.Mul(c565, p741, c680)
	}
	if c685 == nil || c685.Level() < c541.Level() {
		c685, _ = eval.MulNew(c541, p744)
	} else {
		_ = eval.Mul(c541, p744, c685)
	}
	_ = eval.Add(c680, c685, c680)
	if c685 == nil || c685.Level() < c511.Level() {
		c685, _ = eval.MulNew(c511, p747)
	} else {
		_ = eval.Mul(c511, p747, c685)
	}
	if c585 == nil || c585.Level() < c513.Level() {
		c585, _ = eval.MulNew(c513, p750)
	} else {
		_ = eval.Mul(c513, p750, c585)
	}
	_ = eval.Add(c685, c585, c685)
	_ = eval.Add(c680, c685, c680)
	_ = eval.Add(c652, c680, c652)
	_ = eval.Add(c588, c652, c588)
	_ = eval.Rotate(c588, 80, c588)
	_ = eval.Add(c577, c588, c577)
	if c588 == nil || c588.Level() < c514.Level() {
		c588, _ = eval.MulNew(c514, p755)
	} else {
		_ = eval.Mul(c514, p755, c588)
	}
	if c585 == nil || c585.Level() < c521.Level() {
		c585, _ = eval.MulNew(c521, p757)
	} else {
		_ = eval.Mul(c521, p757, c585)
	}
	_ = eval.Add(c588, c585, c588)
	if c585 == nil || c585.Level() < c615.Level() {
		c585, _ = eval.MulNew(c615, p760)
	} else {
		_ = eval.Mul(c615, p760, c585)
	}
	if c652 == nil || c652.Level() < c600.Level() {
		c652, _ = eval.MulNew(c600, p763)
	} else {
		_ = eval.Mul(c600, p763, c652)
	}
	_ = eval.Add(c585, c652, c585)
	_ = eval.Add(c588, c585, c588)
	if c652 == nil || c652.Level() < c568.Level() {
		c652, _ = eval.MulNew(c568, p766)
	} else {
		_ = eval.Mul(c568, p766, c652)
	}
	if c585 == nil || c585.Level() < c560.Level() {
		c585, _ = eval.MulNew(c560, p769)
	} else {
		_ = eval.Mul(c560, p769, c585)
	}
	_ = eval.Add(c652, c585, c652)
	if c585 == nil || c585.Level() < c574.Level() {
		c585, _ = eval.MulNew(c574, p772)
	} else {
		_ = eval.Mul(c574, p772, c585)
	}
	if c685 == nil || c685.Level() < c549.Level() {
		c685, _ = eval.MulNew(c549, p775)
	} else {
		_ = eval.Mul(c549, p775, c685)
	}
	_ = eval.Add(c585, c685, c585)
	_ = eval.Add(c652, c585, c652)
	_ = eval.Add(c588, c652, c588)
	if c652 == nil || c652.Level() < c510.Level() {
		c652, _ = eval.MulNew(c510, p778)
	} else {
		_ = eval.Mul(c510, p778, c652)
	}
	_ = eval.Mul(c545, p781, c545)
	_ = eval.Add(c652, c545, c652)
	if c545 == nil || c545.Level() < c571.Level() {
		c545, _ = eval.MulNew(c571, p784)
	} else {
		_ = eval.Mul(c571, p784, c545)
	}
	if c585 == nil || c585.Level() < c543.Level() {
		c585, _ = eval.MulNew(c543, p787)
	} else {
		_ = eval.Mul(c543, p787, c585)
	}
	_ = eval.Add(c545, c585, c545)
	if c585 == nil || c585.Level() < c565.Level() {
		c585, _ = eval.MulNew(c565, p790)
	} else {
		_ = eval.Mul(c565, p790, c585)
	}
	if c685 == nil || c685.Level() < c541.Level() {
		c685, _ = eval.MulNew(c541, p793)
	} else {
		_ = eval.Mul(c541, p793, c685)
	}
	_ = eval.Add(c585, c685, c585)
	_ = eval.Add(c545, c585, c545)
	_ = eval.Add(c652, c545, c652)
	_ = eval.Add(c588, c652, c588)
	_ = eval.Rotate(c588, 96, c588)
	_ = eval.Add(c577, c588, c577)
	if c588 == nil || c588.Level() < c521.Level() {
		c588, _ = eval.MulNew(c521, p798)
	} else {
		_ = eval.Mul(c521, p798, c588)
	}
	if c685 == nil || c685.Level() < c513.Level() {
		c685, _ = eval.MulNew(c513, p800)
	} else {
		_ = eval.Mul(c513, p800, c685)
	}
	_ = eval.Add(c588, c685, c588)
	if c545 == nil || c545.Level() < c615.Level() {
		c545, _ = eval.MulNew(c615, p803)
	} else {
		_ = eval.Mul(c615, p803, c545)
	}
	if c585 == nil || c585.Level() < c600.Level() {
		c585, _ = eval.MulNew(c600, p806)
	} else {
		_ = eval.Mul(c600, p806, c585)
	}
	_ = eval.Add(c545, c585, c545)
	_ = eval.Add(c588, c545, c588)
	_ = eval.Mul(c568, p809, c568)
	_ = eval.Mul(c560, p812, c560)
	_ = eval.Add(c568, c560, c568)
	_ = eval.Mul(c574, p815, c574)
	_ = eval.Mul(c549, p818, c549)
	_ = eval.Add(c574, c549, c574)
	_ = eval.Mul(c510, p821, c510)
	if c549 == nil || c549.Level() < c514.Level() {
		c549, _ = eval.MulNew(c514, p824)
	} else {
		_ = eval.Mul(c514, p824, c549)
	}
	_ = eval.Add(c510, c549, c510)
	_ = eval.Add(c574, c510, c574)
	_ = eval.Add(c568, c574, c568)
	_ = eval.Add(c588, c568, c588)
	_ = eval.Rotate(c588, 112, c588)
	_ = eval.Mul(c600, p829, c600)
	if c549 == nil || c549.Level() < c513.Level() {
		c549, _ = eval.MulNew(c513, p831)
	} else {
		_ = eval.Mul(c513, p831, c549)
	}
	_ = eval.Add(c600, c549, c600)
	_ = eval.Mul(c615, p834, c615)
	_ = eval.Mul(c521, p831, c521)
	_ = eval.Add(c615, c521, c615)
	_ = eval.Add(c600, c615, c600)
	if c615 == nil || c615.Level() < c511.Level() {
		c615, _ = eval.MulNew(c511, p839)
	} else {
		_ = eval.Mul(c511, p839, c615)
	}
	_ = eval.Mul(c514, p839, c514)
	_ = eval.Add(c615, c514, c615)
	if c521 == nil || c521.Level() < c541.Level() {
		c521, _ = eval.MulNew(c541, p844)
	} else {
		_ = eval.Mul(c541, p844, c521)
	}
	if c545 == nil || c545.Level() < c565.Level() {
		c545, _ = eval.MulNew(c565, p847)
	} else {
		_ = eval.Mul(c565, p847, c545)
	}
	_ = eval.Add(c521, c545, c521)
	_ = eval.Mul(c543, p850, c543)
	_ = eval.Mul(c571, p853, c571)
	_ = eval.Add(c543, c571, c543)
	_ = eval.Add(c521, c543, c521)
	_ = eval.Add(c615, c521, c615)
	_ = eval.Add(c600, c615, c600)
	_ = eval.Rotate(c600, 128, c600)
	_ = eval.Mul(c565, p858, c565)
	if c615 == nil || c615.Level() < c513.Level() {
		c615, _ = eval.MulNew(c513, p860)
	} else {
		_ = eval.Mul(c513, p860, c615)
	}
	_ = eval.Add(c565, c615, c565)
	_ = eval.Mul(c511, p863, c511)
	_ = eval.Mul(c541, p866, c541)
	_ = eval.Add(c511, c541, c511)
	_ = eval.Add(c565, c511, c565)
	_ = eval.Rotate(c565, 144, c565)
	_ = eval.Add(c600, c565, c600)
	_ = eval.Add(c588, c600, c588)
	_ = eval.Add(c577, c588, c577)
	_ = eval.Add(c509, c577, c509)
	_ = eval.Rescale(c509, c509)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c577 == nil { c577 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(9), c577)
	_ = eval.Mul(c577, p879, c577)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c541 == nil { c541 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(8), c541)
	_ = eval.Mul(c541, p881, c541)
	_ = eval.Add(c577, c541, c577)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c541 == nil { c541 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(7), c541)
	_ = eval.Mul(c541, p879, c541)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c521 == nil { c521 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(15), c521)
	_ = eval.Mul(c521, p879, c521)
	_ = eval.Add(c541, c521, c541)
	_ = eval.Add(c577, c541, c577)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c541 == nil { c541 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(2), c541)
	_ = eval.Mul(c541, p879, c541)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c521 == nil { c521 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(14), c521)
	_ = eval.Mul(c521, p879, c521)
	_ = eval.Add(c541, c521, c541)
	if lastDecompID != 509 {
		eval.DecomposeNTT(c509.Level(), params.MaxLevelP(), params.PCount(), c509.Value[1], c509.IsNTT, buffDecompQP)
		lastDecompID = 509
	}
	if c543 == nil { c543 = rlwe.NewCiphertext(params, 1, c509.Level()) }
	_ = eval.AutomorphismHoisted(c509.Level(), c509, buffDecompQP, params.GaloisElement(1), c543)
	_ = eval.Mul(c543, p879, c543)
	if c571 == nil || c571.Level() < c509.Level() {
		c571, _ = eval.MulNew(c509, p879)
	} else {
		_ = eval.Mul(c509, p879, c571)
	}
	_ = eval.Add(c543, c571, c543)
	_ = eval.Mul(c509, p896, c509)
	_ = eval.Rotate(c509, 16, c509)
	_ = eval.Add(c543, c509, c543)
	_ = eval.Add(c541, c543, c541)
	_ = eval.Add(c577, c541, c577)
	if c543 == nil || c543.Level() < c577.Level() {
		c543, _ = eval.RotateNew(c577, 64)
	} else {
		_ = eval.Rotate(c577, 64, c543)
	}
	_ = eval.Add(c577, c543, c577)
	if c545 == nil || c545.Level() < c577.Level() {
		c545, _ = eval.RotateNew(c577, 128)
	} else {
		_ = eval.Rotate(c577, 128, c545)
	}
	_ = eval.Add(c577, c545, c577)
	_ = eval.Rescale(c577, c577)
	_ = eval.MulRelin(c577, c577, c577)
	_ = eval.Rescale(c577, c577)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c545 == nil { c545 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(14), c545)
	if c543 == nil || c543.Level() < c545.Level() {
		c543, _ = eval.MulNew(c545, p921)
	} else {
		_ = eval.Mul(c545, p921, c543)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c514 == nil { c514 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(12), c514)
	if c574 == nil || c574.Level() < c514.Level() {
		c574, _ = eval.MulNew(c514, p923)
	} else {
		_ = eval.Mul(c514, p923, c574)
	}
	_ = eval.Add(c543, c574, c543)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c574 == nil { c574 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(11), c574)
	if c560 == nil || c560.Level() < c574.Level() {
		c560, _ = eval.MulNew(c574, p921)
	} else {
		_ = eval.Mul(c574, p921, c560)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c510 == nil { c510 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(9), c510)
	if c509 == nil || c509.Level() < c510.Level() {
		c509, _ = eval.MulNew(c510, p923)
	} else {
		_ = eval.Mul(c510, p923, c509)
	}
	_ = eval.Add(c560, c509, c560)
	_ = eval.Add(c543, c560, c543)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c560 == nil { c560 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(8), c560)
	if c509 == nil || c509.Level() < c560.Level() {
		c509, _ = eval.MulNew(c560, p921)
	} else {
		_ = eval.Mul(c560, p921, c509)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c565 == nil { c565 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(6), c565)
	if c568 == nil || c568.Level() < c565.Level() {
		c568, _ = eval.MulNew(c565, p923)
	} else {
		_ = eval.Mul(c565, p923, c568)
	}
	_ = eval.Add(c509, c568, c509)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c568 == nil { c568 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(5), c568)
	if c571 == nil || c571.Level() < c568.Level() {
		c571, _ = eval.MulNew(c568, p921)
	} else {
		_ = eval.Mul(c568, p921, c571)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c585 == nil { c585 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(3), c585)
	if c511 == nil || c511.Level() < c585.Level() {
		c511, _ = eval.MulNew(c585, p923)
	} else {
		_ = eval.Mul(c585, p923, c511)
	}
	_ = eval.Add(c571, c511, c571)
	_ = eval.Add(c509, c571, c509)
	_ = eval.Add(c543, c509, c543)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c509 == nil { c509 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(2), c509)
	if c511 == nil || c511.Level() < c509.Level() {
		c511, _ = eval.MulNew(c509, p921)
	} else {
		_ = eval.Mul(c509, p921, c511)
	}
	if c571 == nil || c571.Level() < c577.Level() {
		c571, _ = eval.MulNew(c577, p923)
	} else {
		_ = eval.Mul(c577, p923, c571)
	}
	_ = eval.Add(c511, c571, c511)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c571 == nil { c571 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(1), c571)
	if c541 == nil || c541.Level() < c571.Level() {
		c541, _ = eval.MulNew(c571, p942)
	} else {
		_ = eval.Mul(c571, p942, c541)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c685 == nil { c685 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(4), c685)
	if c521 == nil || c521.Level() < c685.Level() {
		c521, _ = eval.MulNew(c685, p942)
	} else {
		_ = eval.Mul(c685, p942, c521)
	}
	_ = eval.Add(c541, c521, c541)
	_ = eval.Add(c511, c541, c511)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c541 == nil { c541 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(7), c541)
	if c521 == nil || c521.Level() < c541.Level() {
		c521, _ = eval.MulNew(c541, p942)
	} else {
		_ = eval.Mul(c541, p942, c521)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c600 == nil { c600 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(10), c600)
	if c615 == nil || c615.Level() < c600.Level() {
		c615, _ = eval.MulNew(c600, p942)
	} else {
		_ = eval.Mul(c600, p942, c615)
	}
	_ = eval.Add(c521, c615, c521)
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c615 == nil { c615 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(13), c615)
	if c549 == nil || c549.Level() < c615.Level() {
		c549, _ = eval.MulNew(c615, p942)
	} else {
		_ = eval.Mul(c615, p942, c549)
	}
	if lastDecompID != 577 {
		eval.DecomposeNTT(c577.Level(), params.MaxLevelP(), params.PCount(), c577.Value[1], c577.IsNTT, buffDecompQP)
		lastDecompID = 577
	}
	if c588 == nil { c588 = rlwe.NewCiphertext(params, 1, c577.Level()) }
	_ = eval.AutomorphismHoisted(c577.Level(), c577, buffDecompQP, params.GaloisElement(15), c588)
	if c652 == nil || c652.Level() < c588.Level() {
		c652, _ = eval.MulNew(c588, p923)
	} else {
		_ = eval.Mul(c588, p923, c652)
	}
	_ = eval.Add(c549, c652, c549)
	_ = eval.Add(c521, c549, c521)
	_ = eval.Add(c511, c521, c511)
	_ = eval.Add(c543, c511, c543)
	_ = eval.Mul(c685, p955, c685)
	_ = eval.Mul(c568, p957, c568)
	_ = eval.Add(c685, c568, c685)
	_ = eval.Mul(c571, p960, c571)
	if c511 == nil || c511.Level() < c541.Level() {
		c511, _ = eval.MulNew(c541, p963)
	} else {
		_ = eval.Mul(c541, p963, c511)
	}
	_ = eval.Add(c571, c511, c571)
	_ = eval.Add(c685, c571, c685)
	if c571 == nil || c571.Level() < c560.Level() {
		c571, _ = eval.MulNew(c560, p966)
	} else {
		_ = eval.Mul(c560, p966, c571)
	}
	if c568 == nil || c568.Level() < c577.Level() {
		c568, _ = eval.MulNew(c577, p969)
	} else {
		_ = eval.Mul(c577, p969, c568)
	}
	_ = eval.Add(c571, c568, c571)
	_ = eval.Mul(c585, p972, c585)
	_ = eval.Mul(c565, p975, c565)
	_ = eval.Add(c585, c565, c585)
	_ = eval.Mul(c509, p978, c509)
	_ = eval.Add(c585, c509, c585)
	_ = eval.Add(c571, c585, c571)
	_ = eval.Add(c685, c571, c685)
	_ = eval.Rotate(c685, 16, c685)
	_ = eval.Mul(c600, p983, c600)
	_ = eval.Mul(c560, p985, c560)
	_ = eval.Add(c600, c560, c600)
	_ = eval.Mul(c541, p988, c541)
	_ = eval.Mul(c615, p991, c615)
	_ = eval.Add(c541, c615, c541)
	_ = eval.Add(c600, c541, c600)
	_ = eval.Mul(c510, p994, c510)
	_ = eval.Mul(c514, p997, c514)
	_ = eval.Add(c510, c514, c510)
	_ = eval.Mul(c588, p1000, c588)
	_ = eval.Mul(c574, p1003, c574)
	_ = eval.Add(c588, c574, c588)
	_ = eval.Mul(c545, p1006, c545)
	_ = eval.Add(c588, c545, c588)
	_ = eval.Add(c510, c588, c510)
	_ = eval.Add(c600, c510, c600)
	_ = eval.Rotate(c600, 240, c600)
	_ = eval.Add(c685, c600, c685)
	_ = eval.Add(c543, c685, c543)
	_ = eval.Rescale(c543, c543)

	// Store outputs
	encryptedOutputs["classification"] = c543
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
	// MaxLevel=6, LogScale=26
	params, err := hefloat.NewParametersFromLiteral(hefloat.ParametersLiteral{
		LogN:            9,
		LogQ:            []int{29, 26, 26, 26, 26, 26, 26},
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
	ref_509 := append([]float64(nil), values...)
	ref_1003 := make([]float64, len(values))
	ref_1003[245] = 0.04
	ref_1003[247] = -0.04
	ref_1003[248] = 0.04
	ref_997 := make([]float64, len(values))
	ref_997[245] = -0.04
	ref_997[246] = 0.04
	ref_997[248] = -0.04
	ref_997[249] = 0.04
	ref_994 := make([]float64, len(values))
	ref_994[248] = -0.04
	ref_994[249] = 0.04
	ref_991 := make([]float64, len(values))
	ref_991[243] = -0.04
	ref_991[244] = 0.04
	ref_991[246] = -0.04
	ref_991[247] = 0.04
	ref_991[249] = -0.04
	ref_988 := make([]float64, len(values))
	ref_988[249] = -0.04
	ref_978 := make([]float64, len(values))
	ref_978[16] = -0.04
	ref_978[17] = 0.04
	ref_978[19] = -0.04
	ref_978[20] = 0.04
	ref_978[22] = -0.04
	ref_975 := make([]float64, len(values))
	ref_975[17] = -0.04
	ref_975[18] = 0.04
	ref_969 := make([]float64, len(values))
	ref_969[17] = -0.04
	ref_969[18] = 0.04
	ref_969[20] = -0.04
	ref_969[21] = 0.04
	ref_969[23] = -0.04
	ref_969[24] = 0.04
	ref_963 := make([]float64, len(values))
	ref_963[16] = 0.04
	ref_955 := make([]float64, len(values))
	ref_955[16] = 0.04
	ref_955[18] = -0.04
	ref_955[19] = 0.04
	ref_923 := make([]float64, len(values))
	ref_923[0] = -0.04
	ref_923[1] = 0.04
	ref_923[3] = -0.04
	ref_923[4] = 0.04
	ref_923[6] = -0.04
	ref_923[7] = 0.04
	ref_923[9] = -0.04
	ref_1006 := make([]float64, len(values))
	ref_1006[242] = 0.04
	ref_1006[244] = -0.04
	ref_1006[245] = 0.04
	ref_1006[247] = -0.04
	ref_1006[248] = 0.04
	ref_879 := make([]float64, len(values))
	ref_879[0] = -1
	ref_879[1] = -1
	ref_879[2] = -1
	ref_879[3] = -1
	ref_879[4] = -1
	ref_879[7] = -1
	ref_879[8] = -1
	ref_879[9] = -1
	ref_879[10] = -1
	ref_879[11] = -1
	ref_879[14] = -1
	ref_879[15] = -1
	ref_879[16] = -1
	ref_879[17] = -1
	ref_879[18] = -1
	ref_879[21] = -1
	ref_879[22] = -1
	ref_879[23] = -1
	ref_879[24] = -1
	ref_879[25] = -1
	ref_879[28] = -1
	ref_879[29] = -1
	ref_879[30] = -1
	ref_879[31] = -1
	ref_879[32] = -1
	ref_866 := make([]float64, len(values))
	ref_866[191] = 0.25
	ref_866[192] = 0.25
	ref_863 := make([]float64, len(values))
	ref_863[190] = 0.25
	ref_863[191] = 0.25
	ref_860 := make([]float64, len(values))
	ref_860[189] = 0.25
	ref_860[190] = 0.25
	ref_985 := make([]float64, len(values))
	ref_985[248] = 0.04
	ref_858 := make([]float64, len(values))
	ref_858[192] = 0.25
	ref_966 := make([]float64, len(values))
	ref_966[16] = -0.04
	ref_839 := make([]float64, len(values))
	ref_839[172] = 0.25
	ref_839[173] = 0.25
	ref_831 := make([]float64, len(values))
	ref_831[171] = 0.25
	ref_831[172] = 0.25
	ref_829 := make([]float64, len(values))
	ref_829[170] = 0.25
	ref_942 := make([]float64, len(values))
	ref_942[1] = -0.04
	ref_942[2] = 0.04
	ref_942[4] = -0.04
	ref_942[5] = 0.04
	ref_942[7] = -0.04
	ref_942[8] = 0.04
	ref_815 := make([]float64, len(values))
	ref_815[148] = 0.25
	ref_815[149] = 0.25
	ref_812 := make([]float64, len(values))
	ref_812[149] = 0.25
	ref_812[150] = 0.25
	ref_809 := make([]float64, len(values))
	ref_809[150] = 0.25
	ref_809[151] = 0.25
	ref_798 := make([]float64, len(values))
	ref_798[153] = 0.25
	ref_798[154] = 0.25
	ref_793 := make([]float64, len(values))
	ref_793[124] = 0.25
	ref_790 := make([]float64, len(values))
	ref_790[124] = 0.25
	ref_790[125] = 0.25
	ref_787 := make([]float64, len(values))
	ref_787[125] = 0.25
	ref_787[126] = 0.25
	ref_784 := make([]float64, len(values))
	ref_784[126] = 0.25
	ref_784[127] = 0.25
	ref_755 := make([]float64, len(values))
	ref_755[136] = 0.25
	ref_755[137] = 0.25
	ref_750 := make([]float64, len(values))
	ref_750[103] = 0.25
	ref_750[104] = 0.25
	ref_747 := make([]float64, len(values))
	ref_747[104] = 0.25
	ref_747[105] = 0.25
	ref_744 := make([]float64, len(values))
	ref_744[105] = 0.25
	ref_744[106] = 0.25
	ref_881 := make([]float64, len(values))
	ref_881[0] = 8
	ref_881[1] = 8
	ref_881[2] = 8
	ref_881[3] = 8
	ref_881[4] = 8
	ref_881[7] = 8
	ref_881[8] = 8
	ref_881[9] = 8
	ref_881[10] = 8
	ref_881[11] = 8
	ref_881[14] = 8
	ref_881[15] = 8
	ref_881[16] = 8
	ref_881[17] = 8
	ref_881[18] = 8
	ref_881[21] = 8
	ref_881[22] = 8
	ref_881[23] = 8
	ref_881[24] = 8
	ref_881[25] = 8
	ref_881[28] = 8
	ref_881[29] = 8
	ref_881[30] = 8
	ref_881[31] = 8
	ref_881[32] = 8
	ref_627 := make([]float64, len(values))
	ref_627[41] = 0.25
	ref_627[42] = 0.25
	ref_624 := make([]float64, len(values))
	ref_624[42] = 0.25
	ref_624[43] = 0.25
	ref_621 := make([]float64, len(values))
	ref_621[43] = 0.25
	ref_621[44] = 0.25
	ref_738 := make([]float64, len(values))
	ref_738[107] = 0.25
	ref_738[108] = 0.25
	ref_611 := make([]float64, len(values))
	ref_611[20] = 0.25
	ref_611[21] = 0.25
	ref_670 := make([]float64, len(values))
	ref_670[68] = 0.25
	ref_670[69] = 0.25
	ref_1000 := make([]float64, len(values))
	ref_1000[242] = -0.04
	ref_1000[243] = 0.04
	ref_1000[245] = -0.04
	ref_1000[246] = 0.04
	ref_1000[248] = -0.04
	ref_1000[249] = 0.04
	ref_619 := make([]float64, len(values))
	ref_619[44] = 0.25
	ref_619[45] = 0.25
	ref_844 := make([]float64, len(values))
	ref_844[173] = 0.25
	ref_844[174] = 0.25
	ref_590 := make([]float64, len(values))
	ref_590[24] = 0.25
	ref_590[25] = 0.25
	ref_587 := make([]float64, len(values))
	ref_587[25] = 0.25
	ref_587[26] = 0.25
	ref_584 := make([]float64, len(values))
	ref_584[26] = 0.25
	ref_584[27] = 0.25
	ref_757 := make([]float64, len(values))
	ref_757[135] = 0.25
	ref_757[136] = 0.25
	ref_630 := make([]float64, len(values))
	ref_630[40] = 0.25
	ref_630[41] = 0.25
	ref_689 := make([]float64, len(values))
	ref_689[91] = 0.25
	ref_520 := make([]float64, len(values))
	copy(ref_520, []float64{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})
	ref_960 := make([]float64, len(values))
	ref_960[16] = 0.04
	ref_960[18] = -0.04
	ref_960[19] = 0.04
	ref_960[21] = -0.04
	ref_960[22] = 0.04
	ref_579 := make([]float64, len(values))
	ref_579[28] = 0.25
	ref_579[29] = 0.25
	ref_824 := make([]float64, len(values))
	ref_824[154] = 0.25
	ref_824[155] = 0.25
	ref_570 := make([]float64, len(values))
	ref_570[3] = 0.25
	ref_570[4] = 0.25
	ref_697 := make([]float64, len(values))
	ref_697[85] = 0.25
	ref_741 := make([]float64, len(values))
	ref_741[106] = 0.25
	ref_741[107] = 0.25
	ref_614 := make([]float64, len(values))
	ref_614[29] = 0.25
	ref_800 := make([]float64, len(values))
	ref_800[153] = 0.25
	ref_673 := make([]float64, len(values))
	ref_673[62] = 0.25
	ref_735 := make([]float64, len(values))
	ref_735[108] = 0.25
	ref_735[109] = 0.25
	ref_608 := make([]float64, len(values))
	ref_608[19] = 0.25
	ref_608[20] = 0.25
	ref_921 := make([]float64, len(values))
	ref_921[0] = 0.04
	ref_921[2] = -0.04
	ref_921[3] = 0.04
	ref_921[5] = -0.04
	ref_921[6] = 0.04
	ref_921[8] = -0.04
	ref_921[9] = 0.04
	ref_667 := make([]float64, len(values))
	ref_667[67] = 0.25
	ref_667[68] = 0.25
	ref_853 := make([]float64, len(values))
	ref_853[176] = 0.25
	ref_599 := make([]float64, len(values))
	ref_599[21] = 0.25
	ref_599[22] = 0.25
	ref_726 := make([]float64, len(values))
	ref_726[111] = 0.25
	ref_726[112] = 0.25
	ref_581 := make([]float64, len(values))
	ref_581[27] = 0.25
	ref_581[28] = 0.25
	ref_554 := make([]float64, len(values))
	ref_554[0] = 0.25
	ref_983 := make([]float64, len(values))
	ref_983[246] = -0.04
	ref_983[247] = 0.04
	ref_983[249] = -0.04
	ref_729 := make([]float64, len(values))
	ref_729[110] = 0.25
	ref_729[111] = 0.25
	ref_602 := make([]float64, len(values))
	ref_602[17] = 0.25
	ref_602[18] = 0.25
	ref_661 := make([]float64, len(values))
	ref_661[65] = 0.25
	ref_661[66] = 0.25
	ref_847 := make([]float64, len(values))
	ref_847[174] = 0.25
	ref_847[175] = 0.25
	ref_593 := make([]float64, len(values))
	ref_593[23] = 0.25
	ref_593[24] = 0.25
	ref_720 := make([]float64, len(values))
	ref_720[113] = 0.25
	ref_720[114] = 0.25
	ref_818 := make([]float64, len(values))
	ref_818[147] = 0.25
	ref_818[148] = 0.25
	ref_564 := make([]float64, len(values))
	ref_564[1] = 0.25
	ref_564[2] = 0.25
	ref_691 := make([]float64, len(values))
	ref_691[87] = 0.25
	ref_691[88] = 0.25
	ref_732 := make([]float64, len(values))
	ref_732[109] = 0.25
	ref_732[110] = 0.25
	ref_605 := make([]float64, len(values))
	ref_605[18] = 0.25
	ref_605[19] = 0.25
	ref_664 := make([]float64, len(values))
	ref_664[66] = 0.25
	ref_664[67] = 0.25
	ref_850 := make([]float64, len(values))
	ref_850[175] = 0.25
	ref_850[176] = 0.25
	ref_596 := make([]float64, len(values))
	ref_596[22] = 0.25
	ref_596[23] = 0.25
	ref_723 := make([]float64, len(values))
	ref_723[112] = 0.25
	ref_723[113] = 0.25
	ref_772 := make([]float64, len(values))
	ref_772[130] = 0.25
	ref_772[131] = 0.25
	ref_645 := make([]float64, len(values))
	ref_645[47] = 0.25
	ref_645[48] = 0.25
	ref_518 := make([]float64, len(values))
	copy(ref_518, []float64{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})
	ref_763 := make([]float64, len(values))
	ref_763[133] = 0.25
	ref_763[134] = 0.25
	ref_636 := make([]float64, len(values))
	ref_636[39] = 0.25
	ref_957 := make([]float64, len(values))
	ref_957[16] = -0.04
	ref_957[17] = 0.04
	ref_957[19] = -0.04
	ref_576 := make([]float64, len(values))
	ref_576[5] = 0.25
	ref_576[6] = 0.25
	ref_821 := make([]float64, len(values))
	ref_821[147] = 0.25
	ref_567 := make([]float64, len(values))
	ref_567[2] = 0.25
	ref_567[3] = 0.25
	ref_694 := make([]float64, len(values))
	ref_694[86] = 0.25
	ref_694[87] = 0.25
	ref_760 := make([]float64, len(values))
	ref_760[134] = 0.25
	ref_760[135] = 0.25
	ref_633 := make([]float64, len(values))
	ref_633[39] = 0.25
	ref_633[40] = 0.25
	ref_766 := make([]float64, len(values))
	ref_766[132] = 0.25
	ref_766[133] = 0.25
	ref_512 := make([]float64, len(values))
	copy(ref_512, []float64{-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})
	ref_639 := make([]float64, len(values))
	ref_639[45] = 0.25
	ref_639[46] = 0.25
	ref_896 := make([]float64, len(values))
	ref_896[16] = -1
	ref_896[17] = -1
	ref_896[18] = -1
	ref_896[19] = -1
	ref_896[20] = -1
	ref_896[23] = -1
	ref_896[24] = -1
	ref_896[25] = -1
	ref_896[26] = -1
	ref_896[27] = -1
	ref_896[30] = -1
	ref_896[31] = -1
	ref_896[32] = -1
	ref_896[33] = -1
	ref_896[34] = -1
	ref_896[37] = -1
	ref_896[38] = -1
	ref_896[39] = -1
	ref_896[40] = -1
	ref_896[41] = -1
	ref_896[44] = -1
	ref_896[45] = -1
	ref_896[46] = -1
	ref_896[47] = -1
	ref_896[48] = -1
	ref_769 := make([]float64, len(values))
	ref_769[131] = 0.25
	ref_769[132] = 0.25
	ref_642 := make([]float64, len(values))
	ref_642[46] = 0.25
	ref_642[47] = 0.25
	ref_775 := make([]float64, len(values))
	ref_775[129] = 0.25
	ref_775[130] = 0.25
	ref_648 := make([]float64, len(values))
	ref_648[48] = 0.25
	ref_648[49] = 0.25
	ref_834 := make([]float64, len(values))
	ref_834[170] = 0.25
	ref_834[171] = 0.25
	ref_707 := make([]float64, len(values))
	ref_707[88] = 0.25
	ref_707[89] = 0.25
	ref_778 := make([]float64, len(values))
	ref_778[128] = 0.25
	ref_778[129] = 0.25
	ref_651 := make([]float64, len(values))
	ref_651[49] = 0.25
	ref_651[50] = 0.25
	ref_710 := make([]float64, len(values))
	ref_710[89] = 0.25
	ref_710[90] = 0.25
	ref_781 := make([]float64, len(values))
	ref_781[127] = 0.25
	ref_781[128] = 0.25
	ref_527 := make([]float64, len(values))
	copy(ref_527, []float64{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0})
	ref_654 := make([]float64, len(values))
	ref_654[50] = 0.25
	ref_654[51] = 0.25
	ref_713 := make([]float64, len(values))
	ref_713[90] = 0.25
	ref_713[91] = 0.25
	ref_659 := make([]float64, len(values))
	ref_659[64] = 0.25
	ref_659[65] = 0.25
	ref_972 := make([]float64, len(values))
	ref_972[17] = -0.04
	ref_972[18] = 0.04
	ref_972[20] = -0.04
	ref_972[21] = 0.04
	ref_718 := make([]float64, len(values))
	ref_718[114] = 0.25
	ref_803 := make([]float64, len(values))
	ref_803[152] = 0.25
	ref_803[153] = 0.25
	ref_676 := make([]float64, len(values))
	ref_676[62] = 0.25
	ref_676[63] = 0.25
	ref_806 := make([]float64, len(values))
	ref_806[151] = 0.25
	ref_806[152] = 0.25
	ref_552 := make([]float64, len(values))
	ref_552[6] = 0.25
	ref_679 := make([]float64, len(values))
	ref_679[63] = 0.25
	ref_679[64] = 0.25
	ref_557 := make([]float64, len(values))
	ref_557[0] = 0.25
	ref_557[1] = 0.25
	ref_684 := make([]float64, len(values))
	ref_684[68] = 0.25
	ref_573 := make([]float64, len(values))
	ref_573[4] = 0.25
	ref_573[5] = 0.25
	ref_700 := make([]float64, len(values))
	ref_700[85] = 0.25
	ref_700[86] = 0.25
	ref_510 := make([]float64, len(ref_509))
	for i := range ref_510 { ref_510[i] = ref_509[(i + 2 + len(ref_509)) % len(ref_509)] }
	ref_513 := make([]float64, len(ref_510))
	for i := range ref_513 { ref_513[i] = ref_510[i] * ref_512[i] }
	ref_511 := make([]float64, len(ref_509))
	for i := range ref_511 { ref_511[i] = ref_509[(i + 1 + len(ref_509)) % len(ref_509)] }
	ref_514 := make([]float64, len(ref_511))
	for i := range ref_514 { ref_514[i] = ref_511[i] * ref_512[i] }
	ref_515 := make([]float64, len(ref_513))
	for i := range ref_515 { ref_515[i] = ref_513[i] + ref_514[i] }
	ref_516 := make([]float64, len(ref_509))
	for i := range ref_516 { ref_516[i] = ref_509[i] * ref_512[i] }
	ref_517 := make([]float64, len(ref_515))
	for i := range ref_517 { ref_517[i] = ref_515[i] + ref_516[i] }
	ref_519 := make([]float64, len(ref_510))
	for i := range ref_519 { ref_519[i] = ref_510[i] * ref_518[i] }
	ref_521 := make([]float64, len(ref_511))
	for i := range ref_521 { ref_521[i] = ref_511[i] * ref_520[i] }
	ref_522 := make([]float64, len(ref_519))
	for i := range ref_522 { ref_522[i] = ref_519[i] + ref_521[i] }
	ref_523 := make([]float64, len(ref_509))
	for i := range ref_523 { ref_523[i] = ref_509[i] * ref_518[i] }
	ref_524 := make([]float64, len(ref_522))
	for i := range ref_524 { ref_524[i] = ref_522[i] + ref_523[i] }
	ref_525 := make([]float64, len(ref_524))
	for i := range ref_525 { ref_525[i] = ref_524[(i + 16 + len(ref_524)) % len(ref_524)] }
	ref_526 := make([]float64, len(ref_517))
	for i := range ref_526 { ref_526[i] = ref_517[i] + ref_525[i] }
	ref_528 := make([]float64, len(ref_510))
	for i := range ref_528 { ref_528[i] = ref_510[i] * ref_527[i] }
	ref_529 := make([]float64, len(ref_511))
	for i := range ref_529 { ref_529[i] = ref_511[i] * ref_527[i] }
	ref_530 := make([]float64, len(ref_528))
	for i := range ref_530 { ref_530[i] = ref_528[i] + ref_529[i] }
	ref_531 := make([]float64, len(ref_509))
	for i := range ref_531 { ref_531[i] = ref_509[i] * ref_527[i] }
	ref_532 := make([]float64, len(ref_530))
	for i := range ref_532 { ref_532[i] = ref_530[i] + ref_531[i] }
	ref_533 := make([]float64, len(ref_532))
	for i := range ref_533 { ref_533[i] = ref_532[(i + 32 + len(ref_532)) % len(ref_532)] }
	ref_534 := make([]float64, len(ref_526))
	for i := range ref_534 { ref_534[i] = ref_526[i] + ref_533[i] }
	ref_535 := ref_534
	ref_536 := make([]float64, len(ref_535))
	for i := range ref_536 { ref_536[i] = ref_535[i] * ref_535[i] }
	ref_537 := make([]float64, len(ref_536))
	for i := range ref_537 { ref_537[i] = ref_536[(i + 7 + len(ref_536)) % len(ref_536)] }
	ref_553 := make([]float64, len(ref_537))
	for i := range ref_553 { ref_553[i] = ref_537[i] * ref_552[i] }
	ref_555 := make([]float64, len(ref_536))
	for i := range ref_555 { ref_555[i] = ref_536[i] * ref_554[i] }
	ref_556 := make([]float64, len(ref_553))
	for i := range ref_556 { ref_556[i] = ref_553[i] + ref_555[i] }
	ref_538 := make([]float64, len(ref_536))
	for i := range ref_538 { ref_538[i] = ref_536[(i + 1 + len(ref_536)) % len(ref_536)] }
	ref_558 := make([]float64, len(ref_538))
	for i := range ref_558 { ref_558[i] = ref_538[i] * ref_557[i] }
	ref_539 := make([]float64, len(ref_536))
	for i := range ref_539 { ref_539[i] = ref_536[(i + 14 + len(ref_536)) % len(ref_536)] }
	ref_560 := make([]float64, len(ref_539))
	for i := range ref_560 { ref_560[i] = ref_539[i] * ref_554[i] }
	ref_1012 := make([]float64, len(ref_558))
	for i := range ref_1012 { ref_1012[i] = ref_558[i] + ref_560[i] }
	ref_1024 := make([]float64, len(ref_556))
	for i := range ref_1024 { ref_1024[i] = ref_556[i] + ref_1012[i] }
	ref_540 := make([]float64, len(ref_536))
	for i := range ref_540 { ref_540[i] = ref_536[(i + 15 + len(ref_536)) % len(ref_536)] }
	ref_562 := make([]float64, len(ref_540))
	for i := range ref_562 { ref_562[i] = ref_540[i] * ref_557[i] }
	ref_541 := make([]float64, len(ref_536))
	for i := range ref_541 { ref_541[i] = ref_536[(i + 2 + len(ref_536)) % len(ref_536)] }
	ref_565 := make([]float64, len(ref_541))
	for i := range ref_565 { ref_565[i] = ref_541[i] * ref_564[i] }
	ref_1018 := make([]float64, len(ref_562))
	for i := range ref_1018 { ref_1018[i] = ref_562[i] + ref_565[i] }
	ref_542 := make([]float64, len(ref_536))
	for i := range ref_542 { ref_542[i] = ref_536[(i + 3 + len(ref_536)) % len(ref_536)] }
	ref_568 := make([]float64, len(ref_542))
	for i := range ref_568 { ref_568[i] = ref_542[i] * ref_567[i] }
	ref_543 := make([]float64, len(ref_536))
	for i := range ref_543 { ref_543[i] = ref_536[(i + 4 + len(ref_536)) % len(ref_536)] }
	ref_571 := make([]float64, len(ref_543))
	for i := range ref_571 { ref_571[i] = ref_543[i] * ref_570[i] }
	ref_1028 := make([]float64, len(ref_568))
	for i := range ref_1028 { ref_1028[i] = ref_568[i] + ref_571[i] }
	ref_544 := make([]float64, len(ref_536))
	for i := range ref_544 { ref_544[i] = ref_536[(i + 5 + len(ref_536)) % len(ref_536)] }
	ref_574 := make([]float64, len(ref_544))
	for i := range ref_574 { ref_574[i] = ref_544[i] * ref_573[i] }
	ref_545 := make([]float64, len(ref_536))
	for i := range ref_545 { ref_545[i] = ref_536[(i + 6 + len(ref_536)) % len(ref_536)] }
	ref_577 := make([]float64, len(ref_545))
	for i := range ref_577 { ref_577[i] = ref_545[i] * ref_576[i] }
	ref_1038 := make([]float64, len(ref_574))
	for i := range ref_1038 { ref_1038[i] = ref_574[i] + ref_577[i] }
	ref_1039 := make([]float64, len(ref_1028))
	for i := range ref_1039 { ref_1039[i] = ref_1028[i] + ref_1038[i] }
	ref_1037 := make([]float64, len(ref_1018))
	for i := range ref_1037 { ref_1037[i] = ref_1018[i] + ref_1039[i] }
	ref_1035 := make([]float64, len(ref_1024))
	for i := range ref_1035 { ref_1035[i] = ref_1024[i] + ref_1037[i] }
	ref_546 := make([]float64, len(ref_536))
	for i := range ref_546 { ref_546[i] = ref_536[(i + 11 + len(ref_536)) % len(ref_536)] }
	ref_580 := make([]float64, len(ref_546))
	for i := range ref_580 { ref_580[i] = ref_546[i] * ref_579[i] }
	ref_547 := make([]float64, len(ref_536))
	for i := range ref_547 { ref_547[i] = ref_536[(i + 10 + len(ref_536)) % len(ref_536)] }
	ref_582 := make([]float64, len(ref_547))
	for i := range ref_582 { ref_582[i] = ref_547[i] * ref_581[i] }
	ref_583 := make([]float64, len(ref_580))
	for i := range ref_583 { ref_583[i] = ref_580[i] + ref_582[i] }
	ref_548 := make([]float64, len(ref_536))
	for i := range ref_548 { ref_548[i] = ref_536[(i + 9 + len(ref_536)) % len(ref_536)] }
	ref_585 := make([]float64, len(ref_548))
	for i := range ref_585 { ref_585[i] = ref_548[i] * ref_584[i] }
	ref_549 := make([]float64, len(ref_536))
	for i := range ref_549 { ref_549[i] = ref_536[(i + 8 + len(ref_536)) % len(ref_536)] }
	ref_588 := make([]float64, len(ref_549))
	for i := range ref_588 { ref_588[i] = ref_549[i] * ref_587[i] }
	ref_1040 := make([]float64, len(ref_585))
	for i := range ref_1040 { ref_1040[i] = ref_585[i] + ref_588[i] }
	ref_1052 := make([]float64, len(ref_583))
	for i := range ref_1052 { ref_1052[i] = ref_583[i] + ref_1040[i] }
	ref_591 := make([]float64, len(ref_537))
	for i := range ref_591 { ref_591[i] = ref_537[i] * ref_590[i] }
	ref_594 := make([]float64, len(ref_545))
	for i := range ref_594 { ref_594[i] = ref_545[i] * ref_593[i] }
	ref_1046 := make([]float64, len(ref_591))
	for i := range ref_1046 { ref_1046[i] = ref_591[i] + ref_594[i] }
	ref_597 := make([]float64, len(ref_544))
	for i := range ref_597 { ref_597[i] = ref_544[i] * ref_596[i] }
	ref_600 := make([]float64, len(ref_543))
	for i := range ref_600 { ref_600[i] = ref_543[i] * ref_599[i] }
	ref_1056 := make([]float64, len(ref_597))
	for i := range ref_1056 { ref_1056[i] = ref_597[i] + ref_600[i] }
	ref_1074 := make([]float64, len(ref_1046))
	for i := range ref_1074 { ref_1074[i] = ref_1046[i] + ref_1056[i] }
	ref_1088 := make([]float64, len(ref_1052))
	for i := range ref_1088 { ref_1088[i] = ref_1052[i] + ref_1074[i] }
	ref_603 := make([]float64, len(ref_536))
	for i := range ref_603 { ref_603[i] = ref_536[i] * ref_602[i] }
	ref_606 := make([]float64, len(ref_538))
	for i := range ref_606 { ref_606[i] = ref_538[i] * ref_605[i] }
	ref_1066 := make([]float64, len(ref_603))
	for i := range ref_1066 { ref_1066[i] = ref_603[i] + ref_606[i] }
	ref_609 := make([]float64, len(ref_541))
	for i := range ref_609 { ref_609[i] = ref_541[i] * ref_608[i] }
	ref_612 := make([]float64, len(ref_542))
	for i := range ref_612 { ref_612[i] = ref_542[i] * ref_611[i] }
	ref_1080 := make([]float64, len(ref_609))
	for i := range ref_1080 { ref_1080[i] = ref_609[i] + ref_612[i] }
	ref_550 := make([]float64, len(ref_536))
	for i := range ref_550 { ref_550[i] = ref_536[(i + 12 + len(ref_536)) % len(ref_536)] }
	ref_615 := make([]float64, len(ref_550))
	for i := range ref_615 { ref_615[i] = ref_550[i] * ref_614[i] }
	ref_1086 := make([]float64, len(ref_1080))
	for i := range ref_1086 { ref_1086[i] = ref_1080[i] + ref_615[i] }
	ref_1087 := make([]float64, len(ref_1066))
	for i := range ref_1087 { ref_1087[i] = ref_1066[i] + ref_1086[i] }
	ref_1089 := make([]float64, len(ref_1088))
	for i := range ref_1089 { ref_1089[i] = ref_1088[i] + ref_1087[i] }
	ref_617 := make([]float64, len(ref_1089))
	for i := range ref_617 { ref_617[i] = ref_1089[(i + 16 + len(ref_1089)) % len(ref_1089)] }
	ref_618 := make([]float64, len(ref_1035))
	for i := range ref_618 { ref_618[i] = ref_1035[i] + ref_617[i] }
	ref_620 := make([]float64, len(ref_548))
	for i := range ref_620 { ref_620[i] = ref_548[i] * ref_619[i] }
	ref_622 := make([]float64, len(ref_549))
	for i := range ref_622 { ref_622[i] = ref_549[i] * ref_621[i] }
	ref_623 := make([]float64, len(ref_620))
	for i := range ref_623 { ref_623[i] = ref_620[i] + ref_622[i] }
	ref_625 := make([]float64, len(ref_537))
	for i := range ref_625 { ref_625[i] = ref_537[i] * ref_624[i] }
	ref_628 := make([]float64, len(ref_545))
	for i := range ref_628 { ref_628[i] = ref_545[i] * ref_627[i] }
	ref_1090 := make([]float64, len(ref_625))
	for i := range ref_1090 { ref_1090[i] = ref_625[i] + ref_628[i] }
	ref_1102 := make([]float64, len(ref_623))
	for i := range ref_1102 { ref_1102[i] = ref_623[i] + ref_1090[i] }
	ref_631 := make([]float64, len(ref_544))
	for i := range ref_631 { ref_631[i] = ref_544[i] * ref_630[i] }
	ref_634 := make([]float64, len(ref_543))
	for i := range ref_634 { ref_634[i] = ref_543[i] * ref_633[i] }
	ref_1096 := make([]float64, len(ref_631))
	for i := range ref_1096 { ref_1096[i] = ref_631[i] + ref_634[i] }
	ref_637 := make([]float64, len(ref_542))
	for i := range ref_637 { ref_637[i] = ref_542[i] * ref_636[i] }
	ref_640 := make([]float64, len(ref_547))
	for i := range ref_640 { ref_640[i] = ref_547[i] * ref_639[i] }
	ref_1106 := make([]float64, len(ref_637))
	for i := range ref_1106 { ref_1106[i] = ref_637[i] + ref_640[i] }
	ref_1124 := make([]float64, len(ref_1096))
	for i := range ref_1124 { ref_1124[i] = ref_1096[i] + ref_1106[i] }
	ref_1138 := make([]float64, len(ref_1102))
	for i := range ref_1138 { ref_1138[i] = ref_1102[i] + ref_1124[i] }
	ref_643 := make([]float64, len(ref_546))
	for i := range ref_643 { ref_643[i] = ref_546[i] * ref_642[i] }
	ref_646 := make([]float64, len(ref_550))
	for i := range ref_646 { ref_646[i] = ref_550[i] * ref_645[i] }
	ref_1116 := make([]float64, len(ref_643))
	for i := range ref_1116 { ref_1116[i] = ref_643[i] + ref_646[i] }
	ref_551 := make([]float64, len(ref_536))
	for i := range ref_551 { ref_551[i] = ref_536[(i + 13 + len(ref_536)) % len(ref_536)] }
	ref_649 := make([]float64, len(ref_551))
	for i := range ref_649 { ref_649[i] = ref_551[i] * ref_648[i] }
	ref_652 := make([]float64, len(ref_539))
	for i := range ref_652 { ref_652[i] = ref_539[i] * ref_651[i] }
	ref_1130 := make([]float64, len(ref_649))
	for i := range ref_1130 { ref_1130[i] = ref_649[i] + ref_652[i] }
	ref_655 := make([]float64, len(ref_540))
	for i := range ref_655 { ref_655[i] = ref_540[i] * ref_654[i] }
	ref_1136 := make([]float64, len(ref_1130))
	for i := range ref_1136 { ref_1136[i] = ref_1130[i] + ref_655[i] }
	ref_1137 := make([]float64, len(ref_1116))
	for i := range ref_1137 { ref_1137[i] = ref_1116[i] + ref_1136[i] }
	ref_1139 := make([]float64, len(ref_1138))
	for i := range ref_1139 { ref_1139[i] = ref_1138[i] + ref_1137[i] }
	ref_657 := make([]float64, len(ref_1139))
	for i := range ref_657 { ref_657[i] = ref_1139[(i + 32 + len(ref_1139)) % len(ref_1139)] }
	ref_660 := make([]float64, len(ref_546))
	for i := range ref_660 { ref_660[i] = ref_546[i] * ref_659[i] }
	ref_662 := make([]float64, len(ref_550))
	for i := range ref_662 { ref_662[i] = ref_550[i] * ref_661[i] }
	ref_663 := make([]float64, len(ref_660))
	for i := range ref_663 { ref_663[i] = ref_660[i] + ref_662[i] }
	ref_665 := make([]float64, len(ref_551))
	for i := range ref_665 { ref_665[i] = ref_551[i] * ref_664[i] }
	ref_668 := make([]float64, len(ref_539))
	for i := range ref_668 { ref_668[i] = ref_539[i] * ref_667[i] }
	ref_1140 := make([]float64, len(ref_665))
	for i := range ref_1140 { ref_1140[i] = ref_665[i] + ref_668[i] }
	ref_1152 := make([]float64, len(ref_663))
	for i := range ref_1152 { ref_1152[i] = ref_663[i] + ref_1140[i] }
	ref_671 := make([]float64, len(ref_540))
	for i := range ref_671 { ref_671[i] = ref_540[i] * ref_670[i] }
	ref_674 := make([]float64, len(ref_549))
	for i := range ref_674 { ref_674[i] = ref_549[i] * ref_673[i] }
	ref_1146 := make([]float64, len(ref_671))
	for i := range ref_1146 { ref_1146[i] = ref_671[i] + ref_674[i] }
	ref_677 := make([]float64, len(ref_548))
	for i := range ref_677 { ref_677[i] = ref_548[i] * ref_676[i] }
	ref_680 := make([]float64, len(ref_547))
	for i := range ref_680 { ref_680[i] = ref_547[i] * ref_679[i] }
	ref_1156 := make([]float64, len(ref_677))
	for i := range ref_1156 { ref_1156[i] = ref_677[i] + ref_680[i] }
	ref_682 := make([]float64, len(ref_536))
	for i := range ref_682 { ref_682[i] = ref_536[i] * ref_667[i] }
	ref_685 := make([]float64, len(ref_538))
	for i := range ref_685 { ref_685[i] = ref_538[i] * ref_684[i] }
	ref_1166 := make([]float64, len(ref_682))
	for i := range ref_1166 { ref_1166[i] = ref_682[i] + ref_685[i] }
	ref_1167 := make([]float64, len(ref_1156))
	for i := range ref_1167 { ref_1167[i] = ref_1156[i] + ref_1166[i] }
	ref_1165 := make([]float64, len(ref_1146))
	for i := range ref_1165 { ref_1165[i] = ref_1146[i] + ref_1167[i] }
	ref_1163 := make([]float64, len(ref_1152))
	for i := range ref_1163 { ref_1163[i] = ref_1152[i] + ref_1165[i] }
	ref_687 := make([]float64, len(ref_1163))
	for i := range ref_687 { ref_687[i] = ref_1163[(i + 48 + len(ref_1163)) % len(ref_1163)] }
	ref_1168 := make([]float64, len(ref_657))
	for i := range ref_1168 { ref_1168[i] = ref_657[i] + ref_687[i] }
	ref_1306 := make([]float64, len(ref_618))
	for i := range ref_1306 { ref_1306[i] = ref_618[i] + ref_1168[i] }
	ref_690 := make([]float64, len(ref_545))
	for i := range ref_690 { ref_690[i] = ref_545[i] * ref_689[i] }
	ref_692 := make([]float64, len(ref_541))
	for i := range ref_692 { ref_692[i] = ref_541[i] * ref_691[i] }
	ref_693 := make([]float64, len(ref_690))
	for i := range ref_693 { ref_693[i] = ref_690[i] + ref_692[i] }
	ref_695 := make([]float64, len(ref_540))
	for i := range ref_695 { ref_695[i] = ref_540[i] * ref_694[i] }
	ref_698 := make([]float64, len(ref_551))
	for i := range ref_698 { ref_698[i] = ref_551[i] * ref_697[i] }
	ref_1170 := make([]float64, len(ref_695))
	for i := range ref_1170 { ref_1170[i] = ref_695[i] + ref_698[i] }
	ref_1182 := make([]float64, len(ref_693))
	for i := range ref_1182 { ref_1182[i] = ref_693[i] + ref_1170[i] }
	ref_701 := make([]float64, len(ref_536))
	for i := range ref_701 { ref_701[i] = ref_536[i] * ref_700[i] }
	ref_703 := make([]float64, len(ref_539))
	for i := range ref_703 { ref_703[i] = ref_539[i] * ref_700[i] }
	ref_1176 := make([]float64, len(ref_701))
	for i := range ref_1176 { ref_1176[i] = ref_701[i] + ref_703[i] }
	ref_705 := make([]float64, len(ref_538))
	for i := range ref_705 { ref_705[i] = ref_538[i] * ref_694[i] }
	ref_708 := make([]float64, len(ref_542))
	for i := range ref_708 { ref_708[i] = ref_542[i] * ref_707[i] }
	ref_1186 := make([]float64, len(ref_705))
	for i := range ref_1186 { ref_1186[i] = ref_705[i] + ref_708[i] }
	ref_711 := make([]float64, len(ref_543))
	for i := range ref_711 { ref_711[i] = ref_543[i] * ref_710[i] }
	ref_714 := make([]float64, len(ref_544))
	for i := range ref_714 { ref_714[i] = ref_544[i] * ref_713[i] }
	ref_1196 := make([]float64, len(ref_711))
	for i := range ref_1196 { ref_1196[i] = ref_711[i] + ref_714[i] }
	ref_1197 := make([]float64, len(ref_1186))
	for i := range ref_1197 { ref_1197[i] = ref_1186[i] + ref_1196[i] }
	ref_1195 := make([]float64, len(ref_1176))
	for i := range ref_1195 { ref_1195[i] = ref_1176[i] + ref_1197[i] }
	ref_1193 := make([]float64, len(ref_1182))
	for i := range ref_1193 { ref_1193[i] = ref_1182[i] + ref_1195[i] }
	ref_716 := make([]float64, len(ref_1193))
	for i := range ref_716 { ref_716[i] = ref_1193[(i + 64 + len(ref_1193)) % len(ref_1193)] }
	ref_719 := make([]float64, len(ref_546))
	for i := range ref_719 { ref_719[i] = ref_546[i] * ref_718[i] }
	ref_721 := make([]float64, len(ref_547))
	for i := range ref_721 { ref_721[i] = ref_547[i] * ref_720[i] }
	ref_722 := make([]float64, len(ref_719))
	for i := range ref_722 { ref_722[i] = ref_719[i] + ref_721[i] }
	ref_724 := make([]float64, len(ref_548))
	for i := range ref_724 { ref_724[i] = ref_548[i] * ref_723[i] }
	ref_727 := make([]float64, len(ref_549))
	for i := range ref_727 { ref_727[i] = ref_549[i] * ref_726[i] }
	ref_1200 := make([]float64, len(ref_724))
	for i := range ref_1200 { ref_1200[i] = ref_724[i] + ref_727[i] }
	ref_1212 := make([]float64, len(ref_722))
	for i := range ref_1212 { ref_1212[i] = ref_722[i] + ref_1200[i] }
	ref_730 := make([]float64, len(ref_537))
	for i := range ref_730 { ref_730[i] = ref_537[i] * ref_729[i] }
	ref_733 := make([]float64, len(ref_545))
	for i := range ref_733 { ref_733[i] = ref_545[i] * ref_732[i] }
	ref_1206 := make([]float64, len(ref_730))
	for i := range ref_1206 { ref_1206[i] = ref_730[i] + ref_733[i] }
	ref_736 := make([]float64, len(ref_544))
	for i := range ref_736 { ref_736[i] = ref_544[i] * ref_735[i] }
	ref_739 := make([]float64, len(ref_543))
	for i := range ref_739 { ref_739[i] = ref_543[i] * ref_738[i] }
	ref_1216 := make([]float64, len(ref_736))
	for i := range ref_1216 { ref_1216[i] = ref_736[i] + ref_739[i] }
	ref_1234 := make([]float64, len(ref_1206))
	for i := range ref_1234 { ref_1234[i] = ref_1206[i] + ref_1216[i] }
	ref_742 := make([]float64, len(ref_542))
	for i := range ref_742 { ref_742[i] = ref_542[i] * ref_741[i] }
	ref_745 := make([]float64, len(ref_541))
	for i := range ref_745 { ref_745[i] = ref_541[i] * ref_744[i] }
	ref_1226 := make([]float64, len(ref_742))
	for i := range ref_1226 { ref_1226[i] = ref_742[i] + ref_745[i] }
	ref_748 := make([]float64, len(ref_538))
	for i := range ref_748 { ref_748[i] = ref_538[i] * ref_747[i] }
	ref_751 := make([]float64, len(ref_536))
	for i := range ref_751 { ref_751[i] = ref_536[i] * ref_750[i] }
	ref_1240 := make([]float64, len(ref_748))
	for i := range ref_1240 { ref_1240[i] = ref_748[i] + ref_751[i] }
	ref_1241 := make([]float64, len(ref_1226))
	for i := range ref_1241 { ref_1241[i] = ref_1226[i] + ref_1240[i] }
	ref_1239 := make([]float64, len(ref_1234))
	for i := range ref_1239 { ref_1239[i] = ref_1234[i] + ref_1241[i] }
	ref_1237 := make([]float64, len(ref_1212))
	for i := range ref_1237 { ref_1237[i] = ref_1212[i] + ref_1239[i] }
	ref_753 := make([]float64, len(ref_1237))
	for i := range ref_753 { ref_753[i] = ref_1237[(i + 80 + len(ref_1237)) % len(ref_1237)] }
	ref_1244 := make([]float64, len(ref_716))
	for i := range ref_1244 { ref_1244[i] = ref_716[i] + ref_753[i] }
	ref_756 := make([]float64, len(ref_540))
	for i := range ref_756 { ref_756[i] = ref_540[i] * ref_755[i] }
	ref_758 := make([]float64, len(ref_539))
	for i := range ref_758 { ref_758[i] = ref_539[i] * ref_757[i] }
	ref_759 := make([]float64, len(ref_756))
	for i := range ref_759 { ref_759[i] = ref_756[i] + ref_758[i] }
	ref_761 := make([]float64, len(ref_551))
	for i := range ref_761 { ref_761[i] = ref_551[i] * ref_760[i] }
	ref_764 := make([]float64, len(ref_550))
	for i := range ref_764 { ref_764[i] = ref_550[i] * ref_763[i] }
	ref_1246 := make([]float64, len(ref_761))
	for i := range ref_1246 { ref_1246[i] = ref_761[i] + ref_764[i] }
	ref_1258 := make([]float64, len(ref_759))
	for i := range ref_1258 { ref_1258[i] = ref_759[i] + ref_1246[i] }
	ref_767 := make([]float64, len(ref_546))
	for i := range ref_767 { ref_767[i] = ref_546[i] * ref_766[i] }
	ref_770 := make([]float64, len(ref_547))
	for i := range ref_770 { ref_770[i] = ref_547[i] * ref_769[i] }
	ref_1252 := make([]float64, len(ref_767))
	for i := range ref_1252 { ref_1252[i] = ref_767[i] + ref_770[i] }
	ref_773 := make([]float64, len(ref_548))
	for i := range ref_773 { ref_773[i] = ref_548[i] * ref_772[i] }
	ref_776 := make([]float64, len(ref_549))
	for i := range ref_776 { ref_776[i] = ref_549[i] * ref_775[i] }
	ref_1262 := make([]float64, len(ref_773))
	for i := range ref_1262 { ref_1262[i] = ref_773[i] + ref_776[i] }
	ref_1280 := make([]float64, len(ref_1252))
	for i := range ref_1280 { ref_1280[i] = ref_1252[i] + ref_1262[i] }
	ref_1294 := make([]float64, len(ref_1258))
	for i := range ref_1294 { ref_1294[i] = ref_1258[i] + ref_1280[i] }
	ref_779 := make([]float64, len(ref_537))
	for i := range ref_779 { ref_779[i] = ref_537[i] * ref_778[i] }
	ref_782 := make([]float64, len(ref_545))
	for i := range ref_782 { ref_782[i] = ref_545[i] * ref_781[i] }
	ref_1272 := make([]float64, len(ref_779))
	for i := range ref_1272 { ref_1272[i] = ref_779[i] + ref_782[i] }
	ref_785 := make([]float64, len(ref_544))
	for i := range ref_785 { ref_785[i] = ref_544[i] * ref_784[i] }
	ref_788 := make([]float64, len(ref_543))
	for i := range ref_788 { ref_788[i] = ref_543[i] * ref_787[i] }
	ref_1286 := make([]float64, len(ref_785))
	for i := range ref_1286 { ref_1286[i] = ref_785[i] + ref_788[i] }
	ref_791 := make([]float64, len(ref_542))
	for i := range ref_791 { ref_791[i] = ref_542[i] * ref_790[i] }
	ref_794 := make([]float64, len(ref_541))
	for i := range ref_794 { ref_794[i] = ref_541[i] * ref_793[i] }
	ref_1300 := make([]float64, len(ref_791))
	for i := range ref_1300 { ref_1300[i] = ref_791[i] + ref_794[i] }
	ref_1301 := make([]float64, len(ref_1286))
	for i := range ref_1301 { ref_1301[i] = ref_1286[i] + ref_1300[i] }
	ref_1299 := make([]float64, len(ref_1272))
	for i := range ref_1299 { ref_1299[i] = ref_1272[i] + ref_1301[i] }
	ref_1297 := make([]float64, len(ref_1294))
	for i := range ref_1297 { ref_1297[i] = ref_1294[i] + ref_1299[i] }
	ref_796 := make([]float64, len(ref_1297))
	for i := range ref_796 { ref_796[i] = ref_1297[(i + 96 + len(ref_1297)) % len(ref_1297)] }
	ref_1387 := make([]float64, len(ref_1244))
	for i := range ref_1387 { ref_1387[i] = ref_1244[i] + ref_796[i] }
	ref_799 := make([]float64, len(ref_539))
	for i := range ref_799 { ref_799[i] = ref_539[i] * ref_798[i] }
	ref_801 := make([]float64, len(ref_536))
	for i := range ref_801 { ref_801[i] = ref_536[i] * ref_800[i] }
	ref_802 := make([]float64, len(ref_799))
	for i := range ref_802 { ref_802[i] = ref_799[i] + ref_801[i] }
	ref_804 := make([]float64, len(ref_551))
	for i := range ref_804 { ref_804[i] = ref_551[i] * ref_803[i] }
	ref_807 := make([]float64, len(ref_550))
	for i := range ref_807 { ref_807[i] = ref_550[i] * ref_806[i] }
	ref_1308 := make([]float64, len(ref_804))
	for i := range ref_1308 { ref_1308[i] = ref_804[i] + ref_807[i] }
	ref_1320 := make([]float64, len(ref_802))
	for i := range ref_1320 { ref_1320[i] = ref_802[i] + ref_1308[i] }
	ref_810 := make([]float64, len(ref_546))
	for i := range ref_810 { ref_810[i] = ref_546[i] * ref_809[i] }
	ref_813 := make([]float64, len(ref_547))
	for i := range ref_813 { ref_813[i] = ref_547[i] * ref_812[i] }
	ref_1314 := make([]float64, len(ref_810))
	for i := range ref_1314 { ref_1314[i] = ref_810[i] + ref_813[i] }
	ref_816 := make([]float64, len(ref_548))
	for i := range ref_816 { ref_816[i] = ref_548[i] * ref_815[i] }
	ref_819 := make([]float64, len(ref_549))
	for i := range ref_819 { ref_819[i] = ref_549[i] * ref_818[i] }
	ref_1324 := make([]float64, len(ref_816))
	for i := range ref_1324 { ref_1324[i] = ref_816[i] + ref_819[i] }
	ref_822 := make([]float64, len(ref_537))
	for i := range ref_822 { ref_822[i] = ref_537[i] * ref_821[i] }
	ref_825 := make([]float64, len(ref_540))
	for i := range ref_825 { ref_825[i] = ref_540[i] * ref_824[i] }
	ref_1334 := make([]float64, len(ref_822))
	for i := range ref_1334 { ref_1334[i] = ref_822[i] + ref_825[i] }
	ref_1335 := make([]float64, len(ref_1324))
	for i := range ref_1335 { ref_1335[i] = ref_1324[i] + ref_1334[i] }
	ref_1333 := make([]float64, len(ref_1314))
	for i := range ref_1333 { ref_1333[i] = ref_1314[i] + ref_1335[i] }
	ref_1331 := make([]float64, len(ref_1320))
	for i := range ref_1331 { ref_1331[i] = ref_1320[i] + ref_1333[i] }
	ref_827 := make([]float64, len(ref_1331))
	for i := range ref_827 { ref_827[i] = ref_1331[(i + 112 + len(ref_1331)) % len(ref_1331)] }
	ref_830 := make([]float64, len(ref_550))
	for i := range ref_830 { ref_830[i] = ref_550[i] * ref_829[i] }
	ref_832 := make([]float64, len(ref_536))
	for i := range ref_832 { ref_832[i] = ref_536[i] * ref_831[i] }
	ref_833 := make([]float64, len(ref_830))
	for i := range ref_833 { ref_833[i] = ref_830[i] + ref_832[i] }
	ref_835 := make([]float64, len(ref_551))
	for i := range ref_835 { ref_835[i] = ref_551[i] * ref_834[i] }
	ref_837 := make([]float64, len(ref_539))
	for i := range ref_837 { ref_837[i] = ref_539[i] * ref_831[i] }
	ref_1340 := make([]float64, len(ref_835))
	for i := range ref_1340 { ref_1340[i] = ref_835[i] + ref_837[i] }
	ref_1352 := make([]float64, len(ref_833))
	for i := range ref_1352 { ref_1352[i] = ref_833[i] + ref_1340[i] }
	ref_840 := make([]float64, len(ref_538))
	for i := range ref_840 { ref_840[i] = ref_538[i] * ref_839[i] }
	ref_842 := make([]float64, len(ref_540))
	for i := range ref_842 { ref_842[i] = ref_540[i] * ref_839[i] }
	ref_1346 := make([]float64, len(ref_840))
	for i := range ref_1346 { ref_1346[i] = ref_840[i] + ref_842[i] }
	ref_845 := make([]float64, len(ref_541))
	for i := range ref_845 { ref_845[i] = ref_541[i] * ref_844[i] }
	ref_848 := make([]float64, len(ref_542))
	for i := range ref_848 { ref_848[i] = ref_542[i] * ref_847[i] }
	ref_1356 := make([]float64, len(ref_845))
	for i := range ref_1356 { ref_1356[i] = ref_845[i] + ref_848[i] }
	ref_851 := make([]float64, len(ref_543))
	for i := range ref_851 { ref_851[i] = ref_543[i] * ref_850[i] }
	ref_854 := make([]float64, len(ref_544))
	for i := range ref_854 { ref_854[i] = ref_544[i] * ref_853[i] }
	ref_1366 := make([]float64, len(ref_851))
	for i := range ref_1366 { ref_1366[i] = ref_851[i] + ref_854[i] }
	ref_1367 := make([]float64, len(ref_1356))
	for i := range ref_1367 { ref_1367[i] = ref_1356[i] + ref_1366[i] }
	ref_1365 := make([]float64, len(ref_1346))
	for i := range ref_1365 { ref_1365[i] = ref_1346[i] + ref_1367[i] }
	ref_1363 := make([]float64, len(ref_1352))
	for i := range ref_1363 { ref_1363[i] = ref_1352[i] + ref_1365[i] }
	ref_856 := make([]float64, len(ref_1363))
	for i := range ref_856 { ref_856[i] = ref_1363[(i + 128 + len(ref_1363)) % len(ref_1363)] }
	ref_859 := make([]float64, len(ref_542))
	for i := range ref_859 { ref_859[i] = ref_542[i] * ref_858[i] }
	ref_861 := make([]float64, len(ref_536))
	for i := range ref_861 { ref_861[i] = ref_536[i] * ref_860[i] }
	ref_862 := make([]float64, len(ref_859))
	for i := range ref_862 { ref_862[i] = ref_859[i] + ref_861[i] }
	ref_864 := make([]float64, len(ref_538))
	for i := range ref_864 { ref_864[i] = ref_538[i] * ref_863[i] }
	ref_867 := make([]float64, len(ref_541))
	for i := range ref_867 { ref_867[i] = ref_541[i] * ref_866[i] }
	ref_1377 := make([]float64, len(ref_864))
	for i := range ref_1377 { ref_1377[i] = ref_864[i] + ref_867[i] }
	ref_1378 := make([]float64, len(ref_862))
	for i := range ref_1378 { ref_1378[i] = ref_862[i] + ref_1377[i] }
	ref_869 := make([]float64, len(ref_1378))
	for i := range ref_869 { ref_869[i] = ref_1378[(i + 144 + len(ref_1378)) % len(ref_1378)] }
	ref_1383 := make([]float64, len(ref_856))
	for i := range ref_1383 { ref_1383[i] = ref_856[i] + ref_869[i] }
	ref_1386 := make([]float64, len(ref_827))
	for i := range ref_1386 { ref_1386[i] = ref_827[i] + ref_1383[i] }
	ref_1388 := make([]float64, len(ref_1387))
	for i := range ref_1388 { ref_1388[i] = ref_1387[i] + ref_1386[i] }
	ref_1380 := make([]float64, len(ref_1306))
	for i := range ref_1380 { ref_1380[i] = ref_1306[i] + ref_1388[i] }
	ref_871 := ref_1380
	ref_872 := make([]float64, len(ref_871))
	for i := range ref_872 { ref_872[i] = ref_871[(i + 9 + len(ref_871)) % len(ref_871)] }
	ref_880 := make([]float64, len(ref_872))
	for i := range ref_880 { ref_880[i] = ref_872[i] * ref_879[i] }
	ref_873 := make([]float64, len(ref_871))
	for i := range ref_873 { ref_873[i] = ref_871[(i + 8 + len(ref_871)) % len(ref_871)] }
	ref_882 := make([]float64, len(ref_873))
	for i := range ref_882 { ref_882[i] = ref_873[i] * ref_881[i] }
	ref_883 := make([]float64, len(ref_880))
	for i := range ref_883 { ref_883[i] = ref_880[i] + ref_882[i] }
	ref_874 := make([]float64, len(ref_871))
	for i := range ref_874 { ref_874[i] = ref_871[(i + 7 + len(ref_871)) % len(ref_871)] }
	ref_884 := make([]float64, len(ref_874))
	for i := range ref_884 { ref_884[i] = ref_874[i] * ref_879[i] }
	ref_875 := make([]float64, len(ref_871))
	for i := range ref_875 { ref_875[i] = ref_871[(i + 15 + len(ref_871)) % len(ref_871)] }
	ref_886 := make([]float64, len(ref_875))
	for i := range ref_886 { ref_886[i] = ref_875[i] * ref_879[i] }
	ref_1389 := make([]float64, len(ref_884))
	for i := range ref_1389 { ref_1389[i] = ref_884[i] + ref_886[i] }
	ref_1401 := make([]float64, len(ref_883))
	for i := range ref_1401 { ref_1401[i] = ref_883[i] + ref_1389[i] }
	ref_876 := make([]float64, len(ref_871))
	for i := range ref_876 { ref_876[i] = ref_871[(i + 2 + len(ref_871)) % len(ref_871)] }
	ref_888 := make([]float64, len(ref_876))
	for i := range ref_888 { ref_888[i] = ref_876[i] * ref_879[i] }
	ref_877 := make([]float64, len(ref_871))
	for i := range ref_877 { ref_877[i] = ref_871[(i + 14 + len(ref_871)) % len(ref_871)] }
	ref_890 := make([]float64, len(ref_877))
	for i := range ref_890 { ref_890[i] = ref_877[i] * ref_879[i] }
	ref_1395 := make([]float64, len(ref_888))
	for i := range ref_1395 { ref_1395[i] = ref_888[i] + ref_890[i] }
	ref_878 := make([]float64, len(ref_871))
	for i := range ref_878 { ref_878[i] = ref_871[(i + 1 + len(ref_871)) % len(ref_871)] }
	ref_892 := make([]float64, len(ref_878))
	for i := range ref_892 { ref_892[i] = ref_878[i] * ref_879[i] }
	ref_894 := make([]float64, len(ref_871))
	for i := range ref_894 { ref_894[i] = ref_871[i] * ref_879[i] }
	ref_1405 := make([]float64, len(ref_892))
	for i := range ref_1405 { ref_1405[i] = ref_892[i] + ref_894[i] }
	ref_897 := make([]float64, len(ref_871))
	for i := range ref_897 { ref_897[i] = ref_871[i] * ref_896[i] }
	ref_898 := make([]float64, len(ref_897))
	for i := range ref_898 { ref_898[i] = ref_897[(i + 16 + len(ref_897)) % len(ref_897)] }
	ref_1409 := make([]float64, len(ref_1405))
	for i := range ref_1409 { ref_1409[i] = ref_1405[i] + ref_898[i] }
	ref_1410 := make([]float64, len(ref_1395))
	for i := range ref_1410 { ref_1410[i] = ref_1395[i] + ref_1409[i] }
	ref_1408 := make([]float64, len(ref_1401))
	for i := range ref_1408 { ref_1408[i] = ref_1401[i] + ref_1410[i] }
	ref_900 := make([]float64, len(ref_1408))
	for i := range ref_900 { ref_900[i] = ref_1408[(i + 64 + len(ref_1408)) % len(ref_1408)] }
	ref_901 := make([]float64, len(ref_1408))
	for i := range ref_901 { ref_901[i] = ref_1408[i] + ref_900[i] }
	ref_902 := make([]float64, len(ref_901))
	for i := range ref_902 { ref_902[i] = ref_901[(i + 128 + len(ref_901)) % len(ref_901)] }
	ref_903 := make([]float64, len(ref_901))
	for i := range ref_903 { ref_903[i] = ref_901[i] + ref_902[i] }
	ref_904 := ref_903
	ref_905 := make([]float64, len(ref_904))
	for i := range ref_905 { ref_905[i] = ref_904[i] * ref_904[i] }
	ref_906 := make([]float64, len(ref_905))
	for i := range ref_906 { ref_906[i] = ref_905[(i + 14 + len(ref_905)) % len(ref_905)] }
	ref_922 := make([]float64, len(ref_906))
	for i := range ref_922 { ref_922[i] = ref_906[i] * ref_921[i] }
	ref_907 := make([]float64, len(ref_905))
	for i := range ref_907 { ref_907[i] = ref_905[(i + 12 + len(ref_905)) % len(ref_905)] }
	ref_924 := make([]float64, len(ref_907))
	for i := range ref_924 { ref_924[i] = ref_907[i] * ref_923[i] }
	ref_925 := make([]float64, len(ref_922))
	for i := range ref_925 { ref_925[i] = ref_922[i] + ref_924[i] }
	ref_908 := make([]float64, len(ref_905))
	for i := range ref_908 { ref_908[i] = ref_905[(i + 11 + len(ref_905)) % len(ref_905)] }
	ref_926 := make([]float64, len(ref_908))
	for i := range ref_926 { ref_926[i] = ref_908[i] * ref_921[i] }
	ref_909 := make([]float64, len(ref_905))
	for i := range ref_909 { ref_909[i] = ref_905[(i + 9 + len(ref_905)) % len(ref_905)] }
	ref_928 := make([]float64, len(ref_909))
	for i := range ref_928 { ref_928[i] = ref_909[i] * ref_923[i] }
	ref_1411 := make([]float64, len(ref_926))
	for i := range ref_1411 { ref_1411[i] = ref_926[i] + ref_928[i] }
	ref_1423 := make([]float64, len(ref_925))
	for i := range ref_1423 { ref_1423[i] = ref_925[i] + ref_1411[i] }
	ref_910 := make([]float64, len(ref_905))
	for i := range ref_910 { ref_910[i] = ref_905[(i + 8 + len(ref_905)) % len(ref_905)] }
	ref_930 := make([]float64, len(ref_910))
	for i := range ref_930 { ref_930[i] = ref_910[i] * ref_921[i] }
	ref_911 := make([]float64, len(ref_905))
	for i := range ref_911 { ref_911[i] = ref_905[(i + 6 + len(ref_905)) % len(ref_905)] }
	ref_932 := make([]float64, len(ref_911))
	for i := range ref_932 { ref_932[i] = ref_911[i] * ref_923[i] }
	ref_1417 := make([]float64, len(ref_930))
	for i := range ref_1417 { ref_1417[i] = ref_930[i] + ref_932[i] }
	ref_912 := make([]float64, len(ref_905))
	for i := range ref_912 { ref_912[i] = ref_905[(i + 5 + len(ref_905)) % len(ref_905)] }
	ref_934 := make([]float64, len(ref_912))
	for i := range ref_934 { ref_934[i] = ref_912[i] * ref_921[i] }
	ref_913 := make([]float64, len(ref_905))
	for i := range ref_913 { ref_913[i] = ref_905[(i + 3 + len(ref_905)) % len(ref_905)] }
	ref_936 := make([]float64, len(ref_913))
	for i := range ref_936 { ref_936[i] = ref_913[i] * ref_923[i] }
	ref_1427 := make([]float64, len(ref_934))
	for i := range ref_1427 { ref_1427[i] = ref_934[i] + ref_936[i] }
	ref_1445 := make([]float64, len(ref_1417))
	for i := range ref_1445 { ref_1445[i] = ref_1417[i] + ref_1427[i] }
	ref_1459 := make([]float64, len(ref_1423))
	for i := range ref_1459 { ref_1459[i] = ref_1423[i] + ref_1445[i] }
	ref_914 := make([]float64, len(ref_905))
	for i := range ref_914 { ref_914[i] = ref_905[(i + 2 + len(ref_905)) % len(ref_905)] }
	ref_938 := make([]float64, len(ref_914))
	for i := range ref_938 { ref_938[i] = ref_914[i] * ref_921[i] }
	ref_940 := make([]float64, len(ref_905))
	for i := range ref_940 { ref_940[i] = ref_905[i] * ref_923[i] }
	ref_1437 := make([]float64, len(ref_938))
	for i := range ref_1437 { ref_1437[i] = ref_938[i] + ref_940[i] }
	ref_915 := make([]float64, len(ref_905))
	for i := range ref_915 { ref_915[i] = ref_905[(i + 1 + len(ref_905)) % len(ref_905)] }
	ref_943 := make([]float64, len(ref_915))
	for i := range ref_943 { ref_943[i] = ref_915[i] * ref_942[i] }
	ref_916 := make([]float64, len(ref_905))
	for i := range ref_916 { ref_916[i] = ref_905[(i + 4 + len(ref_905)) % len(ref_905)] }
	ref_945 := make([]float64, len(ref_916))
	for i := range ref_945 { ref_945[i] = ref_916[i] * ref_942[i] }
	ref_1451 := make([]float64, len(ref_943))
	for i := range ref_1451 { ref_1451[i] = ref_943[i] + ref_945[i] }
	ref_1473 := make([]float64, len(ref_1437))
	for i := range ref_1473 { ref_1473[i] = ref_1437[i] + ref_1451[i] }
	ref_917 := make([]float64, len(ref_905))
	for i := range ref_917 { ref_917[i] = ref_905[(i + 7 + len(ref_905)) % len(ref_905)] }
	ref_947 := make([]float64, len(ref_917))
	for i := range ref_947 { ref_947[i] = ref_917[i] * ref_942[i] }
	ref_918 := make([]float64, len(ref_905))
	for i := range ref_918 { ref_918[i] = ref_905[(i + 10 + len(ref_905)) % len(ref_905)] }
	ref_949 := make([]float64, len(ref_918))
	for i := range ref_949 { ref_949[i] = ref_918[i] * ref_942[i] }
	ref_1465 := make([]float64, len(ref_947))
	for i := range ref_1465 { ref_1465[i] = ref_947[i] + ref_949[i] }
	ref_919 := make([]float64, len(ref_905))
	for i := range ref_919 { ref_919[i] = ref_905[(i + 13 + len(ref_905)) % len(ref_905)] }
	ref_951 := make([]float64, len(ref_919))
	for i := range ref_951 { ref_951[i] = ref_919[i] * ref_942[i] }
	ref_920 := make([]float64, len(ref_905))
	for i := range ref_920 { ref_920[i] = ref_905[(i + 15 + len(ref_905)) % len(ref_905)] }
	ref_953 := make([]float64, len(ref_920))
	for i := range ref_953 { ref_953[i] = ref_920[i] * ref_923[i] }
	ref_1479 := make([]float64, len(ref_951))
	for i := range ref_1479 { ref_1479[i] = ref_951[i] + ref_953[i] }
	ref_1480 := make([]float64, len(ref_1465))
	for i := range ref_1480 { ref_1480[i] = ref_1465[i] + ref_1479[i] }
	ref_1478 := make([]float64, len(ref_1473))
	for i := range ref_1478 { ref_1478[i] = ref_1473[i] + ref_1480[i] }
	ref_1476 := make([]float64, len(ref_1459))
	for i := range ref_1476 { ref_1476[i] = ref_1459[i] + ref_1478[i] }
	ref_956 := make([]float64, len(ref_916))
	for i := range ref_956 { ref_956[i] = ref_916[i] * ref_955[i] }
	ref_958 := make([]float64, len(ref_912))
	for i := range ref_958 { ref_958[i] = ref_912[i] * ref_957[i] }
	ref_959 := make([]float64, len(ref_956))
	for i := range ref_959 { ref_959[i] = ref_956[i] + ref_958[i] }
	ref_961 := make([]float64, len(ref_915))
	for i := range ref_961 { ref_961[i] = ref_915[i] * ref_960[i] }
	ref_964 := make([]float64, len(ref_917))
	for i := range ref_964 { ref_964[i] = ref_917[i] * ref_963[i] }
	ref_1481 := make([]float64, len(ref_961))
	for i := range ref_1481 { ref_1481[i] = ref_961[i] + ref_964[i] }
	ref_1493 := make([]float64, len(ref_959))
	for i := range ref_1493 { ref_1493[i] = ref_959[i] + ref_1481[i] }
	ref_967 := make([]float64, len(ref_910))
	for i := range ref_967 { ref_967[i] = ref_910[i] * ref_966[i] }
	ref_970 := make([]float64, len(ref_905))
	for i := range ref_970 { ref_970[i] = ref_905[i] * ref_969[i] }
	ref_1487 := make([]float64, len(ref_967))
	for i := range ref_1487 { ref_1487[i] = ref_967[i] + ref_970[i] }
	ref_973 := make([]float64, len(ref_913))
	for i := range ref_973 { ref_973[i] = ref_913[i] * ref_972[i] }
	ref_976 := make([]float64, len(ref_911))
	for i := range ref_976 { ref_976[i] = ref_911[i] * ref_975[i] }
	ref_1497 := make([]float64, len(ref_973))
	for i := range ref_1497 { ref_1497[i] = ref_973[i] + ref_976[i] }
	ref_979 := make([]float64, len(ref_914))
	for i := range ref_979 { ref_979[i] = ref_914[i] * ref_978[i] }
	ref_1501 := make([]float64, len(ref_1497))
	for i := range ref_1501 { ref_1501[i] = ref_1497[i] + ref_979[i] }
	ref_1502 := make([]float64, len(ref_1487))
	for i := range ref_1502 { ref_1502[i] = ref_1487[i] + ref_1501[i] }
	ref_1500 := make([]float64, len(ref_1493))
	for i := range ref_1500 { ref_1500[i] = ref_1493[i] + ref_1502[i] }
	ref_981 := make([]float64, len(ref_1500))
	for i := range ref_981 { ref_981[i] = ref_1500[(i + 16 + len(ref_1500)) % len(ref_1500)] }
	ref_984 := make([]float64, len(ref_918))
	for i := range ref_984 { ref_984[i] = ref_918[i] * ref_983[i] }
	ref_986 := make([]float64, len(ref_910))
	for i := range ref_986 { ref_986[i] = ref_910[i] * ref_985[i] }
	ref_987 := make([]float64, len(ref_984))
	for i := range ref_987 { ref_987[i] = ref_984[i] + ref_986[i] }
	ref_989 := make([]float64, len(ref_917))
	for i := range ref_989 { ref_989[i] = ref_917[i] * ref_988[i] }
	ref_992 := make([]float64, len(ref_919))
	for i := range ref_992 { ref_992[i] = ref_919[i] * ref_991[i] }
	ref_1503 := make([]float64, len(ref_989))
	for i := range ref_1503 { ref_1503[i] = ref_989[i] + ref_992[i] }
	ref_1515 := make([]float64, len(ref_987))
	for i := range ref_1515 { ref_1515[i] = ref_987[i] + ref_1503[i] }
	ref_995 := make([]float64, len(ref_909))
	for i := range ref_995 { ref_995[i] = ref_909[i] * ref_994[i] }
	ref_998 := make([]float64, len(ref_907))
	for i := range ref_998 { ref_998[i] = ref_907[i] * ref_997[i] }
	ref_1509 := make([]float64, len(ref_995))
	for i := range ref_1509 { ref_1509[i] = ref_995[i] + ref_998[i] }
	ref_1001 := make([]float64, len(ref_920))
	for i := range ref_1001 { ref_1001[i] = ref_920[i] * ref_1000[i] }
	ref_1004 := make([]float64, len(ref_908))
	for i := range ref_1004 { ref_1004[i] = ref_908[i] * ref_1003[i] }
	ref_1519 := make([]float64, len(ref_1001))
	for i := range ref_1519 { ref_1519[i] = ref_1001[i] + ref_1004[i] }
	ref_1007 := make([]float64, len(ref_906))
	for i := range ref_1007 { ref_1007[i] = ref_906[i] * ref_1006[i] }
	ref_1523 := make([]float64, len(ref_1519))
	for i := range ref_1523 { ref_1523[i] = ref_1519[i] + ref_1007[i] }
	ref_1524 := make([]float64, len(ref_1509))
	for i := range ref_1524 { ref_1524[i] = ref_1509[i] + ref_1523[i] }
	ref_1522 := make([]float64, len(ref_1515))
	for i := range ref_1522 { ref_1522[i] = ref_1515[i] + ref_1524[i] }
	ref_1009 := make([]float64, len(ref_1522))
	for i := range ref_1009 { ref_1009[i] = ref_1522[(i + 240 + len(ref_1522)) % len(ref_1522)] }
	ref_1525 := make([]float64, len(ref_981))
	for i := range ref_1525 { ref_1525[i] = ref_981[i] + ref_1009[i] }
	ref_1526 := make([]float64, len(ref_1476))
	for i := range ref_1526 { ref_1526[i] = ref_1476[i] + ref_1525[i] }
	ref_1011 := ref_1526
	expectedOutputs := make(map[string][]float64)
	expectedOutputs["classification"] = ref_1011
	precisionChecked = true

	init_constants(params, encoder)
	computeStart := time.Now()
	for i := 0; i < *repetitions; i++ {
			tensor_full_dnn(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, encoder, enc, eval, params)
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
