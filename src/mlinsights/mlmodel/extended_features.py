"""
@file
@brief Implements new features such as polynomial features.
"""
import numpy
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils import check_array
from sklearn.utils.validation import check_is_fitted, FLOAT_DTYPES
from ._extended_features_polynomial import _transform_iall, _transform_ionly
from ._extended_features_polynomial import _transform_iall_transpose, _transform_ionly_transpose


class ExtendedFeatures(BaseEstimator, TransformerMixin):
    """
    Generates extended features such as polynomial features.

    Parameters
    ----------
    kind: string
        ``'poly'`` for polynomial features

    poly_degree : integer
        The degree of the polynomial features. Default = 2.

    poly_transpose: boolean
        Transpose the matrix before doing the computation. Default is False.

    poly_interaction_only: boolean
        If true, only interaction features are produced: features that
        are products of at most degree distinct input features
        (so not ``x[1] ** 2, x[0] * x[2] ** 3``, etc.).

    poly_include_bias: boolean
        If True (default), then include a bias column, the feature in
        which all polynomial powers are zero (i.e. a column of ones -
        acts as an intercept term in a linear model).

    Attributes
    ----------
    poly_powers_ : array, shape (n_output_features, n_input_features)
        powers_[i, j] is the exponent of the jth input in the ith output.

    n_input_features_ : int
        The total number of input features.

    n_output_features_ : int
        The total number of polynomial output features. The number of output
        features is computed by iterating over all suitably sized combinations
        of input features.
    """

    def __init__(self, kind='poly', poly_degree=2, poly_transpose=False,
                 poly_interaction_only=False, poly_include_bias=True):
        BaseEstimator.__init__(self)
        TransformerMixin.__init__(self)
        self.kind = kind
        self.poly_degree = poly_degree
        self.poly_transpose = poly_transpose
        self.poly_include_bias = poly_include_bias
        self.poly_interaction_only = poly_interaction_only

    def get_feature_names(self, input_features=None):
        """
        Returns feature names for output features.

        Parameters
        ----------
        input_features : list of string, length n_features, optional
            String names for input features if available. By default,
            "x0", "x1", ... "xn_features" is used.
        Returns
        -------
        output_feature_names : list of string, length n_output_features
        """
        if self.kind == 'poly':
            return self._get_feature_names_poly(input_features)
        else:
            raise ValueError(
                "Unknown extended features '{}'.".format(self.kind))

    def _get_feature_names_poly(self, input_features=None):
        """
        Returns feature names for output features for
        the polynomial features.
        """
        check_is_fitted(self, ['n_input_features_'])
        if input_features is None:
            input_features = ["x%d" %
                              i for i in range(0, self.n_input_features_)]
        elif len(input_features) != self.n_input_features_:
            raise ValueError("input_features should contain {} strings.".format(
                self.n_input_features_))

        names = ["1"] if self.poly_include_bias else []
        n = self.n_input_features_
        interaction_only = self.poly_interaction_only
        for d in range(0, self.poly_degree):
            if d == 0:
                pos = len(names)
                names.extend(input_features)
                index = list(range(pos, len(names)))
                index.append(len(names))
            else:
                new_index = []
                end = index[-1]
                for i in range(0, n):
                    a = index[i]
                    new_index.append(len(names))
                    start = a + (index[i + 1] - index[i]
                                 if interaction_only else 0)
                    names.extend([a + " " + input_features[i]
                                  for a in names[start:end]])
                new_index.append(len(names))
                index = new_index

        def process_name(col):
            scol = col.split()
            res = []
            for c in sorted(scol):
                if len(res) == 0 or res[-1][0] != c:
                    res.append((c, 1))
                else:
                    res[-1] = (c, res[-1][1] + 1)
            return " ".join(["%s^%d" % r if r[1] > 1 else r[0] for r in res])

        names = [process_name(s) for s in names]
        return names

    def fit(self, X, y=None):
        """
        Compute number of output features.
        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            The data.
        Returns
        -------
        self : instance
        """
        n_features = check_array(X, accept_sparse=True).shape[1]
        self.n_input_features_ = n_features
        self.n_output_features_ = len(self.get_feature_names())

        if self.kind == 'poly':
            return self._fit_poly(X, y)
        else:
            raise ValueError(
                "Unknown extended features '{}'.".format(self.kind))

    def _fit_poly(self, X, y=None):
        """
        Fitting method for the polynomial features.
        """
        return self

    def transform(self, X):
        """
        Transforms data to extended features.

        Parameters
        ----------
        X : array-like or sparse matrix, shape [n_samples, n_features]
            The data to transform, row by row.
            Sparse input should preferably be in CSC format.
        Returns
        -------
        XP : numpy.ndarray or CSC sparse matrix, shape [n_samples, NP]
            The matrix of features, where NP is the number of polynomial
            features generated from the combination of inputs.
        """
        check_is_fitted(self, ['n_input_features_', 'n_output_features_'])
        n_features = X.shape[1]
        if n_features != self.n_input_features_:
            raise ValueError("X shape does not match training shape")
        if self.kind == 'poly':
            return self._transform_poly(X)
        else:
            raise ValueError(
                "Unknown extended features '{}'.".format(self.kind))

    def _transform_poly(self, X):
        """
        Transforms data to polynomial features.
        """
        X = check_array(X, dtype=FLOAT_DTYPES, accept_sparse='csc')

        if sparse.isspmatrix(X):
            if self.poly_transpose:
                XP = sparse.lil_matrix(
                    (self.n_output_features_, X.shape[0]), dtype=X.dtype)
            else:
                XP = sparse.lil_matrix(
                    (X.shape[0], self.n_output_features_), dtype=X.dtype)

            def multiply(A, B):
                return A.multiply(B)

            def final(X):
                return X.tocsc()
        else:
            if self.poly_transpose:
                XP = numpy.empty(
                    (self.n_output_features_, X.shape[0]), dtype=X.dtype)
            else:
                XP = numpy.empty(
                    (X.shape[0], self.n_output_features_), dtype=X.dtype)

            def multiply(A, B):
                return numpy.multiply(A, B)

            def final(X):
                return X

        if self.poly_transpose:
            if self.poly_interaction_only:
                return _transform_ionly_transpose(self.poly_degree, self.poly_include_bias,
                                                  XP, X, multiply, final).T.copy()
            else:
                return _transform_iall_transpose(self.poly_degree, self.poly_include_bias,
                                                 XP, X, multiply, final).T.copy()
        else:
            if self.poly_interaction_only:
                return _transform_ionly(self.poly_degree, self.poly_include_bias,
                                        XP, X, multiply, final)
            else:
                return _transform_iall(self.poly_degree, self.poly_include_bias,
                                       XP, X, multiply, final)
