import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# this script was based on https://github.com/ale-jr/metro-sp-api

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Define the mapping for statuses
status_mapping = {
    "verde": "normal",
    "amarelo": "velocidade_reduzida",
    "cinza": "fechada",
    "vermelho": "paralizada",
}

@app.get("/")
async def index():
    return {'status': 'ok'}

@app.get("/metro-status")
async def get_metro_status(linhas: str = Query(None, description="Lista de linhas para filtrar, separadas por vírgula")):
    url = "https://www.viamobilidade.com.br/"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {e}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract the paragraph that contains "Atualizado em:"
    update_info = soup.select_one('.lines p strong')
    if not update_info:
        raise HTTPException(status_code=404, detail="Update time not found on the page")
    
    # Convert the update time to ISO 8601 format
    raw_date = update_info.get_text(strip=True)
    try:
        update_time = datetime.strptime(raw_date, "%d/%m/%Y %H:%M:%S").isoformat()
    except ValueError:
        raise HTTPException(status_code=500, detail="Failed to parse update time")

    # Convert the 'linhas' query parameter into a list of strings, if provided
    linhas_filtrar = [linha.strip().lower() for linha in linhas.split(",")] if linhas else None

    # Extract the status of each metro line
    lines_status = []
    lines = soup.select("ol.row li")

    if not lines:
        raise HTTPException(status_code=404, detail="Metro status not found on the page")

    # Iterate over each line and extract status
    for line in lines:
        line_name = line.find("span").get("title")
        status_div = line.find("div", class_="status")
        status_text = status_div.get_text(strip=True)
        status_color = status_div.get("class")[1]  # Get the color class

        # Map the status color to the standardized status
        standardized_status = status_mapping.get(status_color.lower(), "unknown")

        # Filtrar as linhas, se a lista de linhas a filtrar foi fornecida
        if linhas_filtrar and line_name.strip().lower() not in linhas_filtrar:
            continue

        lines_status.append({
            "linha": line_name,
            "status": standardized_status,
            "status_color": status_color,
            "status_text": status_text
        })

    return {
        "last_update": update_time,
        "metro_status": lines_status
    }

@app.get("/traffic-status")
async def get_traffic_status():
    origin = "Rua Estero Belaco 285, Saude, São Paulo, SP"
    destination = "Av. Imperatriz Leopoldina, 500 - Vila Leopoldina, São Paulo, SP"
    url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={origin.replace(' ', '+')}"
        f"&destination={destination.replace(' ', '+')}"
        f"&key={API_KEY}"
        f"&departure_time=now"
        f"&alternatives=true"
    )

    logger.debug(url)
    
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching traffic data: {e}")

    data = response.json()
    
    if data['status'] != 'OK':
        raise HTTPException(status_code=404, detail="Could not fetch traffic data")

    routes = []
    for route in data['routes']:
        leg = route['legs'][0]
        traffic_info = {
            "route_summary": route.get('summary', "No summary available"),
            "origin": leg['start_address'],
            "destination": leg['end_address'],
            "distance": leg['distance']['text'],
            "duration_without_traffic": leg['duration']['text'],
            "duration_in_traffic": leg.get('duration_in_traffic', {}).get('text', "No traffic data available"),
        }
        routes.append(traffic_info)

    return {"routes": routes}

if __name__ == "__main__":
    port = os.getenv("PORT") or 8080
    uvicorn.run(app, host="0.0.0.0", port=int(port))
