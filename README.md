# Mondrian Nouns

A noun is either an atom (an unsigned arbitrary-precision integer, a natural number) or a cell (a pair of nouns).  Nouns are acyclic binary trees in which all leafs are atoms.  Nouns are written with `[]` brackets, but rightward-branching cells may elide brackets (i.e., `[4 [0 1]]` == `[4 0 1]` but not `[[4 0] 1]`).

Mondrian is a package for drawing nouns as compact graphical representations.

Usage:

```sh
python3 mondrian.py "[4 0 1]"
mondrian.svg: 28x28px canvas, 3 leaves, depth 2, mode=compact, min-leaf=14.0
```

![](mondrian.svg)

