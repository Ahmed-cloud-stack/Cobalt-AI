#!/usr/bin/env python3
"""Read one numeric reward file for each control or sealed blind attempt."""
import argparse
from pathlib import Path
import sys

def reward_file(path):
    files = [path] if path.is_file() else list(path.rglob("reward.txt"))
    if len(files) != 1:
        raise ValueError(f"{path}: expected exactly one reward file")
    return files[0].resolve()

def reward(path):
    result = path.read_text().strip()
    if result not in {"0", "1"}:
        raise ValueError(f"{path}: expected binary reward")
    return int(result)

parser = argparse.ArgumentParser()
parser.add_argument("oracle", type=Path)
parser.add_argument("nop", type=Path)
parser.add_argument("blind", type=Path, nargs="*")
args = parser.parse_args()
try:
    if len(args.blind) not in (0, 5):
        raise ValueError("Supply all five distinct blind rewards or check controls alone")
    files = [reward_file(path) for path in [args.oracle, args.nop, *args.blind]]
    if len(set(files)) != len(files):
        raise ValueError("Reward paths must be distinct")
    oracle, nop, *blind = [reward(path) for path in files]
    print(f"Oracle {oracle}, NOP {nop}, blind {sum(blind)}/{len(blind)}" if blind else f"Oracle {oracle}, NOP {nop}")
    sys.exit(0 if (oracle, nop) == (1, 0) and sum(blind) <= 1 else 1)
except (ValueError, OSError) as error:
    sys.exit(str(error))
