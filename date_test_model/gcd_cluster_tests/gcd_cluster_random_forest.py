import pandas as pd
import numpy as np
import tarfile
import io
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

FILE_PATH_GZ = 'GCD_VMs.tar.gz'
LAG_STEPS = 3
TEST_SIZE_RATIO = 0.2

def load_and_preprocess(file_path, lag_steps):
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

    for i in range(1, lag_steps + 1):
        df[f'CPU_lag{i}'] = df['CPU'].shift(i)
        df[f'Memory_lag{i}'] = df['Memory'].shift(i)

    df['target'] = df['CPU'].shift(-1)
    df = df.dropna().drop(['CPU', 'Memory', 'vm_id'], axis=1, errors='ignore')

    return df


df = load_and_preprocess(FILE_PATH_GZ, LAG_STEPS)
split_idx = int(len(df) * (1 - TEST_SIZE_RATIO))

train_df = df.iloc[:split_idx]
test_df = df.iloc[split_idx:]

X_train = train_df.drop('target', axis=1).values
y_train = train_df['target'].values
X_test = test_df.drop('target', axis=1).values
y_test = test_df['target'].values

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)


def train_rf(X, y):
    print("Training Random Forest Regressor...")
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        n_jobs=-1,
        random_state=42
    )
    model.fit(X, y)
    return model


def evaluate_rf(model, X, y_true):
    y_pred = model.predict(X)
    y_pred = np.clip(y_pred, 0, 100)

    metrics = {
        "R2": r2_score(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE": mean_absolute_error(y_true, y_pred)
    }
    return metrics


rf_model = train_rf(X_train, y_train)
results = evaluate_rf(rf_model, X_test, y_test)

print("\n--- Random Forest Results ---")
print(f"R²:   {results['R2']:.4f}")
print(f"RMSE: {results['RMSE']:.4f} % CPU")
print(f"MAE:  {results['MAE']:.4f} % CPU")