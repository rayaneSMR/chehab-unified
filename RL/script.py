import pytrs

dataset_path = "fhe_rl/datasets/train_rotations.txt"

with open(dataset_path, "r") as f:
    for idx, line in enumerate(f):
        raw_line = line.strip()
        if not raw_line or raw_line.startswith("#"):
            continue

        # Extract only the S-expression content (up to the last closing parenthesis)
        if ")" in raw_line:
            expr_str = raw_line[: raw_line.rfind(")") + 1].strip()
        else:
            expr_str = raw_line

        try:
            parsed = pytrs.parse_sexpr(expr_str)
        except Exception as e:
            print(f"Failed on line {idx + 1}: {e}")
            print(f"Expression: {expr_str[:80]}...")
            break
    else:
        print("All expressions parsed successfully after stripping metadata tags!")