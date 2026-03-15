import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select

# Load environment variables from .env.test if it exists
load_dotenv(".env.test")

# To run these tests, you must set the GEOSERVER_URL environment variable.
# Example: export GEOSERVER_URL="geoserver+http://localhost:8080/geoserver/workspace/ows"
# Example: export GEOSERVER_LAYER="workspace:layer_name"
# Example: export GEOSERVER_AUTH_HEADER="Bearer token123"
GEOSERVER_URL = os.environ.get("GEOSERVER_URL")
GEOSERVER_LAYER = os.environ.get("GEOSERVER_LAYER")
GEOSERVER_AUTH_HEADER = os.environ.get("GEOSERVER_AUTH_HEADER")

pytestmark = pytest.mark.skipif(
    not GEOSERVER_URL or not GEOSERVER_LAYER, 
    reason="GEOSERVER_URL and GEOSERVER_LAYER environment variables must be set for integration tests"
)

@pytest.fixture(scope="module")
def engine():
    kwargs = {
        "connect_args": {
            "timeout": 300
        }
    }
    if GEOSERVER_AUTH_HEADER:
        kwargs["connect_args"]["headers"] = {"Authorization": GEOSERVER_AUTH_HEADER}
        
    return create_engine(GEOSERVER_URL, **kwargs)

@pytest.fixture(scope="module")
def layer_table(engine):
    metadata = MetaData()
    # autoload_with will trigger GetCapabilities and DescribeFeatureType
    return Table(GEOSERVER_LAYER, metadata, autoload_with=engine)

def test_reflection(layer_table):
    # If the table reflected successfully, we should have columns
    assert len(layer_table.columns) > 0
    # Every WFS layer typically has a geometry column
    col_names = [c.name for c in layer_table.columns]
    assert len(col_names) > 0

def test_get_capabilities(engine):
    """Prints the raw GetCapabilities response for debugging."""
    import json
    import requests

    # Build the raw URL from the engine
    raw_conn = engine.raw_connection()
    url = raw_conn.url
    headers = raw_conn.headers
    timeout = raw_conn.timeout
    raw_conn.close()

    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetCapabilities",
    }
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()

    print("\n===== GetCapabilities Response =====")
    print(resp.text[:5000])  # Print first 5000 chars to avoid flooding
    print("===== End GetCapabilities =====\n")

    # Also print parsed layer names
    import re
    feature_types = re.findall(r'<FeatureType>(.*?)</FeatureType>', resp.text, re.DOTALL)
    layers = []
    for ft in feature_types:
        name_match = re.search(r'<Name>(.*?)</Name>', ft)
        if name_match:
            layers.append(name_match.group(1))
    
    print(f"Parsed {len(layers)} layers:")
    for layer in layers:
        print(f"  - {layer}")

    assert resp.status_code == 200

def test_select_limit(engine, layer_table):
    # Test a basic query fetching just 1 record 
    stmt = select(layer_table).limit(1)
    
    with engine.connect() as conn:
        result = conn.execute(stmt).fetchall()
        assert len(result) <= 1

def test_select_where(engine, layer_table):
    # Try to filter by the first non-geometry string column found in the layer
    str_col = None
    geom_col_name = None
    
    # Simple check for geom cols
    for col in layer_table.columns:
        if str(col.type) == "VARCHAR" and "geom" not in col.name.lower():
            str_col = col
            break
            
    if str_col is None:
        pytest.skip("No non-geometry string column found in the layer to test WHERE clause")

    # Fetch 1 row to get a valid value
    stmt_first = select(str_col.label('test_val')).limit(1)
    with engine.connect() as conn:
        first_row = conn.execute(stmt_first).fetchone()
        
    if not first_row or first_row[0] is None:
        pytest.skip("No data available to filter on")

    test_value = first_row[0]
    
    # Exclude single quotes inside the string itself which breaks simple CQL building without escape
    test_value = test_value.replace("'", "")
    
    # Now build the WHERE query
    stmt = select(layer_table).where(str_col == test_value).limit(10)
    
    with engine.connect() as conn:
        result = conn.execute(stmt).fetchall()
        
        assert len(result) > 0
        for row in result:
            # Check that the returned rows actually match the filter
            row_dict = row._mapping
            assert row_dict[str_col.name] == test_value

def test_countries_usa(engine):
    """Query ne:countries where SOVEREIGNT = 'United States of America'."""
    metadata = MetaData()
    countries = Table("ne:countries", metadata, autoload_with=engine)

    stmt = select(countries).where(countries.c.SOVEREIGNT == "United States of America").limit(10)

    with engine.connect() as conn:
        result = conn.execute(stmt).fetchall()
        print(f"\nFound {len(result)} rows for SOVEREIGNT = 'United States of America'")
        for row in result:
            print(dict(row._mapping))
        assert len(result) > 0
