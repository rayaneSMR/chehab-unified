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
	return []int{48, 24, 8, 240, 16, 248, 3, 32, 96, 5, 80, 2, 72, 7, 56, 4, 88, 1, 40, 64, 6}
}

var (
	p1127 *rlwe.Plaintext
	p1110 *rlwe.Plaintext
	p1101 *rlwe.Plaintext
	p1094 *rlwe.Plaintext
	p1080 *rlwe.Plaintext
	p1077 *rlwe.Plaintext
	p1075 *rlwe.Plaintext
	p1070 *rlwe.Plaintext
	p1067 *rlwe.Plaintext
	p1047 *rlwe.Plaintext
	p1013 *rlwe.Plaintext
	p1001 *rlwe.Plaintext
	p994 *rlwe.Plaintext
	p985 *rlwe.Plaintext
	p983 *rlwe.Plaintext
	p752 *rlwe.Plaintext
	p749 *rlwe.Plaintext
	p622 *rlwe.Plaintext
	p747 *rlwe.Plaintext
	p730 *rlwe.Plaintext
	p727 *rlwe.Plaintext
	p724 *rlwe.Plaintext
	p597 *rlwe.Plaintext
	p978 *rlwe.Plaintext
	p722 *rlwe.Plaintext
	p849 *rlwe.Plaintext
	p976 *rlwe.Plaintext
	p702 *rlwe.Plaintext
	p699 *rlwe.Plaintext
	p953 *rlwe.Plaintext
	p996 *rlwe.Plaintext
	p739 *rlwe.Plaintext
	p680 *rlwe.Plaintext
	p736 *rlwe.Plaintext
	p934 *rlwe.Plaintext
	p677 *rlwe.Plaintext
	p990 *rlwe.Plaintext
	p733 *rlwe.Plaintext
	p674 *rlwe.Plaintext
	p672 *rlwe.Plaintext
	p799 *rlwe.Plaintext
	p655 *rlwe.Plaintext
	p1108 *rlwe.Plaintext
	p594 *rlwe.Plaintext
	p968 *rlwe.Plaintext
	p711 *rlwe.Plaintext
	p652 *rlwe.Plaintext
	p591 *rlwe.Plaintext
	p708 *rlwe.Plaintext
	p705 *rlwe.Plaintext
	p962 *rlwe.Plaintext
	p649 *rlwe.Plaintext
	p874 *rlwe.Plaintext
	p617 *rlwe.Plaintext
	p966 *rlwe.Plaintext
	p614 *rlwe.Plaintext
	p608 *rlwe.Plaintext
	p697 *rlwe.Plaintext
	p824 *rlwe.Plaintext
	p1096 *rlwe.Plaintext
	p839 *rlwe.Plaintext
	p582 *rlwe.Plaintext
	p579 *rlwe.Plaintext
	p836 *rlwe.Plaintext
	p611 *rlwe.Plaintext
	p664 *rlwe.Plaintext
	p1119 *rlwe.Plaintext
	p605 *rlwe.Plaintext
	p833 *rlwe.Plaintext
	p576 *rlwe.Plaintext
	p830 *rlwe.Plaintext
	p661 *rlwe.Plaintext
	p1116 *rlwe.Plaintext
	p602 *rlwe.Plaintext
	p742 *rlwe.Plaintext
	p624 *rlwe.Plaintext
	p683 *rlwe.Plaintext
	p940 *rlwe.Plaintext
	p627 *rlwe.Plaintext
	p689 *rlwe.Plaintext
	p686 *rlwe.Plaintext
	p943 *rlwe.Plaintext
	p630 *rlwe.Plaintext
	p692 *rlwe.Plaintext
	p574 *rlwe.Plaintext
	p633 *rlwe.Plaintext
	p890 *rlwe.Plaintext
	p636 *rlwe.Plaintext
	p893 *rlwe.Plaintext
	p639 *rlwe.Plaintext
	p896 *rlwe.Plaintext
	p588 *rlwe.Plaintext
	p585 *rlwe.Plaintext
	p842 *rlwe.Plaintext
	p647 *rlwe.Plaintext
	p774 *rlwe.Plaintext
	p717 *rlwe.Plaintext
	p714 *rlwe.Plaintext
	p971 *rlwe.Plaintext
	p1113 *rlwe.Plaintext
	p599 *rlwe.Plaintext
	p658 *rlwe.Plaintext
	p755 *rlwe.Plaintext
	p758 *rlwe.Plaintext
	p761 *rlwe.Plaintext
	p888 *rlwe.Plaintext
	p764 *rlwe.Plaintext
	p767 *rlwe.Plaintext
	p1029 *rlwe.Plaintext
	p772 *rlwe.Plaintext
	p642 *rlwe.Plaintext
	p899 *rlwe.Plaintext
	p777 *rlwe.Plaintext
	p780 *rlwe.Plaintext
	p783 *rlwe.Plaintext
	p786 *rlwe.Plaintext
	p789 *rlwe.Plaintext
	p792 *rlwe.Plaintext
	p797 *rlwe.Plaintext
	p667 *rlwe.Plaintext
	p924 *rlwe.Plaintext
	p802 *rlwe.Plaintext
	p805 *rlwe.Plaintext
	p1065 *rlwe.Plaintext
	p808 *rlwe.Plaintext
	p811 *rlwe.Plaintext
	p938 *rlwe.Plaintext
	p814 *rlwe.Plaintext
	p817 *rlwe.Plaintext
	p822 *rlwe.Plaintext
	p827 *rlwe.Plaintext
	p1104 *rlwe.Plaintext
	p847 *rlwe.Plaintext
	p852 *rlwe.Plaintext
	p855 *rlwe.Plaintext
	p858 *rlwe.Plaintext
	p861 *rlwe.Plaintext
	p864 *rlwe.Plaintext
	p1124 *rlwe.Plaintext
	p867 *rlwe.Plaintext
	p872 *rlwe.Plaintext
	p877 *rlwe.Plaintext
	p880 *rlwe.Plaintext
	p883 *rlwe.Plaintext
	p902 *rlwe.Plaintext
	p905 *rlwe.Plaintext
	p908 *rlwe.Plaintext
	p922 *rlwe.Plaintext
	p927 *rlwe.Plaintext
	p930 *rlwe.Plaintext
	p948 *rlwe.Plaintext
	p950 *rlwe.Plaintext
	p958 *rlwe.Plaintext
)

func init_constants(params hefloat.Parameters, encoder *hefloat.Encoder) {
	slotCount := params.MaxSlots()
	_ = slotCount
	p1127 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(-0.25)
		values[1] = float64(0.25)
		encoder.Encode(values, p1127)
	}
	p1110 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.25)
		values[253] = float64(0.25)
		values[255] = float64(-0.25)
		encoder.Encode(values, p1110)
	}
	p1101 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(-0.25)
		values[1] = float64(0.25)
		values[3] = float64(-0.25)
		encoder.Encode(values, p1101)
	}
	p1094 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[1] = float64(-0.25)
		values[2] = float64(0.25)
		encoder.Encode(values, p1094)
	}
	p1080 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[249] = float64(0.05)
		values[250] = float64(0.05)
		values[251] = float64(0.05)
		encoder.Encode(values, p1080)
	}
	p1077 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[250] = float64(0.05)
		values[251] = float64(0.05)
		encoder.Encode(values, p1077)
	}
	p1075 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[251] = float64(0.05)
		encoder.Encode(values, p1075)
	}
	p1070 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[24] = float64(0.05)
		encoder.Encode(values, p1070)
	}
	p1067 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[24] = float64(0.05)
		values[25] = float64(0.05)
		encoder.Encode(values, p1067)
	}
	p1047 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.05)
		values[17] = float64(0.05)
		values[18] = float64(0.05)
		values[19] = float64(0.05)
		encoder.Encode(values, p1047)
	}
	p1013 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		values[1] = float64(0.05)
		values[2] = float64(0.05)
		values[3] = float64(0.05)
		encoder.Encode(values, p1013)
	}
	p1001 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[120] = float64(0.25)
		values[121] = float64(0.25)
		values[122] = float64(0.25)
		encoder.Encode(values, p1001)
	}
	p994 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[106] = float64(0.25)
		values[107] = float64(0.25)
		values[108] = float64(0.25)
		values[109] = float64(0.25)
		values[110] = float64(0.25)
		values[111] = float64(0.25)
		encoder.Encode(values, p994)
	}
	p985 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[93] = float64(0.25)
		values[94] = float64(0.25)
		values[95] = float64(0.25)
		values[96] = float64(0.25)
		values[97] = float64(0.25)
		values[98] = float64(0.25)
		encoder.Encode(values, p985)
	}
	p983 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[96] = float64(0.25)
		values[97] = float64(0.25)
		values[98] = float64(0.25)
		encoder.Encode(values, p983)
	}
	p752 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[133] = float64(0.05)
		values[135] = float64(0.05)
		values[136] = float64(0.05)
		values[137] = float64(0.05)
		values[138] = float64(0.05)
		values[139] = float64(0.05)
		values[141] = float64(0.05)
		values[142] = float64(0.05)
		values[143] = float64(0.05)
		values[144] = float64(0.05)
		values[145] = float64(0.05)
		values[146] = float64(0.05)
		values[147] = float64(0.05)
		values[149] = float64(0.05)
		values[199] = float64(0.05)
		values[201] = float64(0.05)
		values[202] = float64(0.05)
		encoder.Encode(values, p752)
	}
	p749 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[136] = float64(0.05)
		values[138] = float64(0.05)
		values[139] = float64(0.05)
		values[142] = float64(0.05)
		values[144] = float64(0.05)
		values[145] = float64(0.05)
		values[146] = float64(0.05)
		values[147] = float64(0.05)
		values[148] = float64(0.05)
		values[149] = float64(0.05)
		values[150] = float64(0.05)
		values[152] = float64(0.05)
		values[202] = float64(0.05)
		encoder.Encode(values, p749)
	}
	p622 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.05)
		values[17] = float64(0.05)
		values[18] = float64(0.05)
		values[19] = float64(0.05)
		values[20] = float64(0.05)
		values[22] = float64(0.05)
		values[72] = float64(0.05)
		values[74] = float64(0.05)
		values[75] = float64(0.05)
		values[76] = float64(0.05)
		values[77] = float64(0.05)
		values[78] = float64(0.05)
		encoder.Encode(values, p622)
	}
	p747 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[139] = float64(0.05)
		values[145] = float64(0.05)
		values[147] = float64(0.05)
		values[148] = float64(0.05)
		values[149] = float64(0.05)
		values[150] = float64(0.05)
		values[151] = float64(0.05)
		values[152] = float64(0.05)
		values[153] = float64(0.05)
		values[155] = float64(0.05)
		values[161] = float64(0.05)
		encoder.Encode(values, p747)
	}
	p730 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[95] = float64(0.05)
		values[97] = float64(0.05)
		values[98] = float64(0.05)
		values[99] = float64(0.05)
		values[100] = float64(0.05)
		values[101] = float64(0.05)
		values[102] = float64(0.05)
		values[103] = float64(0.05)
		values[105] = float64(0.05)
		values[111] = float64(0.05)
		values[161] = float64(0.05)
		values[163] = float64(0.05)
		values[164] = float64(0.05)
		values[165] = float64(0.05)
		values[166] = float64(0.05)
		values[167] = float64(0.05)
		values[168] = float64(0.05)
		values[169] = float64(0.05)
		values[171] = float64(0.05)
		encoder.Encode(values, p730)
	}
	p727 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[98] = float64(0.05)
		values[100] = float64(0.05)
		values[101] = float64(0.05)
		values[102] = float64(0.05)
		values[103] = float64(0.05)
		values[104] = float64(0.05)
		values[105] = float64(0.05)
		values[106] = float64(0.05)
		values[108] = float64(0.05)
		values[111] = float64(0.05)
		values[112] = float64(0.05)
		values[114] = float64(0.05)
		values[164] = float64(0.05)
		values[166] = float64(0.05)
		values[167] = float64(0.05)
		values[168] = float64(0.05)
		values[169] = float64(0.05)
		values[170] = float64(0.05)
		values[171] = float64(0.05)
		values[172] = float64(0.05)
		encoder.Encode(values, p727)
	}
	p724 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[101] = float64(0.05)
		values[103] = float64(0.05)
		values[104] = float64(0.05)
		values[105] = float64(0.05)
		values[106] = float64(0.05)
		values[107] = float64(0.05)
		values[108] = float64(0.05)
		values[109] = float64(0.05)
		values[111] = float64(0.05)
		values[112] = float64(0.05)
		values[113] = float64(0.05)
		values[114] = float64(0.05)
		values[115] = float64(0.05)
		values[117] = float64(0.05)
		values[167] = float64(0.05)
		values[169] = float64(0.05)
		values[170] = float64(0.05)
		values[171] = float64(0.05)
		values[172] = float64(0.05)
		values[173] = float64(0.05)
		encoder.Encode(values, p724)
	}
	p597 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[25] = float64(0.05)
		values[27] = float64(0.05)
		values[28] = float64(0.05)
		values[31] = float64(0.05)
		values[33] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[37] = float64(0.05)
		values[38] = float64(0.05)
		values[39] = float64(0.05)
		values[41] = float64(0.05)
		encoder.Encode(values, p597)
	}
	p978 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[82] = float64(0.25)
		values[83] = float64(0.25)
		values[84] = float64(0.25)
		encoder.Encode(values, p978)
	}
	p722 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[104] = float64(0.05)
		values[106] = float64(0.05)
		values[107] = float64(0.05)
		values[108] = float64(0.05)
		values[109] = float64(0.05)
		values[110] = float64(0.05)
		values[112] = float64(0.05)
		values[113] = float64(0.05)
		values[114] = float64(0.05)
		values[115] = float64(0.05)
		values[116] = float64(0.05)
		values[117] = float64(0.05)
		values[118] = float64(0.05)
		values[120] = float64(0.05)
		values[170] = float64(0.05)
		values[172] = float64(0.05)
		values[173] = float64(0.05)
		encoder.Encode(values, p722)
	}
	p849 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[231] = float64(0.05)
		values[233] = float64(0.05)
		values[234] = float64(0.05)
		encoder.Encode(values, p849)
	}
	p976 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[82] = float64(0.25)
		values[83] = float64(0.25)
		values[84] = float64(0.25)
		values[85] = float64(0.25)
		values[86] = float64(0.25)
		values[87] = float64(0.25)
		encoder.Encode(values, p976)
	}
	p702 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[61] = float64(0.05)
		values[62] = float64(0.05)
		values[63] = float64(0.05)
		values[64] = float64(0.05)
		values[65] = float64(0.05)
		values[67] = float64(0.05)
		values[117] = float64(0.05)
		values[119] = float64(0.05)
		values[120] = float64(0.05)
		values[121] = float64(0.05)
		values[122] = float64(0.05)
		values[123] = float64(0.05)
		values[125] = float64(0.05)
		values[126] = float64(0.05)
		values[127] = float64(0.05)
		values[128] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[133] = float64(0.05)
		encoder.Encode(values, p702)
	}
	p699 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[99] = float64(0.05)
		values[101] = float64(0.05)
		values[102] = float64(0.05)
		values[105] = float64(0.05)
		values[107] = float64(0.05)
		values[108] = float64(0.05)
		values[109] = float64(0.05)
		values[110] = float64(0.05)
		values[111] = float64(0.05)
		values[112] = float64(0.05)
		values[113] = float64(0.05)
		values[115] = float64(0.05)
		values[165] = float64(0.05)
		encoder.Encode(values, p699)
	}
	p953 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[41] = float64(0.25)
		values[42] = float64(0.25)
		values[43] = float64(0.25)
		values[44] = float64(0.25)
		values[45] = float64(0.25)
		values[46] = float64(0.25)
		encoder.Encode(values, p953)
	}
	p996 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[109] = float64(0.25)
		values[110] = float64(0.25)
		values[111] = float64(0.25)
		values[112] = float64(0.25)
		values[113] = float64(0.25)
		values[114] = float64(0.25)
		encoder.Encode(values, p996)
	}
	p739 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[91] = float64(0.05)
		values[92] = float64(0.05)
		values[93] = float64(0.05)
		values[94] = float64(0.05)
		values[95] = float64(0.05)
		values[96] = float64(0.05)
		values[97] = float64(0.05)
		values[99] = float64(0.05)
		values[149] = float64(0.05)
		values[151] = float64(0.05)
		values[152] = float64(0.05)
		values[155] = float64(0.05)
		values[157] = float64(0.05)
		values[158] = float64(0.05)
		values[159] = float64(0.05)
		values[160] = float64(0.05)
		values[161] = float64(0.05)
		values[162] = float64(0.05)
		values[163] = float64(0.05)
		values[165] = float64(0.05)
		encoder.Encode(values, p739)
	}
	p680 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[61] = float64(0.05)
		values[63] = float64(0.05)
		values[64] = float64(0.05)
		values[65] = float64(0.05)
		values[66] = float64(0.05)
		values[67] = float64(0.05)
		values[68] = float64(0.05)
		values[69] = float64(0.05)
		values[71] = float64(0.05)
		values[74] = float64(0.05)
		values[75] = float64(0.05)
		values[77] = float64(0.05)
		values[127] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[135] = float64(0.05)
		encoder.Encode(values, p680)
	}
	p736 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[90] = float64(0.05)
		values[91] = float64(0.05)
		values[93] = float64(0.05)
		values[143] = float64(0.05)
		values[145] = float64(0.05)
		values[146] = float64(0.05)
		values[147] = float64(0.05)
		values[148] = float64(0.05)
		values[149] = float64(0.05)
		values[150] = float64(0.05)
		values[151] = float64(0.05)
		values[153] = float64(0.05)
		values[154] = float64(0.05)
		values[155] = float64(0.05)
		values[156] = float64(0.05)
		values[157] = float64(0.05)
		values[159] = float64(0.05)
		encoder.Encode(values, p736)
	}
	p934 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.25)
		values[17] = float64(0.25)
		values[18] = float64(0.25)
		encoder.Encode(values, p934)
	}
	p677 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[32] = float64(0.05)
		values[82] = float64(0.05)
		values[84] = float64(0.05)
		values[85] = float64(0.05)
		values[86] = float64(0.05)
		values[87] = float64(0.05)
		values[88] = float64(0.05)
		values[89] = float64(0.05)
		values[90] = float64(0.05)
		values[92] = float64(0.05)
		values[95] = float64(0.05)
		values[96] = float64(0.05)
		values[98] = float64(0.05)
		encoder.Encode(values, p677)
	}
	p990 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[98] = float64(0.25)
		values[99] = float64(0.25)
		values[100] = float64(0.25)
		encoder.Encode(values, p990)
	}
	p733 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[90] = float64(0.05)
		values[91] = float64(0.05)
		values[92] = float64(0.05)
		values[93] = float64(0.05)
		values[94] = float64(0.05)
		values[96] = float64(0.05)
		values[146] = float64(0.05)
		values[148] = float64(0.05)
		values[149] = float64(0.05)
		values[150] = float64(0.05)
		values[151] = float64(0.05)
		values[152] = float64(0.05)
		values[154] = float64(0.05)
		values[155] = float64(0.05)
		values[156] = float64(0.05)
		values[157] = float64(0.05)
		values[158] = float64(0.05)
		values[159] = float64(0.05)
		values[160] = float64(0.05)
		values[162] = float64(0.05)
		encoder.Encode(values, p733)
	}
	p674 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[35] = float64(0.05)
		values[85] = float64(0.05)
		values[87] = float64(0.05)
		values[88] = float64(0.05)
		values[89] = float64(0.05)
		values[90] = float64(0.05)
		values[91] = float64(0.05)
		values[92] = float64(0.05)
		values[93] = float64(0.05)
		values[95] = float64(0.05)
		values[96] = float64(0.05)
		values[97] = float64(0.05)
		values[98] = float64(0.05)
		values[99] = float64(0.05)
		values[101] = float64(0.05)
		encoder.Encode(values, p674)
	}
	p672 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[38] = float64(0.05)
		values[88] = float64(0.05)
		values[90] = float64(0.05)
		values[91] = float64(0.05)
		values[92] = float64(0.05)
		values[93] = float64(0.05)
		values[94] = float64(0.05)
		values[96] = float64(0.05)
		values[97] = float64(0.05)
		values[98] = float64(0.05)
		values[99] = float64(0.05)
		values[100] = float64(0.05)
		values[101] = float64(0.05)
		values[102] = float64(0.05)
		values[104] = float64(0.05)
		encoder.Encode(values, p672)
	}
	p799 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[164] = float64(0.05)
		values[166] = float64(0.05)
		values[167] = float64(0.05)
		values[168] = float64(0.05)
		values[169] = float64(0.05)
		values[170] = float64(0.05)
		values[171] = float64(0.05)
		values[172] = float64(0.05)
		values[174] = float64(0.05)
		values[177] = float64(0.05)
		values[178] = float64(0.05)
		values[180] = float64(0.05)
		encoder.Encode(values, p799)
	}
	p655 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[29] = float64(0.05)
		values[31] = float64(0.05)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[37] = float64(0.05)
		values[39] = float64(0.05)
		values[45] = float64(0.05)
		values[95] = float64(0.05)
		values[97] = float64(0.05)
		values[98] = float64(0.05)
		values[99] = float64(0.05)
		values[100] = float64(0.05)
		values[101] = float64(0.05)
		values[102] = float64(0.05)
		values[103] = float64(0.05)
		values[105] = float64(0.05)
		encoder.Encode(values, p655)
	}
	p1108 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[253] = float64(-0.25)
		values[254] = float64(0.25)
		encoder.Encode(values, p1108)
	}
	p594 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[41] = float64(0.05)
		encoder.Encode(values, p594)
	}
	p968 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[68] = float64(0.25)
		values[69] = float64(0.25)
		values[70] = float64(0.25)
		values[71] = float64(0.25)
		values[72] = float64(0.25)
		values[73] = float64(0.25)
		encoder.Encode(values, p968)
	}
	p711 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[62] = float64(0.05)
		values[63] = float64(0.05)
		values[64] = float64(0.05)
		values[65] = float64(0.05)
		values[66] = float64(0.05)
		values[67] = float64(0.05)
		values[68] = float64(0.05)
		values[70] = float64(0.05)
		values[120] = float64(0.05)
		values[122] = float64(0.05)
		values[123] = float64(0.05)
		values[126] = float64(0.05)
		values[128] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[136] = float64(0.05)
		encoder.Encode(values, p711)
	}
	p652 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[32] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[37] = float64(0.05)
		values[38] = float64(0.05)
		values[39] = float64(0.05)
		values[40] = float64(0.05)
		values[42] = float64(0.05)
		values[45] = float64(0.05)
		values[46] = float64(0.05)
		values[48] = float64(0.05)
		values[98] = float64(0.05)
		values[100] = float64(0.05)
		values[101] = float64(0.05)
		values[102] = float64(0.05)
		values[103] = float64(0.05)
		values[104] = float64(0.05)
		values[105] = float64(0.05)
		values[106] = float64(0.05)
		encoder.Encode(values, p652)
	}
	p591 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[38] = float64(0.05)
		values[40] = float64(0.05)
		values[41] = float64(0.05)
		encoder.Encode(values, p591)
	}
	p708 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[61] = float64(0.05)
		values[111] = float64(0.05)
		values[113] = float64(0.05)
		values[114] = float64(0.05)
		values[115] = float64(0.05)
		values[116] = float64(0.05)
		values[117] = float64(0.05)
		values[118] = float64(0.05)
		values[119] = float64(0.05)
		values[121] = float64(0.05)
		values[124] = float64(0.05)
		values[125] = float64(0.05)
		values[127] = float64(0.05)
		encoder.Encode(values, p708)
	}
	p705 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[61] = float64(0.05)
		values[62] = float64(0.05)
		values[64] = float64(0.05)
		values[114] = float64(0.05)
		values[116] = float64(0.05)
		values[117] = float64(0.05)
		values[118] = float64(0.05)
		values[119] = float64(0.05)
		values[120] = float64(0.05)
		values[121] = float64(0.05)
		values[122] = float64(0.05)
		values[124] = float64(0.05)
		values[125] = float64(0.05)
		values[126] = float64(0.05)
		values[127] = float64(0.05)
		values[128] = float64(0.05)
		values[130] = float64(0.05)
		encoder.Encode(values, p705)
	}
	p962 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[57] = float64(0.25)
		values[58] = float64(0.25)
		values[59] = float64(0.25)
		encoder.Encode(values, p962)
	}
	p649 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[35] = float64(0.05)
		values[37] = float64(0.05)
		values[38] = float64(0.05)
		values[39] = float64(0.05)
		values[40] = float64(0.05)
		values[41] = float64(0.05)
		values[42] = float64(0.05)
		values[43] = float64(0.05)
		values[45] = float64(0.05)
		values[46] = float64(0.05)
		values[47] = float64(0.05)
		values[48] = float64(0.05)
		values[49] = float64(0.05)
		values[51] = float64(0.05)
		values[101] = float64(0.05)
		values[103] = float64(0.05)
		values[104] = float64(0.05)
		values[105] = float64(0.05)
		values[106] = float64(0.05)
		values[107] = float64(0.05)
		encoder.Encode(values, p649)
	}
	p874 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[223] = float64(0.05)
		values[224] = float64(0.05)
		values[225] = float64(0.05)
		values[226] = float64(0.05)
		values[227] = float64(0.05)
		values[228] = float64(0.05)
		values[229] = float64(0.05)
		values[231] = float64(0.05)
		encoder.Encode(values, p874)
	}
	p617 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[28] = float64(0.05)
		values[34] = float64(0.05)
		values[36] = float64(0.05)
		values[37] = float64(0.05)
		values[38] = float64(0.05)
		values[39] = float64(0.05)
		values[40] = float64(0.05)
		values[41] = float64(0.05)
		values[42] = float64(0.05)
		values[44] = float64(0.05)
		encoder.Encode(values, p617)
	}
	p966 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[71] = float64(0.25)
		values[72] = float64(0.25)
		values[73] = float64(0.25)
		encoder.Encode(values, p966)
	}
	p614 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[10] = float64(0.05)
		values[12] = float64(0.05)
		values[13] = float64(0.05)
		values[14] = float64(0.05)
		values[15] = float64(0.05)
		values[16] = float64(0.05)
		values[17] = float64(0.05)
		values[18] = float64(0.05)
		values[20] = float64(0.05)
		values[70] = float64(0.05)
		encoder.Encode(values, p614)
	}
	p608 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.05)
		values[18] = float64(0.05)
		values[19] = float64(0.05)
		values[20] = float64(0.05)
		values[21] = float64(0.05)
		values[22] = float64(0.05)
		values[23] = float64(0.05)
		values[24] = float64(0.05)
		values[26] = float64(0.05)
		values[29] = float64(0.05)
		values[30] = float64(0.05)
		values[32] = float64(0.05)
		encoder.Encode(values, p608)
	}
	p697 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[102] = float64(0.05)
		values[108] = float64(0.05)
		values[110] = float64(0.05)
		values[111] = float64(0.05)
		values[112] = float64(0.05)
		values[113] = float64(0.05)
		values[114] = float64(0.05)
		values[115] = float64(0.05)
		values[116] = float64(0.05)
		values[118] = float64(0.05)
		values[124] = float64(0.05)
		encoder.Encode(values, p697)
	}
	p824 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[199] = float64(0.05)
		values[201] = float64(0.05)
		values[202] = float64(0.05)
		values[203] = float64(0.05)
		values[204] = float64(0.05)
		values[205] = float64(0.05)
		values[207] = float64(0.05)
		values[208] = float64(0.05)
		values[209] = float64(0.05)
		values[210] = float64(0.05)
		values[211] = float64(0.05)
		values[212] = float64(0.05)
		values[213] = float64(0.05)
		values[215] = float64(0.05)
		encoder.Encode(values, p824)
	}
	p1096 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(-0.25)
		encoder.Encode(values, p1096)
	}
	p839 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[186] = float64(0.05)
		values[187] = float64(0.05)
		values[188] = float64(0.05)
		values[189] = float64(0.05)
		values[190] = float64(0.05)
		values[191] = float64(0.05)
		values[192] = float64(0.05)
		values[194] = float64(0.05)
		encoder.Encode(values, p839)
	}
	p582 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[29] = float64(0.05)
		values[31] = float64(0.05)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[37] = float64(0.05)
		values[39] = float64(0.05)
		encoder.Encode(values, p582)
	}
	p579 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		values[1] = float64(0.05)
		values[3] = float64(0.05)
		encoder.Encode(values, p579)
	}
	p836 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[187] = float64(0.05)
		values[189] = float64(0.05)
		values[190] = float64(0.05)
		values[191] = float64(0.05)
		values[192] = float64(0.05)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[195] = float64(0.05)
		values[197] = float64(0.05)
		encoder.Encode(values, p836)
	}
	p611 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[13] = float64(0.05)
		values[15] = float64(0.05)
		values[16] = float64(0.05)
		values[17] = float64(0.05)
		values[18] = float64(0.05)
		values[19] = float64(0.05)
		values[20] = float64(0.05)
		values[21] = float64(0.05)
		values[23] = float64(0.05)
		values[29] = float64(0.05)
		encoder.Encode(values, p611)
	}
	p664 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[41] = float64(0.05)
		values[43] = float64(0.05)
		values[44] = float64(0.05)
		values[47] = float64(0.05)
		values[49] = float64(0.05)
		values[50] = float64(0.05)
		values[51] = float64(0.05)
		values[52] = float64(0.05)
		values[53] = float64(0.05)
		values[54] = float64(0.05)
		values[55] = float64(0.05)
		values[57] = float64(0.05)
		values[107] = float64(0.05)
		encoder.Encode(values, p664)
	}
	p1119 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[250] = float64(0.25)
		values[252] = float64(-0.25)
		values[253] = float64(0.25)
		encoder.Encode(values, p1119)
	}
	p605 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[9] = float64(0.05)
		values[10] = float64(0.05)
		values[11] = float64(0.05)
		values[12] = float64(0.05)
		values[13] = float64(0.05)
		values[14] = float64(0.05)
		values[15] = float64(0.05)
		values[17] = float64(0.05)
		values[67] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		encoder.Encode(values, p605)
	}
	p833 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[190] = float64(0.05)
		values[192] = float64(0.05)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[195] = float64(0.05)
		values[196] = float64(0.05)
		values[197] = float64(0.05)
		values[198] = float64(0.05)
		values[200] = float64(0.05)
		values[206] = float64(0.05)
		encoder.Encode(values, p833)
	}
	p576 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		encoder.Encode(values, p576)
	}
	p830 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[193] = float64(0.05)
		values[195] = float64(0.05)
		values[196] = float64(0.05)
		values[197] = float64(0.05)
		values[198] = float64(0.05)
		values[199] = float64(0.05)
		values[200] = float64(0.05)
		values[201] = float64(0.05)
		values[203] = float64(0.05)
		values[206] = float64(0.05)
		values[207] = float64(0.05)
		values[209] = float64(0.05)
		encoder.Encode(values, p830)
	}
	p661 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[25] = float64(0.05)
		values[26] = float64(0.05)
		values[27] = float64(0.05)
		values[28] = float64(0.05)
		values[29] = float64(0.05)
		values[30] = float64(0.05)
		values[31] = float64(0.05)
		values[33] = float64(0.05)
		values[83] = float64(0.05)
		values[85] = float64(0.05)
		values[86] = float64(0.05)
		values[89] = float64(0.05)
		values[91] = float64(0.05)
		values[92] = float64(0.05)
		values[93] = float64(0.05)
		values[94] = float64(0.05)
		values[95] = float64(0.05)
		values[96] = float64(0.05)
		values[97] = float64(0.05)
		values[99] = float64(0.05)
		encoder.Encode(values, p661)
	}
	p1116 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[250] = float64(-0.25)
		values[251] = float64(0.25)
		encoder.Encode(values, p1116)
	}
	p602 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[19] = float64(0.05)
		values[21] = float64(0.05)
		values[22] = float64(0.05)
		values[23] = float64(0.05)
		values[24] = float64(0.05)
		values[25] = float64(0.05)
		values[26] = float64(0.05)
		values[27] = float64(0.05)
		values[29] = float64(0.05)
		values[30] = float64(0.05)
		values[31] = float64(0.05)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[35] = float64(0.05)
		encoder.Encode(values, p602)
	}
	p742 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[92] = float64(0.05)
		values[94] = float64(0.05)
		values[95] = float64(0.05)
		values[96] = float64(0.05)
		values[97] = float64(0.05)
		values[98] = float64(0.05)
		values[99] = float64(0.05)
		values[100] = float64(0.05)
		values[102] = float64(0.05)
		values[152] = float64(0.05)
		values[158] = float64(0.05)
		values[160] = float64(0.05)
		values[161] = float64(0.05)
		values[162] = float64(0.05)
		values[163] = float64(0.05)
		values[164] = float64(0.05)
		values[165] = float64(0.05)
		values[166] = float64(0.05)
		values[168] = float64(0.05)
		encoder.Encode(values, p742)
	}
	p624 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.05)
		values[17] = float64(0.05)
		values[19] = float64(0.05)
		values[69] = float64(0.05)
		values[71] = float64(0.05)
		values[72] = float64(0.05)
		values[73] = float64(0.05)
		values[74] = float64(0.05)
		values[75] = float64(0.05)
		values[76] = float64(0.05)
		values[77] = float64(0.05)
		encoder.Encode(values, p624)
	}
	p683 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[64] = float64(0.05)
		values[66] = float64(0.05)
		values[67] = float64(0.05)
		values[68] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		values[71] = float64(0.05)
		values[72] = float64(0.05)
		values[74] = float64(0.05)
		values[75] = float64(0.05)
		values[76] = float64(0.05)
		values[77] = float64(0.05)
		values[78] = float64(0.05)
		values[80] = float64(0.05)
		values[130] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[135] = float64(0.05)
		values[136] = float64(0.05)
		encoder.Encode(values, p683)
	}
	p940 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[27] = float64(0.25)
		values[28] = float64(0.25)
		values[29] = float64(0.25)
		values[30] = float64(0.25)
		values[31] = float64(0.25)
		values[32] = float64(0.25)
		encoder.Encode(values, p940)
	}
	p627 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[16] = float64(0.05)
		values[66] = float64(0.05)
		values[68] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		values[71] = float64(0.05)
		values[72] = float64(0.05)
		values[73] = float64(0.05)
		values[74] = float64(0.05)
		values[76] = float64(0.05)
		encoder.Encode(values, p627)
	}
	p689 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[70] = float64(0.05)
		values[72] = float64(0.05)
		values[73] = float64(0.05)
		values[76] = float64(0.05)
		values[78] = float64(0.05)
		values[79] = float64(0.05)
		values[80] = float64(0.05)
		values[81] = float64(0.05)
		values[82] = float64(0.05)
		values[83] = float64(0.05)
		values[84] = float64(0.05)
		values[86] = float64(0.05)
		values[136] = float64(0.05)
		encoder.Encode(values, p689)
	}
	p686 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[67] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		values[71] = float64(0.05)
		values[72] = float64(0.05)
		values[73] = float64(0.05)
		values[75] = float64(0.05)
		values[76] = float64(0.05)
		values[77] = float64(0.05)
		values[78] = float64(0.05)
		values[79] = float64(0.05)
		values[80] = float64(0.05)
		values[81] = float64(0.05)
		values[83] = float64(0.05)
		values[133] = float64(0.05)
		values[135] = float64(0.05)
		values[136] = float64(0.05)
		encoder.Encode(values, p686)
	}
	p943 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[30] = float64(0.25)
		values[31] = float64(0.25)
		values[32] = float64(0.25)
		encoder.Encode(values, p943)
	}
	p630 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[57] = float64(0.05)
		values[63] = float64(0.05)
		values[65] = float64(0.05)
		values[66] = float64(0.05)
		values[67] = float64(0.05)
		values[68] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		values[71] = float64(0.05)
		values[73] = float64(0.05)
		encoder.Encode(values, p630)
	}
	p692 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[73] = float64(0.05)
		values[79] = float64(0.05)
		values[81] = float64(0.05)
		values[82] = float64(0.05)
		values[83] = float64(0.05)
		values[84] = float64(0.05)
		values[85] = float64(0.05)
		values[86] = float64(0.05)
		values[87] = float64(0.05)
		values[89] = float64(0.05)
		values[95] = float64(0.05)
		encoder.Encode(values, p692)
	}
	p574 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		values[1] = float64(0.05)
		values[2] = float64(0.05)
		values[3] = float64(0.05)
		values[4] = float64(0.05)
		values[6] = float64(0.05)
		encoder.Encode(values, p574)
	}
	p633 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[45] = float64(0.05)
		values[47] = float64(0.05)
		values[48] = float64(0.05)
		values[49] = float64(0.05)
		values[50] = float64(0.05)
		values[51] = float64(0.05)
		values[52] = float64(0.05)
		values[53] = float64(0.05)
		values[55] = float64(0.05)
		values[58] = float64(0.05)
		values[59] = float64(0.05)
		values[61] = float64(0.05)
		encoder.Encode(values, p633)
	}
	p890 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[12] = float64(0.05)
		encoder.Encode(values, p890)
	}
	p636 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[48] = float64(0.05)
		values[50] = float64(0.05)
		values[51] = float64(0.05)
		values[52] = float64(0.05)
		values[53] = float64(0.05)
		values[54] = float64(0.05)
		values[55] = float64(0.05)
		values[56] = float64(0.05)
		values[58] = float64(0.05)
		values[59] = float64(0.05)
		values[60] = float64(0.05)
		values[61] = float64(0.05)
		values[62] = float64(0.05)
		values[64] = float64(0.05)
		encoder.Encode(values, p636)
	}
	p893 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		values[2] = float64(0.05)
		values[3] = float64(0.05)
		values[4] = float64(0.05)
		values[5] = float64(0.05)
		values[6] = float64(0.05)
		values[7] = float64(0.05)
		values[8] = float64(0.05)
		values[10] = float64(0.05)
		encoder.Encode(values, p893)
	}
	p639 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[51] = float64(0.05)
		values[53] = float64(0.05)
		values[54] = float64(0.05)
		values[55] = float64(0.05)
		values[56] = float64(0.05)
		values[57] = float64(0.05)
		values[59] = float64(0.05)
		values[60] = float64(0.05)
		values[61] = float64(0.05)
		values[62] = float64(0.05)
		values[63] = float64(0.05)
		values[64] = float64(0.05)
		values[65] = float64(0.05)
		values[67] = float64(0.05)
		encoder.Encode(values, p639)
	}
	p896 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[9] = float64(0.05)
		values[11] = float64(0.05)
		values[12] = float64(0.05)
		encoder.Encode(values, p896)
	}
	p588 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[35] = float64(0.05)
		values[37] = float64(0.05)
		values[38] = float64(0.05)
		values[39] = float64(0.05)
		values[40] = float64(0.05)
		values[41] = float64(0.05)
		encoder.Encode(values, p588)
	}
	p585 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[32] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[37] = float64(0.05)
		values[38] = float64(0.05)
		values[39] = float64(0.05)
		values[40] = float64(0.05)
		encoder.Encode(values, p585)
	}
	p842 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[185] = float64(0.05)
		values[186] = float64(0.05)
		values[187] = float64(0.05)
		values[188] = float64(0.05)
		values[189] = float64(0.05)
		values[191] = float64(0.05)
		encoder.Encode(values, p842)
	}
	p647 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[38] = float64(0.05)
		values[40] = float64(0.05)
		values[41] = float64(0.05)
		values[42] = float64(0.05)
		values[43] = float64(0.05)
		values[44] = float64(0.05)
		values[46] = float64(0.05)
		values[47] = float64(0.05)
		values[48] = float64(0.05)
		values[49] = float64(0.05)
		values[50] = float64(0.05)
		values[51] = float64(0.05)
		values[52] = float64(0.05)
		values[54] = float64(0.05)
		values[104] = float64(0.05)
		values[106] = float64(0.05)
		values[107] = float64(0.05)
		encoder.Encode(values, p647)
	}
	p774 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[165] = float64(0.05)
		values[167] = float64(0.05)
		values[168] = float64(0.05)
		values[171] = float64(0.05)
		values[173] = float64(0.05)
		values[174] = float64(0.05)
		values[175] = float64(0.05)
		values[176] = float64(0.05)
		values[177] = float64(0.05)
		values[178] = float64(0.05)
		values[179] = float64(0.05)
		values[181] = float64(0.05)
		encoder.Encode(values, p774)
	}
	p717 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[66] = float64(0.05)
		values[68] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		values[71] = float64(0.05)
		values[72] = float64(0.05)
		values[73] = float64(0.05)
		values[74] = float64(0.05)
		values[76] = float64(0.05)
		values[82] = float64(0.05)
		values[132] = float64(0.05)
		values[134] = float64(0.05)
		values[135] = float64(0.05)
		values[136] = float64(0.05)
		values[137] = float64(0.05)
		values[138] = float64(0.05)
		values[139] = float64(0.05)
		values[140] = float64(0.05)
		values[142] = float64(0.05)
		encoder.Encode(values, p717)
	}
	p714 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[63] = float64(0.05)
		values[65] = float64(0.05)
		values[66] = float64(0.05)
		values[67] = float64(0.05)
		values[68] = float64(0.05)
		values[69] = float64(0.05)
		values[70] = float64(0.05)
		values[71] = float64(0.05)
		values[73] = float64(0.05)
		values[123] = float64(0.05)
		values[129] = float64(0.05)
		values[131] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[135] = float64(0.05)
		values[136] = float64(0.05)
		values[137] = float64(0.05)
		values[139] = float64(0.05)
		encoder.Encode(values, p714)
	}
	p971 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[65] = float64(0.25)
		values[66] = float64(0.25)
		values[67] = float64(0.25)
		values[68] = float64(0.25)
		values[69] = float64(0.25)
		values[70] = float64(0.25)
		encoder.Encode(values, p971)
	}
	p1113 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[251] = float64(-0.25)
		values[252] = float64(0.25)
		values[254] = float64(-0.25)
		encoder.Encode(values, p1113)
	}
	p599 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[22] = float64(0.05)
		values[24] = float64(0.05)
		values[25] = float64(0.05)
		values[26] = float64(0.05)
		values[27] = float64(0.05)
		values[28] = float64(0.05)
		values[30] = float64(0.05)
		values[31] = float64(0.05)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[34] = float64(0.05)
		values[35] = float64(0.05)
		values[36] = float64(0.05)
		values[38] = float64(0.05)
		encoder.Encode(values, p599)
	}
	p658 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[26] = float64(0.05)
		values[28] = float64(0.05)
		values[29] = float64(0.05)
		values[30] = float64(0.05)
		values[31] = float64(0.05)
		values[32] = float64(0.05)
		values[33] = float64(0.05)
		values[34] = float64(0.05)
		values[36] = float64(0.05)
		values[86] = float64(0.05)
		values[92] = float64(0.05)
		values[94] = float64(0.05)
		values[95] = float64(0.05)
		values[96] = float64(0.05)
		values[97] = float64(0.05)
		values[98] = float64(0.05)
		values[99] = float64(0.05)
		values[100] = float64(0.05)
		values[102] = float64(0.05)
		encoder.Encode(values, p658)
	}
	p755 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[130] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[135] = float64(0.05)
		values[136] = float64(0.05)
		values[137] = float64(0.05)
		values[138] = float64(0.05)
		values[140] = float64(0.05)
		values[141] = float64(0.05)
		values[142] = float64(0.05)
		values[143] = float64(0.05)
		values[144] = float64(0.05)
		values[146] = float64(0.05)
		values[196] = float64(0.05)
		values[198] = float64(0.05)
		values[199] = float64(0.05)
		values[200] = float64(0.05)
		values[201] = float64(0.05)
		values[202] = float64(0.05)
		encoder.Encode(values, p755)
	}
	p758 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[127] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[135] = float64(0.05)
		values[137] = float64(0.05)
		values[140] = float64(0.05)
		values[141] = float64(0.05)
		values[143] = float64(0.05)
		values[193] = float64(0.05)
		values[195] = float64(0.05)
		values[196] = float64(0.05)
		values[197] = float64(0.05)
		values[198] = float64(0.05)
		values[199] = float64(0.05)
		values[200] = float64(0.05)
		values[201] = float64(0.05)
		encoder.Encode(values, p758)
	}
	p761 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[124] = float64(0.05)
		values[126] = float64(0.05)
		values[127] = float64(0.05)
		values[128] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[132] = float64(0.05)
		values[134] = float64(0.05)
		values[140] = float64(0.05)
		values[190] = float64(0.05)
		values[192] = float64(0.05)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[195] = float64(0.05)
		values[196] = float64(0.05)
		values[197] = float64(0.05)
		values[198] = float64(0.05)
		values[200] = float64(0.05)
		encoder.Encode(values, p761)
	}
	p888 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[3] = float64(0.05)
		values[5] = float64(0.05)
		values[6] = float64(0.05)
		values[7] = float64(0.05)
		values[8] = float64(0.05)
		values[9] = float64(0.05)
		values[10] = float64(0.05)
		values[11] = float64(0.05)
		encoder.Encode(values, p888)
	}
	p764 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[121] = float64(0.05)
		values[123] = float64(0.05)
		values[124] = float64(0.05)
		values[125] = float64(0.05)
		values[126] = float64(0.05)
		values[127] = float64(0.05)
		values[128] = float64(0.05)
		values[129] = float64(0.05)
		values[131] = float64(0.05)
		values[181] = float64(0.05)
		values[187] = float64(0.05)
		values[189] = float64(0.05)
		values[190] = float64(0.05)
		values[191] = float64(0.05)
		values[192] = float64(0.05)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[195] = float64(0.05)
		values[197] = float64(0.05)
		encoder.Encode(values, p764)
	}
	p767 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[98] = float64(0.05)
		values[148] = float64(0.05)
		values[150] = float64(0.05)
		values[151] = float64(0.05)
		values[152] = float64(0.05)
		values[153] = float64(0.05)
		values[154] = float64(0.05)
		values[155] = float64(0.05)
		values[156] = float64(0.05)
		values[158] = float64(0.05)
		values[161] = float64(0.05)
		values[162] = float64(0.05)
		values[164] = float64(0.05)
		encoder.Encode(values, p767)
	}
	p1029 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[8] = float64(0.05)
		values[9] = float64(0.05)
		values[10] = float64(0.05)
		values[11] = float64(0.05)
		encoder.Encode(values, p1029)
	}
	p772 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[168] = float64(0.05)
		values[174] = float64(0.05)
		values[176] = float64(0.05)
		values[177] = float64(0.05)
		values[178] = float64(0.05)
		values[179] = float64(0.05)
		values[180] = float64(0.05)
		values[181] = float64(0.05)
		values[182] = float64(0.05)
		values[184] = float64(0.05)
		values[190] = float64(0.05)
		encoder.Encode(values, p772)
	}
	p642 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[54] = float64(0.05)
		values[56] = float64(0.05)
		values[57] = float64(0.05)
		values[60] = float64(0.05)
		values[62] = float64(0.05)
		values[63] = float64(0.05)
		values[64] = float64(0.05)
		values[65] = float64(0.05)
		values[66] = float64(0.05)
		values[67] = float64(0.05)
		values[68] = float64(0.05)
		values[70] = float64(0.05)
		encoder.Encode(values, p642)
	}
	p899 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		values[1] = float64(0.05)
		values[2] = float64(0.05)
		values[3] = float64(0.05)
		values[4] = float64(0.05)
		values[5] = float64(0.05)
		values[7] = float64(0.05)
		values[253] = float64(0.05)
		values[255] = float64(0.05)
		encoder.Encode(values, p899)
	}
	p777 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[162] = float64(0.05)
		values[164] = float64(0.05)
		values[165] = float64(0.05)
		values[166] = float64(0.05)
		values[167] = float64(0.05)
		values[168] = float64(0.05)
		values[170] = float64(0.05)
		values[171] = float64(0.05)
		values[172] = float64(0.05)
		values[173] = float64(0.05)
		values[174] = float64(0.05)
		values[175] = float64(0.05)
		values[176] = float64(0.05)
		values[178] = float64(0.05)
		encoder.Encode(values, p777)
	}
	p780 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[159] = float64(0.05)
		values[161] = float64(0.05)
		values[162] = float64(0.05)
		values[163] = float64(0.05)
		values[164] = float64(0.05)
		values[165] = float64(0.05)
		values[166] = float64(0.05)
		values[167] = float64(0.05)
		values[169] = float64(0.05)
		values[170] = float64(0.05)
		values[171] = float64(0.05)
		values[172] = float64(0.05)
		values[173] = float64(0.05)
		values[175] = float64(0.05)
		encoder.Encode(values, p780)
	}
	p783 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[128] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[132] = float64(0.05)
		values[133] = float64(0.05)
		values[134] = float64(0.05)
		values[136] = float64(0.05)
		values[186] = float64(0.05)
		values[188] = float64(0.05)
		values[189] = float64(0.05)
		values[192] = float64(0.05)
		values[194] = float64(0.05)
		values[195] = float64(0.05)
		values[196] = float64(0.05)
		values[197] = float64(0.05)
		values[198] = float64(0.05)
		values[199] = float64(0.05)
		values[200] = float64(0.05)
		values[202] = float64(0.05)
		encoder.Encode(values, p783)
	}
	p786 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[127] = float64(0.05)
		values[177] = float64(0.05)
		values[179] = float64(0.05)
		values[180] = float64(0.05)
		values[181] = float64(0.05)
		values[182] = float64(0.05)
		values[183] = float64(0.05)
		values[184] = float64(0.05)
		values[185] = float64(0.05)
		values[187] = float64(0.05)
		values[190] = float64(0.05)
		values[191] = float64(0.05)
		values[193] = float64(0.05)
		encoder.Encode(values, p786)
	}
	p789 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[127] = float64(0.05)
		values[128] = float64(0.05)
		values[130] = float64(0.05)
		values[180] = float64(0.05)
		values[182] = float64(0.05)
		values[183] = float64(0.05)
		values[184] = float64(0.05)
		values[185] = float64(0.05)
		values[186] = float64(0.05)
		values[187] = float64(0.05)
		values[188] = float64(0.05)
		values[190] = float64(0.05)
		values[191] = float64(0.05)
		values[192] = float64(0.05)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[196] = float64(0.05)
		encoder.Encode(values, p789)
	}
	p792 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[127] = float64(0.05)
		values[128] = float64(0.05)
		values[129] = float64(0.05)
		values[130] = float64(0.05)
		values[131] = float64(0.05)
		values[133] = float64(0.05)
		values[183] = float64(0.05)
		values[185] = float64(0.05)
		values[186] = float64(0.05)
		values[187] = float64(0.05)
		values[188] = float64(0.05)
		values[189] = float64(0.05)
		values[191] = float64(0.05)
		values[192] = float64(0.05)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[195] = float64(0.05)
		values[196] = float64(0.05)
		values[197] = float64(0.05)
		values[199] = float64(0.05)
		encoder.Encode(values, p792)
	}
	p797 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[197] = float64(0.05)
		values[203] = float64(0.05)
		values[205] = float64(0.05)
		values[206] = float64(0.05)
		values[207] = float64(0.05)
		values[208] = float64(0.05)
		values[209] = float64(0.05)
		values[210] = float64(0.05)
		values[211] = float64(0.05)
		values[213] = float64(0.05)
		encoder.Encode(values, p797)
	}
	p667 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[44] = float64(0.05)
		values[50] = float64(0.05)
		values[52] = float64(0.05)
		values[53] = float64(0.05)
		values[54] = float64(0.05)
		values[55] = float64(0.05)
		values[56] = float64(0.05)
		values[57] = float64(0.05)
		values[58] = float64(0.05)
		values[60] = float64(0.05)
		values[66] = float64(0.05)
		encoder.Encode(values, p667)
	}
	p924 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.25)
		values[1] = float64(0.25)
		values[2] = float64(0.25)
		values[3] = float64(0.25)
		values[4] = float64(0.25)
		values[5] = float64(0.25)
		encoder.Encode(values, p924)
	}
	p802 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[161] = float64(0.05)
		values[163] = float64(0.05)
		values[164] = float64(0.05)
		values[165] = float64(0.05)
		values[166] = float64(0.05)
		values[167] = float64(0.05)
		values[168] = float64(0.05)
		values[169] = float64(0.05)
		values[171] = float64(0.05)
		values[177] = float64(0.05)
		encoder.Encode(values, p802)
	}
	p805 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[158] = float64(0.05)
		values[160] = float64(0.05)
		values[161] = float64(0.05)
		values[162] = float64(0.05)
		values[163] = float64(0.05)
		values[164] = float64(0.05)
		values[165] = float64(0.05)
		values[166] = float64(0.05)
		values[168] = float64(0.05)
		values[218] = float64(0.05)
		encoder.Encode(values, p805)
	}
	p1065 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[24] = float64(0.05)
		values[25] = float64(0.05)
		values[26] = float64(0.05)
		encoder.Encode(values, p1065)
	}
	p808 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[157] = float64(0.05)
		values[158] = float64(0.05)
		values[159] = float64(0.05)
		values[160] = float64(0.05)
		values[161] = float64(0.05)
		values[162] = float64(0.05)
		values[163] = float64(0.05)
		values[165] = float64(0.05)
		values[215] = float64(0.05)
		values[217] = float64(0.05)
		values[218] = float64(0.05)
		encoder.Encode(values, p808)
	}
	p811 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[156] = float64(0.05)
		values[206] = float64(0.05)
		values[208] = float64(0.05)
		values[209] = float64(0.05)
		values[210] = float64(0.05)
		values[211] = float64(0.05)
		values[212] = float64(0.05)
		values[213] = float64(0.05)
		values[214] = float64(0.05)
		values[216] = float64(0.05)
		encoder.Encode(values, p811)
	}
	p938 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[24] = float64(0.25)
		values[25] = float64(0.25)
		values[26] = float64(0.25)
		values[27] = float64(0.25)
		values[28] = float64(0.25)
		values[29] = float64(0.25)
		encoder.Encode(values, p938)
	}
	p814 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[156] = float64(0.05)
		values[157] = float64(0.05)
		values[159] = float64(0.05)
		values[209] = float64(0.05)
		values[211] = float64(0.05)
		values[212] = float64(0.05)
		values[213] = float64(0.05)
		values[214] = float64(0.05)
		values[215] = float64(0.05)
		values[216] = float64(0.05)
		values[217] = float64(0.05)
		encoder.Encode(values, p814)
	}
	p817 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[156] = float64(0.05)
		values[157] = float64(0.05)
		values[158] = float64(0.05)
		values[159] = float64(0.05)
		values[160] = float64(0.05)
		values[162] = float64(0.05)
		values[212] = float64(0.05)
		values[214] = float64(0.05)
		values[215] = float64(0.05)
		values[216] = float64(0.05)
		values[217] = float64(0.05)
		values[218] = float64(0.05)
		encoder.Encode(values, p817)
	}
	p822 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[202] = float64(0.05)
		values[204] = float64(0.05)
		values[205] = float64(0.05)
		values[208] = float64(0.05)
		values[210] = float64(0.05)
		values[211] = float64(0.05)
		values[212] = float64(0.05)
		values[213] = float64(0.05)
		values[214] = float64(0.05)
		values[215] = float64(0.05)
		values[216] = float64(0.05)
		values[218] = float64(0.05)
		encoder.Encode(values, p822)
	}
	p827 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[196] = float64(0.05)
		values[198] = float64(0.05)
		values[199] = float64(0.05)
		values[200] = float64(0.05)
		values[201] = float64(0.05)
		values[202] = float64(0.05)
		values[203] = float64(0.05)
		values[204] = float64(0.05)
		values[206] = float64(0.05)
		values[207] = float64(0.05)
		values[208] = float64(0.05)
		values[209] = float64(0.05)
		values[210] = float64(0.05)
		values[212] = float64(0.05)
		encoder.Encode(values, p827)
	}
	p1104 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[249] = float64(-0.25)
		encoder.Encode(values, p1104)
	}
	p847 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[234] = float64(0.05)
		encoder.Encode(values, p847)
	}
	p852 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[228] = float64(0.05)
		values[230] = float64(0.05)
		values[231] = float64(0.05)
		values[232] = float64(0.05)
		values[233] = float64(0.05)
		values[234] = float64(0.05)
		encoder.Encode(values, p852)
	}
	p855 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[225] = float64(0.05)
		values[227] = float64(0.05)
		values[228] = float64(0.05)
		values[229] = float64(0.05)
		values[230] = float64(0.05)
		values[231] = float64(0.05)
		values[232] = float64(0.05)
		values[233] = float64(0.05)
		encoder.Encode(values, p855)
	}
	p858 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[222] = float64(0.05)
		values[224] = float64(0.05)
		values[225] = float64(0.05)
		values[226] = float64(0.05)
		values[227] = float64(0.05)
		values[228] = float64(0.05)
		values[229] = float64(0.05)
		values[230] = float64(0.05)
		values[232] = float64(0.05)
		encoder.Encode(values, p858)
	}
	p861 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[219] = float64(0.05)
		values[221] = float64(0.05)
		values[222] = float64(0.05)
		values[223] = float64(0.05)
		values[224] = float64(0.05)
		values[225] = float64(0.05)
		values[226] = float64(0.05)
		values[227] = float64(0.05)
		values[229] = float64(0.05)
		encoder.Encode(values, p861)
	}
	p864 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[193] = float64(0.05)
		encoder.Encode(values, p864)
	}
	p1124 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[1] = float64(-0.25)
		values[254] = float64(-0.25)
		values[255] = float64(0.25)
		encoder.Encode(values, p1124)
	}
	p867 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[193] = float64(0.05)
		values[194] = float64(0.05)
		values[196] = float64(0.05)
		encoder.Encode(values, p867)
	}
	p872 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[224] = float64(0.05)
		values[226] = float64(0.05)
		values[227] = float64(0.05)
		values[228] = float64(0.05)
		values[229] = float64(0.05)
		values[230] = float64(0.05)
		values[231] = float64(0.05)
		values[232] = float64(0.05)
		values[234] = float64(0.05)
		encoder.Encode(values, p872)
	}
	p877 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[222] = float64(0.05)
		encoder.Encode(values, p877)
	}
	p880 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[222] = float64(0.05)
		values[223] = float64(0.05)
		values[225] = float64(0.05)
		encoder.Encode(values, p880)
	}
	p883 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[222] = float64(0.05)
		values[223] = float64(0.05)
		values[224] = float64(0.05)
		values[225] = float64(0.05)
		values[226] = float64(0.05)
		values[228] = float64(0.05)
		encoder.Encode(values, p883)
	}
	p902 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[6] = float64(0.05)
		values[8] = float64(0.05)
		values[9] = float64(0.05)
		values[10] = float64(0.05)
		values[11] = float64(0.05)
		values[12] = float64(0.05)
		encoder.Encode(values, p902)
	}
	p905 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.05)
		values[1] = float64(0.05)
		values[2] = float64(0.05)
		values[4] = float64(0.05)
		values[250] = float64(0.05)
		values[252] = float64(0.05)
		values[253] = float64(0.05)
		values[254] = float64(0.05)
		values[255] = float64(0.05)
		encoder.Encode(values, p905)
	}
	p908 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[1] = float64(0.05)
		values[249] = float64(0.05)
		values[250] = float64(0.05)
		values[251] = float64(0.05)
		values[252] = float64(0.05)
		values[253] = float64(0.05)
		values[254] = float64(0.05)
		values[255] = float64(0.05)
		encoder.Encode(values, p908)
	}
	p922 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[0] = float64(0.25)
		values[1] = float64(0.25)
		values[2] = float64(0.25)
		encoder.Encode(values, p922)
	}
	p927 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[3] = float64(0.25)
		values[4] = float64(0.25)
		values[5] = float64(0.25)
		values[6] = float64(0.25)
		values[7] = float64(0.25)
		values[8] = float64(0.25)
		encoder.Encode(values, p927)
	}
	p930 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[14] = float64(0.25)
		values[15] = float64(0.25)
		values[16] = float64(0.25)
		encoder.Encode(values, p930)
	}
	p948 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[44] = float64(0.25)
		values[45] = float64(0.25)
		values[46] = float64(0.25)
		values[47] = float64(0.25)
		values[48] = float64(0.25)
		values[49] = float64(0.25)
		encoder.Encode(values, p948)
	}
	p950 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[41] = float64(0.25)
		values[42] = float64(0.25)
		values[43] = float64(0.25)
		encoder.Encode(values, p950)
	}
	p958 = hefloat.NewPlaintext(params, params.MaxLevel())
	{
		values := make([]float64, slotCount)
		values[55] = float64(0.25)
		values[56] = float64(0.25)
		values[57] = float64(0.25)
		encoder.Encode(values, p958)
	}
}

func tensor_cryptonets(
	encryptedInputs map[string]*rlwe.Ciphertext,
	encodedInputs map[string]*rlwe.Plaintext,
	encryptedOutputs map[string]*rlwe.Ciphertext,
	encodedOutputs map[string]*rlwe.Plaintext,
	encoder *hefloat.Encoder,
	enc *rlwe.Encryptor,
	eval *hefloat.Evaluator,
	params hefloat.Parameters,
) {
	c566 := encryptedInputs["image"]
	_ = c566

	// FHE Operations
	buffDecompQP := make([]ringqp.Poly, params.BaseRNSDecompositionVectorSize(params.MaxLevelQ(), 0))
	for i := range buffDecompQP {
		buffDecompQP[i] = params.RingQP().NewPoly()
	}
	var lastDecompID int = -1
	var c575 *rlwe.Ciphertext
	if c575 == nil || c575.Level() < c566.Level() {
		c575, _ = eval.MulNew(c566, p574)
	} else {
		_ = eval.Mul(c566, p574, c575)
	}
	var c567 *rlwe.Ciphertext
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c567 == nil { c567 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(2), c567)
	var c577 *rlwe.Ciphertext
	if c577 == nil || c577.Level() < c567.Level() {
		c577, _ = eval.MulNew(c567, p576)
	} else {
		_ = eval.Mul(c567, p576, c577)
	}
	_ = eval.Add(c575, c577, c575)
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c577 == nil { c577 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(1), c577)
	var c580 *rlwe.Ciphertext
	if c580 == nil || c580.Level() < c577.Level() {
		c580, _ = eval.MulNew(c577, p579)
	} else {
		_ = eval.Mul(c577, p579, c580)
	}
	var c569 *rlwe.Ciphertext
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c569 == nil { c569 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(7), c569)
	var c583 *rlwe.Ciphertext
	if c583 == nil || c583.Level() < c569.Level() {
		c583, _ = eval.MulNew(c569, p582)
	} else {
		_ = eval.Mul(c569, p582, c583)
	}
	_ = eval.Add(c580, c583, c580)
	_ = eval.Add(c575, c580, c575)
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c580 == nil { c580 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(6), c580)
	if c583 == nil || c583.Level() < c580.Level() {
		c583, _ = eval.MulNew(c580, p585)
	} else {
		_ = eval.Mul(c580, p585, c583)
	}
	var c571 *rlwe.Ciphertext
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c571 == nil { c571 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(5), c571)
	var c589 *rlwe.Ciphertext
	if c589 == nil || c589.Level() < c571.Level() {
		c589, _ = eval.MulNew(c571, p588)
	} else {
		_ = eval.Mul(c571, p588, c589)
	}
	_ = eval.Add(c583, c589, c583)
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c589 == nil { c589 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(4), c589)
	var c592 *rlwe.Ciphertext
	if c592 == nil || c592.Level() < c589.Level() {
		c592, _ = eval.MulNew(c589, p591)
	} else {
		_ = eval.Mul(c589, p591, c592)
	}
	var c573 *rlwe.Ciphertext
	if lastDecompID != 566 {
		eval.DecomposeNTT(c566.Level(), params.MaxLevelP(), params.PCount(), c566.Value[1], c566.IsNTT, buffDecompQP)
		lastDecompID = 566
	}
	if c573 == nil { c573 = rlwe.NewCiphertext(params, 1, c566.Level()) }
	_ = eval.AutomorphismHoisted(c566.Level(), c566, buffDecompQP, params.GaloisElement(3), c573)
	var c595 *rlwe.Ciphertext
	if c595 == nil || c595.Level() < c573.Level() {
		c595, _ = eval.MulNew(c573, p594)
	} else {
		_ = eval.Mul(c573, p594, c595)
	}
	_ = eval.Add(c592, c595, c592)
	_ = eval.Add(c583, c592, c583)
	_ = eval.Add(c575, c583, c575)
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p597)
	} else {
		_ = eval.Mul(c577, p597, c583)
	}
	if c592 == nil || c592.Level() < c567.Level() {
		c592, _ = eval.MulNew(c567, p599)
	} else {
		_ = eval.Mul(c567, p599, c592)
	}
	_ = eval.Add(c583, c592, c583)
	if c592 == nil || c592.Level() < c573.Level() {
		c592, _ = eval.MulNew(c573, p602)
	} else {
		_ = eval.Mul(c573, p602, c592)
	}
	if c595 == nil || c595.Level() < c569.Level() {
		c595, _ = eval.MulNew(c569, p605)
	} else {
		_ = eval.Mul(c569, p605, c595)
	}
	_ = eval.Add(c592, c595, c592)
	_ = eval.Add(c583, c592, c583)
	if c595 == nil || c595.Level() < c589.Level() {
		c595, _ = eval.MulNew(c589, p608)
	} else {
		_ = eval.Mul(c589, p608, c595)
	}
	if c592 == nil || c592.Level() < c571.Level() {
		c592, _ = eval.MulNew(c571, p611)
	} else {
		_ = eval.Mul(c571, p611, c592)
	}
	_ = eval.Add(c595, c592, c595)
	if c592 == nil || c592.Level() < c580.Level() {
		c592, _ = eval.MulNew(c580, p614)
	} else {
		_ = eval.Mul(c580, p614, c592)
	}
	var c618 *rlwe.Ciphertext
	if c618 == nil || c618.Level() < c566.Level() {
		c618, _ = eval.MulNew(c566, p617)
	} else {
		_ = eval.Mul(c566, p617, c618)
	}
	_ = eval.Add(c592, c618, c592)
	_ = eval.Add(c595, c592, c595)
	_ = eval.Add(c583, c595, c583)
	_ = eval.Rotate(c583, 8, c583)
	_ = eval.Add(c575, c583, c575)
	if c595 == nil || c595.Level() < c566.Level() {
		c595, _ = eval.MulNew(c566, p622)
	} else {
		_ = eval.Mul(c566, p622, c595)
	}
	if c592 == nil || c592.Level() < c577.Level() {
		c592, _ = eval.MulNew(c577, p624)
	} else {
		_ = eval.Mul(c577, p624, c592)
	}
	_ = eval.Add(c595, c592, c595)
	if c592 == nil || c592.Level() < c567.Level() {
		c592, _ = eval.MulNew(c567, p627)
	} else {
		_ = eval.Mul(c567, p627, c592)
	}
	if c583 == nil || c583.Level() < c573.Level() {
		c583, _ = eval.MulNew(c573, p630)
	} else {
		_ = eval.Mul(c573, p630, c583)
	}
	_ = eval.Add(c592, c583, c592)
	_ = eval.Add(c595, c592, c595)
	if c592 == nil || c592.Level() < c569.Level() {
		c592, _ = eval.MulNew(c569, p633)
	} else {
		_ = eval.Mul(c569, p633, c592)
	}
	if c583 == nil || c583.Level() < c580.Level() {
		c583, _ = eval.MulNew(c580, p636)
	} else {
		_ = eval.Mul(c580, p636, c583)
	}
	_ = eval.Add(c592, c583, c592)
	if c583 == nil || c583.Level() < c571.Level() {
		c583, _ = eval.MulNew(c571, p639)
	} else {
		_ = eval.Mul(c571, p639, c583)
	}
	if c618 == nil || c618.Level() < c589.Level() {
		c618, _ = eval.MulNew(c589, p642)
	} else {
		_ = eval.Mul(c589, p642, c618)
	}
	_ = eval.Add(c583, c618, c583)
	_ = eval.Add(c592, c583, c592)
	_ = eval.Add(c595, c592, c595)
	_ = eval.Rotate(c595, 16, c595)
	if c592 == nil || c592.Level() < c567.Level() {
		c592, _ = eval.MulNew(c567, p647)
	} else {
		_ = eval.Mul(c567, p647, c592)
	}
	if c583 == nil || c583.Level() < c573.Level() {
		c583, _ = eval.MulNew(c573, p649)
	} else {
		_ = eval.Mul(c573, p649, c583)
	}
	_ = eval.Add(c592, c583, c592)
	if c618 == nil || c618.Level() < c589.Level() {
		c618, _ = eval.MulNew(c589, p652)
	} else {
		_ = eval.Mul(c589, p652, c618)
	}
	if c583 == nil || c583.Level() < c571.Level() {
		c583, _ = eval.MulNew(c571, p655)
	} else {
		_ = eval.Mul(c571, p655, c583)
	}
	_ = eval.Add(c618, c583, c618)
	_ = eval.Add(c592, c618, c592)
	if c618 == nil || c618.Level() < c580.Level() {
		c618, _ = eval.MulNew(c580, p658)
	} else {
		_ = eval.Mul(c580, p658, c618)
	}
	if c583 == nil || c583.Level() < c569.Level() {
		c583, _ = eval.MulNew(c569, p661)
	} else {
		_ = eval.Mul(c569, p661, c583)
	}
	_ = eval.Add(c618, c583, c618)
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p664)
	} else {
		_ = eval.Mul(c577, p664, c583)
	}
	var c668 *rlwe.Ciphertext
	if c668 == nil || c668.Level() < c566.Level() {
		c668, _ = eval.MulNew(c566, p667)
	} else {
		_ = eval.Mul(c566, p667, c668)
	}
	_ = eval.Add(c583, c668, c583)
	_ = eval.Add(c618, c583, c618)
	_ = eval.Add(c592, c618, c592)
	_ = eval.Rotate(c592, 24, c592)
	_ = eval.Add(c595, c592, c595)
	_ = eval.Add(c575, c595, c575)
	if c592 == nil || c592.Level() < c566.Level() {
		c592, _ = eval.MulNew(c566, p672)
	} else {
		_ = eval.Mul(c566, p672, c592)
	}
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p674)
	} else {
		_ = eval.Mul(c577, p674, c583)
	}
	_ = eval.Add(c592, c583, c592)
	if c583 == nil || c583.Level() < c567.Level() {
		c583, _ = eval.MulNew(c567, p677)
	} else {
		_ = eval.Mul(c567, p677, c583)
	}
	if c668 == nil || c668.Level() < c569.Level() {
		c668, _ = eval.MulNew(c569, p680)
	} else {
		_ = eval.Mul(c569, p680, c668)
	}
	_ = eval.Add(c583, c668, c583)
	_ = eval.Add(c592, c583, c592)
	if c668 == nil || c668.Level() < c580.Level() {
		c668, _ = eval.MulNew(c580, p683)
	} else {
		_ = eval.Mul(c580, p683, c668)
	}
	if c618 == nil || c618.Level() < c571.Level() {
		c618, _ = eval.MulNew(c571, p686)
	} else {
		_ = eval.Mul(c571, p686, c618)
	}
	_ = eval.Add(c668, c618, c668)
	if c595 == nil || c595.Level() < c589.Level() {
		c595, _ = eval.MulNew(c589, p689)
	} else {
		_ = eval.Mul(c589, p689, c595)
	}
	if c583 == nil || c583.Level() < c573.Level() {
		c583, _ = eval.MulNew(c573, p692)
	} else {
		_ = eval.Mul(c573, p692, c583)
	}
	_ = eval.Add(c595, c583, c595)
	_ = eval.Add(c668, c595, c668)
	_ = eval.Add(c592, c668, c592)
	_ = eval.Rotate(c592, 32, c592)
	if c668 == nil || c668.Level() < c580.Level() {
		c668, _ = eval.MulNew(c580, p697)
	} else {
		_ = eval.Mul(c580, p697, c668)
	}
	if c595 == nil || c595.Level() < c569.Level() {
		c595, _ = eval.MulNew(c569, p699)
	} else {
		_ = eval.Mul(c569, p699, c595)
	}
	_ = eval.Add(c668, c595, c668)
	if c595 == nil || c595.Level() < c573.Level() {
		c595, _ = eval.MulNew(c573, p702)
	} else {
		_ = eval.Mul(c573, p702, c595)
	}
	if c583 == nil || c583.Level() < c589.Level() {
		c583, _ = eval.MulNew(c589, p705)
	} else {
		_ = eval.Mul(c589, p705, c583)
	}
	_ = eval.Add(c595, c583, c595)
	_ = eval.Add(c668, c595, c668)
	if c595 == nil || c595.Level() < c571.Level() {
		c595, _ = eval.MulNew(c571, p708)
	} else {
		_ = eval.Mul(c571, p708, c595)
	}
	if c583 == nil || c583.Level() < c567.Level() {
		c583, _ = eval.MulNew(c567, p711)
	} else {
		_ = eval.Mul(c567, p711, c583)
	}
	_ = eval.Add(c595, c583, c595)
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p714)
	} else {
		_ = eval.Mul(c577, p714, c583)
	}
	if c618 == nil || c618.Level() < c566.Level() {
		c618, _ = eval.MulNew(c566, p717)
	} else {
		_ = eval.Mul(c566, p717, c618)
	}
	_ = eval.Add(c583, c618, c583)
	_ = eval.Add(c595, c583, c595)
	_ = eval.Add(c668, c595, c668)
	_ = eval.Rotate(c668, 40, c668)
	_ = eval.Add(c592, c668, c592)
	if c595 == nil || c595.Level() < c566.Level() {
		c595, _ = eval.MulNew(c566, p722)
	} else {
		_ = eval.Mul(c566, p722, c595)
	}
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p724)
	} else {
		_ = eval.Mul(c577, p724, c583)
	}
	_ = eval.Add(c595, c583, c595)
	if c583 == nil || c583.Level() < c567.Level() {
		c583, _ = eval.MulNew(c567, p727)
	} else {
		_ = eval.Mul(c567, p727, c583)
	}
	if c668 == nil || c668.Level() < c573.Level() {
		c668, _ = eval.MulNew(c573, p730)
	} else {
		_ = eval.Mul(c573, p730, c668)
	}
	_ = eval.Add(c583, c668, c583)
	_ = eval.Add(c595, c583, c595)
	if c583 == nil || c583.Level() < c580.Level() {
		c583, _ = eval.MulNew(c580, p733)
	} else {
		_ = eval.Mul(c580, p733, c583)
	}
	if c668 == nil || c668.Level() < c569.Level() {
		c668, _ = eval.MulNew(c569, p736)
	} else {
		_ = eval.Mul(c569, p736, c668)
	}
	_ = eval.Add(c583, c668, c583)
	if c668 == nil || c668.Level() < c571.Level() {
		c668, _ = eval.MulNew(c571, p739)
	} else {
		_ = eval.Mul(c571, p739, c668)
	}
	if c618 == nil || c618.Level() < c589.Level() {
		c618, _ = eval.MulNew(c589, p742)
	} else {
		_ = eval.Mul(c589, p742, c618)
	}
	_ = eval.Add(c668, c618, c668)
	_ = eval.Add(c583, c668, c583)
	_ = eval.Add(c595, c583, c595)
	_ = eval.Rotate(c595, 48, c595)
	if c668 == nil || c668.Level() < c577.Level() {
		c668, _ = eval.MulNew(c577, p747)
	} else {
		_ = eval.Mul(c577, p747, c668)
	}
	if c618 == nil || c618.Level() < c567.Level() {
		c618, _ = eval.MulNew(c567, p749)
	} else {
		_ = eval.Mul(c567, p749, c618)
	}
	_ = eval.Add(c668, c618, c668)
	if c618 == nil || c618.Level() < c573.Level() {
		c618, _ = eval.MulNew(c573, p752)
	} else {
		_ = eval.Mul(c573, p752, c618)
	}
	if c583 == nil || c583.Level() < c589.Level() {
		c583, _ = eval.MulNew(c589, p755)
	} else {
		_ = eval.Mul(c589, p755, c583)
	}
	_ = eval.Add(c618, c583, c618)
	_ = eval.Add(c668, c618, c668)
	if c583 == nil || c583.Level() < c571.Level() {
		c583, _ = eval.MulNew(c571, p758)
	} else {
		_ = eval.Mul(c571, p758, c583)
	}
	if c618 == nil || c618.Level() < c580.Level() {
		c618, _ = eval.MulNew(c580, p761)
	} else {
		_ = eval.Mul(c580, p761, c618)
	}
	_ = eval.Add(c583, c618, c583)
	if c618 == nil || c618.Level() < c569.Level() {
		c618, _ = eval.MulNew(c569, p764)
	} else {
		_ = eval.Mul(c569, p764, c618)
	}
	var c768 *rlwe.Ciphertext
	if c768 == nil || c768.Level() < c566.Level() {
		c768, _ = eval.MulNew(c566, p767)
	} else {
		_ = eval.Mul(c566, p767, c768)
	}
	_ = eval.Add(c618, c768, c618)
	_ = eval.Add(c583, c618, c583)
	_ = eval.Add(c668, c583, c668)
	_ = eval.Rotate(c668, 56, c668)
	_ = eval.Add(c595, c668, c595)
	_ = eval.Add(c592, c595, c592)
	_ = eval.Add(c575, c592, c575)
	if c592 == nil || c592.Level() < c589.Level() {
		c592, _ = eval.MulNew(c589, p772)
	} else {
		_ = eval.Mul(c589, p772, c592)
	}
	if c618 == nil || c618.Level() < c571.Level() {
		c618, _ = eval.MulNew(c571, p774)
	} else {
		_ = eval.Mul(c571, p774, c618)
	}
	_ = eval.Add(c592, c618, c592)
	if c583 == nil || c583.Level() < c580.Level() {
		c583, _ = eval.MulNew(c580, p777)
	} else {
		_ = eval.Mul(c580, p777, c583)
	}
	if c768 == nil || c768.Level() < c569.Level() {
		c768, _ = eval.MulNew(c569, p780)
	} else {
		_ = eval.Mul(c569, p780, c768)
	}
	_ = eval.Add(c583, c768, c583)
	_ = eval.Add(c592, c583, c592)
	if c768 == nil || c768.Level() < c566.Level() {
		c768, _ = eval.MulNew(c566, p783)
	} else {
		_ = eval.Mul(c566, p783, c768)
	}
	if c668 == nil || c668.Level() < c573.Level() {
		c668, _ = eval.MulNew(c573, p786)
	} else {
		_ = eval.Mul(c573, p786, c668)
	}
	_ = eval.Add(c768, c668, c768)
	if c668 == nil || c668.Level() < c567.Level() {
		c668, _ = eval.MulNew(c567, p789)
	} else {
		_ = eval.Mul(c567, p789, c668)
	}
	if c595 == nil || c595.Level() < c577.Level() {
		c595, _ = eval.MulNew(c577, p792)
	} else {
		_ = eval.Mul(c577, p792, c595)
	}
	_ = eval.Add(c668, c595, c668)
	_ = eval.Add(c768, c668, c768)
	_ = eval.Add(c592, c768, c592)
	_ = eval.Rotate(c592, 64, c592)
	if c768 == nil || c768.Level() < c569.Level() {
		c768, _ = eval.MulNew(c569, p797)
	} else {
		_ = eval.Mul(c569, p797, c768)
	}
	if c668 == nil || c668.Level() < c566.Level() {
		c668, _ = eval.MulNew(c566, p799)
	} else {
		_ = eval.Mul(c566, p799, c668)
	}
	_ = eval.Add(c768, c668, c768)
	if c595 == nil || c595.Level() < c577.Level() {
		c595, _ = eval.MulNew(c577, p802)
	} else {
		_ = eval.Mul(c577, p802, c595)
	}
	if c668 == nil || c668.Level() < c567.Level() {
		c668, _ = eval.MulNew(c567, p805)
	} else {
		_ = eval.Mul(c567, p805, c668)
	}
	_ = eval.Add(c595, c668, c595)
	_ = eval.Add(c768, c595, c768)
	if c668 == nil || c668.Level() < c573.Level() {
		c668, _ = eval.MulNew(c573, p808)
	} else {
		_ = eval.Mul(c573, p808, c668)
	}
	if c595 == nil || c595.Level() < c580.Level() {
		c595, _ = eval.MulNew(c580, p811)
	} else {
		_ = eval.Mul(c580, p811, c595)
	}
	_ = eval.Add(c668, c595, c668)
	if c595 == nil || c595.Level() < c571.Level() {
		c595, _ = eval.MulNew(c571, p814)
	} else {
		_ = eval.Mul(c571, p814, c595)
	}
	if c583 == nil || c583.Level() < c589.Level() {
		c583, _ = eval.MulNew(c589, p817)
	} else {
		_ = eval.Mul(c589, p817, c583)
	}
	_ = eval.Add(c595, c583, c595)
	_ = eval.Add(c668, c595, c668)
	_ = eval.Add(c768, c668, c768)
	_ = eval.Rotate(c768, 72, c768)
	_ = eval.Add(c592, c768, c592)
	if c768 == nil || c768.Level() < c566.Level() {
		c768, _ = eval.MulNew(c566, p822)
	} else {
		_ = eval.Mul(c566, p822, c768)
	}
	if c668 == nil || c668.Level() < c577.Level() {
		c668, _ = eval.MulNew(c577, p824)
	} else {
		_ = eval.Mul(c577, p824, c668)
	}
	_ = eval.Add(c768, c668, c768)
	if c668 == nil || c668.Level() < c567.Level() {
		c668, _ = eval.MulNew(c567, p827)
	} else {
		_ = eval.Mul(c567, p827, c668)
	}
	if c595 == nil || c595.Level() < c573.Level() {
		c595, _ = eval.MulNew(c573, p830)
	} else {
		_ = eval.Mul(c573, p830, c595)
	}
	_ = eval.Add(c668, c595, c668)
	_ = eval.Add(c768, c668, c768)
	if c668 == nil || c668.Level() < c589.Level() {
		c668, _ = eval.MulNew(c589, p833)
	} else {
		_ = eval.Mul(c589, p833, c668)
	}
	if c583 == nil || c583.Level() < c571.Level() {
		c583, _ = eval.MulNew(c571, p836)
	} else {
		_ = eval.Mul(c571, p836, c583)
	}
	_ = eval.Add(c668, c583, c668)
	if c583 == nil || c583.Level() < c580.Level() {
		c583, _ = eval.MulNew(c580, p839)
	} else {
		_ = eval.Mul(c580, p839, c583)
	}
	if c595 == nil || c595.Level() < c569.Level() {
		c595, _ = eval.MulNew(c569, p842)
	} else {
		_ = eval.Mul(c569, p842, c595)
	}
	_ = eval.Add(c583, c595, c583)
	_ = eval.Add(c668, c583, c668)
	_ = eval.Add(c768, c668, c768)
	_ = eval.Rotate(c768, 80, c768)
	if c668 == nil || c668.Level() < c567.Level() {
		c668, _ = eval.MulNew(c567, p847)
	} else {
		_ = eval.Mul(c567, p847, c668)
	}
	if c583 == nil || c583.Level() < c573.Level() {
		c583, _ = eval.MulNew(c573, p849)
	} else {
		_ = eval.Mul(c573, p849, c583)
	}
	_ = eval.Add(c668, c583, c668)
	if c595 == nil || c595.Level() < c589.Level() {
		c595, _ = eval.MulNew(c589, p852)
	} else {
		_ = eval.Mul(c589, p852, c595)
	}
	if c583 == nil || c583.Level() < c571.Level() {
		c583, _ = eval.MulNew(c571, p855)
	} else {
		_ = eval.Mul(c571, p855, c583)
	}
	_ = eval.Add(c595, c583, c595)
	_ = eval.Add(c668, c595, c668)
	if c595 == nil || c595.Level() < c580.Level() {
		c595, _ = eval.MulNew(c580, p858)
	} else {
		_ = eval.Mul(c580, p858, c595)
	}
	if c583 == nil || c583.Level() < c569.Level() {
		c583, _ = eval.MulNew(c569, p861)
	} else {
		_ = eval.Mul(c569, p861, c583)
	}
	_ = eval.Add(c595, c583, c595)
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p864)
	} else {
		_ = eval.Mul(c577, p864, c583)
	}
	if c618 == nil || c618.Level() < c566.Level() {
		c618, _ = eval.MulNew(c566, p867)
	} else {
		_ = eval.Mul(c566, p867, c618)
	}
	_ = eval.Add(c583, c618, c583)
	_ = eval.Add(c595, c583, c595)
	_ = eval.Add(c668, c595, c668)
	_ = eval.Rotate(c668, 88, c668)
	_ = eval.Add(c768, c668, c768)
	if c668 == nil || c668.Level() < c566.Level() {
		c668, _ = eval.MulNew(c566, p872)
	} else {
		_ = eval.Mul(c566, p872, c668)
	}
	if c618 == nil || c618.Level() < c577.Level() {
		c618, _ = eval.MulNew(c577, p874)
	} else {
		_ = eval.Mul(c577, p874, c618)
	}
	_ = eval.Add(c668, c618, c668)
	if c618 == nil || c618.Level() < c589.Level() {
		c618, _ = eval.MulNew(c589, p877)
	} else {
		_ = eval.Mul(c589, p877, c618)
	}
	if c583 == nil || c583.Level() < c573.Level() {
		c583, _ = eval.MulNew(c573, p880)
	} else {
		_ = eval.Mul(c573, p880, c583)
	}
	_ = eval.Add(c618, c583, c618)
	if c583 == nil || c583.Level() < c567.Level() {
		c583, _ = eval.MulNew(c567, p883)
	} else {
		_ = eval.Mul(c567, p883, c583)
	}
	_ = eval.Add(c618, c583, c618)
	_ = eval.Add(c668, c618, c668)
	_ = eval.Rotate(c668, 96, c668)
	_ = eval.Mul(c573, p888, c573)
	_ = eval.Mul(c566, p890, c566)
	_ = eval.Add(c573, c566, c573)
	_ = eval.Mul(c589, p893, c589)
	_ = eval.Mul(c577, p896, c577)
	_ = eval.Add(c589, c577, c589)
	_ = eval.Add(c573, c589, c573)
	_ = eval.Mul(c571, p899, c571)
	_ = eval.Mul(c567, p902, c567)
	_ = eval.Add(c571, c567, c571)
	_ = eval.Mul(c580, p905, c580)
	_ = eval.Mul(c569, p908, c569)
	_ = eval.Add(c580, c569, c580)
	_ = eval.Add(c571, c580, c571)
	_ = eval.Add(c573, c571, c573)
	_ = eval.Rotate(c573, 248, c573)
	_ = eval.Add(c668, c573, c668)
	_ = eval.Add(c768, c668, c768)
	_ = eval.Add(c592, c768, c592)
	_ = eval.Add(c575, c592, c575)
	_ = eval.Rescale(c575, c575)
	_ = eval.MulRelin(c575, c575, c575)
	_ = eval.Rescale(c575, c575)
	if c592 == nil || c592.Level() < c575.Level() {
		c592, _ = eval.MulNew(c575, p922)
	} else {
		_ = eval.Mul(c575, p922, c592)
	}
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c573 == nil { c573 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(3), c573)
	if c571 == nil || c571.Level() < c573.Level() {
		c571, _ = eval.MulNew(c573, p924)
	} else {
		_ = eval.Mul(c573, p924, c571)
	}
	_ = eval.Add(c592, c571, c592)
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c571 == nil { c571 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(6), c571)
	if c569 == nil || c569.Level() < c571.Level() {
		c569, _ = eval.MulNew(c571, p927)
	} else {
		_ = eval.Mul(c571, p927, c569)
	}
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c668 == nil { c668 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(1), c668)
	if c567 == nil || c567.Level() < c668.Level() {
		c567, _ = eval.MulNew(c668, p930)
	} else {
		_ = eval.Mul(c668, p930, c567)
	}
	_ = eval.Rotate(c567, 8, c567)
	_ = eval.Add(c569, c567, c569)
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c567 == nil { c567 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(5), c567)
	if c589 == nil || c589.Level() < c567.Level() {
		c589, _ = eval.MulNew(c567, p934)
	} else {
		_ = eval.Mul(c567, p934, c589)
	}
	_ = eval.Rotate(c589, 16, c589)
	_ = eval.Add(c569, c589, c569)
	_ = eval.Add(c592, c569, c592)
	if c569 == nil || c569.Level() < c575.Level() {
		c569, _ = eval.MulNew(c575, p938)
	} else {
		_ = eval.Mul(c575, p938, c569)
	}
	if c589 == nil || c589.Level() < c573.Level() {
		c589, _ = eval.MulNew(c573, p940)
	} else {
		_ = eval.Mul(c573, p940, c589)
	}
	_ = eval.Add(c569, c589, c569)
	if c589 == nil || c589.Level() < c571.Level() {
		c589, _ = eval.MulNew(c571, p943)
	} else {
		_ = eval.Mul(c571, p943, c589)
	}
	_ = eval.Add(c569, c589, c569)
	_ = eval.Rotate(c569, 24, c569)
	_ = eval.Add(c592, c569, c592)
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c569 == nil { c569 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(7), c569)
	if c589 == nil || c589.Level() < c569.Level() {
		c589, _ = eval.MulNew(c569, p948)
	} else {
		_ = eval.Mul(c569, p948, c589)
	}
	if c580 == nil || c580.Level() < c668.Level() {
		c580, _ = eval.MulNew(c668, p950)
	} else {
		_ = eval.Mul(c668, p950, c580)
	}
	_ = eval.Add(c589, c580, c589)
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c580 == nil { c580 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(4), c580)
	if c577 == nil || c577.Level() < c580.Level() {
		c577, _ = eval.MulNew(c580, p953)
	} else {
		_ = eval.Mul(c580, p953, c577)
	}
	_ = eval.Add(c589, c577, c589)
	_ = eval.Rotate(c589, 32, c589)
	if lastDecompID != 575 {
		eval.DecomposeNTT(c575.Level(), params.MaxLevelP(), params.PCount(), c575.Value[1], c575.IsNTT, buffDecompQP)
		lastDecompID = 575
	}
	if c577 == nil { c577 = rlwe.NewCiphertext(params, 1, c575.Level()) }
	_ = eval.AutomorphismHoisted(c575.Level(), c575, buffDecompQP, params.GaloisElement(2), c577)
	if c618 == nil || c618.Level() < c577.Level() {
		c618, _ = eval.MulNew(c577, p958)
	} else {
		_ = eval.Mul(c577, p958, c618)
	}
	_ = eval.Rotate(c618, 40, c618)
	_ = eval.Mul(c571, p962, c571)
	_ = eval.Rotate(c571, 48, c571)
	_ = eval.Add(c618, c571, c618)
	_ = eval.Add(c589, c618, c589)
	_ = eval.Add(c592, c589, c592)
	if c589 == nil || c589.Level() < c569.Level() {
		c589, _ = eval.MulNew(c569, p966)
	} else {
		_ = eval.Mul(c569, p966, c589)
	}
	_ = eval.Mul(c580, p968, c580)
	_ = eval.Add(c589, c580, c589)
	_ = eval.Mul(c668, p971, c668)
	_ = eval.Add(c589, c668, c589)
	_ = eval.Rotate(c589, 56, c589)
	if c580 == nil || c580.Level() < c567.Level() {
		c580, _ = eval.MulNew(c567, p976)
	} else {
		_ = eval.Mul(c567, p976, c580)
	}
	if c571 == nil || c571.Level() < c577.Level() {
		c571, _ = eval.MulNew(c577, p978)
	} else {
		_ = eval.Mul(c577, p978, c571)
	}
	_ = eval.Add(c580, c571, c580)
	_ = eval.Rotate(c580, 64, c580)
	_ = eval.Add(c589, c580, c589)
	_ = eval.Mul(c573, p983, c573)
	if c580 == nil || c580.Level() < c575.Level() {
		c580, _ = eval.MulNew(c575, p985)
	} else {
		_ = eval.Mul(c575, p985, c580)
	}
	_ = eval.Add(c573, c580, c573)
	_ = eval.Rotate(c573, 72, c573)
	_ = eval.Mul(c569, p990, c569)
	_ = eval.Rotate(c569, 80, c569)
	_ = eval.Add(c573, c569, c573)
	_ = eval.Mul(c577, p994, c577)
	_ = eval.Mul(c567, p996, c567)
	_ = eval.Add(c577, c567, c577)
	_ = eval.Rotate(c577, 88, c577)
	if c567 == nil || c567.Level() < c575.Level() {
		c567, _ = eval.MulNew(c575, p1001)
	} else {
		_ = eval.Mul(c575, p1001, c567)
	}
	_ = eval.Rotate(c567, 96, c567)
	_ = eval.Add(c577, c567, c577)
	_ = eval.Add(c573, c577, c573)
	_ = eval.Add(c589, c573, c589)
	_ = eval.Add(c592, c589, c592)
	_ = eval.Rescale(c592, c592)
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c589 == nil { c589 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(7), c589)
	if c573 == nil || c573.Level() < c589.Level() {
		c573, _ = eval.MulNew(c589, p1013)
	} else {
		_ = eval.Mul(c589, p1013, c573)
	}
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c577 == nil { c577 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(6), c577)
	if c567 == nil || c567.Level() < c577.Level() {
		c567, _ = eval.MulNew(c577, p1013)
	} else {
		_ = eval.Mul(c577, p1013, c567)
	}
	_ = eval.Add(c573, c567, c573)
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c569 == nil { c569 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(5), c569)
	if c567 == nil || c567.Level() < c569.Level() {
		c567, _ = eval.MulNew(c569, p1013)
	} else {
		_ = eval.Mul(c569, p1013, c567)
	}
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c580 == nil { c580 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(4), c580)
	if c571 == nil || c571.Level() < c580.Level() {
		c571, _ = eval.MulNew(c580, p1013)
	} else {
		_ = eval.Mul(c580, p1013, c571)
	}
	_ = eval.Add(c567, c571, c567)
	_ = eval.Add(c573, c567, c573)
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c567 == nil { c567 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(3), c567)
	if c571 == nil || c571.Level() < c567.Level() {
		c571, _ = eval.MulNew(c567, p1013)
	} else {
		_ = eval.Mul(c567, p1013, c571)
	}
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c668 == nil { c668 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(2), c668)
	if c583 == nil || c583.Level() < c668.Level() {
		c583, _ = eval.MulNew(c668, p1013)
	} else {
		_ = eval.Mul(c668, p1013, c583)
	}
	_ = eval.Add(c571, c583, c571)
	if lastDecompID != 592 {
		eval.DecomposeNTT(c592.Level(), params.MaxLevelP(), params.PCount(), c592.Value[1], c592.IsNTT, buffDecompQP)
		lastDecompID = 592
	}
	if c583 == nil { c583 = rlwe.NewCiphertext(params, 1, c592.Level()) }
	_ = eval.AutomorphismHoisted(c592.Level(), c592, buffDecompQP, params.GaloisElement(1), c583)
	if c768 == nil || c768.Level() < c583.Level() {
		c768, _ = eval.MulNew(c583, p1013)
	} else {
		_ = eval.Mul(c583, p1013, c768)
	}
	if c618 == nil || c618.Level() < c592.Level() {
		c618, _ = eval.MulNew(c592, p1013)
	} else {
		_ = eval.Mul(c592, p1013, c618)
	}
	_ = eval.Add(c768, c618, c768)
	_ = eval.Add(c571, c768, c571)
	_ = eval.Add(c573, c571, c573)
	if c571 == nil || c571.Level() < c580.Level() {
		c571, _ = eval.MulNew(c580, p1029)
	} else {
		_ = eval.Mul(c580, p1029, c571)
	}
	if c618 == nil || c618.Level() < c567.Level() {
		c618, _ = eval.MulNew(c567, p1029)
	} else {
		_ = eval.Mul(c567, p1029, c618)
	}
	_ = eval.Add(c571, c618, c571)
	if c618 == nil || c618.Level() < c668.Level() {
		c618, _ = eval.MulNew(c668, p1029)
	} else {
		_ = eval.Mul(c668, p1029, c618)
	}
	if c768 == nil || c768.Level() < c583.Level() {
		c768, _ = eval.MulNew(c583, p1029)
	} else {
		_ = eval.Mul(c583, p1029, c768)
	}
	_ = eval.Add(c618, c768, c618)
	_ = eval.Add(c571, c618, c571)
	if c618 == nil || c618.Level() < c592.Level() {
		c618, _ = eval.MulNew(c592, p1029)
	} else {
		_ = eval.Mul(c592, p1029, c618)
	}
	if c768 == nil || c768.Level() < c569.Level() {
		c768, _ = eval.MulNew(c569, p1029)
	} else {
		_ = eval.Mul(c569, p1029, c768)
	}
	_ = eval.Add(c618, c768, c618)
	if c768 == nil || c768.Level() < c577.Level() {
		c768, _ = eval.MulNew(c577, p1029)
	} else {
		_ = eval.Mul(c577, p1029, c768)
	}
	if c566 == nil || c566.Level() < c589.Level() {
		c566, _ = eval.MulNew(c589, p1029)
	} else {
		_ = eval.Mul(c589, p1029, c566)
	}
	_ = eval.Add(c768, c566, c768)
	_ = eval.Add(c618, c768, c618)
	_ = eval.Add(c571, c618, c571)
	_ = eval.Rotate(c571, 8, c571)
	_ = eval.Add(c573, c571, c573)
	if c571 == nil || c571.Level() < c592.Level() {
		c571, _ = eval.MulNew(c592, p1047)
	} else {
		_ = eval.Mul(c592, p1047, c571)
	}
	if c618 == nil || c618.Level() < c583.Level() {
		c618, _ = eval.MulNew(c583, p1047)
	} else {
		_ = eval.Mul(c583, p1047, c618)
	}
	_ = eval.Add(c571, c618, c571)
	_ = eval.Mul(c580, p1047, c580)
	if c618 == nil || c618.Level() < c569.Level() {
		c618, _ = eval.MulNew(c569, p1047)
	} else {
		_ = eval.Mul(c569, p1047, c618)
	}
	_ = eval.Add(c580, c618, c580)
	_ = eval.Add(c571, c580, c571)
	if c618 == nil || c618.Level() < c577.Level() {
		c618, _ = eval.MulNew(c577, p1047)
	} else {
		_ = eval.Mul(c577, p1047, c618)
	}
	if c580 == nil || c580.Level() < c668.Level() {
		c580, _ = eval.MulNew(c668, p1047)
	} else {
		_ = eval.Mul(c668, p1047, c580)
	}
	_ = eval.Add(c618, c580, c618)
	if c580 == nil || c580.Level() < c589.Level() {
		c580, _ = eval.MulNew(c589, p1047)
	} else {
		_ = eval.Mul(c589, p1047, c580)
	}
	_ = eval.Mul(c567, p1047, c567)
	_ = eval.Add(c580, c567, c580)
	_ = eval.Add(c618, c580, c618)
	_ = eval.Add(c571, c618, c571)
	_ = eval.Rotate(c571, 16, c571)
	_ = eval.Mul(c592, p1065, c592)
	_ = eval.Mul(c583, p1067, c583)
	_ = eval.Add(c592, c583, c592)
	_ = eval.Mul(c668, p1070, c668)
	_ = eval.Add(c592, c668, c592)
	_ = eval.Rotate(c592, 24, c592)
	_ = eval.Add(c571, c592, c571)
	_ = eval.Mul(c569, p1075, c569)
	_ = eval.Mul(c577, p1077, c577)
	_ = eval.Add(c569, c577, c569)
	_ = eval.Mul(c589, p1080, c589)
	_ = eval.Add(c569, c589, c569)
	_ = eval.Rotate(c569, 248, c569)
	_ = eval.Add(c571, c569, c571)
	_ = eval.Add(c573, c571, c573)
	_ = eval.Rescale(c573, c573)
	_ = eval.MulRelin(c573, c573, c573)
	_ = eval.Rescale(c573, c573)
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c571 == nil { c571 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(1), c571)
	if c569 == nil || c569.Level() < c571.Level() {
		c569, _ = eval.MulNew(c571, p1094)
	} else {
		_ = eval.Mul(c571, p1094, c569)
	}
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c589 == nil { c589 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(3), c589)
	if c577 == nil || c577.Level() < c589.Level() {
		c577, _ = eval.MulNew(c589, p1096)
	} else {
		_ = eval.Mul(c589, p1096, c577)
	}
	_ = eval.Add(c569, c577, c569)
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c592 == nil { c592 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(2), c592)
	if c668 == nil || c668.Level() < c592.Level() {
		c668, _ = eval.MulNew(c592, p576)
	} else {
		_ = eval.Mul(c592, p576, c668)
	}
	if c577 == nil || c577.Level() < c573.Level() {
		c577, _ = eval.MulNew(c573, p1101)
	} else {
		_ = eval.Mul(c573, p1101, c577)
	}
	_ = eval.Add(c668, c577, c668)
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c577 == nil { c577 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(7), c577)
	if c583 == nil || c583.Level() < c577.Level() {
		c583, _ = eval.MulNew(c577, p1104)
	} else {
		_ = eval.Mul(c577, p1104, c583)
	}
	_ = eval.Rotate(c583, 240, c583)
	_ = eval.Add(c668, c583, c668)
	_ = eval.Add(c569, c668, c569)
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c668 == nil { c668 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(4), c668)
	_ = eval.Mul(c668, p1108, c668)
	_ = eval.Mul(c589, p1110, c589)
	_ = eval.Add(c668, c589, c668)
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c589 == nil { c589 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(5), c589)
	_ = eval.Mul(c589, p1113, c589)
	_ = eval.Mul(c577, p1116, c577)
	_ = eval.Add(c589, c577, c589)
	_ = eval.Add(c668, c589, c668)
	if lastDecompID != 573 {
		eval.DecomposeNTT(c573.Level(), params.MaxLevelP(), params.PCount(), c573.Value[1], c573.IsNTT, buffDecompQP)
		lastDecompID = 573
	}
	if c589 == nil { c589 = rlwe.NewCiphertext(params, 1, c573.Level()) }
	_ = eval.AutomorphismHoisted(c573.Level(), c573, buffDecompQP, params.GaloisElement(6), c589)
	_ = eval.Mul(c589, p1119, c589)
	if c618 == nil || c618.Level() < c573.Level() {
		c618, _ = eval.MulNew(c573, p576)
	} else {
		_ = eval.Mul(c573, p576, c618)
	}
	_ = eval.Add(c589, c618, c589)
	_ = eval.Mul(c592, p1124, c592)
	_ = eval.Mul(c571, p1127, c571)
	_ = eval.Add(c592, c571, c592)
	_ = eval.Add(c589, c592, c589)
	_ = eval.Add(c668, c589, c668)
	_ = eval.Rotate(c668, 248, c668)
	_ = eval.Add(c569, c668, c569)
	_ = eval.Rescale(c569, c569)

	// Store outputs
	encryptedOutputs["classification"] = c569
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
	ref_566 := append([]float64(nil), values...)
	ref_1127 := make([]float64, len(values))
	ref_1127[0] = -0.25
	ref_1127[1] = 0.25
	ref_1110 := make([]float64, len(values))
	ref_1110[0] = 0.25
	ref_1110[253] = 0.25
	ref_1110[255] = -0.25
	ref_1101 := make([]float64, len(values))
	ref_1101[0] = -0.25
	ref_1101[1] = 0.25
	ref_1101[3] = -0.25
	ref_1094 := make([]float64, len(values))
	ref_1094[1] = -0.25
	ref_1094[2] = 0.25
	ref_1080 := make([]float64, len(values))
	ref_1080[249] = 0.05
	ref_1080[250] = 0.05
	ref_1080[251] = 0.05
	ref_1077 := make([]float64, len(values))
	ref_1077[250] = 0.05
	ref_1077[251] = 0.05
	ref_1075 := make([]float64, len(values))
	ref_1075[251] = 0.05
	ref_1070 := make([]float64, len(values))
	ref_1070[24] = 0.05
	ref_1067 := make([]float64, len(values))
	ref_1067[24] = 0.05
	ref_1067[25] = 0.05
	ref_1047 := make([]float64, len(values))
	ref_1047[16] = 0.05
	ref_1047[17] = 0.05
	ref_1047[18] = 0.05
	ref_1047[19] = 0.05
	ref_1013 := make([]float64, len(values))
	ref_1013[0] = 0.05
	ref_1013[1] = 0.05
	ref_1013[2] = 0.05
	ref_1013[3] = 0.05
	ref_1001 := make([]float64, len(values))
	ref_1001[120] = 0.25
	ref_1001[121] = 0.25
	ref_1001[122] = 0.25
	ref_994 := make([]float64, len(values))
	ref_994[106] = 0.25
	ref_994[107] = 0.25
	ref_994[108] = 0.25
	ref_994[109] = 0.25
	ref_994[110] = 0.25
	ref_994[111] = 0.25
	ref_985 := make([]float64, len(values))
	ref_985[93] = 0.25
	ref_985[94] = 0.25
	ref_985[95] = 0.25
	ref_985[96] = 0.25
	ref_985[97] = 0.25
	ref_985[98] = 0.25
	ref_983 := make([]float64, len(values))
	ref_983[96] = 0.25
	ref_983[97] = 0.25
	ref_983[98] = 0.25
	ref_752 := make([]float64, len(values))
	ref_752[133] = 0.05
	ref_752[135] = 0.05
	ref_752[136] = 0.05
	ref_752[137] = 0.05
	ref_752[138] = 0.05
	ref_752[139] = 0.05
	ref_752[141] = 0.05
	ref_752[142] = 0.05
	ref_752[143] = 0.05
	ref_752[144] = 0.05
	ref_752[145] = 0.05
	ref_752[146] = 0.05
	ref_752[147] = 0.05
	ref_752[149] = 0.05
	ref_752[199] = 0.05
	ref_752[201] = 0.05
	ref_752[202] = 0.05
	ref_749 := make([]float64, len(values))
	ref_749[136] = 0.05
	ref_749[138] = 0.05
	ref_749[139] = 0.05
	ref_749[142] = 0.05
	ref_749[144] = 0.05
	ref_749[145] = 0.05
	ref_749[146] = 0.05
	ref_749[147] = 0.05
	ref_749[148] = 0.05
	ref_749[149] = 0.05
	ref_749[150] = 0.05
	ref_749[152] = 0.05
	ref_749[202] = 0.05
	ref_622 := make([]float64, len(values))
	ref_622[16] = 0.05
	ref_622[17] = 0.05
	ref_622[18] = 0.05
	ref_622[19] = 0.05
	ref_622[20] = 0.05
	ref_622[22] = 0.05
	ref_622[72] = 0.05
	ref_622[74] = 0.05
	ref_622[75] = 0.05
	ref_622[76] = 0.05
	ref_622[77] = 0.05
	ref_622[78] = 0.05
	ref_747 := make([]float64, len(values))
	ref_747[139] = 0.05
	ref_747[145] = 0.05
	ref_747[147] = 0.05
	ref_747[148] = 0.05
	ref_747[149] = 0.05
	ref_747[150] = 0.05
	ref_747[151] = 0.05
	ref_747[152] = 0.05
	ref_747[153] = 0.05
	ref_747[155] = 0.05
	ref_747[161] = 0.05
	ref_730 := make([]float64, len(values))
	ref_730[95] = 0.05
	ref_730[97] = 0.05
	ref_730[98] = 0.05
	ref_730[99] = 0.05
	ref_730[100] = 0.05
	ref_730[101] = 0.05
	ref_730[102] = 0.05
	ref_730[103] = 0.05
	ref_730[105] = 0.05
	ref_730[111] = 0.05
	ref_730[161] = 0.05
	ref_730[163] = 0.05
	ref_730[164] = 0.05
	ref_730[165] = 0.05
	ref_730[166] = 0.05
	ref_730[167] = 0.05
	ref_730[168] = 0.05
	ref_730[169] = 0.05
	ref_730[171] = 0.05
	ref_727 := make([]float64, len(values))
	ref_727[98] = 0.05
	ref_727[100] = 0.05
	ref_727[101] = 0.05
	ref_727[102] = 0.05
	ref_727[103] = 0.05
	ref_727[104] = 0.05
	ref_727[105] = 0.05
	ref_727[106] = 0.05
	ref_727[108] = 0.05
	ref_727[111] = 0.05
	ref_727[112] = 0.05
	ref_727[114] = 0.05
	ref_727[164] = 0.05
	ref_727[166] = 0.05
	ref_727[167] = 0.05
	ref_727[168] = 0.05
	ref_727[169] = 0.05
	ref_727[170] = 0.05
	ref_727[171] = 0.05
	ref_727[172] = 0.05
	ref_724 := make([]float64, len(values))
	ref_724[101] = 0.05
	ref_724[103] = 0.05
	ref_724[104] = 0.05
	ref_724[105] = 0.05
	ref_724[106] = 0.05
	ref_724[107] = 0.05
	ref_724[108] = 0.05
	ref_724[109] = 0.05
	ref_724[111] = 0.05
	ref_724[112] = 0.05
	ref_724[113] = 0.05
	ref_724[114] = 0.05
	ref_724[115] = 0.05
	ref_724[117] = 0.05
	ref_724[167] = 0.05
	ref_724[169] = 0.05
	ref_724[170] = 0.05
	ref_724[171] = 0.05
	ref_724[172] = 0.05
	ref_724[173] = 0.05
	ref_597 := make([]float64, len(values))
	ref_597[25] = 0.05
	ref_597[27] = 0.05
	ref_597[28] = 0.05
	ref_597[31] = 0.05
	ref_597[33] = 0.05
	ref_597[34] = 0.05
	ref_597[35] = 0.05
	ref_597[36] = 0.05
	ref_597[37] = 0.05
	ref_597[38] = 0.05
	ref_597[39] = 0.05
	ref_597[41] = 0.05
	ref_978 := make([]float64, len(values))
	ref_978[82] = 0.25
	ref_978[83] = 0.25
	ref_978[84] = 0.25
	ref_722 := make([]float64, len(values))
	ref_722[104] = 0.05
	ref_722[106] = 0.05
	ref_722[107] = 0.05
	ref_722[108] = 0.05
	ref_722[109] = 0.05
	ref_722[110] = 0.05
	ref_722[112] = 0.05
	ref_722[113] = 0.05
	ref_722[114] = 0.05
	ref_722[115] = 0.05
	ref_722[116] = 0.05
	ref_722[117] = 0.05
	ref_722[118] = 0.05
	ref_722[120] = 0.05
	ref_722[170] = 0.05
	ref_722[172] = 0.05
	ref_722[173] = 0.05
	ref_849 := make([]float64, len(values))
	ref_849[231] = 0.05
	ref_849[233] = 0.05
	ref_849[234] = 0.05
	ref_976 := make([]float64, len(values))
	ref_976[82] = 0.25
	ref_976[83] = 0.25
	ref_976[84] = 0.25
	ref_976[85] = 0.25
	ref_976[86] = 0.25
	ref_976[87] = 0.25
	ref_702 := make([]float64, len(values))
	ref_702[61] = 0.05
	ref_702[62] = 0.05
	ref_702[63] = 0.05
	ref_702[64] = 0.05
	ref_702[65] = 0.05
	ref_702[67] = 0.05
	ref_702[117] = 0.05
	ref_702[119] = 0.05
	ref_702[120] = 0.05
	ref_702[121] = 0.05
	ref_702[122] = 0.05
	ref_702[123] = 0.05
	ref_702[125] = 0.05
	ref_702[126] = 0.05
	ref_702[127] = 0.05
	ref_702[128] = 0.05
	ref_702[129] = 0.05
	ref_702[130] = 0.05
	ref_702[131] = 0.05
	ref_702[133] = 0.05
	ref_699 := make([]float64, len(values))
	ref_699[99] = 0.05
	ref_699[101] = 0.05
	ref_699[102] = 0.05
	ref_699[105] = 0.05
	ref_699[107] = 0.05
	ref_699[108] = 0.05
	ref_699[109] = 0.05
	ref_699[110] = 0.05
	ref_699[111] = 0.05
	ref_699[112] = 0.05
	ref_699[113] = 0.05
	ref_699[115] = 0.05
	ref_699[165] = 0.05
	ref_953 := make([]float64, len(values))
	ref_953[41] = 0.25
	ref_953[42] = 0.25
	ref_953[43] = 0.25
	ref_953[44] = 0.25
	ref_953[45] = 0.25
	ref_953[46] = 0.25
	ref_996 := make([]float64, len(values))
	ref_996[109] = 0.25
	ref_996[110] = 0.25
	ref_996[111] = 0.25
	ref_996[112] = 0.25
	ref_996[113] = 0.25
	ref_996[114] = 0.25
	ref_739 := make([]float64, len(values))
	ref_739[91] = 0.05
	ref_739[92] = 0.05
	ref_739[93] = 0.05
	ref_739[94] = 0.05
	ref_739[95] = 0.05
	ref_739[96] = 0.05
	ref_739[97] = 0.05
	ref_739[99] = 0.05
	ref_739[149] = 0.05
	ref_739[151] = 0.05
	ref_739[152] = 0.05
	ref_739[155] = 0.05
	ref_739[157] = 0.05
	ref_739[158] = 0.05
	ref_739[159] = 0.05
	ref_739[160] = 0.05
	ref_739[161] = 0.05
	ref_739[162] = 0.05
	ref_739[163] = 0.05
	ref_739[165] = 0.05
	ref_680 := make([]float64, len(values))
	ref_680[61] = 0.05
	ref_680[63] = 0.05
	ref_680[64] = 0.05
	ref_680[65] = 0.05
	ref_680[66] = 0.05
	ref_680[67] = 0.05
	ref_680[68] = 0.05
	ref_680[69] = 0.05
	ref_680[71] = 0.05
	ref_680[74] = 0.05
	ref_680[75] = 0.05
	ref_680[77] = 0.05
	ref_680[127] = 0.05
	ref_680[129] = 0.05
	ref_680[130] = 0.05
	ref_680[131] = 0.05
	ref_680[132] = 0.05
	ref_680[133] = 0.05
	ref_680[134] = 0.05
	ref_680[135] = 0.05
	ref_736 := make([]float64, len(values))
	ref_736[90] = 0.05
	ref_736[91] = 0.05
	ref_736[93] = 0.05
	ref_736[143] = 0.05
	ref_736[145] = 0.05
	ref_736[146] = 0.05
	ref_736[147] = 0.05
	ref_736[148] = 0.05
	ref_736[149] = 0.05
	ref_736[150] = 0.05
	ref_736[151] = 0.05
	ref_736[153] = 0.05
	ref_736[154] = 0.05
	ref_736[155] = 0.05
	ref_736[156] = 0.05
	ref_736[157] = 0.05
	ref_736[159] = 0.05
	ref_934 := make([]float64, len(values))
	ref_934[16] = 0.25
	ref_934[17] = 0.25
	ref_934[18] = 0.25
	ref_677 := make([]float64, len(values))
	ref_677[32] = 0.05
	ref_677[82] = 0.05
	ref_677[84] = 0.05
	ref_677[85] = 0.05
	ref_677[86] = 0.05
	ref_677[87] = 0.05
	ref_677[88] = 0.05
	ref_677[89] = 0.05
	ref_677[90] = 0.05
	ref_677[92] = 0.05
	ref_677[95] = 0.05
	ref_677[96] = 0.05
	ref_677[98] = 0.05
	ref_990 := make([]float64, len(values))
	ref_990[98] = 0.25
	ref_990[99] = 0.25
	ref_990[100] = 0.25
	ref_733 := make([]float64, len(values))
	ref_733[90] = 0.05
	ref_733[91] = 0.05
	ref_733[92] = 0.05
	ref_733[93] = 0.05
	ref_733[94] = 0.05
	ref_733[96] = 0.05
	ref_733[146] = 0.05
	ref_733[148] = 0.05
	ref_733[149] = 0.05
	ref_733[150] = 0.05
	ref_733[151] = 0.05
	ref_733[152] = 0.05
	ref_733[154] = 0.05
	ref_733[155] = 0.05
	ref_733[156] = 0.05
	ref_733[157] = 0.05
	ref_733[158] = 0.05
	ref_733[159] = 0.05
	ref_733[160] = 0.05
	ref_733[162] = 0.05
	ref_674 := make([]float64, len(values))
	ref_674[32] = 0.05
	ref_674[33] = 0.05
	ref_674[35] = 0.05
	ref_674[85] = 0.05
	ref_674[87] = 0.05
	ref_674[88] = 0.05
	ref_674[89] = 0.05
	ref_674[90] = 0.05
	ref_674[91] = 0.05
	ref_674[92] = 0.05
	ref_674[93] = 0.05
	ref_674[95] = 0.05
	ref_674[96] = 0.05
	ref_674[97] = 0.05
	ref_674[98] = 0.05
	ref_674[99] = 0.05
	ref_674[101] = 0.05
	ref_672 := make([]float64, len(values))
	ref_672[32] = 0.05
	ref_672[33] = 0.05
	ref_672[34] = 0.05
	ref_672[35] = 0.05
	ref_672[36] = 0.05
	ref_672[38] = 0.05
	ref_672[88] = 0.05
	ref_672[90] = 0.05
	ref_672[91] = 0.05
	ref_672[92] = 0.05
	ref_672[93] = 0.05
	ref_672[94] = 0.05
	ref_672[96] = 0.05
	ref_672[97] = 0.05
	ref_672[98] = 0.05
	ref_672[99] = 0.05
	ref_672[100] = 0.05
	ref_672[101] = 0.05
	ref_672[102] = 0.05
	ref_672[104] = 0.05
	ref_799 := make([]float64, len(values))
	ref_799[164] = 0.05
	ref_799[166] = 0.05
	ref_799[167] = 0.05
	ref_799[168] = 0.05
	ref_799[169] = 0.05
	ref_799[170] = 0.05
	ref_799[171] = 0.05
	ref_799[172] = 0.05
	ref_799[174] = 0.05
	ref_799[177] = 0.05
	ref_799[178] = 0.05
	ref_799[180] = 0.05
	ref_655 := make([]float64, len(values))
	ref_655[29] = 0.05
	ref_655[31] = 0.05
	ref_655[32] = 0.05
	ref_655[33] = 0.05
	ref_655[34] = 0.05
	ref_655[35] = 0.05
	ref_655[36] = 0.05
	ref_655[37] = 0.05
	ref_655[39] = 0.05
	ref_655[45] = 0.05
	ref_655[95] = 0.05
	ref_655[97] = 0.05
	ref_655[98] = 0.05
	ref_655[99] = 0.05
	ref_655[100] = 0.05
	ref_655[101] = 0.05
	ref_655[102] = 0.05
	ref_655[103] = 0.05
	ref_655[105] = 0.05
	ref_1108 := make([]float64, len(values))
	ref_1108[253] = -0.25
	ref_1108[254] = 0.25
	ref_594 := make([]float64, len(values))
	ref_594[41] = 0.05
	ref_968 := make([]float64, len(values))
	ref_968[68] = 0.25
	ref_968[69] = 0.25
	ref_968[70] = 0.25
	ref_968[71] = 0.25
	ref_968[72] = 0.25
	ref_968[73] = 0.25
	ref_711 := make([]float64, len(values))
	ref_711[62] = 0.05
	ref_711[63] = 0.05
	ref_711[64] = 0.05
	ref_711[65] = 0.05
	ref_711[66] = 0.05
	ref_711[67] = 0.05
	ref_711[68] = 0.05
	ref_711[70] = 0.05
	ref_711[120] = 0.05
	ref_711[122] = 0.05
	ref_711[123] = 0.05
	ref_711[126] = 0.05
	ref_711[128] = 0.05
	ref_711[129] = 0.05
	ref_711[130] = 0.05
	ref_711[131] = 0.05
	ref_711[132] = 0.05
	ref_711[133] = 0.05
	ref_711[134] = 0.05
	ref_711[136] = 0.05
	ref_652 := make([]float64, len(values))
	ref_652[32] = 0.05
	ref_652[34] = 0.05
	ref_652[35] = 0.05
	ref_652[36] = 0.05
	ref_652[37] = 0.05
	ref_652[38] = 0.05
	ref_652[39] = 0.05
	ref_652[40] = 0.05
	ref_652[42] = 0.05
	ref_652[45] = 0.05
	ref_652[46] = 0.05
	ref_652[48] = 0.05
	ref_652[98] = 0.05
	ref_652[100] = 0.05
	ref_652[101] = 0.05
	ref_652[102] = 0.05
	ref_652[103] = 0.05
	ref_652[104] = 0.05
	ref_652[105] = 0.05
	ref_652[106] = 0.05
	ref_591 := make([]float64, len(values))
	ref_591[38] = 0.05
	ref_591[40] = 0.05
	ref_591[41] = 0.05
	ref_708 := make([]float64, len(values))
	ref_708[61] = 0.05
	ref_708[111] = 0.05
	ref_708[113] = 0.05
	ref_708[114] = 0.05
	ref_708[115] = 0.05
	ref_708[116] = 0.05
	ref_708[117] = 0.05
	ref_708[118] = 0.05
	ref_708[119] = 0.05
	ref_708[121] = 0.05
	ref_708[124] = 0.05
	ref_708[125] = 0.05
	ref_708[127] = 0.05
	ref_705 := make([]float64, len(values))
	ref_705[61] = 0.05
	ref_705[62] = 0.05
	ref_705[64] = 0.05
	ref_705[114] = 0.05
	ref_705[116] = 0.05
	ref_705[117] = 0.05
	ref_705[118] = 0.05
	ref_705[119] = 0.05
	ref_705[120] = 0.05
	ref_705[121] = 0.05
	ref_705[122] = 0.05
	ref_705[124] = 0.05
	ref_705[125] = 0.05
	ref_705[126] = 0.05
	ref_705[127] = 0.05
	ref_705[128] = 0.05
	ref_705[130] = 0.05
	ref_962 := make([]float64, len(values))
	ref_962[57] = 0.25
	ref_962[58] = 0.25
	ref_962[59] = 0.25
	ref_649 := make([]float64, len(values))
	ref_649[35] = 0.05
	ref_649[37] = 0.05
	ref_649[38] = 0.05
	ref_649[39] = 0.05
	ref_649[40] = 0.05
	ref_649[41] = 0.05
	ref_649[42] = 0.05
	ref_649[43] = 0.05
	ref_649[45] = 0.05
	ref_649[46] = 0.05
	ref_649[47] = 0.05
	ref_649[48] = 0.05
	ref_649[49] = 0.05
	ref_649[51] = 0.05
	ref_649[101] = 0.05
	ref_649[103] = 0.05
	ref_649[104] = 0.05
	ref_649[105] = 0.05
	ref_649[106] = 0.05
	ref_649[107] = 0.05
	ref_874 := make([]float64, len(values))
	ref_874[223] = 0.05
	ref_874[224] = 0.05
	ref_874[225] = 0.05
	ref_874[226] = 0.05
	ref_874[227] = 0.05
	ref_874[228] = 0.05
	ref_874[229] = 0.05
	ref_874[231] = 0.05
	ref_617 := make([]float64, len(values))
	ref_617[28] = 0.05
	ref_617[34] = 0.05
	ref_617[36] = 0.05
	ref_617[37] = 0.05
	ref_617[38] = 0.05
	ref_617[39] = 0.05
	ref_617[40] = 0.05
	ref_617[41] = 0.05
	ref_617[42] = 0.05
	ref_617[44] = 0.05
	ref_966 := make([]float64, len(values))
	ref_966[71] = 0.25
	ref_966[72] = 0.25
	ref_966[73] = 0.25
	ref_614 := make([]float64, len(values))
	ref_614[10] = 0.05
	ref_614[12] = 0.05
	ref_614[13] = 0.05
	ref_614[14] = 0.05
	ref_614[15] = 0.05
	ref_614[16] = 0.05
	ref_614[17] = 0.05
	ref_614[18] = 0.05
	ref_614[20] = 0.05
	ref_614[70] = 0.05
	ref_608 := make([]float64, len(values))
	ref_608[16] = 0.05
	ref_608[18] = 0.05
	ref_608[19] = 0.05
	ref_608[20] = 0.05
	ref_608[21] = 0.05
	ref_608[22] = 0.05
	ref_608[23] = 0.05
	ref_608[24] = 0.05
	ref_608[26] = 0.05
	ref_608[29] = 0.05
	ref_608[30] = 0.05
	ref_608[32] = 0.05
	ref_697 := make([]float64, len(values))
	ref_697[102] = 0.05
	ref_697[108] = 0.05
	ref_697[110] = 0.05
	ref_697[111] = 0.05
	ref_697[112] = 0.05
	ref_697[113] = 0.05
	ref_697[114] = 0.05
	ref_697[115] = 0.05
	ref_697[116] = 0.05
	ref_697[118] = 0.05
	ref_697[124] = 0.05
	ref_824 := make([]float64, len(values))
	ref_824[199] = 0.05
	ref_824[201] = 0.05
	ref_824[202] = 0.05
	ref_824[203] = 0.05
	ref_824[204] = 0.05
	ref_824[205] = 0.05
	ref_824[207] = 0.05
	ref_824[208] = 0.05
	ref_824[209] = 0.05
	ref_824[210] = 0.05
	ref_824[211] = 0.05
	ref_824[212] = 0.05
	ref_824[213] = 0.05
	ref_824[215] = 0.05
	ref_1096 := make([]float64, len(values))
	ref_1096[0] = -0.25
	ref_839 := make([]float64, len(values))
	ref_839[186] = 0.05
	ref_839[187] = 0.05
	ref_839[188] = 0.05
	ref_839[189] = 0.05
	ref_839[190] = 0.05
	ref_839[191] = 0.05
	ref_839[192] = 0.05
	ref_839[194] = 0.05
	ref_582 := make([]float64, len(values))
	ref_582[29] = 0.05
	ref_582[31] = 0.05
	ref_582[32] = 0.05
	ref_582[33] = 0.05
	ref_582[34] = 0.05
	ref_582[35] = 0.05
	ref_582[36] = 0.05
	ref_582[37] = 0.05
	ref_582[39] = 0.05
	ref_579 := make([]float64, len(values))
	ref_579[0] = 0.05
	ref_579[1] = 0.05
	ref_579[3] = 0.05
	ref_836 := make([]float64, len(values))
	ref_836[187] = 0.05
	ref_836[189] = 0.05
	ref_836[190] = 0.05
	ref_836[191] = 0.05
	ref_836[192] = 0.05
	ref_836[193] = 0.05
	ref_836[194] = 0.05
	ref_836[195] = 0.05
	ref_836[197] = 0.05
	ref_611 := make([]float64, len(values))
	ref_611[13] = 0.05
	ref_611[15] = 0.05
	ref_611[16] = 0.05
	ref_611[17] = 0.05
	ref_611[18] = 0.05
	ref_611[19] = 0.05
	ref_611[20] = 0.05
	ref_611[21] = 0.05
	ref_611[23] = 0.05
	ref_611[29] = 0.05
	ref_664 := make([]float64, len(values))
	ref_664[41] = 0.05
	ref_664[43] = 0.05
	ref_664[44] = 0.05
	ref_664[47] = 0.05
	ref_664[49] = 0.05
	ref_664[50] = 0.05
	ref_664[51] = 0.05
	ref_664[52] = 0.05
	ref_664[53] = 0.05
	ref_664[54] = 0.05
	ref_664[55] = 0.05
	ref_664[57] = 0.05
	ref_664[107] = 0.05
	ref_1119 := make([]float64, len(values))
	ref_1119[250] = 0.25
	ref_1119[252] = -0.25
	ref_1119[253] = 0.25
	ref_605 := make([]float64, len(values))
	ref_605[9] = 0.05
	ref_605[10] = 0.05
	ref_605[11] = 0.05
	ref_605[12] = 0.05
	ref_605[13] = 0.05
	ref_605[14] = 0.05
	ref_605[15] = 0.05
	ref_605[17] = 0.05
	ref_605[67] = 0.05
	ref_605[69] = 0.05
	ref_605[70] = 0.05
	ref_833 := make([]float64, len(values))
	ref_833[190] = 0.05
	ref_833[192] = 0.05
	ref_833[193] = 0.05
	ref_833[194] = 0.05
	ref_833[195] = 0.05
	ref_833[196] = 0.05
	ref_833[197] = 0.05
	ref_833[198] = 0.05
	ref_833[200] = 0.05
	ref_833[206] = 0.05
	ref_576 := make([]float64, len(values))
	ref_576[0] = 0.05
	ref_830 := make([]float64, len(values))
	ref_830[193] = 0.05
	ref_830[195] = 0.05
	ref_830[196] = 0.05
	ref_830[197] = 0.05
	ref_830[198] = 0.05
	ref_830[199] = 0.05
	ref_830[200] = 0.05
	ref_830[201] = 0.05
	ref_830[203] = 0.05
	ref_830[206] = 0.05
	ref_830[207] = 0.05
	ref_830[209] = 0.05
	ref_661 := make([]float64, len(values))
	ref_661[25] = 0.05
	ref_661[26] = 0.05
	ref_661[27] = 0.05
	ref_661[28] = 0.05
	ref_661[29] = 0.05
	ref_661[30] = 0.05
	ref_661[31] = 0.05
	ref_661[33] = 0.05
	ref_661[83] = 0.05
	ref_661[85] = 0.05
	ref_661[86] = 0.05
	ref_661[89] = 0.05
	ref_661[91] = 0.05
	ref_661[92] = 0.05
	ref_661[93] = 0.05
	ref_661[94] = 0.05
	ref_661[95] = 0.05
	ref_661[96] = 0.05
	ref_661[97] = 0.05
	ref_661[99] = 0.05
	ref_1116 := make([]float64, len(values))
	ref_1116[250] = -0.25
	ref_1116[251] = 0.25
	ref_602 := make([]float64, len(values))
	ref_602[19] = 0.05
	ref_602[21] = 0.05
	ref_602[22] = 0.05
	ref_602[23] = 0.05
	ref_602[24] = 0.05
	ref_602[25] = 0.05
	ref_602[26] = 0.05
	ref_602[27] = 0.05
	ref_602[29] = 0.05
	ref_602[30] = 0.05
	ref_602[31] = 0.05
	ref_602[32] = 0.05
	ref_602[33] = 0.05
	ref_602[35] = 0.05
	ref_742 := make([]float64, len(values))
	ref_742[92] = 0.05
	ref_742[94] = 0.05
	ref_742[95] = 0.05
	ref_742[96] = 0.05
	ref_742[97] = 0.05
	ref_742[98] = 0.05
	ref_742[99] = 0.05
	ref_742[100] = 0.05
	ref_742[102] = 0.05
	ref_742[152] = 0.05
	ref_742[158] = 0.05
	ref_742[160] = 0.05
	ref_742[161] = 0.05
	ref_742[162] = 0.05
	ref_742[163] = 0.05
	ref_742[164] = 0.05
	ref_742[165] = 0.05
	ref_742[166] = 0.05
	ref_742[168] = 0.05
	ref_624 := make([]float64, len(values))
	ref_624[16] = 0.05
	ref_624[17] = 0.05
	ref_624[19] = 0.05
	ref_624[69] = 0.05
	ref_624[71] = 0.05
	ref_624[72] = 0.05
	ref_624[73] = 0.05
	ref_624[74] = 0.05
	ref_624[75] = 0.05
	ref_624[76] = 0.05
	ref_624[77] = 0.05
	ref_683 := make([]float64, len(values))
	ref_683[64] = 0.05
	ref_683[66] = 0.05
	ref_683[67] = 0.05
	ref_683[68] = 0.05
	ref_683[69] = 0.05
	ref_683[70] = 0.05
	ref_683[71] = 0.05
	ref_683[72] = 0.05
	ref_683[74] = 0.05
	ref_683[75] = 0.05
	ref_683[76] = 0.05
	ref_683[77] = 0.05
	ref_683[78] = 0.05
	ref_683[80] = 0.05
	ref_683[130] = 0.05
	ref_683[132] = 0.05
	ref_683[133] = 0.05
	ref_683[134] = 0.05
	ref_683[135] = 0.05
	ref_683[136] = 0.05
	ref_940 := make([]float64, len(values))
	ref_940[27] = 0.25
	ref_940[28] = 0.25
	ref_940[29] = 0.25
	ref_940[30] = 0.25
	ref_940[31] = 0.25
	ref_940[32] = 0.25
	ref_627 := make([]float64, len(values))
	ref_627[16] = 0.05
	ref_627[66] = 0.05
	ref_627[68] = 0.05
	ref_627[69] = 0.05
	ref_627[70] = 0.05
	ref_627[71] = 0.05
	ref_627[72] = 0.05
	ref_627[73] = 0.05
	ref_627[74] = 0.05
	ref_627[76] = 0.05
	ref_689 := make([]float64, len(values))
	ref_689[70] = 0.05
	ref_689[72] = 0.05
	ref_689[73] = 0.05
	ref_689[76] = 0.05
	ref_689[78] = 0.05
	ref_689[79] = 0.05
	ref_689[80] = 0.05
	ref_689[81] = 0.05
	ref_689[82] = 0.05
	ref_689[83] = 0.05
	ref_689[84] = 0.05
	ref_689[86] = 0.05
	ref_689[136] = 0.05
	ref_686 := make([]float64, len(values))
	ref_686[67] = 0.05
	ref_686[69] = 0.05
	ref_686[70] = 0.05
	ref_686[71] = 0.05
	ref_686[72] = 0.05
	ref_686[73] = 0.05
	ref_686[75] = 0.05
	ref_686[76] = 0.05
	ref_686[77] = 0.05
	ref_686[78] = 0.05
	ref_686[79] = 0.05
	ref_686[80] = 0.05
	ref_686[81] = 0.05
	ref_686[83] = 0.05
	ref_686[133] = 0.05
	ref_686[135] = 0.05
	ref_686[136] = 0.05
	ref_943 := make([]float64, len(values))
	ref_943[30] = 0.25
	ref_943[31] = 0.25
	ref_943[32] = 0.25
	ref_630 := make([]float64, len(values))
	ref_630[57] = 0.05
	ref_630[63] = 0.05
	ref_630[65] = 0.05
	ref_630[66] = 0.05
	ref_630[67] = 0.05
	ref_630[68] = 0.05
	ref_630[69] = 0.05
	ref_630[70] = 0.05
	ref_630[71] = 0.05
	ref_630[73] = 0.05
	ref_692 := make([]float64, len(values))
	ref_692[73] = 0.05
	ref_692[79] = 0.05
	ref_692[81] = 0.05
	ref_692[82] = 0.05
	ref_692[83] = 0.05
	ref_692[84] = 0.05
	ref_692[85] = 0.05
	ref_692[86] = 0.05
	ref_692[87] = 0.05
	ref_692[89] = 0.05
	ref_692[95] = 0.05
	ref_574 := make([]float64, len(values))
	ref_574[0] = 0.05
	ref_574[1] = 0.05
	ref_574[2] = 0.05
	ref_574[3] = 0.05
	ref_574[4] = 0.05
	ref_574[6] = 0.05
	ref_633 := make([]float64, len(values))
	ref_633[45] = 0.05
	ref_633[47] = 0.05
	ref_633[48] = 0.05
	ref_633[49] = 0.05
	ref_633[50] = 0.05
	ref_633[51] = 0.05
	ref_633[52] = 0.05
	ref_633[53] = 0.05
	ref_633[55] = 0.05
	ref_633[58] = 0.05
	ref_633[59] = 0.05
	ref_633[61] = 0.05
	ref_890 := make([]float64, len(values))
	ref_890[12] = 0.05
	ref_636 := make([]float64, len(values))
	ref_636[48] = 0.05
	ref_636[50] = 0.05
	ref_636[51] = 0.05
	ref_636[52] = 0.05
	ref_636[53] = 0.05
	ref_636[54] = 0.05
	ref_636[55] = 0.05
	ref_636[56] = 0.05
	ref_636[58] = 0.05
	ref_636[59] = 0.05
	ref_636[60] = 0.05
	ref_636[61] = 0.05
	ref_636[62] = 0.05
	ref_636[64] = 0.05
	ref_893 := make([]float64, len(values))
	ref_893[0] = 0.05
	ref_893[2] = 0.05
	ref_893[3] = 0.05
	ref_893[4] = 0.05
	ref_893[5] = 0.05
	ref_893[6] = 0.05
	ref_893[7] = 0.05
	ref_893[8] = 0.05
	ref_893[10] = 0.05
	ref_639 := make([]float64, len(values))
	ref_639[51] = 0.05
	ref_639[53] = 0.05
	ref_639[54] = 0.05
	ref_639[55] = 0.05
	ref_639[56] = 0.05
	ref_639[57] = 0.05
	ref_639[59] = 0.05
	ref_639[60] = 0.05
	ref_639[61] = 0.05
	ref_639[62] = 0.05
	ref_639[63] = 0.05
	ref_639[64] = 0.05
	ref_639[65] = 0.05
	ref_639[67] = 0.05
	ref_896 := make([]float64, len(values))
	ref_896[9] = 0.05
	ref_896[11] = 0.05
	ref_896[12] = 0.05
	ref_588 := make([]float64, len(values))
	ref_588[35] = 0.05
	ref_588[37] = 0.05
	ref_588[38] = 0.05
	ref_588[39] = 0.05
	ref_588[40] = 0.05
	ref_588[41] = 0.05
	ref_585 := make([]float64, len(values))
	ref_585[32] = 0.05
	ref_585[34] = 0.05
	ref_585[35] = 0.05
	ref_585[36] = 0.05
	ref_585[37] = 0.05
	ref_585[38] = 0.05
	ref_585[39] = 0.05
	ref_585[40] = 0.05
	ref_842 := make([]float64, len(values))
	ref_842[185] = 0.05
	ref_842[186] = 0.05
	ref_842[187] = 0.05
	ref_842[188] = 0.05
	ref_842[189] = 0.05
	ref_842[191] = 0.05
	ref_647 := make([]float64, len(values))
	ref_647[38] = 0.05
	ref_647[40] = 0.05
	ref_647[41] = 0.05
	ref_647[42] = 0.05
	ref_647[43] = 0.05
	ref_647[44] = 0.05
	ref_647[46] = 0.05
	ref_647[47] = 0.05
	ref_647[48] = 0.05
	ref_647[49] = 0.05
	ref_647[50] = 0.05
	ref_647[51] = 0.05
	ref_647[52] = 0.05
	ref_647[54] = 0.05
	ref_647[104] = 0.05
	ref_647[106] = 0.05
	ref_647[107] = 0.05
	ref_774 := make([]float64, len(values))
	ref_774[165] = 0.05
	ref_774[167] = 0.05
	ref_774[168] = 0.05
	ref_774[171] = 0.05
	ref_774[173] = 0.05
	ref_774[174] = 0.05
	ref_774[175] = 0.05
	ref_774[176] = 0.05
	ref_774[177] = 0.05
	ref_774[178] = 0.05
	ref_774[179] = 0.05
	ref_774[181] = 0.05
	ref_717 := make([]float64, len(values))
	ref_717[66] = 0.05
	ref_717[68] = 0.05
	ref_717[69] = 0.05
	ref_717[70] = 0.05
	ref_717[71] = 0.05
	ref_717[72] = 0.05
	ref_717[73] = 0.05
	ref_717[74] = 0.05
	ref_717[76] = 0.05
	ref_717[82] = 0.05
	ref_717[132] = 0.05
	ref_717[134] = 0.05
	ref_717[135] = 0.05
	ref_717[136] = 0.05
	ref_717[137] = 0.05
	ref_717[138] = 0.05
	ref_717[139] = 0.05
	ref_717[140] = 0.05
	ref_717[142] = 0.05
	ref_714 := make([]float64, len(values))
	ref_714[63] = 0.05
	ref_714[65] = 0.05
	ref_714[66] = 0.05
	ref_714[67] = 0.05
	ref_714[68] = 0.05
	ref_714[69] = 0.05
	ref_714[70] = 0.05
	ref_714[71] = 0.05
	ref_714[73] = 0.05
	ref_714[123] = 0.05
	ref_714[129] = 0.05
	ref_714[131] = 0.05
	ref_714[132] = 0.05
	ref_714[133] = 0.05
	ref_714[134] = 0.05
	ref_714[135] = 0.05
	ref_714[136] = 0.05
	ref_714[137] = 0.05
	ref_714[139] = 0.05
	ref_971 := make([]float64, len(values))
	ref_971[65] = 0.25
	ref_971[66] = 0.25
	ref_971[67] = 0.25
	ref_971[68] = 0.25
	ref_971[69] = 0.25
	ref_971[70] = 0.25
	ref_1113 := make([]float64, len(values))
	ref_1113[251] = -0.25
	ref_1113[252] = 0.25
	ref_1113[254] = -0.25
	ref_599 := make([]float64, len(values))
	ref_599[22] = 0.05
	ref_599[24] = 0.05
	ref_599[25] = 0.05
	ref_599[26] = 0.05
	ref_599[27] = 0.05
	ref_599[28] = 0.05
	ref_599[30] = 0.05
	ref_599[31] = 0.05
	ref_599[32] = 0.05
	ref_599[33] = 0.05
	ref_599[34] = 0.05
	ref_599[35] = 0.05
	ref_599[36] = 0.05
	ref_599[38] = 0.05
	ref_658 := make([]float64, len(values))
	ref_658[26] = 0.05
	ref_658[28] = 0.05
	ref_658[29] = 0.05
	ref_658[30] = 0.05
	ref_658[31] = 0.05
	ref_658[32] = 0.05
	ref_658[33] = 0.05
	ref_658[34] = 0.05
	ref_658[36] = 0.05
	ref_658[86] = 0.05
	ref_658[92] = 0.05
	ref_658[94] = 0.05
	ref_658[95] = 0.05
	ref_658[96] = 0.05
	ref_658[97] = 0.05
	ref_658[98] = 0.05
	ref_658[99] = 0.05
	ref_658[100] = 0.05
	ref_658[102] = 0.05
	ref_755 := make([]float64, len(values))
	ref_755[130] = 0.05
	ref_755[132] = 0.05
	ref_755[133] = 0.05
	ref_755[134] = 0.05
	ref_755[135] = 0.05
	ref_755[136] = 0.05
	ref_755[137] = 0.05
	ref_755[138] = 0.05
	ref_755[140] = 0.05
	ref_755[141] = 0.05
	ref_755[142] = 0.05
	ref_755[143] = 0.05
	ref_755[144] = 0.05
	ref_755[146] = 0.05
	ref_755[196] = 0.05
	ref_755[198] = 0.05
	ref_755[199] = 0.05
	ref_755[200] = 0.05
	ref_755[201] = 0.05
	ref_755[202] = 0.05
	ref_758 := make([]float64, len(values))
	ref_758[127] = 0.05
	ref_758[129] = 0.05
	ref_758[130] = 0.05
	ref_758[131] = 0.05
	ref_758[132] = 0.05
	ref_758[133] = 0.05
	ref_758[134] = 0.05
	ref_758[135] = 0.05
	ref_758[137] = 0.05
	ref_758[140] = 0.05
	ref_758[141] = 0.05
	ref_758[143] = 0.05
	ref_758[193] = 0.05
	ref_758[195] = 0.05
	ref_758[196] = 0.05
	ref_758[197] = 0.05
	ref_758[198] = 0.05
	ref_758[199] = 0.05
	ref_758[200] = 0.05
	ref_758[201] = 0.05
	ref_761 := make([]float64, len(values))
	ref_761[124] = 0.05
	ref_761[126] = 0.05
	ref_761[127] = 0.05
	ref_761[128] = 0.05
	ref_761[129] = 0.05
	ref_761[130] = 0.05
	ref_761[131] = 0.05
	ref_761[132] = 0.05
	ref_761[134] = 0.05
	ref_761[140] = 0.05
	ref_761[190] = 0.05
	ref_761[192] = 0.05
	ref_761[193] = 0.05
	ref_761[194] = 0.05
	ref_761[195] = 0.05
	ref_761[196] = 0.05
	ref_761[197] = 0.05
	ref_761[198] = 0.05
	ref_761[200] = 0.05
	ref_888 := make([]float64, len(values))
	ref_888[3] = 0.05
	ref_888[5] = 0.05
	ref_888[6] = 0.05
	ref_888[7] = 0.05
	ref_888[8] = 0.05
	ref_888[9] = 0.05
	ref_888[10] = 0.05
	ref_888[11] = 0.05
	ref_764 := make([]float64, len(values))
	ref_764[121] = 0.05
	ref_764[123] = 0.05
	ref_764[124] = 0.05
	ref_764[125] = 0.05
	ref_764[126] = 0.05
	ref_764[127] = 0.05
	ref_764[128] = 0.05
	ref_764[129] = 0.05
	ref_764[131] = 0.05
	ref_764[181] = 0.05
	ref_764[187] = 0.05
	ref_764[189] = 0.05
	ref_764[190] = 0.05
	ref_764[191] = 0.05
	ref_764[192] = 0.05
	ref_764[193] = 0.05
	ref_764[194] = 0.05
	ref_764[195] = 0.05
	ref_764[197] = 0.05
	ref_767 := make([]float64, len(values))
	ref_767[98] = 0.05
	ref_767[148] = 0.05
	ref_767[150] = 0.05
	ref_767[151] = 0.05
	ref_767[152] = 0.05
	ref_767[153] = 0.05
	ref_767[154] = 0.05
	ref_767[155] = 0.05
	ref_767[156] = 0.05
	ref_767[158] = 0.05
	ref_767[161] = 0.05
	ref_767[162] = 0.05
	ref_767[164] = 0.05
	ref_1029 := make([]float64, len(values))
	ref_1029[8] = 0.05
	ref_1029[9] = 0.05
	ref_1029[10] = 0.05
	ref_1029[11] = 0.05
	ref_772 := make([]float64, len(values))
	ref_772[168] = 0.05
	ref_772[174] = 0.05
	ref_772[176] = 0.05
	ref_772[177] = 0.05
	ref_772[178] = 0.05
	ref_772[179] = 0.05
	ref_772[180] = 0.05
	ref_772[181] = 0.05
	ref_772[182] = 0.05
	ref_772[184] = 0.05
	ref_772[190] = 0.05
	ref_642 := make([]float64, len(values))
	ref_642[54] = 0.05
	ref_642[56] = 0.05
	ref_642[57] = 0.05
	ref_642[60] = 0.05
	ref_642[62] = 0.05
	ref_642[63] = 0.05
	ref_642[64] = 0.05
	ref_642[65] = 0.05
	ref_642[66] = 0.05
	ref_642[67] = 0.05
	ref_642[68] = 0.05
	ref_642[70] = 0.05
	ref_899 := make([]float64, len(values))
	ref_899[0] = 0.05
	ref_899[1] = 0.05
	ref_899[2] = 0.05
	ref_899[3] = 0.05
	ref_899[4] = 0.05
	ref_899[5] = 0.05
	ref_899[7] = 0.05
	ref_899[253] = 0.05
	ref_899[255] = 0.05
	ref_777 := make([]float64, len(values))
	ref_777[162] = 0.05
	ref_777[164] = 0.05
	ref_777[165] = 0.05
	ref_777[166] = 0.05
	ref_777[167] = 0.05
	ref_777[168] = 0.05
	ref_777[170] = 0.05
	ref_777[171] = 0.05
	ref_777[172] = 0.05
	ref_777[173] = 0.05
	ref_777[174] = 0.05
	ref_777[175] = 0.05
	ref_777[176] = 0.05
	ref_777[178] = 0.05
	ref_780 := make([]float64, len(values))
	ref_780[159] = 0.05
	ref_780[161] = 0.05
	ref_780[162] = 0.05
	ref_780[163] = 0.05
	ref_780[164] = 0.05
	ref_780[165] = 0.05
	ref_780[166] = 0.05
	ref_780[167] = 0.05
	ref_780[169] = 0.05
	ref_780[170] = 0.05
	ref_780[171] = 0.05
	ref_780[172] = 0.05
	ref_780[173] = 0.05
	ref_780[175] = 0.05
	ref_783 := make([]float64, len(values))
	ref_783[128] = 0.05
	ref_783[129] = 0.05
	ref_783[130] = 0.05
	ref_783[131] = 0.05
	ref_783[132] = 0.05
	ref_783[133] = 0.05
	ref_783[134] = 0.05
	ref_783[136] = 0.05
	ref_783[186] = 0.05
	ref_783[188] = 0.05
	ref_783[189] = 0.05
	ref_783[192] = 0.05
	ref_783[194] = 0.05
	ref_783[195] = 0.05
	ref_783[196] = 0.05
	ref_783[197] = 0.05
	ref_783[198] = 0.05
	ref_783[199] = 0.05
	ref_783[200] = 0.05
	ref_783[202] = 0.05
	ref_786 := make([]float64, len(values))
	ref_786[127] = 0.05
	ref_786[177] = 0.05
	ref_786[179] = 0.05
	ref_786[180] = 0.05
	ref_786[181] = 0.05
	ref_786[182] = 0.05
	ref_786[183] = 0.05
	ref_786[184] = 0.05
	ref_786[185] = 0.05
	ref_786[187] = 0.05
	ref_786[190] = 0.05
	ref_786[191] = 0.05
	ref_786[193] = 0.05
	ref_789 := make([]float64, len(values))
	ref_789[127] = 0.05
	ref_789[128] = 0.05
	ref_789[130] = 0.05
	ref_789[180] = 0.05
	ref_789[182] = 0.05
	ref_789[183] = 0.05
	ref_789[184] = 0.05
	ref_789[185] = 0.05
	ref_789[186] = 0.05
	ref_789[187] = 0.05
	ref_789[188] = 0.05
	ref_789[190] = 0.05
	ref_789[191] = 0.05
	ref_789[192] = 0.05
	ref_789[193] = 0.05
	ref_789[194] = 0.05
	ref_789[196] = 0.05
	ref_792 := make([]float64, len(values))
	ref_792[127] = 0.05
	ref_792[128] = 0.05
	ref_792[129] = 0.05
	ref_792[130] = 0.05
	ref_792[131] = 0.05
	ref_792[133] = 0.05
	ref_792[183] = 0.05
	ref_792[185] = 0.05
	ref_792[186] = 0.05
	ref_792[187] = 0.05
	ref_792[188] = 0.05
	ref_792[189] = 0.05
	ref_792[191] = 0.05
	ref_792[192] = 0.05
	ref_792[193] = 0.05
	ref_792[194] = 0.05
	ref_792[195] = 0.05
	ref_792[196] = 0.05
	ref_792[197] = 0.05
	ref_792[199] = 0.05
	ref_797 := make([]float64, len(values))
	ref_797[197] = 0.05
	ref_797[203] = 0.05
	ref_797[205] = 0.05
	ref_797[206] = 0.05
	ref_797[207] = 0.05
	ref_797[208] = 0.05
	ref_797[209] = 0.05
	ref_797[210] = 0.05
	ref_797[211] = 0.05
	ref_797[213] = 0.05
	ref_667 := make([]float64, len(values))
	ref_667[44] = 0.05
	ref_667[50] = 0.05
	ref_667[52] = 0.05
	ref_667[53] = 0.05
	ref_667[54] = 0.05
	ref_667[55] = 0.05
	ref_667[56] = 0.05
	ref_667[57] = 0.05
	ref_667[58] = 0.05
	ref_667[60] = 0.05
	ref_667[66] = 0.05
	ref_924 := make([]float64, len(values))
	ref_924[0] = 0.25
	ref_924[1] = 0.25
	ref_924[2] = 0.25
	ref_924[3] = 0.25
	ref_924[4] = 0.25
	ref_924[5] = 0.25
	ref_802 := make([]float64, len(values))
	ref_802[161] = 0.05
	ref_802[163] = 0.05
	ref_802[164] = 0.05
	ref_802[165] = 0.05
	ref_802[166] = 0.05
	ref_802[167] = 0.05
	ref_802[168] = 0.05
	ref_802[169] = 0.05
	ref_802[171] = 0.05
	ref_802[177] = 0.05
	ref_805 := make([]float64, len(values))
	ref_805[158] = 0.05
	ref_805[160] = 0.05
	ref_805[161] = 0.05
	ref_805[162] = 0.05
	ref_805[163] = 0.05
	ref_805[164] = 0.05
	ref_805[165] = 0.05
	ref_805[166] = 0.05
	ref_805[168] = 0.05
	ref_805[218] = 0.05
	ref_1065 := make([]float64, len(values))
	ref_1065[24] = 0.05
	ref_1065[25] = 0.05
	ref_1065[26] = 0.05
	ref_808 := make([]float64, len(values))
	ref_808[157] = 0.05
	ref_808[158] = 0.05
	ref_808[159] = 0.05
	ref_808[160] = 0.05
	ref_808[161] = 0.05
	ref_808[162] = 0.05
	ref_808[163] = 0.05
	ref_808[165] = 0.05
	ref_808[215] = 0.05
	ref_808[217] = 0.05
	ref_808[218] = 0.05
	ref_811 := make([]float64, len(values))
	ref_811[156] = 0.05
	ref_811[206] = 0.05
	ref_811[208] = 0.05
	ref_811[209] = 0.05
	ref_811[210] = 0.05
	ref_811[211] = 0.05
	ref_811[212] = 0.05
	ref_811[213] = 0.05
	ref_811[214] = 0.05
	ref_811[216] = 0.05
	ref_938 := make([]float64, len(values))
	ref_938[24] = 0.25
	ref_938[25] = 0.25
	ref_938[26] = 0.25
	ref_938[27] = 0.25
	ref_938[28] = 0.25
	ref_938[29] = 0.25
	ref_814 := make([]float64, len(values))
	ref_814[156] = 0.05
	ref_814[157] = 0.05
	ref_814[159] = 0.05
	ref_814[209] = 0.05
	ref_814[211] = 0.05
	ref_814[212] = 0.05
	ref_814[213] = 0.05
	ref_814[214] = 0.05
	ref_814[215] = 0.05
	ref_814[216] = 0.05
	ref_814[217] = 0.05
	ref_817 := make([]float64, len(values))
	ref_817[156] = 0.05
	ref_817[157] = 0.05
	ref_817[158] = 0.05
	ref_817[159] = 0.05
	ref_817[160] = 0.05
	ref_817[162] = 0.05
	ref_817[212] = 0.05
	ref_817[214] = 0.05
	ref_817[215] = 0.05
	ref_817[216] = 0.05
	ref_817[217] = 0.05
	ref_817[218] = 0.05
	ref_822 := make([]float64, len(values))
	ref_822[202] = 0.05
	ref_822[204] = 0.05
	ref_822[205] = 0.05
	ref_822[208] = 0.05
	ref_822[210] = 0.05
	ref_822[211] = 0.05
	ref_822[212] = 0.05
	ref_822[213] = 0.05
	ref_822[214] = 0.05
	ref_822[215] = 0.05
	ref_822[216] = 0.05
	ref_822[218] = 0.05
	ref_827 := make([]float64, len(values))
	ref_827[196] = 0.05
	ref_827[198] = 0.05
	ref_827[199] = 0.05
	ref_827[200] = 0.05
	ref_827[201] = 0.05
	ref_827[202] = 0.05
	ref_827[203] = 0.05
	ref_827[204] = 0.05
	ref_827[206] = 0.05
	ref_827[207] = 0.05
	ref_827[208] = 0.05
	ref_827[209] = 0.05
	ref_827[210] = 0.05
	ref_827[212] = 0.05
	ref_1104 := make([]float64, len(values))
	ref_1104[249] = -0.25
	ref_847 := make([]float64, len(values))
	ref_847[234] = 0.05
	ref_852 := make([]float64, len(values))
	ref_852[228] = 0.05
	ref_852[230] = 0.05
	ref_852[231] = 0.05
	ref_852[232] = 0.05
	ref_852[233] = 0.05
	ref_852[234] = 0.05
	ref_855 := make([]float64, len(values))
	ref_855[225] = 0.05
	ref_855[227] = 0.05
	ref_855[228] = 0.05
	ref_855[229] = 0.05
	ref_855[230] = 0.05
	ref_855[231] = 0.05
	ref_855[232] = 0.05
	ref_855[233] = 0.05
	ref_858 := make([]float64, len(values))
	ref_858[222] = 0.05
	ref_858[224] = 0.05
	ref_858[225] = 0.05
	ref_858[226] = 0.05
	ref_858[227] = 0.05
	ref_858[228] = 0.05
	ref_858[229] = 0.05
	ref_858[230] = 0.05
	ref_858[232] = 0.05
	ref_861 := make([]float64, len(values))
	ref_861[219] = 0.05
	ref_861[221] = 0.05
	ref_861[222] = 0.05
	ref_861[223] = 0.05
	ref_861[224] = 0.05
	ref_861[225] = 0.05
	ref_861[226] = 0.05
	ref_861[227] = 0.05
	ref_861[229] = 0.05
	ref_864 := make([]float64, len(values))
	ref_864[193] = 0.05
	ref_1124 := make([]float64, len(values))
	ref_1124[1] = -0.25
	ref_1124[254] = -0.25
	ref_1124[255] = 0.25
	ref_867 := make([]float64, len(values))
	ref_867[193] = 0.05
	ref_867[194] = 0.05
	ref_867[196] = 0.05
	ref_872 := make([]float64, len(values))
	ref_872[224] = 0.05
	ref_872[226] = 0.05
	ref_872[227] = 0.05
	ref_872[228] = 0.05
	ref_872[229] = 0.05
	ref_872[230] = 0.05
	ref_872[231] = 0.05
	ref_872[232] = 0.05
	ref_872[234] = 0.05
	ref_877 := make([]float64, len(values))
	ref_877[222] = 0.05
	ref_880 := make([]float64, len(values))
	ref_880[222] = 0.05
	ref_880[223] = 0.05
	ref_880[225] = 0.05
	ref_883 := make([]float64, len(values))
	ref_883[222] = 0.05
	ref_883[223] = 0.05
	ref_883[224] = 0.05
	ref_883[225] = 0.05
	ref_883[226] = 0.05
	ref_883[228] = 0.05
	ref_902 := make([]float64, len(values))
	ref_902[6] = 0.05
	ref_902[8] = 0.05
	ref_902[9] = 0.05
	ref_902[10] = 0.05
	ref_902[11] = 0.05
	ref_902[12] = 0.05
	ref_905 := make([]float64, len(values))
	ref_905[0] = 0.05
	ref_905[1] = 0.05
	ref_905[2] = 0.05
	ref_905[4] = 0.05
	ref_905[250] = 0.05
	ref_905[252] = 0.05
	ref_905[253] = 0.05
	ref_905[254] = 0.05
	ref_905[255] = 0.05
	ref_908 := make([]float64, len(values))
	ref_908[1] = 0.05
	ref_908[249] = 0.05
	ref_908[250] = 0.05
	ref_908[251] = 0.05
	ref_908[252] = 0.05
	ref_908[253] = 0.05
	ref_908[254] = 0.05
	ref_908[255] = 0.05
	ref_922 := make([]float64, len(values))
	ref_922[0] = 0.25
	ref_922[1] = 0.25
	ref_922[2] = 0.25
	ref_927 := make([]float64, len(values))
	ref_927[3] = 0.25
	ref_927[4] = 0.25
	ref_927[5] = 0.25
	ref_927[6] = 0.25
	ref_927[7] = 0.25
	ref_927[8] = 0.25
	ref_930 := make([]float64, len(values))
	ref_930[14] = 0.25
	ref_930[15] = 0.25
	ref_930[16] = 0.25
	ref_948 := make([]float64, len(values))
	ref_948[44] = 0.25
	ref_948[45] = 0.25
	ref_948[46] = 0.25
	ref_948[47] = 0.25
	ref_948[48] = 0.25
	ref_948[49] = 0.25
	ref_950 := make([]float64, len(values))
	ref_950[41] = 0.25
	ref_950[42] = 0.25
	ref_950[43] = 0.25
	ref_958 := make([]float64, len(values))
	ref_958[55] = 0.25
	ref_958[56] = 0.25
	ref_958[57] = 0.25
	ref_575 := make([]float64, len(ref_566))
	for i := range ref_575 { ref_575[i] = ref_566[i] * ref_574[i] }
	ref_567 := make([]float64, len(ref_566))
	for i := range ref_567 { ref_567[i] = ref_566[(i + 2 + len(ref_566)) % len(ref_566)] }
	ref_577 := make([]float64, len(ref_567))
	for i := range ref_577 { ref_577[i] = ref_567[i] * ref_576[i] }
	ref_578 := make([]float64, len(ref_575))
	for i := range ref_578 { ref_578[i] = ref_575[i] + ref_577[i] }
	ref_568 := make([]float64, len(ref_566))
	for i := range ref_568 { ref_568[i] = ref_566[(i + 1 + len(ref_566)) % len(ref_566)] }
	ref_580 := make([]float64, len(ref_568))
	for i := range ref_580 { ref_580[i] = ref_568[i] * ref_579[i] }
	ref_569 := make([]float64, len(ref_566))
	for i := range ref_569 { ref_569[i] = ref_566[(i + 7 + len(ref_566)) % len(ref_566)] }
	ref_583 := make([]float64, len(ref_569))
	for i := range ref_583 { ref_583[i] = ref_569[i] * ref_582[i] }
	ref_1133 := make([]float64, len(ref_580))
	for i := range ref_1133 { ref_1133[i] = ref_580[i] + ref_583[i] }
	ref_1145 := make([]float64, len(ref_578))
	for i := range ref_1145 { ref_1145[i] = ref_578[i] + ref_1133[i] }
	ref_570 := make([]float64, len(ref_566))
	for i := range ref_570 { ref_570[i] = ref_566[(i + 6 + len(ref_566)) % len(ref_566)] }
	ref_586 := make([]float64, len(ref_570))
	for i := range ref_586 { ref_586[i] = ref_570[i] * ref_585[i] }
	ref_571 := make([]float64, len(ref_566))
	for i := range ref_571 { ref_571[i] = ref_566[(i + 5 + len(ref_566)) % len(ref_566)] }
	ref_589 := make([]float64, len(ref_571))
	for i := range ref_589 { ref_589[i] = ref_571[i] * ref_588[i] }
	ref_1139 := make([]float64, len(ref_586))
	for i := range ref_1139 { ref_1139[i] = ref_586[i] + ref_589[i] }
	ref_572 := make([]float64, len(ref_566))
	for i := range ref_572 { ref_572[i] = ref_566[(i + 4 + len(ref_566)) % len(ref_566)] }
	ref_592 := make([]float64, len(ref_572))
	for i := range ref_592 { ref_592[i] = ref_572[i] * ref_591[i] }
	ref_573 := make([]float64, len(ref_566))
	for i := range ref_573 { ref_573[i] = ref_566[(i + 3 + len(ref_566)) % len(ref_566)] }
	ref_595 := make([]float64, len(ref_573))
	for i := range ref_595 { ref_595[i] = ref_573[i] * ref_594[i] }
	ref_1149 := make([]float64, len(ref_592))
	for i := range ref_1149 { ref_1149[i] = ref_592[i] + ref_595[i] }
	ref_1150 := make([]float64, len(ref_1139))
	for i := range ref_1150 { ref_1150[i] = ref_1139[i] + ref_1149[i] }
	ref_1148 := make([]float64, len(ref_1145))
	for i := range ref_1148 { ref_1148[i] = ref_1145[i] + ref_1150[i] }
	ref_598 := make([]float64, len(ref_568))
	for i := range ref_598 { ref_598[i] = ref_568[i] * ref_597[i] }
	ref_600 := make([]float64, len(ref_567))
	for i := range ref_600 { ref_600[i] = ref_567[i] * ref_599[i] }
	ref_601 := make([]float64, len(ref_598))
	for i := range ref_601 { ref_601[i] = ref_598[i] + ref_600[i] }
	ref_603 := make([]float64, len(ref_573))
	for i := range ref_603 { ref_603[i] = ref_573[i] * ref_602[i] }
	ref_606 := make([]float64, len(ref_569))
	for i := range ref_606 { ref_606[i] = ref_569[i] * ref_605[i] }
	ref_1151 := make([]float64, len(ref_603))
	for i := range ref_1151 { ref_1151[i] = ref_603[i] + ref_606[i] }
	ref_1163 := make([]float64, len(ref_601))
	for i := range ref_1163 { ref_1163[i] = ref_601[i] + ref_1151[i] }
	ref_609 := make([]float64, len(ref_572))
	for i := range ref_609 { ref_609[i] = ref_572[i] * ref_608[i] }
	ref_612 := make([]float64, len(ref_571))
	for i := range ref_612 { ref_612[i] = ref_571[i] * ref_611[i] }
	ref_1157 := make([]float64, len(ref_609))
	for i := range ref_1157 { ref_1157[i] = ref_609[i] + ref_612[i] }
	ref_615 := make([]float64, len(ref_570))
	for i := range ref_615 { ref_615[i] = ref_570[i] * ref_614[i] }
	ref_618 := make([]float64, len(ref_566))
	for i := range ref_618 { ref_618[i] = ref_566[i] * ref_617[i] }
	ref_1167 := make([]float64, len(ref_615))
	for i := range ref_1167 { ref_1167[i] = ref_615[i] + ref_618[i] }
	ref_1168 := make([]float64, len(ref_1157))
	for i := range ref_1168 { ref_1168[i] = ref_1157[i] + ref_1167[i] }
	ref_1166 := make([]float64, len(ref_1163))
	for i := range ref_1166 { ref_1166[i] = ref_1163[i] + ref_1168[i] }
	ref_620 := make([]float64, len(ref_1166))
	for i := range ref_620 { ref_620[i] = ref_1166[(i + 8 + len(ref_1166)) % len(ref_1166)] }
	ref_621 := make([]float64, len(ref_1148))
	for i := range ref_621 { ref_621[i] = ref_1148[i] + ref_620[i] }
	ref_623 := make([]float64, len(ref_566))
	for i := range ref_623 { ref_623[i] = ref_566[i] * ref_622[i] }
	ref_625 := make([]float64, len(ref_568))
	for i := range ref_625 { ref_625[i] = ref_568[i] * ref_624[i] }
	ref_626 := make([]float64, len(ref_623))
	for i := range ref_626 { ref_626[i] = ref_623[i] + ref_625[i] }
	ref_628 := make([]float64, len(ref_567))
	for i := range ref_628 { ref_628[i] = ref_567[i] * ref_627[i] }
	ref_631 := make([]float64, len(ref_573))
	for i := range ref_631 { ref_631[i] = ref_573[i] * ref_630[i] }
	ref_1169 := make([]float64, len(ref_628))
	for i := range ref_1169 { ref_1169[i] = ref_628[i] + ref_631[i] }
	ref_1181 := make([]float64, len(ref_626))
	for i := range ref_1181 { ref_1181[i] = ref_626[i] + ref_1169[i] }
	ref_634 := make([]float64, len(ref_569))
	for i := range ref_634 { ref_634[i] = ref_569[i] * ref_633[i] }
	ref_637 := make([]float64, len(ref_570))
	for i := range ref_637 { ref_637[i] = ref_570[i] * ref_636[i] }
	ref_1175 := make([]float64, len(ref_634))
	for i := range ref_1175 { ref_1175[i] = ref_634[i] + ref_637[i] }
	ref_640 := make([]float64, len(ref_571))
	for i := range ref_640 { ref_640[i] = ref_571[i] * ref_639[i] }
	ref_643 := make([]float64, len(ref_572))
	for i := range ref_643 { ref_643[i] = ref_572[i] * ref_642[i] }
	ref_1185 := make([]float64, len(ref_640))
	for i := range ref_1185 { ref_1185[i] = ref_640[i] + ref_643[i] }
	ref_1186 := make([]float64, len(ref_1175))
	for i := range ref_1186 { ref_1186[i] = ref_1175[i] + ref_1185[i] }
	ref_1184 := make([]float64, len(ref_1181))
	for i := range ref_1184 { ref_1184[i] = ref_1181[i] + ref_1186[i] }
	ref_645 := make([]float64, len(ref_1184))
	for i := range ref_645 { ref_645[i] = ref_1184[(i + 16 + len(ref_1184)) % len(ref_1184)] }
	ref_648 := make([]float64, len(ref_567))
	for i := range ref_648 { ref_648[i] = ref_567[i] * ref_647[i] }
	ref_650 := make([]float64, len(ref_573))
	for i := range ref_650 { ref_650[i] = ref_573[i] * ref_649[i] }
	ref_651 := make([]float64, len(ref_648))
	for i := range ref_651 { ref_651[i] = ref_648[i] + ref_650[i] }
	ref_653 := make([]float64, len(ref_572))
	for i := range ref_653 { ref_653[i] = ref_572[i] * ref_652[i] }
	ref_656 := make([]float64, len(ref_571))
	for i := range ref_656 { ref_656[i] = ref_571[i] * ref_655[i] }
	ref_1187 := make([]float64, len(ref_653))
	for i := range ref_1187 { ref_1187[i] = ref_653[i] + ref_656[i] }
	ref_1199 := make([]float64, len(ref_651))
	for i := range ref_1199 { ref_1199[i] = ref_651[i] + ref_1187[i] }
	ref_659 := make([]float64, len(ref_570))
	for i := range ref_659 { ref_659[i] = ref_570[i] * ref_658[i] }
	ref_662 := make([]float64, len(ref_569))
	for i := range ref_662 { ref_662[i] = ref_569[i] * ref_661[i] }
	ref_1193 := make([]float64, len(ref_659))
	for i := range ref_1193 { ref_1193[i] = ref_659[i] + ref_662[i] }
	ref_665 := make([]float64, len(ref_568))
	for i := range ref_665 { ref_665[i] = ref_568[i] * ref_664[i] }
	ref_668 := make([]float64, len(ref_566))
	for i := range ref_668 { ref_668[i] = ref_566[i] * ref_667[i] }
	ref_1203 := make([]float64, len(ref_665))
	for i := range ref_1203 { ref_1203[i] = ref_665[i] + ref_668[i] }
	ref_1204 := make([]float64, len(ref_1193))
	for i := range ref_1204 { ref_1204[i] = ref_1193[i] + ref_1203[i] }
	ref_1202 := make([]float64, len(ref_1199))
	for i := range ref_1202 { ref_1202[i] = ref_1199[i] + ref_1204[i] }
	ref_670 := make([]float64, len(ref_1202))
	for i := range ref_670 { ref_670[i] = ref_1202[(i + 24 + len(ref_1202)) % len(ref_1202)] }
	ref_1205 := make([]float64, len(ref_645))
	for i := range ref_1205 { ref_1205[i] = ref_645[i] + ref_670[i] }
	ref_1271 := make([]float64, len(ref_621))
	for i := range ref_1271 { ref_1271[i] = ref_621[i] + ref_1205[i] }
	ref_673 := make([]float64, len(ref_566))
	for i := range ref_673 { ref_673[i] = ref_566[i] * ref_672[i] }
	ref_675 := make([]float64, len(ref_568))
	for i := range ref_675 { ref_675[i] = ref_568[i] * ref_674[i] }
	ref_676 := make([]float64, len(ref_673))
	for i := range ref_676 { ref_676[i] = ref_673[i] + ref_675[i] }
	ref_678 := make([]float64, len(ref_567))
	for i := range ref_678 { ref_678[i] = ref_567[i] * ref_677[i] }
	ref_681 := make([]float64, len(ref_569))
	for i := range ref_681 { ref_681[i] = ref_569[i] * ref_680[i] }
	ref_1207 := make([]float64, len(ref_678))
	for i := range ref_1207 { ref_1207[i] = ref_678[i] + ref_681[i] }
	ref_1219 := make([]float64, len(ref_676))
	for i := range ref_1219 { ref_1219[i] = ref_676[i] + ref_1207[i] }
	ref_684 := make([]float64, len(ref_570))
	for i := range ref_684 { ref_684[i] = ref_570[i] * ref_683[i] }
	ref_687 := make([]float64, len(ref_571))
	for i := range ref_687 { ref_687[i] = ref_571[i] * ref_686[i] }
	ref_1213 := make([]float64, len(ref_684))
	for i := range ref_1213 { ref_1213[i] = ref_684[i] + ref_687[i] }
	ref_690 := make([]float64, len(ref_572))
	for i := range ref_690 { ref_690[i] = ref_572[i] * ref_689[i] }
	ref_693 := make([]float64, len(ref_573))
	for i := range ref_693 { ref_693[i] = ref_573[i] * ref_692[i] }
	ref_1223 := make([]float64, len(ref_690))
	for i := range ref_1223 { ref_1223[i] = ref_690[i] + ref_693[i] }
	ref_1224 := make([]float64, len(ref_1213))
	for i := range ref_1224 { ref_1224[i] = ref_1213[i] + ref_1223[i] }
	ref_1222 := make([]float64, len(ref_1219))
	for i := range ref_1222 { ref_1222[i] = ref_1219[i] + ref_1224[i] }
	ref_695 := make([]float64, len(ref_1222))
	for i := range ref_695 { ref_695[i] = ref_1222[(i + 32 + len(ref_1222)) % len(ref_1222)] }
	ref_698 := make([]float64, len(ref_570))
	for i := range ref_698 { ref_698[i] = ref_570[i] * ref_697[i] }
	ref_700 := make([]float64, len(ref_569))
	for i := range ref_700 { ref_700[i] = ref_569[i] * ref_699[i] }
	ref_701 := make([]float64, len(ref_698))
	for i := range ref_701 { ref_701[i] = ref_698[i] + ref_700[i] }
	ref_703 := make([]float64, len(ref_573))
	for i := range ref_703 { ref_703[i] = ref_573[i] * ref_702[i] }
	ref_706 := make([]float64, len(ref_572))
	for i := range ref_706 { ref_706[i] = ref_572[i] * ref_705[i] }
	ref_1227 := make([]float64, len(ref_703))
	for i := range ref_1227 { ref_1227[i] = ref_703[i] + ref_706[i] }
	ref_1239 := make([]float64, len(ref_701))
	for i := range ref_1239 { ref_1239[i] = ref_701[i] + ref_1227[i] }
	ref_709 := make([]float64, len(ref_571))
	for i := range ref_709 { ref_709[i] = ref_571[i] * ref_708[i] }
	ref_712 := make([]float64, len(ref_567))
	for i := range ref_712 { ref_712[i] = ref_567[i] * ref_711[i] }
	ref_1233 := make([]float64, len(ref_709))
	for i := range ref_1233 { ref_1233[i] = ref_709[i] + ref_712[i] }
	ref_715 := make([]float64, len(ref_568))
	for i := range ref_715 { ref_715[i] = ref_568[i] * ref_714[i] }
	ref_718 := make([]float64, len(ref_566))
	for i := range ref_718 { ref_718[i] = ref_566[i] * ref_717[i] }
	ref_1243 := make([]float64, len(ref_715))
	for i := range ref_1243 { ref_1243[i] = ref_715[i] + ref_718[i] }
	ref_1244 := make([]float64, len(ref_1233))
	for i := range ref_1244 { ref_1244[i] = ref_1233[i] + ref_1243[i] }
	ref_1242 := make([]float64, len(ref_1239))
	for i := range ref_1242 { ref_1242[i] = ref_1239[i] + ref_1244[i] }
	ref_720 := make([]float64, len(ref_1242))
	for i := range ref_720 { ref_720[i] = ref_1242[(i + 40 + len(ref_1242)) % len(ref_1242)] }
	ref_1247 := make([]float64, len(ref_695))
	for i := range ref_1247 { ref_1247[i] = ref_695[i] + ref_720[i] }
	ref_723 := make([]float64, len(ref_566))
	for i := range ref_723 { ref_723[i] = ref_566[i] * ref_722[i] }
	ref_725 := make([]float64, len(ref_568))
	for i := range ref_725 { ref_725[i] = ref_568[i] * ref_724[i] }
	ref_726 := make([]float64, len(ref_723))
	for i := range ref_726 { ref_726[i] = ref_723[i] + ref_725[i] }
	ref_728 := make([]float64, len(ref_567))
	for i := range ref_728 { ref_728[i] = ref_567[i] * ref_727[i] }
	ref_731 := make([]float64, len(ref_573))
	for i := range ref_731 { ref_731[i] = ref_573[i] * ref_730[i] }
	ref_1249 := make([]float64, len(ref_728))
	for i := range ref_1249 { ref_1249[i] = ref_728[i] + ref_731[i] }
	ref_1261 := make([]float64, len(ref_726))
	for i := range ref_1261 { ref_1261[i] = ref_726[i] + ref_1249[i] }
	ref_734 := make([]float64, len(ref_570))
	for i := range ref_734 { ref_734[i] = ref_570[i] * ref_733[i] }
	ref_737 := make([]float64, len(ref_569))
	for i := range ref_737 { ref_737[i] = ref_569[i] * ref_736[i] }
	ref_1255 := make([]float64, len(ref_734))
	for i := range ref_1255 { ref_1255[i] = ref_734[i] + ref_737[i] }
	ref_740 := make([]float64, len(ref_571))
	for i := range ref_740 { ref_740[i] = ref_571[i] * ref_739[i] }
	ref_743 := make([]float64, len(ref_572))
	for i := range ref_743 { ref_743[i] = ref_572[i] * ref_742[i] }
	ref_1265 := make([]float64, len(ref_740))
	for i := range ref_1265 { ref_1265[i] = ref_740[i] + ref_743[i] }
	ref_1266 := make([]float64, len(ref_1255))
	for i := range ref_1266 { ref_1266[i] = ref_1255[i] + ref_1265[i] }
	ref_1264 := make([]float64, len(ref_1261))
	for i := range ref_1264 { ref_1264[i] = ref_1261[i] + ref_1266[i] }
	ref_745 := make([]float64, len(ref_1264))
	for i := range ref_745 { ref_745[i] = ref_1264[(i + 48 + len(ref_1264)) % len(ref_1264)] }
	ref_748 := make([]float64, len(ref_568))
	for i := range ref_748 { ref_748[i] = ref_568[i] * ref_747[i] }
	ref_750 := make([]float64, len(ref_567))
	for i := range ref_750 { ref_750[i] = ref_567[i] * ref_749[i] }
	ref_751 := make([]float64, len(ref_748))
	for i := range ref_751 { ref_751[i] = ref_748[i] + ref_750[i] }
	ref_753 := make([]float64, len(ref_573))
	for i := range ref_753 { ref_753[i] = ref_573[i] * ref_752[i] }
	ref_756 := make([]float64, len(ref_572))
	for i := range ref_756 { ref_756[i] = ref_572[i] * ref_755[i] }
	ref_1273 := make([]float64, len(ref_753))
	for i := range ref_1273 { ref_1273[i] = ref_753[i] + ref_756[i] }
	ref_1285 := make([]float64, len(ref_751))
	for i := range ref_1285 { ref_1285[i] = ref_751[i] + ref_1273[i] }
	ref_759 := make([]float64, len(ref_571))
	for i := range ref_759 { ref_759[i] = ref_571[i] * ref_758[i] }
	ref_762 := make([]float64, len(ref_570))
	for i := range ref_762 { ref_762[i] = ref_570[i] * ref_761[i] }
	ref_1279 := make([]float64, len(ref_759))
	for i := range ref_1279 { ref_1279[i] = ref_759[i] + ref_762[i] }
	ref_765 := make([]float64, len(ref_569))
	for i := range ref_765 { ref_765[i] = ref_569[i] * ref_764[i] }
	ref_768 := make([]float64, len(ref_566))
	for i := range ref_768 { ref_768[i] = ref_566[i] * ref_767[i] }
	ref_1289 := make([]float64, len(ref_765))
	for i := range ref_1289 { ref_1289[i] = ref_765[i] + ref_768[i] }
	ref_1290 := make([]float64, len(ref_1279))
	for i := range ref_1290 { ref_1290[i] = ref_1279[i] + ref_1289[i] }
	ref_1288 := make([]float64, len(ref_1285))
	for i := range ref_1288 { ref_1288[i] = ref_1285[i] + ref_1290[i] }
	ref_770 := make([]float64, len(ref_1288))
	for i := range ref_770 { ref_770[i] = ref_1288[(i + 56 + len(ref_1288)) % len(ref_1288)] }
	ref_1293 := make([]float64, len(ref_745))
	for i := range ref_1293 { ref_1293[i] = ref_745[i] + ref_770[i] }
	ref_1365 := make([]float64, len(ref_1247))
	for i := range ref_1365 { ref_1365[i] = ref_1247[i] + ref_1293[i] }
	ref_1401 := make([]float64, len(ref_1271))
	for i := range ref_1401 { ref_1401[i] = ref_1271[i] + ref_1365[i] }
	ref_773 := make([]float64, len(ref_572))
	for i := range ref_773 { ref_773[i] = ref_572[i] * ref_772[i] }
	ref_775 := make([]float64, len(ref_571))
	for i := range ref_775 { ref_775[i] = ref_571[i] * ref_774[i] }
	ref_776 := make([]float64, len(ref_773))
	for i := range ref_776 { ref_776[i] = ref_773[i] + ref_775[i] }
	ref_778 := make([]float64, len(ref_570))
	for i := range ref_778 { ref_778[i] = ref_570[i] * ref_777[i] }
	ref_781 := make([]float64, len(ref_569))
	for i := range ref_781 { ref_781[i] = ref_569[i] * ref_780[i] }
	ref_1295 := make([]float64, len(ref_778))
	for i := range ref_1295 { ref_1295[i] = ref_778[i] + ref_781[i] }
	ref_1307 := make([]float64, len(ref_776))
	for i := range ref_1307 { ref_1307[i] = ref_776[i] + ref_1295[i] }
	ref_784 := make([]float64, len(ref_566))
	for i := range ref_784 { ref_784[i] = ref_566[i] * ref_783[i] }
	ref_787 := make([]float64, len(ref_573))
	for i := range ref_787 { ref_787[i] = ref_573[i] * ref_786[i] }
	ref_1301 := make([]float64, len(ref_784))
	for i := range ref_1301 { ref_1301[i] = ref_784[i] + ref_787[i] }
	ref_790 := make([]float64, len(ref_567))
	for i := range ref_790 { ref_790[i] = ref_567[i] * ref_789[i] }
	ref_793 := make([]float64, len(ref_568))
	for i := range ref_793 { ref_793[i] = ref_568[i] * ref_792[i] }
	ref_1311 := make([]float64, len(ref_790))
	for i := range ref_1311 { ref_1311[i] = ref_790[i] + ref_793[i] }
	ref_1312 := make([]float64, len(ref_1301))
	for i := range ref_1312 { ref_1312[i] = ref_1301[i] + ref_1311[i] }
	ref_1310 := make([]float64, len(ref_1307))
	for i := range ref_1310 { ref_1310[i] = ref_1307[i] + ref_1312[i] }
	ref_795 := make([]float64, len(ref_1310))
	for i := range ref_795 { ref_795[i] = ref_1310[(i + 64 + len(ref_1310)) % len(ref_1310)] }
	ref_798 := make([]float64, len(ref_569))
	for i := range ref_798 { ref_798[i] = ref_569[i] * ref_797[i] }
	ref_800 := make([]float64, len(ref_566))
	for i := range ref_800 { ref_800[i] = ref_566[i] * ref_799[i] }
	ref_801 := make([]float64, len(ref_798))
	for i := range ref_801 { ref_801[i] = ref_798[i] + ref_800[i] }
	ref_803 := make([]float64, len(ref_568))
	for i := range ref_803 { ref_803[i] = ref_568[i] * ref_802[i] }
	ref_806 := make([]float64, len(ref_567))
	for i := range ref_806 { ref_806[i] = ref_567[i] * ref_805[i] }
	ref_1317 := make([]float64, len(ref_803))
	for i := range ref_1317 { ref_1317[i] = ref_803[i] + ref_806[i] }
	ref_1329 := make([]float64, len(ref_801))
	for i := range ref_1329 { ref_1329[i] = ref_801[i] + ref_1317[i] }
	ref_809 := make([]float64, len(ref_573))
	for i := range ref_809 { ref_809[i] = ref_573[i] * ref_808[i] }
	ref_812 := make([]float64, len(ref_570))
	for i := range ref_812 { ref_812[i] = ref_570[i] * ref_811[i] }
	ref_1323 := make([]float64, len(ref_809))
	for i := range ref_1323 { ref_1323[i] = ref_809[i] + ref_812[i] }
	ref_815 := make([]float64, len(ref_571))
	for i := range ref_815 { ref_815[i] = ref_571[i] * ref_814[i] }
	ref_818 := make([]float64, len(ref_572))
	for i := range ref_818 { ref_818[i] = ref_572[i] * ref_817[i] }
	ref_1333 := make([]float64, len(ref_815))
	for i := range ref_1333 { ref_1333[i] = ref_815[i] + ref_818[i] }
	ref_1334 := make([]float64, len(ref_1323))
	for i := range ref_1334 { ref_1334[i] = ref_1323[i] + ref_1333[i] }
	ref_1332 := make([]float64, len(ref_1329))
	for i := range ref_1332 { ref_1332[i] = ref_1329[i] + ref_1334[i] }
	ref_820 := make([]float64, len(ref_1332))
	for i := range ref_820 { ref_820[i] = ref_1332[(i + 72 + len(ref_1332)) % len(ref_1332)] }
	ref_1339 := make([]float64, len(ref_795))
	for i := range ref_1339 { ref_1339[i] = ref_795[i] + ref_820[i] }
	ref_823 := make([]float64, len(ref_566))
	for i := range ref_823 { ref_823[i] = ref_566[i] * ref_822[i] }
	ref_825 := make([]float64, len(ref_568))
	for i := range ref_825 { ref_825[i] = ref_568[i] * ref_824[i] }
	ref_826 := make([]float64, len(ref_823))
	for i := range ref_826 { ref_826[i] = ref_823[i] + ref_825[i] }
	ref_828 := make([]float64, len(ref_567))
	for i := range ref_828 { ref_828[i] = ref_567[i] * ref_827[i] }
	ref_831 := make([]float64, len(ref_573))
	for i := range ref_831 { ref_831[i] = ref_573[i] * ref_830[i] }
	ref_1341 := make([]float64, len(ref_828))
	for i := range ref_1341 { ref_1341[i] = ref_828[i] + ref_831[i] }
	ref_1353 := make([]float64, len(ref_826))
	for i := range ref_1353 { ref_1353[i] = ref_826[i] + ref_1341[i] }
	ref_834 := make([]float64, len(ref_572))
	for i := range ref_834 { ref_834[i] = ref_572[i] * ref_833[i] }
	ref_837 := make([]float64, len(ref_571))
	for i := range ref_837 { ref_837[i] = ref_571[i] * ref_836[i] }
	ref_1347 := make([]float64, len(ref_834))
	for i := range ref_1347 { ref_1347[i] = ref_834[i] + ref_837[i] }
	ref_840 := make([]float64, len(ref_570))
	for i := range ref_840 { ref_840[i] = ref_570[i] * ref_839[i] }
	ref_843 := make([]float64, len(ref_569))
	for i := range ref_843 { ref_843[i] = ref_569[i] * ref_842[i] }
	ref_1357 := make([]float64, len(ref_840))
	for i := range ref_1357 { ref_1357[i] = ref_840[i] + ref_843[i] }
	ref_1358 := make([]float64, len(ref_1347))
	for i := range ref_1358 { ref_1358[i] = ref_1347[i] + ref_1357[i] }
	ref_1356 := make([]float64, len(ref_1353))
	for i := range ref_1356 { ref_1356[i] = ref_1353[i] + ref_1358[i] }
	ref_845 := make([]float64, len(ref_1356))
	for i := range ref_845 { ref_845[i] = ref_1356[(i + 80 + len(ref_1356)) % len(ref_1356)] }
	ref_848 := make([]float64, len(ref_567))
	for i := range ref_848 { ref_848[i] = ref_567[i] * ref_847[i] }
	ref_850 := make([]float64, len(ref_573))
	for i := range ref_850 { ref_850[i] = ref_573[i] * ref_849[i] }
	ref_851 := make([]float64, len(ref_848))
	for i := range ref_851 { ref_851[i] = ref_848[i] + ref_850[i] }
	ref_853 := make([]float64, len(ref_572))
	for i := range ref_853 { ref_853[i] = ref_572[i] * ref_852[i] }
	ref_856 := make([]float64, len(ref_571))
	for i := range ref_856 { ref_856[i] = ref_571[i] * ref_855[i] }
	ref_1367 := make([]float64, len(ref_853))
	for i := range ref_1367 { ref_1367[i] = ref_853[i] + ref_856[i] }
	ref_1379 := make([]float64, len(ref_851))
	for i := range ref_1379 { ref_1379[i] = ref_851[i] + ref_1367[i] }
	ref_859 := make([]float64, len(ref_570))
	for i := range ref_859 { ref_859[i] = ref_570[i] * ref_858[i] }
	ref_862 := make([]float64, len(ref_569))
	for i := range ref_862 { ref_862[i] = ref_569[i] * ref_861[i] }
	ref_1373 := make([]float64, len(ref_859))
	for i := range ref_1373 { ref_1373[i] = ref_859[i] + ref_862[i] }
	ref_865 := make([]float64, len(ref_568))
	for i := range ref_865 { ref_865[i] = ref_568[i] * ref_864[i] }
	ref_868 := make([]float64, len(ref_566))
	for i := range ref_868 { ref_868[i] = ref_566[i] * ref_867[i] }
	ref_1383 := make([]float64, len(ref_865))
	for i := range ref_1383 { ref_1383[i] = ref_865[i] + ref_868[i] }
	ref_1384 := make([]float64, len(ref_1373))
	for i := range ref_1384 { ref_1384[i] = ref_1373[i] + ref_1383[i] }
	ref_1382 := make([]float64, len(ref_1379))
	for i := range ref_1382 { ref_1382[i] = ref_1379[i] + ref_1384[i] }
	ref_870 := make([]float64, len(ref_1382))
	for i := range ref_870 { ref_870[i] = ref_1382[(i + 88 + len(ref_1382)) % len(ref_1382)] }
	ref_1389 := make([]float64, len(ref_845))
	for i := range ref_1389 { ref_1389[i] = ref_845[i] + ref_870[i] }
	ref_873 := make([]float64, len(ref_566))
	for i := range ref_873 { ref_873[i] = ref_566[i] * ref_872[i] }
	ref_875 := make([]float64, len(ref_568))
	for i := range ref_875 { ref_875[i] = ref_568[i] * ref_874[i] }
	ref_876 := make([]float64, len(ref_873))
	for i := range ref_876 { ref_876[i] = ref_873[i] + ref_875[i] }
	ref_878 := make([]float64, len(ref_572))
	for i := range ref_878 { ref_878[i] = ref_572[i] * ref_877[i] }
	ref_881 := make([]float64, len(ref_573))
	for i := range ref_881 { ref_881[i] = ref_573[i] * ref_880[i] }
	ref_1391 := make([]float64, len(ref_878))
	for i := range ref_1391 { ref_1391[i] = ref_878[i] + ref_881[i] }
	ref_884 := make([]float64, len(ref_567))
	for i := range ref_884 { ref_884[i] = ref_567[i] * ref_883[i] }
	ref_1393 := make([]float64, len(ref_1391))
	for i := range ref_1393 { ref_1393[i] = ref_1391[i] + ref_884[i] }
	ref_1394 := make([]float64, len(ref_876))
	for i := range ref_1394 { ref_1394[i] = ref_876[i] + ref_1393[i] }
	ref_886 := make([]float64, len(ref_1394))
	for i := range ref_886 { ref_886[i] = ref_1394[(i + 96 + len(ref_1394)) % len(ref_1394)] }
	ref_889 := make([]float64, len(ref_573))
	for i := range ref_889 { ref_889[i] = ref_573[i] * ref_888[i] }
	ref_891 := make([]float64, len(ref_566))
	for i := range ref_891 { ref_891[i] = ref_566[i] * ref_890[i] }
	ref_892 := make([]float64, len(ref_889))
	for i := range ref_892 { ref_892[i] = ref_889[i] + ref_891[i] }
	ref_894 := make([]float64, len(ref_572))
	for i := range ref_894 { ref_894[i] = ref_572[i] * ref_893[i] }
	ref_897 := make([]float64, len(ref_568))
	for i := range ref_897 { ref_897[i] = ref_568[i] * ref_896[i] }
	ref_1403 := make([]float64, len(ref_894))
	for i := range ref_1403 { ref_1403[i] = ref_894[i] + ref_897[i] }
	ref_1415 := make([]float64, len(ref_892))
	for i := range ref_1415 { ref_1415[i] = ref_892[i] + ref_1403[i] }
	ref_900 := make([]float64, len(ref_571))
	for i := range ref_900 { ref_900[i] = ref_571[i] * ref_899[i] }
	ref_903 := make([]float64, len(ref_567))
	for i := range ref_903 { ref_903[i] = ref_567[i] * ref_902[i] }
	ref_1409 := make([]float64, len(ref_900))
	for i := range ref_1409 { ref_1409[i] = ref_900[i] + ref_903[i] }
	ref_906 := make([]float64, len(ref_570))
	for i := range ref_906 { ref_906[i] = ref_570[i] * ref_905[i] }
	ref_909 := make([]float64, len(ref_569))
	for i := range ref_909 { ref_909[i] = ref_569[i] * ref_908[i] }
	ref_1419 := make([]float64, len(ref_906))
	for i := range ref_1419 { ref_1419[i] = ref_906[i] + ref_909[i] }
	ref_1420 := make([]float64, len(ref_1409))
	for i := range ref_1420 { ref_1420[i] = ref_1409[i] + ref_1419[i] }
	ref_1418 := make([]float64, len(ref_1415))
	for i := range ref_1418 { ref_1418[i] = ref_1415[i] + ref_1420[i] }
	ref_911 := make([]float64, len(ref_1418))
	for i := range ref_911 { ref_911[i] = ref_1418[(i + 248 + len(ref_1418)) % len(ref_1418)] }
	ref_1425 := make([]float64, len(ref_886))
	for i := range ref_1425 { ref_1425[i] = ref_886[i] + ref_911[i] }
	ref_1426 := make([]float64, len(ref_1389))
	for i := range ref_1426 { ref_1426[i] = ref_1389[i] + ref_1425[i] }
	ref_1424 := make([]float64, len(ref_1339))
	for i := range ref_1424 { ref_1424[i] = ref_1339[i] + ref_1426[i] }
	ref_1422 := make([]float64, len(ref_1401))
	for i := range ref_1422 { ref_1422[i] = ref_1401[i] + ref_1424[i] }
	ref_913 := ref_1422
	ref_914 := make([]float64, len(ref_913))
	for i := range ref_914 { ref_914[i] = ref_913[i] * ref_913[i] }
	ref_923 := make([]float64, len(ref_914))
	for i := range ref_923 { ref_923[i] = ref_914[i] * ref_922[i] }
	ref_915 := make([]float64, len(ref_914))
	for i := range ref_915 { ref_915[i] = ref_914[(i + 3 + len(ref_914)) % len(ref_914)] }
	ref_925 := make([]float64, len(ref_915))
	for i := range ref_925 { ref_925[i] = ref_915[i] * ref_924[i] }
	ref_926 := make([]float64, len(ref_923))
	for i := range ref_926 { ref_926[i] = ref_923[i] + ref_925[i] }
	ref_916 := make([]float64, len(ref_914))
	for i := range ref_916 { ref_916[i] = ref_914[(i + 6 + len(ref_914)) % len(ref_914)] }
	ref_928 := make([]float64, len(ref_916))
	for i := range ref_928 { ref_928[i] = ref_916[i] * ref_927[i] }
	ref_917 := make([]float64, len(ref_914))
	for i := range ref_917 { ref_917[i] = ref_914[(i + 1 + len(ref_914)) % len(ref_914)] }
	ref_931 := make([]float64, len(ref_917))
	for i := range ref_931 { ref_931[i] = ref_917[i] * ref_930[i] }
	ref_932 := make([]float64, len(ref_931))
	for i := range ref_932 { ref_932[i] = ref_931[(i + 8 + len(ref_931)) % len(ref_931)] }
	ref_1427 := make([]float64, len(ref_928))
	for i := range ref_1427 { ref_1427[i] = ref_928[i] + ref_932[i] }
	ref_918 := make([]float64, len(ref_914))
	for i := range ref_918 { ref_918[i] = ref_914[(i + 5 + len(ref_914)) % len(ref_914)] }
	ref_935 := make([]float64, len(ref_918))
	for i := range ref_935 { ref_935[i] = ref_918[i] * ref_934[i] }
	ref_936 := make([]float64, len(ref_935))
	for i := range ref_936 { ref_936[i] = ref_935[(i + 16 + len(ref_935)) % len(ref_935)] }
	ref_1429 := make([]float64, len(ref_1427))
	for i := range ref_1429 { ref_1429[i] = ref_1427[i] + ref_936[i] }
	ref_1430 := make([]float64, len(ref_926))
	for i := range ref_1430 { ref_1430[i] = ref_926[i] + ref_1429[i] }
	ref_939 := make([]float64, len(ref_914))
	for i := range ref_939 { ref_939[i] = ref_914[i] * ref_938[i] }
	ref_941 := make([]float64, len(ref_915))
	for i := range ref_941 { ref_941[i] = ref_915[i] * ref_940[i] }
	ref_942 := make([]float64, len(ref_939))
	for i := range ref_942 { ref_942[i] = ref_939[i] + ref_941[i] }
	ref_944 := make([]float64, len(ref_916))
	for i := range ref_944 { ref_944[i] = ref_916[i] * ref_943[i] }
	ref_945 := make([]float64, len(ref_942))
	for i := range ref_945 { ref_945[i] = ref_942[i] + ref_944[i] }
	ref_946 := make([]float64, len(ref_945))
	for i := range ref_946 { ref_946[i] = ref_945[(i + 24 + len(ref_945)) % len(ref_945)] }
	ref_1446 := make([]float64, len(ref_1430))
	for i := range ref_1446 { ref_1446[i] = ref_1430[i] + ref_946[i] }
	ref_919 := make([]float64, len(ref_914))
	for i := range ref_919 { ref_919[i] = ref_914[(i + 7 + len(ref_914)) % len(ref_914)] }
	ref_949 := make([]float64, len(ref_919))
	for i := range ref_949 { ref_949[i] = ref_919[i] * ref_948[i] }
	ref_951 := make([]float64, len(ref_917))
	for i := range ref_951 { ref_951[i] = ref_917[i] * ref_950[i] }
	ref_952 := make([]float64, len(ref_949))
	for i := range ref_952 { ref_952[i] = ref_949[i] + ref_951[i] }
	ref_920 := make([]float64, len(ref_914))
	for i := range ref_920 { ref_920[i] = ref_914[(i + 4 + len(ref_914)) % len(ref_914)] }
	ref_954 := make([]float64, len(ref_920))
	for i := range ref_954 { ref_954[i] = ref_920[i] * ref_953[i] }
	ref_955 := make([]float64, len(ref_952))
	for i := range ref_955 { ref_955[i] = ref_952[i] + ref_954[i] }
	ref_956 := make([]float64, len(ref_955))
	for i := range ref_956 { ref_956[i] = ref_955[(i + 32 + len(ref_955)) % len(ref_955)] }
	ref_921 := make([]float64, len(ref_914))
	for i := range ref_921 { ref_921[i] = ref_914[(i + 2 + len(ref_914)) % len(ref_914)] }
	ref_959 := make([]float64, len(ref_921))
	for i := range ref_959 { ref_959[i] = ref_921[i] * ref_958[i] }
	ref_960 := make([]float64, len(ref_959))
	for i := range ref_960 { ref_960[i] = ref_959[(i + 40 + len(ref_959)) % len(ref_959)] }
	ref_963 := make([]float64, len(ref_916))
	for i := range ref_963 { ref_963[i] = ref_916[i] * ref_962[i] }
	ref_964 := make([]float64, len(ref_963))
	for i := range ref_964 { ref_964[i] = ref_963[(i + 48 + len(ref_963)) % len(ref_963)] }
	ref_1442 := make([]float64, len(ref_960))
	for i := range ref_1442 { ref_1442[i] = ref_960[i] + ref_964[i] }
	ref_1445 := make([]float64, len(ref_956))
	for i := range ref_1445 { ref_1445[i] = ref_956[i] + ref_1442[i] }
	ref_1470 := make([]float64, len(ref_1446))
	for i := range ref_1470 { ref_1470[i] = ref_1446[i] + ref_1445[i] }
	ref_967 := make([]float64, len(ref_919))
	for i := range ref_967 { ref_967[i] = ref_919[i] * ref_966[i] }
	ref_969 := make([]float64, len(ref_920))
	for i := range ref_969 { ref_969[i] = ref_920[i] * ref_968[i] }
	ref_970 := make([]float64, len(ref_967))
	for i := range ref_970 { ref_970[i] = ref_967[i] + ref_969[i] }
	ref_972 := make([]float64, len(ref_917))
	for i := range ref_972 { ref_972[i] = ref_917[i] * ref_971[i] }
	ref_973 := make([]float64, len(ref_970))
	for i := range ref_973 { ref_973[i] = ref_970[i] + ref_972[i] }
	ref_974 := make([]float64, len(ref_973))
	for i := range ref_974 { ref_974[i] = ref_973[(i + 56 + len(ref_973)) % len(ref_973)] }
	ref_977 := make([]float64, len(ref_918))
	for i := range ref_977 { ref_977[i] = ref_918[i] * ref_976[i] }
	ref_979 := make([]float64, len(ref_921))
	for i := range ref_979 { ref_979[i] = ref_921[i] * ref_978[i] }
	ref_980 := make([]float64, len(ref_977))
	for i := range ref_980 { ref_980[i] = ref_977[i] + ref_979[i] }
	ref_981 := make([]float64, len(ref_980))
	for i := range ref_981 { ref_981[i] = ref_980[(i + 64 + len(ref_980)) % len(ref_980)] }
	ref_1452 := make([]float64, len(ref_974))
	for i := range ref_1452 { ref_1452[i] = ref_974[i] + ref_981[i] }
	ref_984 := make([]float64, len(ref_915))
	for i := range ref_984 { ref_984[i] = ref_915[i] * ref_983[i] }
	ref_986 := make([]float64, len(ref_914))
	for i := range ref_986 { ref_986[i] = ref_914[i] * ref_985[i] }
	ref_987 := make([]float64, len(ref_984))
	for i := range ref_987 { ref_987[i] = ref_984[i] + ref_986[i] }
	ref_988 := make([]float64, len(ref_987))
	for i := range ref_988 { ref_988[i] = ref_987[(i + 72 + len(ref_987)) % len(ref_987)] }
	ref_991 := make([]float64, len(ref_919))
	for i := range ref_991 { ref_991[i] = ref_919[i] * ref_990[i] }
	ref_992 := make([]float64, len(ref_991))
	for i := range ref_992 { ref_992[i] = ref_991[(i + 80 + len(ref_991)) % len(ref_991)] }
	ref_1462 := make([]float64, len(ref_988))
	for i := range ref_1462 { ref_1462[i] = ref_988[i] + ref_992[i] }
	ref_995 := make([]float64, len(ref_921))
	for i := range ref_995 { ref_995[i] = ref_921[i] * ref_994[i] }
	ref_997 := make([]float64, len(ref_918))
	for i := range ref_997 { ref_997[i] = ref_918[i] * ref_996[i] }
	ref_998 := make([]float64, len(ref_995))
	for i := range ref_998 { ref_998[i] = ref_995[i] + ref_997[i] }
	ref_999 := make([]float64, len(ref_998))
	for i := range ref_999 { ref_999[i] = ref_998[(i + 88 + len(ref_998)) % len(ref_998)] }
	ref_1002 := make([]float64, len(ref_914))
	for i := range ref_1002 { ref_1002[i] = ref_914[i] * ref_1001[i] }
	ref_1003 := make([]float64, len(ref_1002))
	for i := range ref_1003 { ref_1003[i] = ref_1002[(i + 96 + len(ref_1002)) % len(ref_1002)] }
	ref_1476 := make([]float64, len(ref_999))
	for i := range ref_1476 { ref_1476[i] = ref_999[i] + ref_1003[i] }
	ref_1477 := make([]float64, len(ref_1462))
	for i := range ref_1477 { ref_1477[i] = ref_1462[i] + ref_1476[i] }
	ref_1475 := make([]float64, len(ref_1452))
	for i := range ref_1475 { ref_1475[i] = ref_1452[i] + ref_1477[i] }
	ref_1473 := make([]float64, len(ref_1470))
	for i := range ref_1473 { ref_1473[i] = ref_1470[i] + ref_1475[i] }
	ref_1005 := ref_1473
	ref_1006 := make([]float64, len(ref_1005))
	for i := range ref_1006 { ref_1006[i] = ref_1005[(i + 7 + len(ref_1005)) % len(ref_1005)] }
	ref_1014 := make([]float64, len(ref_1006))
	for i := range ref_1014 { ref_1014[i] = ref_1006[i] * ref_1013[i] }
	ref_1007 := make([]float64, len(ref_1005))
	for i := range ref_1007 { ref_1007[i] = ref_1005[(i + 6 + len(ref_1005)) % len(ref_1005)] }
	ref_1015 := make([]float64, len(ref_1007))
	for i := range ref_1015 { ref_1015[i] = ref_1007[i] * ref_1013[i] }
	ref_1016 := make([]float64, len(ref_1014))
	for i := range ref_1016 { ref_1016[i] = ref_1014[i] + ref_1015[i] }
	ref_1008 := make([]float64, len(ref_1005))
	for i := range ref_1008 { ref_1008[i] = ref_1005[(i + 5 + len(ref_1005)) % len(ref_1005)] }
	ref_1017 := make([]float64, len(ref_1008))
	for i := range ref_1017 { ref_1017[i] = ref_1008[i] * ref_1013[i] }
	ref_1009 := make([]float64, len(ref_1005))
	for i := range ref_1009 { ref_1009[i] = ref_1005[(i + 4 + len(ref_1005)) % len(ref_1005)] }
	ref_1019 := make([]float64, len(ref_1009))
	for i := range ref_1019 { ref_1019[i] = ref_1009[i] * ref_1013[i] }
	ref_1478 := make([]float64, len(ref_1017))
	for i := range ref_1478 { ref_1478[i] = ref_1017[i] + ref_1019[i] }
	ref_1490 := make([]float64, len(ref_1016))
	for i := range ref_1490 { ref_1490[i] = ref_1016[i] + ref_1478[i] }
	ref_1010 := make([]float64, len(ref_1005))
	for i := range ref_1010 { ref_1010[i] = ref_1005[(i + 3 + len(ref_1005)) % len(ref_1005)] }
	ref_1021 := make([]float64, len(ref_1010))
	for i := range ref_1021 { ref_1021[i] = ref_1010[i] * ref_1013[i] }
	ref_1011 := make([]float64, len(ref_1005))
	for i := range ref_1011 { ref_1011[i] = ref_1005[(i + 2 + len(ref_1005)) % len(ref_1005)] }
	ref_1023 := make([]float64, len(ref_1011))
	for i := range ref_1023 { ref_1023[i] = ref_1011[i] * ref_1013[i] }
	ref_1484 := make([]float64, len(ref_1021))
	for i := range ref_1484 { ref_1484[i] = ref_1021[i] + ref_1023[i] }
	ref_1012 := make([]float64, len(ref_1005))
	for i := range ref_1012 { ref_1012[i] = ref_1005[(i + 1 + len(ref_1005)) % len(ref_1005)] }
	ref_1025 := make([]float64, len(ref_1012))
	for i := range ref_1025 { ref_1025[i] = ref_1012[i] * ref_1013[i] }
	ref_1027 := make([]float64, len(ref_1005))
	for i := range ref_1027 { ref_1027[i] = ref_1005[i] * ref_1013[i] }
	ref_1494 := make([]float64, len(ref_1025))
	for i := range ref_1494 { ref_1494[i] = ref_1025[i] + ref_1027[i] }
	ref_1495 := make([]float64, len(ref_1484))
	for i := range ref_1495 { ref_1495[i] = ref_1484[i] + ref_1494[i] }
	ref_1493 := make([]float64, len(ref_1490))
	for i := range ref_1493 { ref_1493[i] = ref_1490[i] + ref_1495[i] }
	ref_1030 := make([]float64, len(ref_1009))
	for i := range ref_1030 { ref_1030[i] = ref_1009[i] * ref_1029[i] }
	ref_1031 := make([]float64, len(ref_1010))
	for i := range ref_1031 { ref_1031[i] = ref_1010[i] * ref_1029[i] }
	ref_1032 := make([]float64, len(ref_1030))
	for i := range ref_1032 { ref_1032[i] = ref_1030[i] + ref_1031[i] }
	ref_1033 := make([]float64, len(ref_1011))
	for i := range ref_1033 { ref_1033[i] = ref_1011[i] * ref_1029[i] }
	ref_1035 := make([]float64, len(ref_1012))
	for i := range ref_1035 { ref_1035[i] = ref_1012[i] * ref_1029[i] }
	ref_1496 := make([]float64, len(ref_1033))
	for i := range ref_1496 { ref_1496[i] = ref_1033[i] + ref_1035[i] }
	ref_1508 := make([]float64, len(ref_1032))
	for i := range ref_1508 { ref_1508[i] = ref_1032[i] + ref_1496[i] }
	ref_1037 := make([]float64, len(ref_1005))
	for i := range ref_1037 { ref_1037[i] = ref_1005[i] * ref_1029[i] }
	ref_1039 := make([]float64, len(ref_1008))
	for i := range ref_1039 { ref_1039[i] = ref_1008[i] * ref_1029[i] }
	ref_1502 := make([]float64, len(ref_1037))
	for i := range ref_1502 { ref_1502[i] = ref_1037[i] + ref_1039[i] }
	ref_1041 := make([]float64, len(ref_1007))
	for i := range ref_1041 { ref_1041[i] = ref_1007[i] * ref_1029[i] }
	ref_1043 := make([]float64, len(ref_1006))
	for i := range ref_1043 { ref_1043[i] = ref_1006[i] * ref_1029[i] }
	ref_1512 := make([]float64, len(ref_1041))
	for i := range ref_1512 { ref_1512[i] = ref_1041[i] + ref_1043[i] }
	ref_1513 := make([]float64, len(ref_1502))
	for i := range ref_1513 { ref_1513[i] = ref_1502[i] + ref_1512[i] }
	ref_1511 := make([]float64, len(ref_1508))
	for i := range ref_1511 { ref_1511[i] = ref_1508[i] + ref_1513[i] }
	ref_1045 := make([]float64, len(ref_1511))
	for i := range ref_1045 { ref_1045[i] = ref_1511[(i + 8 + len(ref_1511)) % len(ref_1511)] }
	ref_1046 := make([]float64, len(ref_1493))
	for i := range ref_1046 { ref_1046[i] = ref_1493[i] + ref_1045[i] }
	ref_1048 := make([]float64, len(ref_1005))
	for i := range ref_1048 { ref_1048[i] = ref_1005[i] * ref_1047[i] }
	ref_1049 := make([]float64, len(ref_1012))
	for i := range ref_1049 { ref_1049[i] = ref_1012[i] * ref_1047[i] }
	ref_1050 := make([]float64, len(ref_1048))
	for i := range ref_1050 { ref_1050[i] = ref_1048[i] + ref_1049[i] }
	ref_1051 := make([]float64, len(ref_1009))
	for i := range ref_1051 { ref_1051[i] = ref_1009[i] * ref_1047[i] }
	ref_1053 := make([]float64, len(ref_1008))
	for i := range ref_1053 { ref_1053[i] = ref_1008[i] * ref_1047[i] }
	ref_1514 := make([]float64, len(ref_1051))
	for i := range ref_1514 { ref_1514[i] = ref_1051[i] + ref_1053[i] }
	ref_1526 := make([]float64, len(ref_1050))
	for i := range ref_1526 { ref_1526[i] = ref_1050[i] + ref_1514[i] }
	ref_1055 := make([]float64, len(ref_1007))
	for i := range ref_1055 { ref_1055[i] = ref_1007[i] * ref_1047[i] }
	ref_1057 := make([]float64, len(ref_1011))
	for i := range ref_1057 { ref_1057[i] = ref_1011[i] * ref_1047[i] }
	ref_1520 := make([]float64, len(ref_1055))
	for i := range ref_1520 { ref_1520[i] = ref_1055[i] + ref_1057[i] }
	ref_1059 := make([]float64, len(ref_1006))
	for i := range ref_1059 { ref_1059[i] = ref_1006[i] * ref_1047[i] }
	ref_1061 := make([]float64, len(ref_1010))
	for i := range ref_1061 { ref_1061[i] = ref_1010[i] * ref_1047[i] }
	ref_1530 := make([]float64, len(ref_1059))
	for i := range ref_1530 { ref_1530[i] = ref_1059[i] + ref_1061[i] }
	ref_1531 := make([]float64, len(ref_1520))
	for i := range ref_1531 { ref_1531[i] = ref_1520[i] + ref_1530[i] }
	ref_1529 := make([]float64, len(ref_1526))
	for i := range ref_1529 { ref_1529[i] = ref_1526[i] + ref_1531[i] }
	ref_1063 := make([]float64, len(ref_1529))
	for i := range ref_1063 { ref_1063[i] = ref_1529[(i + 16 + len(ref_1529)) % len(ref_1529)] }
	ref_1066 := make([]float64, len(ref_1005))
	for i := range ref_1066 { ref_1066[i] = ref_1005[i] * ref_1065[i] }
	ref_1068 := make([]float64, len(ref_1012))
	for i := range ref_1068 { ref_1068[i] = ref_1012[i] * ref_1067[i] }
	ref_1069 := make([]float64, len(ref_1066))
	for i := range ref_1069 { ref_1069[i] = ref_1066[i] + ref_1068[i] }
	ref_1071 := make([]float64, len(ref_1011))
	for i := range ref_1071 { ref_1071[i] = ref_1011[i] * ref_1070[i] }
	ref_1072 := make([]float64, len(ref_1069))
	for i := range ref_1072 { ref_1072[i] = ref_1069[i] + ref_1071[i] }
	ref_1073 := make([]float64, len(ref_1072))
	for i := range ref_1073 { ref_1073[i] = ref_1072[(i + 24 + len(ref_1072)) % len(ref_1072)] }
	ref_1532 := make([]float64, len(ref_1063))
	for i := range ref_1532 { ref_1532[i] = ref_1063[i] + ref_1073[i] }
	ref_1076 := make([]float64, len(ref_1008))
	for i := range ref_1076 { ref_1076[i] = ref_1008[i] * ref_1075[i] }
	ref_1078 := make([]float64, len(ref_1007))
	for i := range ref_1078 { ref_1078[i] = ref_1007[i] * ref_1077[i] }
	ref_1079 := make([]float64, len(ref_1076))
	for i := range ref_1079 { ref_1079[i] = ref_1076[i] + ref_1078[i] }
	ref_1081 := make([]float64, len(ref_1006))
	for i := range ref_1081 { ref_1081[i] = ref_1006[i] * ref_1080[i] }
	ref_1082 := make([]float64, len(ref_1079))
	for i := range ref_1082 { ref_1082[i] = ref_1079[i] + ref_1081[i] }
	ref_1083 := make([]float64, len(ref_1082))
	for i := range ref_1083 { ref_1083[i] = ref_1082[(i + 248 + len(ref_1082)) % len(ref_1082)] }
	ref_1534 := make([]float64, len(ref_1532))
	for i := range ref_1534 { ref_1534[i] = ref_1532[i] + ref_1083[i] }
	ref_1535 := make([]float64, len(ref_1046))
	for i := range ref_1535 { ref_1535[i] = ref_1046[i] + ref_1534[i] }
	ref_1085 := ref_1535
	ref_1086 := make([]float64, len(ref_1085))
	for i := range ref_1086 { ref_1086[i] = ref_1085[i] * ref_1085[i] }
	ref_1087 := make([]float64, len(ref_1086))
	for i := range ref_1087 { ref_1087[i] = ref_1086[(i + 1 + len(ref_1086)) % len(ref_1086)] }
	ref_1095 := make([]float64, len(ref_1087))
	for i := range ref_1095 { ref_1095[i] = ref_1087[i] * ref_1094[i] }
	ref_1088 := make([]float64, len(ref_1086))
	for i := range ref_1088 { ref_1088[i] = ref_1086[(i + 3 + len(ref_1086)) % len(ref_1086)] }
	ref_1097 := make([]float64, len(ref_1088))
	for i := range ref_1097 { ref_1097[i] = ref_1088[i] * ref_1096[i] }
	ref_1098 := make([]float64, len(ref_1095))
	for i := range ref_1098 { ref_1098[i] = ref_1095[i] + ref_1097[i] }
	ref_1089 := make([]float64, len(ref_1086))
	for i := range ref_1089 { ref_1089[i] = ref_1086[(i + 2 + len(ref_1086)) % len(ref_1086)] }
	ref_1560 := make([]float64, len(ref_1089))
	for i := range ref_1560 { ref_1560[i] = ref_1089[i] * ref_576[i] }
	ref_1102 := make([]float64, len(ref_1086))
	for i := range ref_1102 { ref_1102[i] = ref_1086[i] * ref_1101[i] }
	ref_1536 := make([]float64, len(ref_1560))
	for i := range ref_1536 { ref_1536[i] = ref_1560[i] + ref_1102[i] }
	ref_1090 := make([]float64, len(ref_1086))
	for i := range ref_1090 { ref_1090[i] = ref_1086[(i + 7 + len(ref_1086)) % len(ref_1086)] }
	ref_1105 := make([]float64, len(ref_1090))
	for i := range ref_1105 { ref_1105[i] = ref_1090[i] * ref_1104[i] }
	ref_1106 := make([]float64, len(ref_1105))
	for i := range ref_1106 { ref_1106[i] = ref_1105[(i + 240 + len(ref_1105)) % len(ref_1105)] }
	ref_1538 := make([]float64, len(ref_1536))
	for i := range ref_1538 { ref_1538[i] = ref_1536[i] + ref_1106[i] }
	ref_1539 := make([]float64, len(ref_1098))
	for i := range ref_1539 { ref_1539[i] = ref_1098[i] + ref_1538[i] }
	ref_1091 := make([]float64, len(ref_1086))
	for i := range ref_1091 { ref_1091[i] = ref_1086[(i + 4 + len(ref_1086)) % len(ref_1086)] }
	ref_1109 := make([]float64, len(ref_1091))
	for i := range ref_1109 { ref_1109[i] = ref_1091[i] * ref_1108[i] }
	ref_1111 := make([]float64, len(ref_1088))
	for i := range ref_1111 { ref_1111[i] = ref_1088[i] * ref_1110[i] }
	ref_1112 := make([]float64, len(ref_1109))
	for i := range ref_1112 { ref_1112[i] = ref_1109[i] + ref_1111[i] }
	ref_1092 := make([]float64, len(ref_1086))
	for i := range ref_1092 { ref_1092[i] = ref_1086[(i + 5 + len(ref_1086)) % len(ref_1086)] }
	ref_1114 := make([]float64, len(ref_1092))
	for i := range ref_1114 { ref_1114[i] = ref_1092[i] * ref_1113[i] }
	ref_1117 := make([]float64, len(ref_1090))
	for i := range ref_1117 { ref_1117[i] = ref_1090[i] * ref_1116[i] }
	ref_1540 := make([]float64, len(ref_1114))
	for i := range ref_1540 { ref_1540[i] = ref_1114[i] + ref_1117[i] }
	ref_1552 := make([]float64, len(ref_1112))
	for i := range ref_1552 { ref_1552[i] = ref_1112[i] + ref_1540[i] }
	ref_1093 := make([]float64, len(ref_1086))
	for i := range ref_1093 { ref_1093[i] = ref_1086[(i + 6 + len(ref_1086)) % len(ref_1086)] }
	ref_1120 := make([]float64, len(ref_1093))
	for i := range ref_1120 { ref_1120[i] = ref_1093[i] * ref_1119[i] }
	ref_1561 := make([]float64, len(ref_1086))
	for i := range ref_1561 { ref_1561[i] = ref_1086[i] * ref_576[i] }
	ref_1546 := make([]float64, len(ref_1120))
	for i := range ref_1546 { ref_1546[i] = ref_1120[i] + ref_1561[i] }
	ref_1125 := make([]float64, len(ref_1089))
	for i := range ref_1125 { ref_1125[i] = ref_1089[i] * ref_1124[i] }
	ref_1128 := make([]float64, len(ref_1087))
	for i := range ref_1128 { ref_1128[i] = ref_1087[i] * ref_1127[i] }
	ref_1556 := make([]float64, len(ref_1125))
	for i := range ref_1556 { ref_1556[i] = ref_1125[i] + ref_1128[i] }
	ref_1557 := make([]float64, len(ref_1546))
	for i := range ref_1557 { ref_1557[i] = ref_1546[i] + ref_1556[i] }
	ref_1555 := make([]float64, len(ref_1552))
	for i := range ref_1555 { ref_1555[i] = ref_1552[i] + ref_1557[i] }
	ref_1130 := make([]float64, len(ref_1555))
	for i := range ref_1130 { ref_1130[i] = ref_1555[(i + 248 + len(ref_1555)) % len(ref_1555)] }
	ref_1131 := make([]float64, len(ref_1539))
	for i := range ref_1131 { ref_1131[i] = ref_1539[i] + ref_1130[i] }
	ref_1132 := ref_1131
	expectedOutputs := make(map[string][]float64)
	expectedOutputs["classification"] = ref_1132
	precisionChecked = true

	init_constants(params, encoder)
	computeStart := time.Now()
	for i := 0; i < *repetitions; i++ {
			tensor_cryptonets(encryptedInputs, encodedInputs, encryptedOutputs, encodedOutputs, encoder, enc, eval, params)
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
