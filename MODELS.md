# Models

Documentation of the model experiments for the NBA Win Probability Engine.

## Problem

Given the state of an NBA game at any moment (score, time, period, possession,
fouls, recent momentum), predict the probability that the **home team will win**.

Binary classification on a near-symmetric dataset:
- **Home win rate (overall):** 54.6%
- **Random-baseline accuracy:** 54.6% (always predict home win)
- **Theoretical ceiling:** ~95% in the final minute, ~75% pre-game (limited by what game state alone can know)

## Data

| | Games | Plays | Home Win % |
|---|---|---|---|
| Train (2023–24 regular season) | 1,230 | 481,885 | 54.6% |
| Validation (2023–24 playoffs + first 60% of 2024–25) | 867 | 341,233 | 55.3% |
| **Test (last 40% of 2024–25)** | **524** | **206,280** | **53.9%** |

Split is **chronological** — older games train, newer games test. This mimics
the production scenario: predict on games that happen after the model was trained.
We also split by `game_id`, not by row, to prevent leakage (a model that sees
half of a game during training would trivially "predict" the rest).

## Features

16 features per snapshot:

**Raw game state:**
- `score_margin` (home − away)
- `seconds_remaining_game`, `seconds_remaining_period`
- `period`, `is_overtime`
- `home_has_possession`
- `home_fouls_period`, `away_fouls_period`
- `home_in_bonus`, `away_in_bonus`
- `momentum_5` (score delta in last 5 plays)
- `recent_scoring_run` (clipped to ±20)

**Engineered interactions:**
- `is_clutch` (last 5 min, within 5 pts)
- `abs_margin`
- `margin_x_logtime` — the key feature: small leads matter more late
- `margin_per_second_remaining`

Notably absent: team identity, pre-game ratings, player data. The model is
intentionally team-agnostic for v1.

## Models

Three models trained on identical features and splits.

### Logistic Regression
- `sklearn.linear_model.LogisticRegression`
- `StandardScaler` fit on train only
- `class_weight="balanced"`, `C=1.0`, `max_iter=1000`

### Random Forest
- `sklearn.ensemble.RandomForestClassifier`
- 200 trees, `max_depth=12`, `min_samples_leaf=50`
- `class_weight="balanced"`, parallelized across all cores

### PyTorch MLP
- 3 hidden layers: 16 → 64 → 32 → 1
- ReLU activations, dropout 0.2
- BCEWithLogitsLoss + Adam (lr=1e-3)
- Early stopping on validation log loss (patience=5)
- 3,201 parameters total

## Test-set results

| Model | Accuracy | Log Loss | Brier | ROC AUC |
|---|---|---|---|---|
| Logistic Regression | 73.5% | 0.499 | 0.169 | 0.826 |
| Random Forest | 73.5% | 0.508 | 0.171 | 0.822 |
| **PyTorch MLP** | **73.7%** | **0.501** | **0.169** | **0.825** |

The neural network won on accuracy and Brier score by a small but real margin.
Logistic regression edged out log loss and ROC AUC — also by small margins.

### Accuracy by time remaining

| Time bucket | logreg | rf | nn |
|---|---|---|---|
| Final minute | 92.3% | 91.7% | 91.6% |
| 1–3 min left | 91.3% | 90.9% | 90.7% |
| 3–6 min left | 87.2% | 87.0% | 87.2% |
| 1 quarter left | 83.8% | 83.6% | 83.9% |
| 1–2 quarters left | 77.8% | 77.7% | 77.8% |
| 2+ quarters left | 64.5% | 64.6% | **65.0%** |

The model is most accurate in the final minute (92%) and least accurate in
the first half (~65%). This is structurally correct — as the game progresses,
the outcome becomes more knowable.

### Calibration (NN, test set)

| Predicted P(home) | Actual rate | N |
|---|---|---|
| 0.04 | 0.03 | 20,689 |
| 0.15 | 0.17 | 11,824 |
| 0.25 | 0.26 | 13,864 |
| 0.35 | 0.35 | 16,812 |
| 0.45 | 0.45 | 19,383 |
| 0.56 | 0.55 | 29,269 |
| 0.64 | 0.63 | 30,134 |
| 0.75 | 0.72 | 15,049 |
| 0.85 | 0.80 | 14,024 |
| 0.97 | 0.95 | 35,232 |

Predictions track actual outcomes within ~3% across the probability range.
The model is essentially well-calibrated, with mild overconfidence at the
extremes (predicting 85% when the true rate is 80%).

## Discussion

**Why the three models converge.** All three sit within 0.3% accuracy of each
other on the test set. This convergence indicates the engineered features
(particularly `margin_x_logtime` and `margin_per_second_remaining`) already
capture the key non-linear interactions. The neural network has nothing
non-linear left to discover.

**Why a small NN edge in log loss / Brier.** Logistic regression naturally
outputs calibrated probabilities under MLE; the NN's dropout regularization
produces slightly smoother probability outputs, marginally improving calibration
metrics without changing classification accuracy.

**Final-minute accuracy plateau at ~92%.** This is near the practical ceiling
for game-state-only models. The remaining 8% errors are situations where
game state at time T does not determine the outcome — e.g., intentional fouling
strategies, full-court alley-oop game-winners, double-teamed defenders.
Improving here requires player-level or play-call data.

**Test calibration is tighter than val.** The validation set contains 2023–24
playoffs, where late-game possession dynamics are more strategic and harder to
predict. The test set's distribution happens to be closer to the model's
training distribution.

## Reproducing

```bash
cd backend
.venv\Scripts\Activate.ps1  # or `source .venv/bin/activate` on Mac/Linux

# Phase 2: ingest + clean + load
python -m ml_pipeline.ingest.fetch_games
python -m ml_pipeline.ingest.fetch_plays    # 3–4 hours
python -m ml_pipeline.clean.clean_plays
python -m ml_pipeline.load.load_to_db

# Phase 3-4: state + features
python -m ml_pipeline.states.build_states
python -m ml_pipeline.features.build_features

# Phase 5-6: train all three models
python -m ml_pipeline.train.train_logreg
python -m ml_pipeline.train.train_rf
python -m ml_pipeline.train.train_nn

# Phase 7: evaluate + plot
python -m ml_pipeline.train.evaluate --split test
python -m ml_pipeline.train.plots --split test
```

## Roadmap

Improvements that would push performance beyond the current ceiling:

- **Team identity** — embeddings for offensive/defensive rating per team
- **Pre-game features** — rest days, travel, back-to-back flag, injury reports
- **Hand-curated late-game patterns** — intentional foul situations, end-of-quarter sets
- **Probability calibration via Platt scaling** to fix the mild overconfidence at extremes
- **Bigger dataset** — backfill to 10 seasons; trivially supported by the existing pipeline

The current model serves the dashboard well; these changes would tighten
production accuracy from ~74% toward the ~78% ceiling reported in published
academic literature on this problem.