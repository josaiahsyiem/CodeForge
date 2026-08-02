FROM python:3.12-slim

# System libraries that geopandas/shapely/rasterio need
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev libgeos-dev libproj-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# The Python geo stack NLGeo uses
RUN pip install --no-cache-dir \
    geopandas shapely pandas numpy requests

# Non-root user for safety
RUN useradd -m runner