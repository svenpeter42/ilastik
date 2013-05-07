"""Core functionality for crossfold operator implemented as simple
functions for ease of testing.

"""

import numpy as np


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


def train(samples, labels, folds):
    """Train a set of classifiers.

    Parameters
    ----------
    samples : array-like [n_samples, n_features]

    labels : array-like [n_samples]

    folds : nested list
        The output of make_folds().

    Returns
    -------
    predictors : list of vigra random forests

    """
    pass


def predict(samples, probabilities=True, in_fold=None):
    """Ensures that no sample gets predicted by a classifier that it
    was used to train.

    Parameters
    ----------
    samples : array-like [n_samples, n_features]

    probabilities : bool, optional
        Whether to return predictions or probabilities.

    in_fold : array-like, [n_samples], optional
        in_fold[i] == j if sample i was used to train classifier j;
        otherwise in_fold[i] = -1.

    Returns
    -------
    predictions: numpy array-like, [n_samples] or [n_samples, n_classes]

    """
    pass
