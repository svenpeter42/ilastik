"""Core functionality for crossfold operator implemented as simple
functions for ease of testing.

"""

import numpy as np
import vigra


def make_folds(labels, n_folds):
    """Make stratified folds.

    Parameters
    ----------
    labels : array-like, [n_samples]

    n_folds : int
        The number of folds.

    Returns
    -------
    folds : nested list
        Sample indices in each fold.

    """
    labels = np.asarray(labels)

    # ensure they are contiguous
    _, labels = np.unique(labels, return_inverse=True)

    if n_folds > np.min(np.bincount(labels)):
        raise Exception('number of folds is greater than instances of a label')

    n_labels = labels.size
    idx = np.argsort(labels)

    for i in xrange(n_folds):
        test_index = np.zeros(n_labels, dtype=np.bool)
        test_index[idx[i::n_folds]] = True
        train_index = np.logical_not(test_index)
        ind = np.arange(n_labels)
        train_index = ind[train_index]
        test_index = ind[test_index]
        yield train_index, test_index


def train_and_predict(samples, labels, folds, rf_kwargs,
                      probabilities=True):
    """Cross-validation on a set of image patches.

    Parameters
    ----------
    samples : list of array-like
        List of patch arrays for each image.

    labels : list of array-like
        List of label arrays for each image.

    folds : nested list
        List of (train, test) index pairs.

    probabilities : bool, optional
        Whether to return predictions or probabilities.

    Returns
    -------
    predictors : collection of vigra random forests

    predictions: list of array-like
        Prediction labels or probabilities for each image.

    """
    samples = list(np.asarray(s) for s in samples)
    labels = list(np.asarray(lab).squeeze() for lab in labels)

    for s, lab in zip(samples, labels):
        if s.ndim != 2:
            raise Exception()
        if lab.ndim != 1:
            raise Exception()
        if s.shape[0] != lab.shape[0]:
            raise Exception()

    classifiers = list(vigra.learning.RandomForest(**rf_kwargs)
                       for _ in range(len(folds)))
    predictions = [None] * len(samples)

    for c, (train, test) in zip(classifiers, folds):
        X = np.vstack(list(samples[i] for i in train))
        Y = np.vstack(list(labels[i] for i in train))
        c.learnRF(X, Y)

        for idx in test:
            if probabilities:
                predictions[idx] = c.predictProbabilities(samples[idx])
            else:
                predictions[idx] = c.predictLabels(samples[idx])

    return classifiers, predictions
