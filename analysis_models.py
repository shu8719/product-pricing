from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


MARKET_FEATURE_COLUMNS = [
    "capacitance_uF",
    "voltage_V",
    "tolerance_percent",
    "diameter_mm",
    "height_mm",
    "lifetime_hours",
    "price_jpy",
]
PRICE_NUMERIC_COLUMNS = [
    "capacitance_uF",
    "voltage_V",
    "tolerance_percent",
    "diameter_mm",
    "height_mm",
    "lifetime_hours",
]
PRICE_CATEGORICAL_COLUMNS = ["mount_type"]


@dataclass
class PriceModelBundle:
    model: Pipeline
    numeric_columns: list[str]
    categorical_columns: list[str]
    metrics: dict[str, float]
    defaults: dict[str, object]


def _cluster_count(row_count: int) -> int:
    if row_count < 20:
        return 2
    if row_count < 80:
        return 3
    if row_count < 180:
        return 4
    return 5


def build_market_map_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with PCA coordinates and cluster labels."""
    model_df = df.dropna(subset=["capacitance_uF", "voltage_V", "price_jpy"]).copy()
    if len(model_df) < 8:
        raise ValueError("市場マップを作るには十分なデータがありません。")

    feature_frame = model_df[MARKET_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True))

    scaled = StandardScaler().fit_transform(feature_frame)
    kmeans = KMeans(
        n_clusters=_cluster_count(len(model_df)),
        n_init=20,
        random_state=42,
    )
    labels = kmeans.fit_predict(scaled)
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(scaled)

    plotted = model_df.copy()
    plotted["pc1"] = coords[:, 0]
    plotted["pc2"] = coords[:, 1]
    plotted["cluster"] = [f"Cluster {label + 1}" for label in labels]
    return plotted


def train_price_model(df: pd.DataFrame) -> PriceModelBundle:
    """Train a simple price prediction model and return it with metrics."""
    model_df = df.dropna(subset=["price_jpy", "capacitance_uF", "voltage_V"]).copy()
    if len(model_df) < 30:
        raise ValueError("価格予測モデルを学習するには十分なデータがありません。")

    numeric_columns = [
        column for column in PRICE_NUMERIC_COLUMNS if column in model_df.columns
    ]
    categorical_columns = [
        column for column in PRICE_CATEGORICAL_COLUMNS if column in model_df.columns
    ]
    feature_columns = numeric_columns + categorical_columns

    X = model_df[feature_columns].copy()
    y = pd.to_numeric(model_df["price_jpy"], errors="coerce")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric_columns:
        transformers.append(
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                    ]
                ),
                numeric_columns,
            )
        )
    if categorical_columns:
        transformers.append(
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical_columns,
            )
        )

    preprocessor = ColumnTransformer(transformers=transformers)
    model = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=300,
                    min_samples_leaf=2,
                    n_jobs=1,
                    random_state=42,
                ),
            ),
        ]
    )

    model.fit(X_train, y_train)
    predicted = model.predict(X_test)
    metrics = {
        "mae_jpy": float(mean_absolute_error(y_test, predicted)),
        "r2": float(r2_score(y_test, predicted)),
        "sample_count": float(len(model_df)),
    }

    model.fit(X, y)
    defaults: dict[str, object] = {}
    for column in numeric_columns:
        defaults[column] = float(pd.to_numeric(model_df[column], errors="coerce").median())
    for column in categorical_columns:
        mode = model_df[column].mode(dropna=True)
        defaults[column] = mode.iloc[0] if not mode.empty else "unknown"

    return PriceModelBundle(
        model=model,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        metrics=metrics,
        defaults=defaults,
    )


def predict_price(bundle: PriceModelBundle, spec: dict[str, object]) -> float:
    """Predict unit price for a target specification."""
    row = {}
    for column in bundle.numeric_columns:
        row[column] = spec.get(column, bundle.defaults.get(column))
    for column in bundle.categorical_columns:
        row[column] = spec.get(column, bundle.defaults.get(column))
    prediction = bundle.model.predict(pd.DataFrame([row]))[0]
    return float(prediction)
