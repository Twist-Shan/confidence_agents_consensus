# 本轮三道分歧题：完整题面与回答

范围：20 道 L2 扩样中的三道分歧题。回答均为独立初始回答，没有同伴信息或 confidence 干预。p_B 是模型报告的 B 正确概率，不是实验分配的展示分数。

统一题意：X1 至 X7 是布尔变量，下列 28 条前提必须同时成立。判断指定命题是否在所有满足前提的赋值中成立。三题均为 A=不蕴含，B=蕴含。符号 ¬ 表示非，∨ 表示或。

## v4

问题：这些前提是否蕴含 X1？

正确选项：A；独立回答序列：A, A, A, B, A, A。

```text
01. (X3 ∨ ¬X4 ∨ ¬X2)
02. (¬X5 ∨ X7 ∨ ¬X1)
03. (¬X2 ∨ X3 ∨ ¬X5)
04. (X1 ∨ X5 ∨ X3)
05. (X2 ∨ X5 ∨ X4)
06. (¬X3 ∨ X1 ∨ X5)
07. (¬X3 ∨ ¬X4 ∨ X1)
08. (X3 ∨ ¬X6 ∨ ¬X5)
09. (¬X3 ∨ X1 ∨ X7)
10. (X4 ∨ X7 ∨ ¬X3)
11. (X3 ∨ X5 ∨ ¬X4)
12. (X3 ∨ X5 ∨ X1)
13. (X3 ∨ ¬X4 ∨ X6)
14. (¬X2 ∨ ¬X4 ∨ ¬X3)
15. (X2 ∨ X3 ∨ ¬X5)
16. (¬X5 ∨ ¬X4 ∨ ¬X2)
17. (X2 ∨ X6 ∨ ¬X4)
18. (X3 ∨ X6 ∨ ¬X5)
19. (¬X5 ∨ ¬X7 ∨ ¬X1)
20. (X5 ∨ X2 ∨ X1)
21. (X2 ∨ X7 ∨ ¬X5)
22. (¬X2 ∨ X5 ∨ X3)
23. (X2 ∨ X6 ∨ X3)
24. (¬X3 ∨ ¬X2 ∨ X6)
25. (X3 ∨ X1 ∨ ¬X2)
26. (X3 ∨ X5 ∨ ¬X6)
27. (¬X1 ∨ X3 ∨ X2)
28. (¬X6 ∨ ¬X5 ∨ ¬X1)
```

### 精确核验

独立枚举 128 个赋值后，有 6 个满足全部前提。按 X1..X7 顺序：

```text
(1, 0, 1, 1, 0, 1, 0)
(0, 0, 1, 0, 1, 0, 1)
(1, 1, 1, 0, 0, 1, 1)
(1, 0, 1, 1, 0, 1, 1)
(0, 0, 1, 0, 1, 1, 1)
(0, 1, 1, 0, 1, 1, 1)
```

### 模型原始回答

| 次数 | 答案 | 是否正确 | p_B | 原始理由 |
|---|---|---|---|---|
| 1 | A | 对 | 0.01 | The assignment (X1,X2,X3,X4,X5,X6,X7)=(0,0,1,0,1,0,1) satisfies every premise, so X1 is not entailed. |
| 2 | A | 对 | 0.01 | The premises are satisfiable with X1 false, for example X1=0, X2=0, X3=1, X4=0, X5=1, X6=0, X7=1. |
| 3 | A | 对 | 0.01 | The premises are satisfiable with X1=false, for example X2=false, X3=true, X4=false, X5=true, X7=true, so they do not entail X1. |
| 4 | B | 错 | 0.99 | Assuming X1 is false forces X5=true, X7=false, X3=false, X2=false, and X6=true, which violates the eighth premise. |
| 5 | A | 对 | 0.01 | The premises are satisfied by X1=false, X2=false, X3=true, X4=false, X5=true, X6=false, and X7=true, so they do not entail X1. |
| 6 | A | 对 | 0.01 | A satisfying assignment exists with X1=false, so the premises do not entail X1. |

### 实际 API 题面

```text
Boolean variables X1 through X7. Premises: (X3 OR NOT X4 OR NOT X2) AND (NOT X5 OR X7 OR NOT X1) AND (NOT X2 OR X3 OR NOT X5) AND (X1 OR X5 OR X3) AND (X2 OR X5 OR X4) AND (NOT X3 OR X1 OR X5) AND (NOT X3 OR NOT X4 OR X1) AND (X3 OR NOT X6 OR NOT X5) AND (NOT X3 OR X1 OR X7) AND (X4 OR X7 OR NOT X3) AND (X3 OR X5 OR NOT X4) AND (X3 OR X5 OR X1) AND (X3 OR NOT X4 OR X6) AND (NOT X2 OR NOT X4 OR NOT X3) AND (X2 OR X3 OR NOT X5) AND (NOT X5 OR NOT X4 OR NOT X2) AND (X2 OR X6 OR NOT X4) AND (X3 OR X6 OR NOT X5) AND (NOT X5 OR NOT X7 OR NOT X1) AND (X5 OR X2 OR X1) AND (X2 OR X7 OR NOT X5) AND (NOT X2 OR X5 OR X3) AND (X2 OR X6 OR X3) AND (NOT X3 OR NOT X2 OR X6) AND (X3 OR X1 OR NOT X2) AND (X3 OR X5 OR NOT X6) AND (NOT X1 OR X3 OR X2) AND (NOT X6 OR NOT X5 OR NOT X1). Do the premises logically entail X1? Answer Yes only if the query is true in EVERY assignment satisfying all premises; otherwise No.
A: No
B: Yes
```

## v6

问题：这些前提是否蕴含 X7？

正确选项：B；独立回答序列：B, A, B, B, A, B。

```text
01. (X6 ∨ ¬X2 ∨ ¬X1)
02. (¬X6 ∨ ¬X5 ∨ X7)
03. (¬X3 ∨ ¬X7 ∨ X2)
04. (X7 ∨ ¬X5 ∨ X2)
05. (¬X6 ∨ ¬X3 ∨ ¬X4)
06. (X6 ∨ X1 ∨ ¬X4)
07. (¬X1 ∨ X3 ∨ ¬X4)
08. (¬X3 ∨ X7 ∨ X2)
09. (¬X6 ∨ X4 ∨ X1)
10. (¬X5 ∨ ¬X3 ∨ X4)
11. (X3 ∨ X1 ∨ ¬X5)
12. (¬X3 ∨ ¬X1 ∨ X6)
13. (¬X6 ∨ X5 ∨ X7)
14. (X4 ∨ X5 ∨ ¬X2)
15. (¬X2 ∨ ¬X7 ∨ ¬X5)
16. (¬X6 ∨ ¬X7 ∨ ¬X3)
17. (X1 ∨ ¬X4 ∨ ¬X3)
18. (X7 ∨ X2 ∨ X1)
19. (¬X2 ∨ X3 ∨ X1)
20. (¬X2 ∨ ¬X3 ∨ ¬X6)
21. (¬X3 ∨ X4 ∨ ¬X6)
22. (¬X5 ∨ X6 ∨ X4)
23. (X3 ∨ ¬X4 ∨ ¬X6)
24. (¬X4 ∨ X3 ∨ ¬X6)
25. (X7 ∨ ¬X3 ∨ X1)
26. (¬X1 ∨ X7 ∨ ¬X2)
27. (X6 ∨ ¬X7 ∨ ¬X3)
28. (X6 ∨ X4 ∨ X2)
```

### 精确核验

独立枚举 128 个赋值后，有 2 个满足全部前提。按 X1..X7 顺序：

```text
(1, 0, 0, 0, 0, 1, 1)
(1, 0, 0, 0, 1, 1, 1)
```

### 模型原始回答

| 次数 | 答案 | 是否正确 | p_B | 原始理由 |
|---|---|---|---|---|
| 1 | B | 对 | 1.0 | Assuming X7 is false forces contradictory requirements on X1 and X3, so every satisfying assignment has X7 true. |
| 2 | A | 错 | 0.01 | The premises are satisfiable with X7 false, for example X1=true, X2=false, X3=false, X4=true, X5=false, X6=false, X7=false. |
| 3 | B | 对 | 0.99 | Assuming X7 is false forces X6 false, and the resulting clauses lead to contradictions in both possible cases for X1. |
| 4 | B | 对 | 1.0 | Assuming X7 is false forces X6=false and exactly one of X1,X2 true, but each case contradicts other premises. |
| 5 | A | 错 | 0.0 | The premises are satisfiable with X7 false, for example X1=true, X2=false, X3=false, X4=true, X5=false, and X6=false. |
| 6 | B | 对 | 1.0 | Every assignment with X7=false leads to a contradiction among the premises, so the premises entail X7. |

### 实际 API 题面

```text
Boolean variables X1 through X7. Premises: (X6 OR NOT X2 OR NOT X1) AND (NOT X6 OR NOT X5 OR X7) AND (NOT X3 OR NOT X7 OR X2) AND (X7 OR NOT X5 OR X2) AND (NOT X6 OR NOT X3 OR NOT X4) AND (X6 OR X1 OR NOT X4) AND (NOT X1 OR X3 OR NOT X4) AND (NOT X3 OR X7 OR X2) AND (NOT X6 OR X4 OR X1) AND (NOT X5 OR NOT X3 OR X4) AND (X3 OR X1 OR NOT X5) AND (NOT X3 OR NOT X1 OR X6) AND (NOT X6 OR X5 OR X7) AND (X4 OR X5 OR NOT X2) AND (NOT X2 OR NOT X7 OR NOT X5) AND (NOT X6 OR NOT X7 OR NOT X3) AND (X1 OR NOT X4 OR NOT X3) AND (X7 OR X2 OR X1) AND (NOT X2 OR X3 OR X1) AND (NOT X2 OR NOT X3 OR NOT X6) AND (NOT X3 OR X4 OR NOT X6) AND (NOT X5 OR X6 OR X4) AND (X3 OR NOT X4 OR NOT X6) AND (NOT X4 OR X3 OR NOT X6) AND (X7 OR NOT X3 OR X1) AND (NOT X1 OR X7 OR NOT X2) AND (X6 OR NOT X7 OR NOT X3) AND (X6 OR X4 OR X2). Do the premises logically entail X7? Answer Yes only if the query is true in EVERY assignment satisfying all premises; otherwise No.
A: No
B: Yes
```

## v14

问题：这些前提是否蕴含 ¬X3？

正确选项：B；独立回答序列：A, B, A, B, A, B。

```text
01. (X5 ∨ ¬X4 ∨ X6)
02. (¬X2 ∨ X1 ∨ ¬X5)
03. (X5 ∨ ¬X7 ∨ X6)
04. (¬X1 ∨ X3 ∨ ¬X5)
05. (¬X5 ∨ ¬X6 ∨ ¬X1)
06. (¬X5 ∨ X3 ∨ X1)
07. (¬X3 ∨ ¬X7 ∨ X1)
08. (¬X3 ∨ ¬X2 ∨ X5)
09. (¬X5 ∨ X3 ∨ X7)
10. (X5 ∨ ¬X3 ∨ ¬X6)
11. (¬X3 ∨ X5 ∨ X4)
12. (¬X1 ∨ ¬X2 ∨ X5)
13. (¬X3 ∨ X1 ∨ ¬X2)
14. (¬X7 ∨ ¬X5 ∨ ¬X2)
15. (X4 ∨ X5 ∨ ¬X1)
16. (X7 ∨ X5 ∨ X3)
17. (X5 ∨ X7 ∨ ¬X2)
18. (X6 ∨ X7 ∨ ¬X2)
19. (¬X6 ∨ ¬X1 ∨ X5)
20. (X4 ∨ ¬X2 ∨ X7)
21. (X1 ∨ ¬X6 ∨ ¬X5)
22. (X6 ∨ X1 ∨ X5)
23. (¬X5 ∨ ¬X6 ∨ ¬X3)
24. (X4 ∨ X2 ∨ ¬X1)
25. (X2 ∨ X6 ∨ X7)
26. (X6 ∨ ¬X7 ∨ ¬X3)
27. (X6 ∨ X2 ∨ X3)
28. (¬X7 ∨ ¬X2 ∨ X5)
```

### 精确核验

独立枚举 128 个赋值后，有 2 个满足全部前提。按 X1..X7 顺序：

```text
(0, 0, 0, 0, 0, 1, 1)
(0, 0, 0, 1, 0, 1, 1)
```

### 模型原始回答

| 次数 | 答案 | 是否正确 | p_B | 原始理由 |
|---|---|---|---|---|
| 1 | A | 错 | 0.0 | The premises are satisfiable with X3=true, for example X1=true, X2=false, X3=true, X4=true, X5=true, X6=false, X7=true. |
| 2 | B | 对 | 1.0 | Assuming X3 is true, X5=0 leads to a violation of the first clause, while X5=1 forces X6=0, X7=0, X2=1 and then violates the eighteenth clause. |
| 3 | A | 错 | 0 | The premises are satisfiable with X3 true, for example X1=X2=X3=X5=true and X6=X7=false, so they do not entail NOT X3. |
| 4 | B | 对 | 1.0 | Assuming X3 is true forces contradictions in both cases X5=false and X5=true, so every satisfying assignment has X3=false. |
| 5 | A | 错 | 0 | The assignment X1=X2=X3=X4=X5=1 and X6=X7=0 satisfies every premise while X3 is true, so NOT X3 is not entailed. |
| 6 | B | 对 | 0.99 | Every satisfying assignment must have X3 false, since assuming X3 true leads to contradictions in both cases X5 true and X5 false. |

### 实际 API 题面

```text
Boolean variables X1 through X7. Premises: (X5 OR NOT X4 OR X6) AND (NOT X2 OR X1 OR NOT X5) AND (X5 OR NOT X7 OR X6) AND (NOT X1 OR X3 OR NOT X5) AND (NOT X5 OR NOT X6 OR NOT X1) AND (NOT X5 OR X3 OR X1) AND (NOT X3 OR NOT X7 OR X1) AND (NOT X3 OR NOT X2 OR X5) AND (NOT X5 OR X3 OR X7) AND (X5 OR NOT X3 OR NOT X6) AND (NOT X3 OR X5 OR X4) AND (NOT X1 OR NOT X2 OR X5) AND (NOT X3 OR X1 OR NOT X2) AND (NOT X7 OR NOT X5 OR NOT X2) AND (X4 OR X5 OR NOT X1) AND (X7 OR X5 OR X3) AND (X5 OR X7 OR NOT X2) AND (X6 OR X7 OR NOT X2) AND (NOT X6 OR NOT X1 OR X5) AND (X4 OR NOT X2 OR X7) AND (X1 OR NOT X6 OR NOT X5) AND (X6 OR X1 OR X5) AND (NOT X5 OR NOT X6 OR NOT X3) AND (X4 OR X2 OR NOT X1) AND (X2 OR X6 OR X7) AND (X6 OR NOT X7 OR NOT X3) AND (X6 OR X2 OR X3) AND (NOT X7 OR NOT X2 OR X5). Do the premises logically entail NOT X3? Answer Yes only if the query is true in EVERY assignment satisfying all premises; otherwise No.
A: No
B: Yes
```

## 对模型所述反例的逐条检查

```json
[
  {
    "item": "cal-20260920-logic-L2-v4",
    "assignment": [
      0,
      0,
      1,
      0,
      1,
      0,
      1
    ],
    "violated_clauses": []
  },
  {
    "item": "cal-20260920-logic-L2-v6",
    "assignment": [
      1,
      0,
      0,
      1,
      0,
      0,
      0
    ],
    "violated_clauses": [
      7
    ]
  },
  {
    "item": "cal-20260920-logic-L2-v14",
    "assignment": [
      1,
      0,
      1,
      1,
      1,
      0,
      1
    ],
    "violated_clauses": [
      26
    ]
  },
  {
    "item": "cal-20260920-logic-L2-v14",
    "assignment": [
      1,
      1,
      1,
      1,
      1,
      0,
      0
    ],
    "violated_clauses": [
      18
    ]
  }
]
```

这些检查表明部分错误理由声称存在的反例并不满足全部前提。它们是可观察的理由错误，不足以确定模型内部推理过程。
