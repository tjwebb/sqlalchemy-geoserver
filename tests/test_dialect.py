import json
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, select, text

@patch('sqlalchemy_geoserver.dbapi.requests.Session.send')
def test_dbapi_get_features(mock_send):
    # Mock response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "features": [
            {
                "properties": {"id": 1, "name": "test_feature"},
                "geometry_name": "geom",
                "geometry": {"type": "Point", "coordinates": [10, 20]}
            }
        ]
    }
    mock_resp.status_code = 200
    mock_send.return_value = mock_resp

    engine = create_engine("geoserver+http://localhost:8080/geoserver/workspace/ows")
    
    with engine.connect() as conn:
        # direct dbapi execution via json string
        res = conn.execute(
            text(json.dumps({
                "command": "GetFeatures",
                "layer": "test_layer"
            }))
        )
        rows = res.fetchall()
        assert len(rows) == 1
        assert rows[0] == (1, 'test_feature', '{"type": "Point", "coordinates": [10, 20]}')


@patch('sqlalchemy_geoserver.dbapi.requests.Session.send')
def test_sqlalchemy_core_query(mock_send):
    # Testing the full SQLAlchemy compilation -> DBAPI mock flow
    # 1. Mock describe feature type (get_columns)
    mock_describe = MagicMock()
    mock_describe.json.return_value = {
        "featureTypes": [{
            "properties": [
                {"name": "id", "type": "xsd:int", "localType": "int"},
                {"name": "name", "type": "xsd:string", "localType": "string"}
            ]
        }]
    }

    # 2. Mock capabilities (has_table / get_table_names)
    mock_capabilities = MagicMock()
    mock_capabilities.text = "<FeatureType><Name>test_layer</Name></FeatureType>"

    # 3. Mock get_features
    mock_features = MagicMock()
    mock_features.json.return_value = {
        "features": [
            {
                "properties": {"id": 100, "name": "foo"},
                "geometry": None,
                "geometry_name": "geom"
            }
        ]
    }

    # Bind the mock based on the 'request' parameter
    def side_effect(prepared_request, **kwargs):
        req = prepared_request.url
        if "DescribeFeatureType" in req:
            return mock_describe
        elif "GetCapabilities" in req:
            return mock_capabilities
        elif "GetFeature" in req:
            return mock_features
        raise ValueError(f"Unknown request {req}")

    mock_send.side_effect = side_effect

    engine = create_engine("geoserver+http://localhost:8080/geoserver/workspace/ows")
    metadata = MetaData()
    test_table = Table('test_layer', metadata, autoload_with=engine)

    assert 'name' in test_table.c

    stmt = select(test_table).where(test_table.c.name == 'foo').limit(10)

    # When we execute, it goes to GeoServerCompiler which generates JSON
    # which is passed to dbapi.Cursor.execute
    with engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()
        assert len(rows) == 1
        assert rows[0] == (100, 'foo')
        
    # Verify the parameters passed in the WFS GetFeature call
    calls = mock_send.call_args_list
    get_feature_call = [c for c in calls if "GetFeature" in c[0][0].url][0]
    wfs_url = get_feature_call[0][0].url
    
    assert 'typeName=test_layer' in wfs_url
    assert 'maxFeatures=10' in wfs_url
    
    # Asserting CQL filter compilation!
    assert 'CQL_FILTER=name+%3D+%27foo%27' in wfs_url
