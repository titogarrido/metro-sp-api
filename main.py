import os
import uvicorn
from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
from datetime import datetime

app = FastAPI()

# this script was based on https://github.com/ale-jr/metro-sp-api

# Define the mapping for statuses
status_mapping = {
    "verde": "normal",
    "amarelo": "reduced_speed",
    "cinza": "closed",
    "vermelho": "paralyzed",
}

@app.get("/")
async def index():
    return {'status': 'ok'}

@app.get("/metro-status")
async def get_metro_status():
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

if __name__ == "__main__":
    port = os.getenv("PORT") or 8080
    uvicorn.run(app, host="0.0.0.0", port=int(port))