import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error
from datetime import datetime
import joblib
import sys
from math import radians, sin, cos, sqrt, atan2

# Load the data
trips = pd.read_csv('trips_data.csv')
stops = pd.read_csv('stops_data.csv')
arrivals = pd.read_csv('dwell_sorted.csv')
segments = pd.read_csv('run_data.csv')

# Print columns for debugging
print("Columns in trips DataFrame:", trips.columns.tolist())
print("Columns in stops DataFrame:", stops.columns.tolist())
print("Columns in arrivals DataFrame:", arrivals.columns.tolist())
print("Columns in segments DataFrame:", segments.columns.tolist())

# Convert time to minutes from start of the day
def time_to_minutes(t):
    if pd.isna(t):
        return np.nan
    if isinstance(t, str):
        try:
            x = datetime.strptime(t, '%H:%M:%S')
        except ValueError:
            try:
                x = datetime.strptime(t, '%H:%M')
            except ValueError:
                return np.nan
        return x.hour * 60 + x.minute
    return t  # Already in minutes

# Apply time conversion where necessary
for df, cols in [(trips, ['start_time', 'end_time']), (arrivals, ['arrival_time', 'departure_time']), (segments, ['start_time', 'end_time'])]:
    for col in cols:
        if col in df.columns:
            df[col] = df[col].apply(time_to_minutes)

# Fill missing values in arrivals
arrivals.fillna(0, inplace=True)

# Ensure 'stop_sequence' exists in arrivals
if 'stop_sequence' not in arrivals.columns:
    arrivals['stop_sequence'] = arrivals.groupby('trip_id').cumcount() + 1

# Ensure 'stop_id' exists in arrivals
if 'stop_id' not in arrivals.columns:
    if 'bus_stop' in arrivals.columns and 'stop_id' in stops.columns:
        # Standardize the 'bus_stop' and 'stop_id' columns for consistent merging
        arrivals['bus_stop'] = arrivals['bus_stop'].astype(str).str.strip()
        stops['stop_id'] = stops['stop_id'].astype(str).str.strip()
        # Merge on 'bus_stop' from arrivals and 'stop_id' from stops
        arrivals = arrivals.merge(
            stops[['stop_id', 'route_id', 'direction', 'latitude', 'longitude']],
            left_on='bus_stop',
            right_on='stop_id',
            how='left',
            suffixes=('', '_stop')
        )
        if arrivals['stop_id'].isnull().any():
            missing_stops = arrivals[arrivals['stop_id'].isnull()]
            print("Error: Missing 'stop_id' after merging for the following stops:")
            print(missing_stops[['trip_id', 'bus_stop']])
            # Decide how to handle these rows
            arrivals = arrivals[~arrivals['stop_id'].isnull()]
    else:
        print("Error: 'stop_id' not found in 'stops' or 'bus_stop' not found in 'arrivals'.")
        sys.exit(1)

# Merge 'start_time' from trips into arrivals
if 'start_time' not in arrivals.columns:
    if 'trip_id' in arrivals.columns and 'start_time' in trips.columns:
        arrivals = arrivals.merge(trips[['trip_id', 'start_time']], on='trip_id', how='left')
    else:
        print("Error: Cannot merge 'start_time' into 'arrivals'.")
        sys.exit(1)

# Compute 'scheduled_time' for each stop
if 'scheduled_time' not in arrivals.columns:
    fixed_interval = 5  # Adjust as needed based on actual schedule
    arrivals['scheduled_time'] = arrivals['start_time'] + (arrivals['stop_sequence'] - 1) * fixed_interval

# Compute 'scheduled_travel_time' between stops
if 'scheduled_travel_time' not in arrivals.columns:
    arrivals['scheduled_travel_time'] = arrivals.groupby('trip_id')['scheduled_time'].diff().fillna(0)

# Create segments DataFrame
required_cols = ['trip_id', 'stop_id', 'scheduled_travel_time', 'scheduled_time']
missing_cols = [col for col in required_cols if col not in arrivals.columns]
if missing_cols:
    print(f"Error: Missing columns in 'arrivals': {missing_cols}")
    sys.exit(1)

segments = arrivals[['trip_id', 'stop_id', 'scheduled_travel_time', 'scheduled_time']].copy()
segments['end_stop_id'] = segments.groupby('trip_id')['stop_id'].shift(-1)
segments['end_scheduled_time'] = segments.groupby('trip_id')['scheduled_time'].shift(-1)
segments['end_scheduled_travel_time'] = segments.groupby('trip_id')['scheduled_travel_time'].shift(-1)

# Drop rows where 'end_stop_id' is NaN (last stop in each trip)
segments = segments.dropna(subset=['end_stop_id'])

# Convert stop IDs to appropriate data types
segments['start_stop_id'] = segments['stop_id'].astype(str)
segments['end_stop_id'] = segments['end_stop_id'].astype(str)

# Rename columns
segments.rename(columns={
    'scheduled_travel_time': 'scheduled_start_time'
}, inplace=True)

# Compute 'scheduled_travel_time' for segments
segments['scheduled_travel_time'] = segments['end_scheduled_time'] - segments['scheduled_time']

# Ensure 'scheduled_time' is present in segments
if 'scheduled_time' not in segments.columns:
    print("Error: 'scheduled_time' is missing from 'segments' after processing.")
    sys.exit(1)

# If 'segment_length' is not in segments, set a default or merge from another DataFrame
if 'segment_length' not in segments.columns:
    if 'length' in segments.columns:
        segments['segment_length'] = segments['length']
    else:
        # As a placeholder, assign default segment lengths
        segments['segment_length'] = 1.0  # Replace with actual data if available

# Compute the target variable - actual travel time between stops
arrivals['actual_travel_time'] = arrivals.groupby('trip_id')['arrival_time'].diff().fillna(0)

# Merge 'actual_travel_time' into segments
segments = segments.merge(
    arrivals[['trip_id', 'stop_id', 'actual_travel_time']],
    left_on=['trip_id', 'end_stop_id'],
    right_on=['trip_id', 'stop_id'],
    how='left',
    suffixes=('', '_arrival')
)

# Print columns to debug
print("Columns in 'segments' after merge:", segments.columns.tolist())

# Remove unnecessary columns
if 'stop_id_arrival' in segments.columns:
    segments.drop(columns=['stop_id_arrival'], inplace=True)

# Remove negative or zero travel times
segments = segments[segments['actual_travel_time'] > 0]

# Prepare features for the model
features = pd.DataFrame()
features['scheduled_travel_time'] = segments['scheduled_travel_time']
features['dwell_time_in_seconds'] = arrivals['dwell_time_in_seconds'].values[:len(segments)]
features['segment_length'] = segments['segment_length']
if 'date' in arrivals.columns:
    features['day_of_week'] = pd.to_datetime(arrivals['date']).dt.dayofweek.values[:len(segments)]
else:
    features['day_of_week'] = 0  # Default value if 'date' is missing
features['hour_of_day'] = segments['scheduled_time'] // 60  # Hour of day

# Target variable
target = segments['actual_travel_time']

# Remove any NaN or infinite values
features = features.replace([np.inf, -np.inf], np.nan).dropna()
target = target.loc[features.index]

# Ensure that features and target have the same length
if len(features) != len(target):
    print("Error: Mismatch in length between features and target.")
    sys.exit(1)

# Split the data into training and test sets
X_train, X_test, y_train, y_test = train_test_split(
    features, target, test_size=0.2, random_state=42
)

# Model training
model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5)
model.fit(X_train, y_train)

# Model evaluation
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
print(f"Mean Absolute Error: {mae}")

# Save the model
model_path = 'bus_travel_time_model.pkl'
joblib.dump(model, model_path)

print("Model training completed.")
print(f"Model saved to: {model_path}")

# Изменяем подготовку данных
def prepare_features(df):
    features = pd.DataFrame()
    
    # Рассчитываем расстояние между остановками
    features['segment_length'] = calculate_distances(
        df['latitude'], 
        df['longitude'],
        df['latitude'].shift(),
        df['longitude'].shift()
    )
    
    # Время суток (час)
    features['hour_of_day'] = df['scheduled_time'].apply(
        lambda x: int(x.split(':')[0]) if isinstance(x, str) else x // 60
    )
    
    # День недели (можно добавить позже)
    features['day_of_week'] = 0
    
    return features

def calculate_distances(lat1, lon1, lat2, lon2):
    # Используем формулу гаверсинусов для расчета расстояния
    R = 6371  # радиус Земли в километрах
    
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    distance = R * c
    
    return distance

# Основной процесс тренировки
def train_model(data):
    features = prepare_features(data)
    
    # Целевая переменная - время в пути между остановками
    target = data['travel_time']  # предполагаем, что это время в минутах
    
    # Разделение данных
    X_train, X_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=42
    )
    
    # Обучение модели
    model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5)
    model.fit(X_train, y_train)
    
    # Сохранение модели
    joblib.dump(model, 'bus_travel_time_model.pkl')
    
    return model

# Запуск тренировки
if __name__ == "__main__":
    # Загрузка данных
    data = pd.read_csv('routes_data.csv')
    model = train_model(data)
