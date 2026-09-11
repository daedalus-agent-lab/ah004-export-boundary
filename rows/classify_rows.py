#!/usr/bin/env python3
"""Which of the published A/R agreement rows could have separated the two rules at all?

The published table (#31676) reports, for each workload, how many requests the additive rule (A) and the
product gate (R) admitted. Where they agree, the text calls the row "the same accepted request IDs".
Agreement on a row is only evidence about the rules if the row could have disagreed; some rows cannot,
by arithmetic, whatever the implementations do.

With cap = beta, two regions are forced, using 1 - prod(1-b_i) <= sum(b_i) (union bound):

  sum(b) <= beta                -> product risk <= sum(b) <= beta: the product form MUST admit every set
                                   the additive form admits. No row here can separate them.
  sum(b) > -ln(1-beta)          -> the product form must refuse; and since -ln(1-beta) > beta, so must the
                                   additive form. No row here can separate them either.

Only the window beta < sum(b) <= -ln(1-beta) can separate, and at beta = 1/10 it is 0.00536052 wide —
5.36% of the additive cap. A workload measures a difference between the rules only if its accepted set
lands inside that window. Everything else is an identity, and should be reported as one.

Usage: python3 classify_rows.py
"""
from fractions import Fraction as F
from math import log

BETA = F(1, 10)
CAP = BETA
WINDOW_LO = float(BETA)
WINDOW_HI = -log(1 - float(BETA))

# published in #31676 section 1: (name, bounds as listed, published A, published R, published W)
ROWS = [
    ("10 x .01",                 [F(1, 100)] * 10,                        10, 10, 10),
    ("11 x .01",                 [F(1, 100)] * 11,                        10, 10, 10),
    ("30 x .002",                [F(2, 1000)] * 30,                       30, 30, 30),
    ("10 x .04",                 [F(4, 100)] * 10,                         2,  2,  2),
    ("20 alternating .002/.04",  [F(2, 1000), F(4, 100)] * 10,             12, 12,  2),
    ("10 aborting .01 + work",   [F(1, 100)] * 11,                         0,  0,  0),
    ("peer 10 x .02",            [F(2, 100)] * 10,                         5,  5,  5),
    ("peer 3 x .1",              [F(1, 10)] * 3,                           1,  1,  1),
    ("2 x .051",                 [F(51, 1000)] * 2,                        1,  2,  2),
    ("[.051,.051] + 24 x .002",  [F(51, 1000)] * 2 + [F(2, 1000)] * 24,   25,  2,  2),
    ("24 x .002 + [.051,.051]",  [F(2, 1000)] * 24 + [F(51, 1000)] * 2,   25, 25,  2),
]


def admit(bounds, rule):
    """Both rules in their published meaning, in the order given, no reordering."""
    spent = F(0)
    keep = F(1)
    n = 0
    for b in bounds:
        if rule == "A":
            if spent + b <= CAP:
                spent += b
                n += 1
        else:
            if keep * (1 - b) >= 1 - BETA:
                keep *= (1 - b)
                n += 1
    return n


def ssum(bounds, n):
    return sum(bounds[:n], F(0))


def classify(bounds, a, r):
    """Did this row measure a difference, or was agreement forced? Only three answers are allowed."""
    if a != r:
        return f"SEPARATION: A={a}, R={r} — this row measures a difference"
    s = ssum(bounds, a)
    if float(s) <= WINDOW_LO:
        return "identity (low): accepted sum <= beta, so the product form MUST admit the same set"
    nxt = bounds[a] if a < len(bounds) else None
    if nxt is not None and float(s + nxt) > WINDOW_HI:
        return "identity (high): the next item is past -ln(1-beta), so both MUST refuse"
    return "NOT FORCED: agreement here is neither required nor a separation"


def main() -> int:
    print(f"cap = beta = {float(BETA):.6f}")
    print(f"separating window: ({WINDOW_LO:.6f}, {WINDOW_HI:.6f}]  width {WINDOW_HI-WINDOW_LO:.8f} "
          f"= {(WINDOW_HI-WINDOW_LO)/float(BETA)*100:.4f}% of the cap\n")
    print(f"{'row':26} {'pub A/R/W':>12} {'mine A/R':>10} {'match':>6}  classification")
    forced = separations = 0
    for name, bounds, pa, pr, pw in ROWS:
        a, r = admit(bounds, "A"), admit(bounds, "R")
        # the abort row's published figures are EFFECTS, not admissions: 10 accepted requests were
        # all aborted, so no effect was created. Comparing it with admissions would be a category error.
        aborts = name.startswith("10 aborting")
        match = "n/a" if aborts else ("yes" if (a, r) == (pa, pr) else f"NO({a}/{r})")
        why = "published figures are effects, not admissions" if aborts else classify(bounds, a, r)
        if not aborts:
            forced += why.startswith("identity")
            separations += why.startswith("SEPARATION")
        print(f"{name:26} {f'{pa}/{pr}/{pw}':>12} {f'{a}/{r}':>10} {match:>6}  {why}")

    print(f"\nof the {len(ROWS)-1} comparable rows: {forced} forced agreements, "
          f"{separations} measured separations")

    print("\nhow narrow the separating region is at beta=1/10:")
    print(f"  a single item CANNOT separate the rules: with one item the product risk IS its bound,")
    print(f"  so both forms admit iff b <= beta and both refuse iff b > beta.")
    for b in (F(1, 100), F(51, 1000), F(1, 10)):
        print(f"    b={float(b):<7.4f} A admits {admit([b],'A')}  R admits {admit([b],'R')}  -> same")
    for pair in ([F(51, 1000)] * 2, [F(52, 1000)] * 2, [F(1, 20)] * 2, [F(1, 10)] * 2):
        a, r = admit(pair, "A"), admit(pair, "R")
        s = float(sum(pair))
        print(f"    2 x {float(pair[0]):<5.3f} sum {s:.6f} in-window {WINDOW_LO < s <= WINDOW_HI}  "
              f"A admits {a}, R admits {r}  {'SEPARATES' if a != r else 'agrees'}")
    print(f"\n  so a row separates only if its accepted set sums into the {WINDOW_HI-WINDOW_LO:.8f}-wide")
    print(f"  window ({WINDOW_LO:.4f}, {WINDOW_HI:.8f}], and that takes at least two items.")
    print(f"  At .05 per item that is a workload with zero margin for anything else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
