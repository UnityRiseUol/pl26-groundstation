import os
import requests
from PIL import Image
from io import BytesIO
import math

# Tile source URL (OpenStreetMap or another provider)
TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

# Save folder
TILE_SAVE_PATH = "tiles"

# Zoom levels to download (for example, zoom 12 to 14)
ZOOM_LEVELS = [12, 13, 14]

# Coordinates for University of Liverpool area (approximate)
LAT = 53.4084
LON = -2.9916

# Tile size in pixels
TILE_SIZE = 256

# Function to calculate tile coordinates for a given latitude, longitude, and zoom level
def lat_lon_to_tile(lat, lon, zoom):
    x = (lon + 180) / 360 * (2 ** zoom)
    y = (1 - (math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi)) / 2 * (2 ** zoom)
    return int(x), int(y)

# Function to download a single tile
def download_tile(x, y, z):
    url = TILE_URL.format(s="a", x=x, y=y, z=z)
    response = requests.get(url)
    
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    else:
        print(f"Error fetching tile ({x}, {y}, {z})")
        return None

# Function to save tile as PNG
def save_tile(x, y, z, tile_image):
    if not os.path.exists(TILE_SAVE_PATH):
        os.makedirs(TILE_SAVE_PATH)
    
    file_path = os.path.join(TILE_SAVE_PATH, f"{z}_{x}_{y}.png")
    tile_image.save(file_path)
    print(f"Saved tile: {file_path}")

# Main function to download tiles in a bounding box
def download_tiles(lat, lon, zoom_levels):
    for zoom in zoom_levels:
        print(f"Downloading tiles for zoom level {zoom}...")
        
        # Get the tile coordinates for the bounding box
        tile_x, tile_y = lat_lon_to_tile(lat, lon, zoom)
        
        # Set a range of tile coordinates around the center point
        tile_range = 2  # Change this for more tiles in the area
        for dx in range(-tile_range, tile_range + 1):
            for dy in range(-tile_range, tile_range + 1):
                x = tile_x + dx
                y = tile_y + dy
                
                # Download the tile
                tile_image = download_tile(x, y, zoom)
                
                if tile_image:
                    save_tile(x, y, zoom, tile_image)

# Entry point
if __name__ == "__main__":
    download_tiles(LAT, LON, ZOOM_LEVELS)
