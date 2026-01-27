import pandas as pd
import numpy as np
import tarfile
import io
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

FILE_PATH_GZ = 'GCD_VMs.tar.gz'
LAG_STEPS = 3
TEST_SIZE_RATIO = 0.2


def load_and_preprocess_xgb(file_path, lag_steps):
    all_data = []
    with tarfile.open(file_path, 'r:gz') as tar:
        for member in tar.getmembers():
            if member.isfile():
                f = tar.extractfile(member)
                if f:
                    df_vm = pd.read_csv(io.BytesIO(f.read()), sep=r"\s+",
                                        header=None, names=["CPU", "Memory"], engine="python")
                    all_data.append(df_vm)

    df_raw = pd.concat(all_data, ignore_index=True)
    df = df_raw.copy()

    df['target'] = df['CPU'].shift(-1)

    for i in range(1, lag_steps + 1):
        df[f'CPU_lag{i}'] = df['CPU'].shift(i)
        df[f'Memory_lag{i}'] = df['Memory'].shift(i)

    df = df.dropna().drop(['CPU', 'Memory'], axis=1)
    return df


def train_xgb(x, y):
    print("Training XGBoost Regressor...")
    model = XGBRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        objective='reg:squarederror',
        n_jobs=-1,
        random_state=42
    )
    model.fit(x, y)
    return model


def evaluate_xgb(model, x, y_true):
    y_pred = model.predict(x)
    y_pred = np.clip(y_pred, 0, 100)  # Ensure realistic CPU bounds

    metrics = {
        "R2": r2_score(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE": mean_absolute_error(y_true, y_pred)
    }
    return y_true, y_pred, metrics

df_processed = load_and_preprocess_xgb(FILE_PATH_GZ, LAG_STEPS)

split_idx = int(len(df_processed) * (1 - TEST_SIZE_RATIO))
train_df = df_processed.iloc[:split_idx]
test_df = df_processed.iloc[split_idx:]

x_train, y_train = train_df.drop('target', axis=1), train_df['target']
x_test, y_test = test_df.drop('target', axis=1), test_df['target']

model = train_xgb(x_train, y_train)
y_true, y_pred, results = evaluate_xgb(model, x_test, y_test)

print("\n--- XGBoost Results ---")
print(f"R²:   {results['R2']:.4f}")
print(f"RMSE: {results['RMSE']:.4f} % CPU")
print(f"MAE:  {results['MAE']:.4f} % CPU")