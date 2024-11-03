from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to the appropriate origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

routes_data = []

# Load trained model
model_path = 'data/bus_travel_time_model.pkl'  # Ensure this path points to your trained model
if not os.path.exists(model_path):
    print(f"Model file not found at {model_path}. Please ensure the model is trained and saved.")
    exit(1)

model = joblib.load(model_path)
model_features = [
    'scheduled_travel_time', 'dwell_time_in_seconds',
    'segment_length', 'day_of_week', 'hour_of_day'
]

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

@app.get("/api/routes")
async def get_routes():
    if not routes_data:
        return {
            "routes": [{
                "id": "1",
                "name": "Default Route",
                "stops": [
                    {
                        "id": "1",
                        "name": "Stop 1",
                        "coordinates": [51.1605, 71.4704],
                        "predictedArrivalTime": "10:00"
                    },
                    {
                        "id": "2",
                        "name": "Stop 2",
                        "coordinates": [51.1705, 71.4804],
                        "predictedArrivalTime": "10:15"
                    }
                ],
                "segments": [
                    {
                        "from": {
                            "id": "1",
                            "name": "Stop 1",
                            "coordinates": [51.1605, 71.4704]
                        },
                        "to": {
                            "id": "2",
                            "name": "Stop 2",
                            "coordinates": [51.1705, 71.4804]
                        },
                        "travelTime": 15
                    }
                ]
            }]
        }
    return {"routes": routes_data}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        elif file.filename.endswith('.json'):
            df = pd.read_json(file.file)
        else:
            return {"error": "Only CSV and JSON files are supported"}

        required_columns = [
            'route_id', 'stop_id', 'latitude', 'longitude',
            'scheduled_time', 'dwell_time_in_seconds', 'segment_length'
        ]
        missing_columns = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            return {
                "error": f"Missing required columns: {', '.join(missing_columns)}"
            }

        df['route_id'] = df['route_id'].astype(str)
        df['stop_id'] = df['stop_id'].astype(str)

        if 'scheduled_time' in df.columns:
            df['scheduled_time'] = df['scheduled_time'].apply(
                lambda x: time_to_minutes(x)
                if isinstance(x, str) else x
            )

        # Calculate 'scheduled_travel_time' between stops
        df = df.sort_values(by=['route_id', 'scheduled_time'])
        df['scheduled_travel_time'] = df.groupby('route_id')['scheduled_time'].diff().fillna(0)

        routes = process_data_with_predictions(df)
        global routes_data
        routes_data = routes

        return {"routes": routes_data}
    except Exception as e:
        print(f"Error details: {e}")
        return {"error": f"An error occurred: {str(e)}"}
    
    


def predict_travel_time(row, start_time):
    # Подготовка данных для предсказания
    features = pd.DataFrame([{
        'scheduled_travel_time': row['scheduled_travel_time'],
        'dwell_time_in_seconds': row['dwell_time_in_seconds'],
        'segment_length': row['segment_length'],
        'day_of_week': start_time.weekday(),
        'hour_of_day': start_time.hour
    }])

    # Используем модель для предсказания времени в пути
    predicted_travel_time = model.predict(features)[0]  # Model output in minutes
    return float(predicted_travel_time) 

def process_data_with_predictions(df: pd.DataFrame) -> List[Dict]:
    routes = []
    for route_id in df['route_id'].unique():
        route_stops = df[df['route_id'] == route_id].sort_values('scheduled_time')
        
        stops = []
        segments = []
        prev_stop = None
        prev_arrival_time = None

        # Initialize start_time based on scheduled time of the first stop
        first_stop = route_stops.iloc[0]
        scheduled_time_minutes = first_stop['scheduled_time']
        start_time = datetime.now().replace(
            hour=int(scheduled_time_minutes // 60) % 24,
            minute=int(scheduled_time_minutes % 60),
            second=0, microsecond=0
        )

        for idx, row in route_stops.iterrows():
            # Если это первая остановка, предсказанное время в пути равно 0
            if idx == 0:
                predicted_travel_time = 0
            else:
                # Подготовка данных для предсказания времени между предыдущей и текущей остановкой
                features = pd.DataFrame([{
                    'scheduled_travel_time': row['scheduled_travel_time'],
                    'dwell_time_in_seconds': row['dwell_time_in_seconds'],
                    'segment_length': row['segment_length'],
                    'day_of_week': start_time.weekday(),
                    'hour_of_day': start_time.hour
                }])

                # Предсказанное время в пути между предыдущей и текущей остановкой
                predicted_travel_time = model.predict(features)[0]
            
            # Обновляем время прибытия на текущую остановку на основе предсказанного времени
            arrival_time = start_time + timedelta(minutes=float(predicted_travel_time))
            stop = {
                "id": str(row['stop_id']),
                "name": row.get('address', f"Stop {row['stop_id']}"),
                "coordinates": [float(row['latitude']), float(row['longitude'])],
                "predictedArrivalTime": arrival_time.strftime("%H:%M")
            }

            # Рассчитываем travelTime как разницу между текущим и предыдущим временем прибытия
            if prev_stop and prev_arrival_time:
                travel_time = (arrival_time - prev_arrival_time).total_seconds() / 60
                segment = {
                    "from": prev_stop,
                    "to": stop,
                    "travelTime": round(travel_time, 2)  # Точное время в пути между остановками
                }
                segments.append(segment)

            stops.append(stop)
            prev_stop = stop
            prev_arrival_time = arrival_time  # Обновляем предыдущее время прибытия
            start_time = arrival_time + timedelta(seconds=float(row['dwell_time_in_seconds']))

        route = {
            "id": str(route_id),
            "name": f"Route {route_id}",
            "stops": stops,
            "segments": segments
        }
        routes.append(route)

    return routes

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
