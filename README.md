# SQLAlchemy GeoServer Dialect

[![PyPI](https://img.shields.io/pypi/v/sqlalchemy-geoserver)](https://pypi.org/project/sqlalchemy-geoserver/)

A DB-API 2.0 driver and a SQLAlchemy Dialect designed to query GeoServer WFS layers using pseudo-SQL converted to valid underlying HTTP `CQL_FILTER` queries.

## Installation

```bash
pip install sqlalchemy-geoserver
```

*(Note: In the root of this repository, you may install locally using `pip install -e .`)*

## Connection String

The SQLAlchemy engine is created using the scheme `geoserver+http://` or `geoserver+https://`. Provide the base URL to your GeoServer workspace's WFS endpoint:

```python
engine = create_engine(
    "geoserver+http://localhost:8080/geoserver/workspace/ows"
)
```

If your GeoServer instance requires an authorization header, pass it via `connect_args`:

```python
engine = create_engine(
    "geoserver+https://geoserver.example.com/geoserver/workspace/ows",
    connect_args={"headers": {"Authorization": "Bearer token123"}}
)
```

## Usage

This driver acts as a "Read Only" interface fetching a `FeatureCollection` from a GeoServer WFS API request. It parses standard SQL `SELECT` queries that use standard logical operators (`==`, `!=`, `<`, `>`, `IN`, `LIKE`, etc.) and translates those to their equivalent GeoServer **CQL**.

```python
from sqlalchemy import create_engine, MetaData, Table, select

# Create an engine to the geoserver host and specific workspace/layer path
engine = create_engine(
    "geoserver+http://localhost:8080/geoserver/workspace/ows"
)

# You can also pass authentication headers if required
# engine = create_engine(
#     "geoserver+https://geoserver.example.com/geoserver/workspace/ows",
#     connect_args={"headers": {"Authorization": "Bearer token123"}}
# )

metadata = MetaData()
metadata.reflect(bind=engine)

# Tables correspond to the layer names available at that endpoint
# Assuming there is a layer named 'layer_name'
layer_table = Table('layer_name', metadata, autoload_with=engine)

# Standard SQLAlchemy core query
stmt = select(layer_table).where(layer_table.c.property_name == 'value')

with engine.connect() as conn:
    results = conn.execute(stmt).fetchall()
    for row in results:
        print(row._mapping)
```

## Local GeoServer Setup

To run a local GeoServer instance using Docker:

```bash
docker run -d -p 8080:8080 --name geoserver \
  -v ./geoserver_data/:/opt/geoserver_data \
  docker.osgeo.org/geoserver:3.0.x
```

GeoServer will be available at `http://localhost:8080/geoserver`. The WFS endpoint for a workspace named `myworkspace` would be:

```
geoserver+http://localhost:8080/geoserver/myworkspace/ows
```
