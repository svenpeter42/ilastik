"""Core functionality for crossfold operator implemented as simple
functions for ease of testing.

"""

def make_folds(labels, n_folds, extra_labels=None):
    """Creates folds stratified by both labels and extra labels.

    Parameters
    ----------
    labels : array-like, [n_samples]

    n_folds : int
        The number of folds.

    extra_labels : array-like, [n_samples], optional
        These labels are stratified across folds but otherwise not used.

    Returns
    -------
    folds : nested list
        Sample indices in each fold.

    """
    pass


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
