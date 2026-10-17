# Practical Feature Engineering for Machine Learning

Feature engineering transforms raw tabular data into representations that improve model learning capacity and predictive accuracy.

## Numerical Preprocessing
- **Standardization (Z-score scaling):** Transforms features to zero mean and unit variance. Critical for models sensitive to scale like SVMs, logistic regression, and neural networks.
- **Robust Scaling:** Uses median and interquartile range (IQR), preventing outliers from skewing scaling boundaries.
- **Log Transformation:** Normalizes highly skewed distributions (e.g. monetary amounts, website visit counts).

## Categorical Encodings
- **One-Hot Encoding:** For low-cardinality nominal variables without intrinsic ordinal ranking.
- **Target Encoding:** Replaces categories with the expected target value, with smoothing to prevent overfitting.