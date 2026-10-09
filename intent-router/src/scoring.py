"""Turn a message vector into one score per intent.

Every scoring method is an IntentScorer with the same interface, so the router
and the evaluation treat them identically:

    similarity (score = cosine, 0..1)
        max        best single example of each intent
        topk_mean  mean of the k best examples of each intent
        centroid   cosine to the intent's mean vector (re-normalised)
    classifier (score = probability, sums to 1 across intents)
        logreg     logistic regression on the embeddings, C chosen by 5-fold CV on train
        mlp        small neural network (one hidden layer of 64), for comparison

`held_out_rankings()` scores every training example WITHOUT that example having
been seen: leave-one-out for similarity methods, 5-fold cross-validation for
classifiers. The evaluation tunes thresholds on these, never on test.json.
"""

from abc import ABC, abstractmethod

import numpy as np
from sklearn.base import ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.neural_network import MLPClassifier

from src.config import SCORING_METHODS

Ranking = list[tuple[str, float]]  # (intent, score), best first

CV_FOLDS = 5
SEED = 42
LOGREG_C_GRID = (0.1, 1.0, 10.0)


class IntentScorer(ABC):
    score_kind = "cosine"  # or "probability": decides which threshold scale applies

    def __init__(self, vectors: np.ndarray, labels: np.ndarray) -> None:
        """vectors: (n, dim) unit-length training rows; labels: (n,) intent of each row."""
        self.vectors = vectors
        self.labels = labels
        self.intents = list(dict.fromkeys(labels.tolist()))  # unique, in first-seen order
        self.params: dict = {}  # hyperparameters chosen during fitting, for reporting

    def rank(self, query: np.ndarray) -> Ranking:
        """Every intent with its score, best first."""
        return self._ranking(self._scores(query, exclude=None))

    def held_out_rankings(self) -> list[Ranking]:
        """One ranking per training row, computed without that row (leave-one-out)."""
        return [self._ranking(self._scores(vector, exclude=i)) for i, vector in enumerate(self.vectors)]

    @abstractmethod
    def _scores(self, query: np.ndarray, exclude: int | None) -> np.ndarray:
        """One score per intent, in `self.intents` order. `exclude` = training row to leave out."""

    def _ranking(self, scores: np.ndarray) -> Ranking:
        order = np.argsort(scores)[::-1]
        return [(self.intents[i], float(scores[i])) for i in order]


# ---- similarity scorers ----

class SimilarityScorer(IntentScorer):
    def __init__(self, vectors: np.ndarray, labels: np.ndarray) -> None:
        super().__init__(vectors, labels)
        self._rows = [np.flatnonzero(labels == intent) for intent in self.intents]

    def _example_similarities(self, query: np.ndarray, exclude: int | None) -> np.ndarray:
        sims = self.vectors @ query
        if exclude is not None:
            sims[exclude] = -np.inf
        return sims


class MaxScorer(SimilarityScorer):
    def _scores(self, query: np.ndarray, exclude: int | None) -> np.ndarray:
        sims = self._example_similarities(query, exclude)
        return np.array([sims[rows].max() for rows in self._rows])


class TopKMeanScorer(SimilarityScorer):
    def __init__(self, vectors: np.ndarray, labels: np.ndarray, k: int) -> None:
        super().__init__(vectors, labels)
        self.k = k
        self.params = {"k": k}

    def _scores(self, query: np.ndarray, exclude: int | None) -> np.ndarray:
        sims = self._example_similarities(query, exclude)
        scores = []
        for rows in self._rows:
            intent_sims = sims[rows]
            intent_sims = intent_sims[np.isfinite(intent_sims)]  # drop the left-out example
            scores.append(np.sort(intent_sims)[-self.k :].mean())
        return np.array(scores)


class CentroidScorer(SimilarityScorer):
    def __init__(self, vectors: np.ndarray, labels: np.ndarray) -> None:
        super().__init__(vectors, labels)
        # Normalising the sum gives the same direction as normalising the mean.
        self._sums = np.stack([vectors[rows].sum(axis=0) for rows in self._rows])

    def _scores(self, query: np.ndarray, exclude: int | None) -> np.ndarray:
        sums = self._sums
        if exclude is not None:
            sums = sums.copy()
            sums[self.intents.index(self.labels[exclude])] -= self.vectors[exclude]
        centroids = sums / np.linalg.norm(sums, axis=1, keepdims=True)
        return centroids @ query


# ---- classifier scorers ----

class ClassifierScorer(IntentScorer):
    """A scikit-learn classifier trained on the embeddings. Score = predicted probability."""

    score_kind = "probability"

    def __init__(
        self,
        vectors: np.ndarray,
        labels: np.ndarray,
        estimator: ClassifierMixin,
        param_grid: dict[str, list] | None = None,
    ) -> None:
        super().__init__(vectors, labels)
        self._cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=SEED)

        if param_grid:
            search = GridSearchCV(estimator, param_grid, cv=self._cv).fit(vectors, labels)
            self.params = search.best_params_
            self.model = search.best_estimator_  # refitted on all of train
        else:
            self.model = clone(estimator).fit(vectors, labels)

        # Column order of predict_proba (sorted class names) -> self.intents order.
        classes = self.model.classes_.tolist()
        self._columns = [classes.index(intent) for intent in self.intents]

    def _scores(self, query: np.ndarray, exclude: int | None) -> np.ndarray:
        if exclude is not None:
            raise ValueError("classifiers are held out with k-fold CV, not leave-one-out")
        return self.model.predict_proba(query[np.newaxis, :])[0][self._columns]

    def held_out_rankings(self) -> list[Ranking]:
        """Out-of-fold probabilities: each row scored by a model trained on the other 4 folds."""
        proba = cross_val_predict(
            clone(self.model), self.vectors, self.labels, cv=self._cv, method="predict_proba"
        )
        return [self._ranking(row[self._columns]) for row in proba]


def make_scorer(method: str, vectors: np.ndarray, labels: np.ndarray, k: int) -> IntentScorer:
    if method == "max":
        return MaxScorer(vectors, labels)
    if method == "topk_mean":
        return TopKMeanScorer(vectors, labels, k)
    if method == "centroid":
        return CentroidScorer(vectors, labels)
    if method == "logreg":
        return ClassifierScorer(
            vectors,
            labels,
            LogisticRegression(class_weight="balanced", max_iter=5000),
            {"C": list(LOGREG_C_GRID)},
        )
    if method == "mlp":
        return ClassifierScorer(
            vectors,
            labels,
            MLPClassifier(
                hidden_layer_sizes=(64,), alpha=1e-3, early_stopping=True, max_iter=500, random_state=SEED
            ),
        )
    raise ValueError(f"scoring must be one of {SCORING_METHODS}, got {method!r}")
