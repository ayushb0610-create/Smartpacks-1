"""
ML-predicted shelf life, trained exclusively on real user feedback.

Design rule this module exists to enforce (see /areas/packsmart-ai.md):
no fake or synthetic training data, ever. There is no bootstrap dataset,
no data augmentation, and no "reasonable-looking" made-up rows. The only
label this model ever sees is `recommendation_runs.actual_shelf_life_days`,
which is written exactly once, by PATCH /api/history/{id}/feedback, when a
person reports how long their own pack actually lasted.

Consequences of that rule:
  * Until at least `settings.ml_min_training_rows` real feedback rows exist,
    `predict()` returns None and the API simply omits
    mlPredictedShelfLifeDays — it never falls back to a guess dressed up as
    a prediction.
  * The model retrains from scratch each time (small data, cheap to redo)
    rather than incrementally fitting, so a correction to one feedback row
    is fully reflected on the next retrain.
  * Predictions are clipped to a sane physical range but are never
    fabricated when the underlying feature (e.g. a route) is missing.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import RecommendationRun

logger = logging.getLogger("smartpack.ml")

NUMERIC_FEATURES = [
    "storage_temp_c",
    "rh_pct",
    "water_activity",
    "ph",
    "weight_g",
    "target_life_days",
    "ox_sensitivity",
    "light_sensitivity",
    "predicted_shelf_life_days",  # the engine's own deterministic estimate
]
CATEGORICAL_FEATURES = ["commodity", "storage_type", "transport_mode", "top_material"]


@dataclass
class _TrainedModel:
    regressor: GradientBoostingRegressor
    encoder: OneHotEncoder
    trained_at: float
    n_rows: int


class ShelfLifeModel:
    """Thread-safe holder for the current fitted model, retrained
    periodically (see config.ml_retrain_interval_s) rather than on every
    request."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model: _TrainedModel | None = None
        self._last_attempt = 0.0

    def _rows_to_frame(self, rows: list[RecommendationRun]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        numeric = np.array(
            [[getattr(r, f) or 0.0 for f in NUMERIC_FEATURES] for r in rows],
            dtype=float,
        )
        categorical = np.array(
            [[getattr(r, f) or "unknown" for f in CATEGORICAL_FEATURES] for r in rows],
            dtype=object,
        )
        target = np.array([r.actual_shelf_life_days for r in rows], dtype=float)
        return numeric, categorical, target

    def maybe_retrain(self, db: Session, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_attempt) < settings.ml_retrain_interval_s:
            return
        self._last_attempt = now

        rows = (
            db.execute(
                select(RecommendationRun).where(
                    RecommendationRun.actual_shelf_life_days.is_not(None)
                )
            )
            .scalars()
            .all()
        )
        if len(rows) < settings.ml_min_training_rows:
            logger.info(
                "ML: %d real feedback rows, need %d — not training yet.",
                len(rows), settings.ml_min_training_rows,
            )
            with self._lock:
                self._model = None
            return

        numeric, categorical, target = self._rows_to_frame(rows)
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        cat_encoded = encoder.fit_transform(categorical)
        X = np.hstack([numeric, cat_encoded])

        regressor = GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0
        )
        regressor.fit(X, target)

        with self._lock:
            self._model = _TrainedModel(regressor, encoder, now, len(rows))
        logger.info("ML: retrained on %d real feedback rows.", len(rows))

    def predict_one(self, features: dict[str, Any]) -> float | None:
        with self._lock:
            model = self._model
        if model is None:
            return None
        try:
            numeric = np.array([[features.get(f, 0.0) or 0.0 for f in NUMERIC_FEATURES]], dtype=float)
            categorical = np.array(
                [[features.get(f, "unknown") or "unknown" for f in CATEGORICAL_FEATURES]], dtype=object
            )
            cat_encoded = model.encoder.transform(categorical)
            X = np.hstack([numeric, cat_encoded])
            pred = float(model.regressor.predict(X)[0])
        except Exception:  # pragma: no cover - defensive; never break /recommend over ML
            logger.exception("ML prediction failed; omitting mlPredictedShelfLifeDays.")
            return None
        # Physically sane floor/ceiling — a prediction of 0 or negative days
        # is a model artifact, not a real answer.
        pred = max(0.5, min(pred, 720.0))
        return round(pred, 1)

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    @property
    def training_rows(self) -> int:
        return self._model.n_rows if self._model else 0


shelf_life_model = ShelfLifeModel()
