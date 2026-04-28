# Зведені показники по конфігураціях ablation-матриці

**Джерело:** `results/batch_20260426_220040/runs.csv`
**Кількість успішних запусків:** 120
**Конфігурації:** A, B, C, D, E, F, G, H

Кожна секція показує дві таблиці: усереднені метрики якості й усереднену економіку (тривалість, токени, вартість) у розрізі категорій сценаріїв (Normal / Edge / Corner).

---

## Легенда конфігурацій

| Label | Опис | Увімкнені стадії |
|---|---|---|
| A | Baseline (LLM + validator, no RAG, no feedback) | `validation` |
| B | LLM + Val + Feedback (no RAG) | `feedback_loop, validation` |
| C | Semantic RAG + Val + Feedback | `feedback_loop, retrieval, validation` |
| D | Metric Examples + Val + Feedback | `feedback_loop, metric_examples, validation` |
| E | Full system (semantic + metric examples + val + feedback) | `feedback_loop, metric_examples, retrieval, validation` |
| F | Semantic RAG + Val (no feedback) — pure RAG effect | `retrieval, validation` |
| G | Metric Examples + Val (no feedback) — pure metric-examples effect | `metric_examples, validation` |
| H | Semantic + Metric Examples + Val (no feedback) — pure combined effect | `metric_examples, retrieval, validation` |

---

## Конфігурація A — Baseline (LLM + validator, no RAG, no feedback)

**Увімкнені стадії:** `validation`

### Підсумкові показники якості — конфігурація A

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 0.600 | 0.850 | 0.457 | 100% |
| Edge (5 сценаріїв) | 5 | 0.000 | 1.000 | 0.475 | 100% |
| Corner (8 сценаріїв) | 5 | 0.200 | 1.000 | 0.457 | 100% |
| **Усього** | **15** | **0.267** | **0.950** | **0.463** | **100%** |

### Економіка — конфігурація A

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.00 | 71.3 | 786 | 8,340 | $0.1017 | $0.5083 |
| Edge | 0.00 | 59.0 | 784 | 7,299 | $0.0892 | $0.4458 |
| Corner | 0.00 | 49.0 | 782 | 5,928 | $0.0727 | $0.3635 |
| **Усього** | **0.00** | **59.8** | **784** | **7,189** | **$0.0878** | **$1.3176** |

---

## Конфігурація B — LLM + Val + Feedback (no RAG)

**Увімкнені стадії:** `feedback_loop, validation`

### Підсумкові показники якості — конфігурація B

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 1.000 | 1.000 | 0.482 | 100% |
| Edge (5 сценаріїв) | 5 | 0.800 | 1.000 | 0.426 | 100% |
| Corner (8 сценаріїв) | 5 | 0.950 | 1.000 | 0.422 | 100% |
| **Усього** | **15** | **0.917** | **1.000** | **0.443** | **100%** |

### Економіка — конфігурація B

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.60 | 95.6 | 1,543 | 11,375 | $0.1396 | $0.6979 |
| Edge | 1.00 | 178.2 | 1,690 | 13,174 | $0.1615 | $0.8074 |
| Corner | 0.80 | 105.5 | 1,625 | 13,161 | $0.1612 | $0.8059 |
| **Усього** | **0.80** | **126.4** | **1,619** | **12,570** | **$0.1541** | **$2.3113** |

---

## Конфігурація C — Semantic RAG + Val + Feedback

**Увімкнені стадії:** `feedback_loop, retrieval, validation`

### Підсумкові показники якості — конфігурація C

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 1.000 | 1.000 | 0.522 | 100% |
| Edge (5 сценаріїв) | 5 | 1.000 | 0.900 | 0.454 | 100% |
| Corner (8 сценаріїв) | 5 | 1.000 | 1.000 | 0.403 | 100% |
| **Усього** | **15** | **1.000** | **0.967** | **0.460** | **100%** |

### Економіка — конфігурація C

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.60 | 139.9 | 2,544 | 11,132 | $0.1387 | $0.6934 |
| Edge | 1.00 | 115.2 | 2,871 | 14,159 | $0.1757 | $0.8783 |
| Corner | 0.80 | 134.2 | 2,618 | 14,085 | $0.1743 | $0.8713 |
| **Усього** | **0.80** | **129.8** | **2,677** | **13,125** | **$0.1629** | **$2.4430** |

---

## Конфігурація D — Metric Examples + Val + Feedback

**Увімкнені стадії:** `feedback_loop, metric_examples, validation`

### Підсумкові показники якості — конфігурація D

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 1.000 | 1.000 | 0.510 | 100% |
| Edge (5 сценаріїв) | 5 | 1.000 | 1.000 | 0.445 | 100% |
| Corner (8 сценаріїв) | 5 | 1.000 | 1.000 | 0.477 | 100% |
| **Усього** | **15** | **1.000** | **1.000** | **0.477** | **100%** |

### Економіка — конфігурація D

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.40 | 87.3 | 1,302 | 10,420 | $0.1277 | $0.6383 |
| Edge | 0.20 | 66.7 | 1,183 | 8,186 | $0.1006 | $0.5030 |
| Corner | 0.20 | 62.8 | 1,133 | 7,788 | $0.0957 | $0.4786 |
| **Усього** | **0.27** | **72.3** | **1,206** | **8,798** | **$0.1080** | **$1.6199** |

---

## Конфігурація E — Full system (semantic + metric examples + val + feedback)

**Увімкнені стадії:** `feedback_loop, metric_examples, retrieval, validation`

### Підсумкові показники якості — конфігурація E

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 1.000 | 1.000 | 0.507 | 100% |
| Edge (5 сценаріїв) | 5 | 0.950 | 1.000 | 0.438 | 100% |
| Corner (8 сценаріїв) | 5 | 1.000 | 1.000 | 0.425 | 100% |
| **Усього** | **15** | **0.983** | **1.000** | **0.456** | **100%** |

### Економіка — конфігурація E

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.20 | 55.3 | 2,153 | 6,499 | $0.0823 | $0.4115 |
| Edge | 0.40 | 97.8 | 2,347 | 12,200 | $0.1511 | $0.7555 |
| Corner | 0.40 | 124.8 | 2,316 | 12,563 | $0.1554 | $0.7770 |
| **Усього** | **0.33** | **92.6** | **2,272** | **10,421** | **$0.1296** | **$1.9440** |

---

## Конфігурація F — Semantic RAG + Val (no feedback) — pure RAG effect

**Увімкнені стадії:** `retrieval, validation`

### Підсумкові показники якості — конфігурація F

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 0.700 | 0.950 | 0.520 | 100% |
| Edge (5 сценаріїв) | 5 | 0.000 | 1.000 | 0.422 | 100% |
| Corner (8 сценаріїв) | 5 | 0.200 | 0.900 | 0.450 | 100% |
| **Усього** | **15** | **0.300** | **0.950** | **0.464** | **100%** |

### Економіка — конфігурація F

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.00 | 75.1 | 1,836 | 9,068 | $0.1125 | $0.5625 |
| Edge | 0.00 | 50.3 | 1,719 | 6,055 | $0.0761 | $0.3805 |
| Corner | 0.00 | 65.8 | 1,733 | 8,019 | $0.0997 | $0.4985 |
| **Усього** | **0.00** | **63.7** | **1,762** | **7,714** | **$0.0961** | **$1.4415** |

---

## Конфігурація G — Metric Examples + Val (no feedback) — pure metric-examples effect

**Увімкнені стадії:** `metric_examples, validation`

### Підсумкові показники якості — конфігурація G

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 1.000 | 0.850 | 0.482 | 100% |
| Edge (5 сценаріїв) | 5 | 0.800 | 1.000 | 0.437 | 100% |
| Corner (8 сценаріїв) | 5 | 1.000 | 0.900 | 0.447 | 100% |
| **Усього** | **15** | **0.933** | **0.917** | **0.455** | **100%** |

### Економіка — конфігурація G

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.00 | 46.2 | 928 | 5,663 | $0.0698 | $0.3491 |
| Edge | 0.00 | 70.2 | 951 | 5,659 | $0.0698 | $0.3491 |
| Corner | 0.00 | 64.0 | 950 | 7,827 | $0.0958 | $0.4792 |
| **Усього** | **0.00** | **60.2** | **943** | **6,383** | **$0.0785** | **$1.1773** |

---

## Конфігурація H — Semantic + Metric Examples + Val (no feedback) — pure combined effect

**Увімкнені стадії:** `metric_examples, retrieval, validation`

### Підсумкові показники якості — конфігурація H

| Категорія | n | meter_accuracy | rhyme_accuracy | semantic_relevance | num_lines = expected |
|---|---|---|---|---|---|
| Normal (5 сценаріїв) | 5 | 1.000 | 0.950 | 0.510 | 100% |
| Edge (5 сценаріїв) | 5 | 0.750 | 1.000 | 0.483 | 100% |
| Corner (8 сценаріїв) | 5 | 0.600 | 1.000 | 0.412 | 100% |
| **Усього** | **15** | **0.783** | **0.983** | **0.468** | **100%** |

### Економіка — конфігурація H

| Категорія | avg iters | avg duration (s) | avg input tokens | avg output tokens | avg cost (USD) | total cost (USD) |
|---|---|---|---|---|---|---|
| Normal | 0.00 | 69.2 | 1,978 | 8,623 | $0.1074 | $0.5372 |
| Edge | 0.00 | 113.4 | 1,887 | 8,283 | $0.1032 | $0.5159 |
| Corner | 0.00 | 53.4 | 1,901 | 6,582 | $0.0828 | $0.4140 |
| **Усього** | **0.00** | **78.7** | **1,922** | **7,829** | **$0.0978** | **$1.4670** |

---
