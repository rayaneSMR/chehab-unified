import sys
import os

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'RL'))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from pytrs.peak_ram import PeakRAMEstimate, estimate_peak_ram, FHEParams
from pytrs.expr import Var, Op, Const
import unittest

class TestPeakRAMDFSOrder(unittest.TestCase):
    def test_dfs_order(self):
        # A tree where left-to-right and right-to-left evaluation order gives different peak liveness.
        # e.g., (A + B) * (C + (D * E))
        # Left-to-right:
        # A, B -> A+B (1 live)
        # C -> A+B, C (2 live)
        # D, E -> A+B, C, D, E -> D*E (4 live peak?)
        
        # Let's create an asymmetrical tree:
        # T1 = Op("+", [Var("v1"), Var("v2")])
        # T2 = Op("+", [Var("v3"), Op("+", [Var("v4"), Var("v5")])])
        # Root = Op("*", [T1, T2])
        
        # If we go left-to-right: 
        # v1, v2 -> T1 (live: T1) -> peak 2
        # v3, v4, v5 -> T2 (live: T1, v3, v4, v5) -> peak 4
        # T1, T2 -> Root
        
        # We can just verify it matches the C++ topological sort which goes left-to-right.
        # Actually, let's just make sure it runs and doesn't crash, and maybe hardcode the expected slots for a known tree.
        a, b, c, d, e = Var("a"), Var("b"), Var("c"), Var("d"), Var("e")
        t1 = Op("+", [a, b])
        t2 = Op("+", [c, Op("+", [d, e])])
        root = Op("*", [t1, t2])
        
        p = FHEParams()
        est = estimate_peak_ram(root, p, keys_threshold=9999)
        # Left-to-right peak:
        # load a (live=1), load b (live=2), t1=a+b (live=1)
        # load c (live=2)
        # load d (live=3), load e (live=4), d+e (live=3)
        # c+(d+e) (live=2)
        # t1*t2 (live=1)
        # Peak should be 4.
        self.assertEqual(est.slots_fixed, 4)

if __name__ == '__main__':
    unittest.main()
