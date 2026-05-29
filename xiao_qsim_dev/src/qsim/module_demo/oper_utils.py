import numpy as np

def isvalid(x):
    return np.isfinite(x)

def regress(x, y):
    '''
    x, y is 1-D vector
    '''
    v = np.logical_and(isvalid(x), isvalid(y))
    if v.sum() < 2:
        return np.nan, np.nan
    X = x[v]
    Y = y[v]
    meanx = np.mean(X)
    meany = np.mean(Y)
    stdx = np.sum(np.power(X - meanx, 2))
    beta = np.sum((X-meanx) * (Y-meany))
    beta = beta / stdx
    alpha = meany - beta  * meanx
    return alpha, beta

def resid(x, y):
    '''
    x, y is 1-D vector
    '''
    rsd = y.copy()
    rsd[:] = np.nan

    v = np.logical_and(isvalid(x), isvalid(y))
    if v.sum() < 2:
        return rsd

    X = x[v]
    Y = y[v]
    meanx = np.mean(X)
    meany = np.mean(Y)
    stdx = np.sum(np.power(X - meanx, 2))
    beta = np.sum((X-meanx) * (Y-meany))
    beta = beta / stdx
    alpha = meany - beta  * meanx
    rsd[v] = Y - (alpha + beta * X)
    return rsd