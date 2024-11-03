from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
import os
from pydantic import BaseModel
import time

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

        # Конвертируем scheduled_time в минуты
        if 'scheduled_time' in df.columns:
            df['scheduled_time'] = df['scheduled_time'].apply(time_to_minutes)

        required_columns = [
            'route_id', 'stop_id', 'latitude', 'longitude',
            'scheduled_time'
        ]
        missing_columns = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            return {
                "error": f"Missing required columns: {', '.join(missing_columns)}"
            }

        # Добавляем вычисление segment_length
        df['segment_length'] = df.apply(
            lambda row: calculate_distance(
                row['latitude'], 
                row['longitude'],
                df.shift(1)['latitude'].iloc[0] if pd.notna(df.shift(1)['latitude'].iloc[0]) else row['latitude'],
                df.shift(1)['longitude'].iloc[0] if pd.notna(df.shift(1)['longitude'].iloc[0]) else row['longitude']
            ),
            axis=1
        )
        
        # Добавляем фиксированное значение dwell_time_in_seconds
        df['dwell_time_in_seconds'] = 30  # среднее время остановки

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

def process_data_with_predictions(df):
    routes = []
    
    # Группируем данные по маршрутам
    for route_id, route_stops in df.groupby('route_id'):
        stops = []
        segments = []
        prev_stop = None
        prev_arrival_time = None

        # Initialize start_time based on scheduled time of the first stop
        first_stop = route_stops.iloc[0]
        scheduled_time_minutes = first_stop['scheduled_time']
        start_time = datetime.now().replace(
            hour=int(scheduled_time_minutes // 60),
            minute=int(scheduled_time_minutes % 60),
            second=0, microsecond=0
        )

        for idx, row in route_stops.iterrows():
            # Если это первая остановка, предсказанное время в пути равно 0
            if idx == 0:
                predicted_travel_time = 0
            else:
                # Подготовка данных для предсказания
                features = pd.DataFrame([{
                    'scheduled_travel_time': row['scheduled_travel_time'],
                    'dwell_time_in_seconds': row['dwell_time_in_seconds'],
                    'segment_length': row['segment_length'],
                    'day_of_week': start_time.weekday(),
                    'hour_of_day': start_time.hour
                }])

                predicted_travel_time = model.predict(features)[0]

            arrival_time = start_time + timedelta(minutes=float(predicted_travel_time))
            
            stop = {
                "id": str(row['stop_id']),
                "name": row.get('address', f"Stop {row['stop_id']}"),
                "coordinates": [float(row['latitude']), float(row['longitude'])],
                "predictedArrivalTime": arrival_time.strftime("%H:%M")
            }

            if prev_stop and prev_arrival_time:
                travel_time = (arrival_time - prev_arrival_time).total_seconds() / 60
                segment = {
                    "from": prev_stop,
                    "to": stop,
                    "travelTime": round(travel_time, 2)
                }
                segments.append(segment)

            stops.append(stop)
            prev_stop = stop
            prev_arrival_time = arrival_time
            start_time = arrival_time + timedelta(seconds=float(row['dwell_time_in_seconds']))

        route = {
            "id": str(route_id),
            "name": f"Route {route_id}",
            "stops": stops,
            "segments": segments
        }
        routes.append(route)

    return routes

# Добавим новые модели данных
class StopCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    scheduled_time: str

class RouteCreate(BaseModel):
    name: str
    stops: List[StopCreate]

# Добавим новые эндпоинты
@app.post("/api/routes/create")
async def create_route(route: RouteCreate):
    try:
        global routes_data
        route_id = str(int(time.time()))
        
        # Преобразуем данные в формат DataFrame
        stops_data = []
        for idx, stop in enumerate(route.stops):
            stops_data.append({
                'route_id': route_id,
                'stop_id': idx + 1,
                'latitude': stop.latitude,
                'longitude': stop.longitude,
                'scheduled_time': time_to_minutes(stop.scheduled_time),
                'address': stop.name
            })
        
        new_route_df = pd.DataFrame(stops_data)
        
        # Добавляем необходимые колонки
        new_route_df['dwell_time_in_seconds'] = 30
        
        # Вычисляем длину сегментов
        new_route_df['segment_length'] = new_route_df.apply(
            lambda row: calculate_distance(
                row['latitude'], 
                row['longitude'],
                new_route_df.shift(1)['latitude'].iloc[0] if pd.notna(new_route_df.shift(1)['latitude'].iloc[0]) else row['latitude'],
                new_route_df.shift(1)['longitude'].iloc[0] if pd.notna(new_route_df.shift(1)['longitude'].iloc[0]) else row['longitude']
            ),
            axis=1
        )

        # Вычисляем scheduled_travel_time как разницу между временем текущей и предыдущей остановки
        new_route_df['scheduled_travel_time'] = new_route_df['scheduled_time'].diff()
        # Для первой остановки ставим 0
        new_route_df.loc[0, 'scheduled_travel_time'] = 0
        
        # Заполняем пропущенные значения средним временем
        mean_travel_time = new_route_df['scheduled_travel_time'].mean()
        new_route_df['scheduled_travel_time'] = new_route_df['scheduled_travel_time'].fillna(mean_travel_time)

        # Обработаем маршрут и добавим предсказания
        processed_route = process_data_with_predictions(new_route_df)[0]
        processed_route['name'] = route.name
        routes_data.append(processed_route)
        
        return {"success": True, "route": processed_route}
    except Exception as e:
        print(f"Error creating route: {str(e)}")  # Добавляем детальный вывод ошибки
        return {"error": f"Failed to create route: {str(e)}"}

def calculate_distance(lat1, lon1, lat2, lon2):
    # Простой расчет расстояния между координатами (можно улучшить)
    from math import sqrt
    return sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111  # приблизительно в км

@app.delete("/api/routes/{route_id}")
async def delete_route(route_id: str):
    try:
        global routes_data
        routes_data = [route for route in routes_data if route["id"] != route_id]
        return {"success": True}
    except Exception as e:
        print(f"Error deleting route: {e}")
        return {"error": f"Failed to delete route: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
