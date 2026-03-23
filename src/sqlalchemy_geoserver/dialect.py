import json
import sqlalchemy
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.types import TypeEngine, UserDefinedType
from .compiler import GeoServerCompiler, GeoServerIdentifierPreparer

# Geometry type names returned by GeoServer DescribeFeatureType
GEOMETRY_TYPE_NAMES = {
    "geometry", "point", "linestring", "polygon",
    "multipoint", "multilinestring", "multipolygon",
    "geometrycollection", "curve", "surface", "multisurface", "multicurve",
}


class GeoJSON(UserDefinedType):
    """Custom SQLAlchemy type that deserializes GeoServer geometry values
    into GeoJSON dicts."""
    cache_ok = True

    def get_col_spec(self):
        return "GEOMETRY"

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return value
        return process

class GeoServerDialect(DefaultDialect):
    name = "geoserver"
    driver = "rest"
    
    statement_compiler = GeoServerCompiler
    preparer = GeoServerIdentifierPreparer
    
    supports_alter = False
    supports_sane_rowcount = False
    supports_statement_cache = False
    supports_default_values = False
    supports_empty_insert = False
    
    # DBAPI class mapping
    @classmethod
    def import_dbapi(cls):
        from . import dbapi
        return dbapi

    def create_connect_args(self, url):
        # Example url: geoserver+http://localhost/geoserver/workspace/ows
        # We strip the "geoserver+" from the URL to pass to Requests
        drivername = url.drivername
        if drivername.startswith("geoserver+"):
            protocol = drivername.split("+")[1]
            base_url = f"{protocol}://{url.host}"
            if url.port:
                base_url += f":{url.port}"
            if url.database:
                base_url += f"/{url.database}"
        else:
            base_url = f"http://{url.host}"
            if url.port:
                base_url += f":{url.port}"
            if url.database:
                base_url += f"/{url.database}"
        
        args = []
        kwargs = {
            "url": base_url,
        }
        # If connect_args includes 'headers', it will be passed by create_engine
        return args, kwargs

    def get_schema_names(self, connection, **kw):
        return ["default"]

    def has_table(self, connection, table_name, schema=None, **kw):
        # First check against GetCapabilities layer list
        instruction = json.dumps({"command": "GetLayers"})
        cursor = connection.exec_driver_sql(instruction)
        layers = [row[0] for row in cursor.fetchall()]
        
        # Exact match
        if table_name in layers:
            return True
        
        # Try matching with/without workspace prefix
        # e.g. table_name="ne:countries" might be listed as "countries" or vice versa
        for layer in layers:
            # Strip workspace prefix for comparison
            layer_short = layer.split(":")[-1] if ":" in layer else layer
            table_short = table_name.split(":")[-1] if ":" in table_name else table_name
            if layer_short == table_short:
                return True
        
        # Final fallback: try DescribeFeatureType directly
        try:
            desc_instruction = json.dumps({"command": "GetFields", "layer": table_name})
            desc_cursor = connection.exec_driver_sql(desc_instruction)
            rows = desc_cursor.fetchall()
            return len(rows) > 0
        except Exception:
            return False

    def get_table_names(self, connection, schema=None, **kw):
        instruction = json.dumps({"command": "GetLayers"})
        cursor = connection.exec_driver_sql(instruction)
        return [row[0] for row in cursor.fetchall()]

    def get_columns(self, connection, table_name, schema=None, **kw):
        # Ask GeoServer for fields using DescribeFeatureType
        instruction = json.dumps({
            "command": "GetFields",
            "layer": table_name
        })
        cursor = connection.exec_driver_sql(instruction)
        columns = []
        for row in cursor.fetchall():
            name, type_str, localType = row
            # Simple mapping from XSD types to SQLAlchemy types
            # localType usually contains "int", "string", "Geometry", etc.
            type_str_lower = (localType or type_str or "").lower()
            
            if type_str_lower in GEOMETRY_TYPE_NAMES or "gml:" in (type_str or "").lower():
                col_type = GeoJSON
            elif "int" in type_str_lower or "long" in type_str_lower:
                col_type = sqlalchemy.types.Integer
            elif "float" in type_str_lower or "double" in type_str_lower or "decimal" in type_str_lower:
                col_type = sqlalchemy.types.Float
            elif "date" in type_str_lower or "time" in type_str_lower:
                col_type = sqlalchemy.types.DateTime
            else:
                col_type = sqlalchemy.types.String
                
            columns.append({
                "name": name,
                "type": col_type,
                "nullable": True,
                "default": None,
            })
        return columns

    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        return {"constrained_columns": [], "name": None}

    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        return []

    def get_indexes(self, connection, table_name, schema=None, **kw):
        return []

    def do_ping(self, dbapi_connection):
        try:
            # We can issue a simple capabilities request
            cursor = dbapi_connection.cursor()
            cursor.execute(json.dumps({"command": "GetLayers"}))
            return True
        except Exception:
            return False
