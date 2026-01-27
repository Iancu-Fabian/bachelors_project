import pandas as pd

FILE_PATH = 'TestK8sData.csv'

df = pd.read_csv(FILE_PATH)

df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df = df.set_index('Timestamp').sort_index()

df = df[['CPU', 'PodsNumber']]

from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import numpy as np

df_xgb = df.copy()

df_xgb['Pods_lag1'] = df_xgb['PodsNumber'].shift(1)
df_xgb['Pods_lag2'] = df_xgb['PodsNumber'].shift(2)
df_xgb['Pods_lag3'] = df_xgb['PodsNumber'].shift(3)

df_xgb = df_xgb.dropna()

split_point = int(len(df_xgb) * 0.8)
train_xgb = df_xgb.iloc[:split_point]
test_xgb = df_xgb.iloc[split_point:]

X_train = train_xgb[['CPU', 'Pods_lag1', 'Pods_lag2', 'Pods_lag3']]
y_train = train_xgb['PodsNumber']

X_test = test_xgb[['CPU', 'Pods_lag1', 'Pods_lag2', 'Pods_lag3']]
y_test = test_xgb['PodsNumber']

xgb_model = XGBRegressor(
    n_estimators=200,
    max_depth=3,
    learning_rate=0.05,
    objective='reg:squarederror'
)

xgb_model.fit(X_train, y_train)

y_pred = xgb_model.predict(X_test)
y_pred = np.round(np.maximum(0, y_pred))

rmse_xgb = np.sqrt(mean_squared_error(y_test, y_pred))
mae_xgb = mean_absolute_error(y_test, y_pred)

print("\n--- ✅ XGBoost Results ---")
print("RMSE:", rmse_xgb)
print("MAE:", mae_xgb)