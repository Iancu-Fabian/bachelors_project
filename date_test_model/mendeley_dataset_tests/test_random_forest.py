import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import numpy as np

FILE_PATH = 'TestK8sData.csv'

df = pd.read_csv(FILE_PATH)

df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df = df.set_index('Timestamp').sort_index()

df = df[['CPU', 'PodsNumber']]

df_rf = df.copy()

df_rf['Pods_lag1'] = df_rf['PodsNumber'].shift(1)
df_rf['Pods_lag2'] = df_rf['PodsNumber'].shift(2)
df_rf['Pods_lag3'] = df_rf['PodsNumber'].shift(3)

df_rf = df_rf.dropna()

split_point = int(len(df_rf) * 0.8)
train_rf = df_rf.iloc[:split_point]
test_rf = df_rf.iloc[split_point:]

X_train = train_rf[['CPU', 'Pods_lag1', 'Pods_lag2', 'Pods_lag3']]
y_train = train_rf['PodsNumber']

X_test = test_rf[['CPU', 'Pods_lag1', 'Pods_lag2', 'Pods_lag3']]
y_test = test_rf['PodsNumber']

rf_model = RandomForestRegressor(
    n_estimators=300,
    max_depth=6,
    random_state=42,
    n_jobs=-1
)

rf_model.fit(X_train, y_train)

y_pred_rf = rf_model.predict(X_test)
y_pred_rf = np.round(np.maximum(0, y_pred_rf))

rmse_rf = np.sqrt(mean_squared_error(y_test, y_pred_rf))
mae_rf = mean_absolute_error(y_test, y_pred_rf)

print("\n--- 🌲 Random Forest Results ---")
print("RMSE:", rmse_rf)
print("MAE:", mae_rf)