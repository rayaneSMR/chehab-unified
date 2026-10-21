import sys
import os
import argparse

# Support framework flag (--framework constrained/morl/unified/baseline)
PYTRS_FRAMEWORK = {
    "constrained": "constrained",
    "morl": "morl",
    "unified": "constrained",
    "baseline": "constrained",
    "original": "baseline",
}
framework_parser = argparse.ArgumentParser(add_help=False)
framework_parser.add_argument(
    "--framework",
    choices=["constrained", "morl", "unified", "baseline", "original"],
    default="unified",
    help="Framework to use (default: unified). Put it BEFORE the sub-command.",
)
args, _ = framework_parser.parse_known_args()
try:
    import pytrs.config
    pytrs.config.framework = PYTRS_FRAMEWORK.get(args.framework, "constrained")
except ImportError:
    pass

from .run import run_agent
from .train import train_agent
from .train_mo import train_agent_mo
from .test import test_agent, test_agent_v2
from .utils import load_embeddings_from_config
from .TRAE_bpe import BPETokenizer  # Import for pickle compatibility
from .morl import run_interactive, add_subparser
from .config import (
    get_model_path,
    get_tokenizer_type,
    print_config,
    set_framework,
    get_framework_spec,
    set_embeddings_model_type,
)
from .baseline.run_baseline import run_agent as run_agent_baseline


def parse_arguments(args=None):
    """Parse command line arguments"""
    global framework_parser
    parser = argparse.ArgumentParser(
        description="FHE RL Agent", parents=[framework_parser]
    )

    # Add tokenizer type argument
    parser.add_argument(
        "--tokenizer_type",
        choices=["dynamic", "bpe"],
        default=get_tokenizer_type(),
        help="Tokenizer type to use (default: from config)",
    )

    # Embedder selection
    parser.add_argument(
        "--embedder",
        type=str,
        choices=["gnn", "trae"],
        default="gnn",
        help="Embedder architecture to use: 'gnn' (Graph2Seq GNN AE, default) or 'trae' (Transformer Autoencoder)",
    )

    # Add config flag
    parser.add_argument(
        "--show_config", action="store_true", help="Show current configuration and exit"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="mode", help="Available commands")

    # ─── TRAIN COMMAND ────────────────────────────────────────────────────────
    train_parser = subparsers.add_parser("train", help="Train the agent")
    train_parser.add_argument(
        "--constraint",
        type=str,
        default="mem",
        choices=["mem", "noise"],
        help="Constraint metric to enforce: 'mem' (Process Peak RAM in MB, default) or 'noise' (multiplicative depth/noise bits)",
    )
    train_parser.add_argument(
        "--budgets",
        type=str,
        default=None,
        help="Comma-separated list of budgets (e.g., '1500,2000,2600,1000000' for mem, '230,236,369,9000000' for noise)",
    )
    train_parser.add_argument(
        "--timesteps",
        type=int,
        default=2_000_000,
        help="Total training timesteps (default: 2000000)",
    )
    train_parser.add_argument(
        "--total_timesteps",
        type=int,
        default=None,
        help="Alias for --timesteps",
    )
    train_parser.add_argument(
        "--dataset",
        type=str,
        default="./fhe_rl/datasets/final_llm_dataset.txt",
        help="Path to the dataset file",
    )
    train_parser.add_argument(
        "--eval_freq",
        type=int,
        default=10000,
        help="Evaluation frequency (default: 10000)",
    )
    train_parser.add_argument(
        "--num_envs",
        type=int,
        default=8,
        help="Number of parallel environments (default: 8)",
    )
    train_parser.add_argument(
        "--n_envs",
        type=int,
        default=None,
        help="Alias for --num_envs",
    )
    train_parser.add_argument(
        "--denom_factor",
        type=int,
        default=4,
        help="Lagrangian update frequency denominator (default: 4)",
    )
    train_parser.add_argument(
        "--method",
        type=str,
        default="nato_sc",
        choices=[
            "none",
            "lagrangian_od_ov",
            "lagrangian_perstep",
            "lagrangian_always_done",
            "margin_barrier",
            "noise_masking",
            "nato_sc",
            "lagrangian_pid",
            "lagrangian_pid_nato",
        ],
        help="Constraint enforcement method (default: nato_sc)",
    )
    train_parser.add_argument(
        "--algo",
        type=str,
        default="lagrangian_pid",
        choices=["ppo", "focops", "lagrangian_pid"],
        help="RL algorithm (default: lagrangian_pid)",
    )
    train_parser.add_argument(
        "--budget_encoding",
        type=str,
        default="film",
        choices=["raw", "embed", "film"],
        help="Budget encoding in policy (default: film)",
    )
    train_parser.add_argument(
        "--policy_variant",
        type=str,
        default="film_a",
        choices=["film_a", "film_b"],
        help="FiLM policy conditioning variant: film_a (budget only) or film_b (budget + preference fused)",
    )
    train_parser.add_argument(
        "--ent_coef",
        type=float,
        default=0.01,
        help="Entropy coefficient for exploration (default: 0.01)",
    )
    train_parser.add_argument(
        "--curriculum",
        action="store_true",
        default=False,
        help="Enable curriculum budget scheduling",
    )
    train_parser.add_argument(
        "--n_cycle",
        type=int,
        default=1,
        help="Biased-preference cycle length. 0 for always random. (default: 1)",
    )
    train_parser.add_argument(
        "--n_budget",
        type=int,
        default=5,
        help="Fixed normalization budget for rotation keys (default: 5)",
    )
    train_parser.add_argument(
        "--lambda_env",
        type=float,
        default=0.0,
        help="Pareto-envelope bonus weight (default: 0.0)",
    )
    train_parser.add_argument(
        "--lambda_kl",
        type=float,
        default=0.0,
        help="KL-divergence bonus weight (default: 0.0)",
    )
    train_parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to specific checkpoint .zip to resume from",
    )
    train_parser.add_argument(
        "--fresh_start",
        action="store_true",
        default=False,
        help="Start fresh training from step 0 (ignores existing checkpoints; default is auto-resume)",
    )
    train_parser.add_argument(
        "--n_pref",
        type=int,
        default=11,
        help="Number of preference points (default: 11 for 10 vectors; 9 for 8 vectors, dropping the 2 least important extreme-keys vectors)",
    )
    train_parser.add_argument(
        "--embedder",
        type=str,
        choices=["gnn", "trae"],
        default="gnn",
        help="Embedder architecture to use (default: gnn)",
    )

    # ─── TEST COMMAND ─────────────────────────────────────────────────────────
    test_parser = subparsers.add_parser("test", help="Test the agent")
    test_parser.add_argument(
        "--model", type=str, default=None, help="Path to trained model .zip file"
    )
    test_parser.add_argument(
        "--constraint",
        type=str,
        default="mem",
        choices=["mem", "noise"],
        help="Constraint metric to test on: 'mem' (default) or 'noise'",
    )
    test_parser.add_argument(
        "--budgets", type=str, default=None, help="Comma-separated budgets to TEST on"
    )
    test_parser.add_argument(
        "--train_budgets",
        type=str,
        default=None,
        help="Comma-separated budgets the model was TRAINED on",
    )
    test_parser.add_argument(
        "--method",
        type=str,
        default="nato_sc",
        choices=[
            "none",
            "lagrangian_od_ov",
            "lagrangian_perstep",
            "lagrangian_always_done",
            "margin_barrier",
            "noise_masking",
            "nato_sc",
            "lagrangian_pid",
            "lagrangian_pid_nato",
        ],
        help="Constraint method",
    )
    dataset_group = test_parser.add_mutually_exclusive_group()
    dataset_group.add_argument(
        "--dataset",
        type=str,
        default="./fhe_rl/datasets/benchmarks.txt",
        help="Path to evaluation dataset",
    )
    dataset_group.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="DNN tensor-graph benchmark name (e.g., resnet20_relu). The C++ runner serializes "
             "the graph to an S-expression automatically; no hand-written expression needed.",
    )
    test_parser.add_argument(
        "--budget_encoding",
        type=str,
        default="film",
        choices=["raw", "embed", "film"],
        help="Budget encoding in policy (default: film)",
    )
    test_parser.add_argument(
        "--policy_variant",
        type=str,
        default="film_a",
        choices=["film_a", "film_b"],
        help="FiLM variant used during training",
    )
    test_parser.add_argument(
        "--deterministic",
        action="store_true",
        default=True,
        help="Use deterministic actions",
    )
    test_parser.add_argument(
        "--output_dir",
        type=str,
        default="./test_results",
        help="Output directory for results",
    )
    test_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for output Excel file",
    )
    test_parser.add_argument(
        "--v2", action="store_true", default=False, help="Use test_agent_v2"
    )

    # ─── RUN COMMAND ──────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser("run", help="Run the agent on a single input file")
    run_parser.add_argument(
        "pos_input_file",
        nargs="?",
        default=None,
        help="Input file with expressions (positional)",
    )
    run_parser.add_argument(
        "pos_output_file",
        nargs="?",
        default=None,
        help="Output file for rewritten expressions (positional)",
    )
    run_parser.add_argument(
        "--input_file",
        type=str,
        default=None,
        help="Input file with expressions",
    )
    run_parser.add_argument(
        "--output_file",
        type=str,
        default=None,
        help="Output file for rewritten expressions",
    )
    run_parser.add_argument(
        "--w_ops",
        type=float,
        default=None,
        help="Weight for operations in MORL",
    )

    # ─── INTERACTIVE COMMAND ──────────────────────────────────────────────────
    add_subparser(subparsers)

    return parser.parse_args(args)


def main(args=None):
    parsed_args = parse_arguments(args)

    if parsed_args.show_config:
        print_config()
        return

    mode = parsed_args.mode
    if not mode:
        print("Please specify a command: train, test, run, or interactive")
        print("Use --help for more information")
        return

    framework_name = getattr(parsed_args, "framework", "unified")
    if framework_name == "original":
        framework_name = "baseline"
    set_framework(framework_name)
    spec = get_framework_spec()

    # Embedder selection & propagation (GNN only for unified; keep original for morl/constrained)
    if framework_name == "unified":
        embedder_choice = getattr(parsed_args, "embedder", "gnn")
        set_embeddings_model_type(embedder_choice)
    else:
        embedder_choice = "trae"
        set_embeddings_model_type(embedder_choice)

    # ─────────────────────────────── TRAIN ────────────────────────────
    if mode == "train":
        embeddings, tokenizer = load_embeddings_from_config(parsed_args.tokenizer_type, embedder_type=embedder_choice)
        emb_cls = type(embeddings).__name__ if embeddings is not None else "None"
        emb_path = get_model_path("gnn_embeddings_model" if embedder_choice == "gnn" else "dynamic_embeddings_model")
        emb_sz = os.path.getsize(emb_path) if os.path.exists(emb_path) else 0
        print(f"=== Embedder Selection ({framework_name.upper()}): {embedder_choice.upper()} ===")
        print(f"  Class:        {emb_cls}")
        print(f"  Output Dim:   256")
        print(f"  Weights File: {emb_path} ({emb_sz / (1024*1024):.2f} MB)")

        # Parse budgets with smart defaults based on constraint metric
        budget_options = None
        if parsed_args.budgets:
            budget_options = [int(b.strip()) for b in parsed_args.budgets.split(",")]
            print(f"Using custom budgets: {budget_options}")
        else:
            if parsed_args.constraint == "mem":
                budget_options = [1500, 2000, 2600, 1_000_000]
            else:
                budget_options = [230, 236, 369, 9_000_000]
            print(f"Using default {parsed_args.constraint.upper()} budgets: {budget_options}")

        total_timesteps = (
            parsed_args.total_timesteps
            if parsed_args.total_timesteps is not None
            else parsed_args.timesteps
        )
        num_envs = (
            parsed_args.n_envs
            if parsed_args.n_envs is not None
            else parsed_args.num_envs
        )

        if framework_name == "morl":
            train_agent_mo(
                parsed_args.dataset,
                embeddings,
                total_timesteps=total_timesteps,
                num_envs=num_envs,
                ent_coef=parsed_args.ent_coef,
                n_cycle=parsed_args.n_cycle,
                n_budget=parsed_args.n_budget,
                lambda_env=parsed_args.lambda_env,
                lambda_kl=parsed_args.lambda_kl,
                eval_freq=parsed_args.eval_freq,
                budget_options=budget_options,
                constraint_method=parsed_args.method,
                algo=parsed_args.algo,
                checkpoint_path=parsed_args.checkpoint,
                fresh_start=parsed_args.fresh_start,
                n_pref=parsed_args.n_pref,
            )
        else:
            # Unified & Constrained frameworks
            train_agent(
                parsed_args.dataset,
                embeddings,
                total_timesteps=total_timesteps,
                num_envs=num_envs,
                budget_options=budget_options,
                constraint_method=parsed_args.method,
                constraint_metric=parsed_args.constraint,
                budget_encoding=parsed_args.budget_encoding,
                ent_coef=parsed_args.ent_coef,
                algo=parsed_args.algo,
                n_cycle=parsed_args.n_cycle,
                n_budget=parsed_args.n_budget,
                lambda_env=parsed_args.lambda_env,
                lambda_kl=parsed_args.lambda_kl,
                policy_variant=parsed_args.policy_variant,
                pref_mode=spec["pref_mode"],
                denom_factor=parsed_args.denom_factor,
                curriculum=parsed_args.curriculum,
                eval_freq=parsed_args.eval_freq,
                checkpoint_path=parsed_args.checkpoint,
                fresh_start=parsed_args.fresh_start,
                n_pref=parsed_args.n_pref,
            )

    # ─────────────────────────────── TEST ─────────────────────────────
    elif mode == "test":
        if framework_name == "morl":
            print("The 'test' command supports --framework constrained or unified.")
            sys.exit(1)
        embeddings, tokenizer = load_embeddings_from_config(parsed_args.tokenizer_type, embedder_type=embedder_choice)

        agent_zip = (
            parsed_args.model
            if parsed_args.model
            else get_model_path(spec.get("model_key", "agent_model"))
        )

        test_budgets = None
        if parsed_args.budgets:
            test_budgets = [int(b.strip()) for b in parsed_args.budgets.split(",")]

        train_budgets = None
        if parsed_args.train_budgets:
            train_budgets = [int(b.strip()) for b in parsed_args.train_budgets.split(",")]

        expressions_file = parsed_args.benchmark or parsed_args.dataset
        out_file = getattr(parsed_args, "output", None)
        if not out_file and getattr(parsed_args, "output_dir", None):
            import os
            os.makedirs(parsed_args.output_dir, exist_ok=True)
            model_name = os.path.basename(agent_zip).replace(".zip", "")
            out_file = os.path.join(parsed_args.output_dir, f"test_results_{model_name}.xlsx")

        if parsed_args.v2:
            test_agent_v2(
                expressions_file,
                embeddings,
                agent_zip,
                output_file=out_file,
                test_budgets=test_budgets,
                budget_options=train_budgets,
                constraint_method=parsed_args.method,
            )
        else:
            test_agent(
                expressions_file,
                embeddings,
                agent_zip,
                output_file=out_file,
                test_budgets=test_budgets,
                budget_options=train_budgets,
                constraint_method=parsed_args.method,
            )

    # ─────────────────────────────── RUN ──────────────────────────────
    elif mode == "run":
        embeddings, tokenizer = load_embeddings_from_config(parsed_args.tokenizer_type, embedder_type=embedder_choice)
        input_file = parsed_args.pos_input_file or parsed_args.input_file or "fhe_io_example.txt"
        output_file = parsed_args.pos_output_file or parsed_args.output_file or "fhe_out.txt"

        if framework_name == "baseline":
            agent_zip = get_model_path("agent_model")
            run_agent_baseline(input_file, embeddings, agent_zip, output_file)
        else:
            agent_zip = get_model_path("agent_model")
            run_agent(input_file, embeddings, agent_zip, output_file, noise_budget=1500)

    elif mode == "interactive":
        run_interactive(mode=getattr(parsed_args, "interactive_mode", None))


if __name__ == "__main__":
    main()
