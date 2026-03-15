import json
import logging
import requests
from typing import Any, Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# DBAPI 2.0 attributes
apilevel = "2.0"
threadsafety = 1
paramstyle = "pyformat"

class Error(Exception):
    pass

class Warning(Exception):
    pass

class InterfaceError(Error):
    pass

class DatabaseError(Error):
    pass

class DataError(DatabaseError):
    pass

class OperationalError(DatabaseError):
    pass

class IntegrityError(DatabaseError):
    pass

class InternalError(DatabaseError):
    pass

class ProgrammingError(DatabaseError):
    pass

class NotSupportedError(DatabaseError):
    pass

def connect(*args, **kwargs):
    """
    Establish a connection to the GeoServer endpoint.
    kwargs should contain:
    - url: The base URL to the GeoServer workspace (e.g. http://localhost:8080/geoserver/workspace/ows)
    - headers: Optional dictionary of HTTP headers for authentication/etc.
    """
    url = kwargs.get('url')
    if not url:
        raise InterfaceError("Connection url is required")
    headers = kwargs.get('headers', {})
    timeout = kwargs.get('timeout', 30)
    return Connection(url, headers=headers, timeout=timeout)

class Connection:
    def __init__(self, url: str, headers: Dict[str, str] = None, timeout: int = 30):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.schemas = []
        self._closed = False

    def close(self):
        self._closed = True

    def commit(self):
        # Read-only, no-op
        pass

    def rollback(self):
        # Read-only, no-op
        pass

    def cursor(self):
        if self._closed:
            raise InterfaceError("Connection is closed")
        return Cursor(self)

class Cursor:
    def __init__(self, connection: Connection):
        self.connection = connection
        self.description = None
        self.rowcount = -1
        self.arraysize = 1
        self._closed = False
        self._results = []
        self._ptr = 0

    def close(self):
        self._closed = True

    def execute(self, operation: str, parameters: Optional[Dict] = None):
        if self._closed:
            raise InterfaceError("Cursor is closed")

        self.description = None
        self.rowcount = -1
        self._results = []
        self._ptr = 0

        # Replace parameters if present
        if parameters:
            # Poor man's parameter binding - the dialect compiler will handle most escaping,
            # but standard DBAPI execution paths might use this.
            for k, v in parameters.items():
                operation = operation.replace(f"%({k})s", str(v))

        # We expect the Dialect Compiler to pass a special JSON instruction for WFS requests
        try:
            instruction = json.loads(operation)
        except json.JSONDecodeError:
            # If not JSON, it could be a ping query or raw SQL that isn't supported
            if operation.strip().lower() in ("select 1", "ping"):
                self._results = [(1,)]
                self.description = (("1", None, None, None, None, None, None),)
                self.rowcount = 1
                return self
            raise NotSupportedError(f"Unsupported query operation (must be valid dialect JSON): {operation}")

        # Execute WFS Request
        command = instruction.get("command")
        if command == "GetFeatures":
            self._execute_get_features(instruction)
        elif command == "GetFields":
            self._execute_get_fields(instruction)
        elif command == "GetLayers":
            self._execute_get_layers(instruction)
        else:
            raise NotSupportedError(f"Unknown command: {command}")

        return self

    def _execute_get_features(self, instruction: dict):
        layer = instruction.get("layer")
        cql_filter = instruction.get("cql_filter")
        columns = instruction.get("columns", []) # Expected output columns
        limit = instruction.get("limit")
        offset = instruction.get("offset")

        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": layer,
            "outputFormat": "application/json"
        }
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        if limit is not None:
            params["maxFeatures"] = limit
        if offset is not None:
            params["startIndex"] = offset

        try:
            req = requests.Request('GET', self.connection.url, params=params, headers=self.connection.headers)
            prepared = req.prepare()
            logger.info("Requesting GeoServer URL: %s", prepared.url)
            
            resp = requests.Session().send(prepared, timeout=self.connection.timeout)
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                logger.error("GeoServer returned non-JSON response: %s", resp.text[:2000])
                raise OperationalError(f"GeoServer returned non-JSON response (status {resp.status_code}): {resp.text[:500]}")
        except OperationalError:
            raise
        except Exception as e:
            raise OperationalError(f"Failed to fetch from GeoServer: {e}")

        features = data.get("features", [])
        
        # Prepare description from columns
        # If no explicit columns are requested (SELECT *), we derive from the first feature
        if not columns and features:
            props = features[0].get("properties", {})
            columns = list(props.keys())
            # Usually we also want the geometry
            geometry_name = features[0].get("geometry_name", "geometry")
            columns.append(geometry_name)
        elif not columns:
            columns = []

        self.description = tuple((col, None, None, None, None, None, None) for col in columns)

        row_data = []
        for feature in features:
            props = feature.get("properties", {})
            geom = json.dumps(feature.get("geometry"))
            geom_name = feature.get("geometry_name", "geometry")
            
            row = []
            for col in columns:
                if col == geom_name:
                    row.append(geom)
                else:
                    row.append(props.get(col))
            row_data.append(tuple(row))

        self._results = row_data
        self.rowcount = len(row_data)

    def _execute_get_fields(self, instruction: dict):
        import re
        layer = instruction.get("layer")
        
        # First, try JSON output format
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "DescribeFeatureType",
            "typeName": layer,
            "outputFormat": "application/json"
        }

        try:
            req = requests.Request('GET', self.connection.url, params=params, headers=self.connection.headers)
            prepared = req.prepare()
            logger.info("Requesting GeoServer URL: %s", prepared.url)
            
            resp = requests.Session().send(prepared, timeout=self.connection.timeout)
            resp.raise_for_status()
            data = resp.json()
            
            feature_types = data.get("featureTypes", [])
            if feature_types:
                properties = feature_types[0].get("properties", [])
                self.description = (
                    ("name", None, None, None, None, None, None),
                    ("type", None, None, None, None, None, None),
                    ("localType", None, None, None, None, None, None),
                )
                row_data = []
                for prop in properties:
                    row_data.append((prop.get("name"), prop.get("type"), prop.get("localType")))
                self._results = row_data
                self.rowcount = len(row_data)
                return
        except Exception:
            logger.debug("JSON DescribeFeatureType failed, falling back to XML")

        # Fallback: request without outputFormat (returns XSD/XML)
        params_xml = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "DescribeFeatureType",
            "typeName": layer,
        }

        try:
            req = requests.Request('GET', self.connection.url, params=params_xml, headers=self.connection.headers)
            prepared = req.prepare()
            logger.info("Requesting GeoServer URL (XML fallback): %s", prepared.url)
            
            resp = requests.Session().send(prepared, timeout=self.connection.timeout)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            raise OperationalError(f"Failed to fetch DescribeFeatureType from GeoServer: {e}")

        # Parse XSD elements: <xsd:element name="..." type="..." .../>
        elements = re.findall(
            r'<xsd:element[^>]+name=["\']([^"\']+)["\'][^>]+type=["\']([^"\']+)["\']',
            text
        )

        self.description = (
            ("name", None, None, None, None, None, None),
            ("type", None, None, None, None, None, None),
            ("localType", None, None, None, None, None, None),
        )

        row_data = []
        for name, xsd_type in elements:
            # Derive a localType from the xsd type (e.g. "xsd:string" -> "string")
            local_type = xsd_type.split(":")[-1] if ":" in xsd_type else xsd_type
            row_data.append((name, xsd_type, local_type))

        self._results = row_data
        self.rowcount = len(row_data)

    def _execute_get_layers(self, instruction: dict):
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetCapabilities"
        }
        # A full implementation would parse XML from GetCapabilities, but GeoServer API might have a JSON equivalent,
        # or we just fetch layer list differently. For now, WFS 1.0.0 GetCapabilities is XML only usually.
        # WMS GetCapabilities can be JSON if configured, but let's parse the bare minimum XML or use REST API.
        # Actually, since GeoServer WFS GetCapabilities is XML, we can do a simple regex or use `xml.etree`.
        try:
            req = requests.Request('GET', self.connection.url, params=params, headers=self.connection.headers)
            prepared = req.prepare()
            logger.info("Requesting GeoServer URL: %s", prepared.url)

            resp = requests.Session().send(prepared, timeout=self.connection.timeout)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            raise OperationalError(f"Failed to fetch GetCapabilities from GeoServer: {e}")

        # Very naive XML parsing to find <Name> inside <FeatureType>
        import re
        # Find blocks of <FeatureType>...</FeatureType>
        feature_types = re.findall(r'<FeatureType>(.*?)</FeatureType>', text, re.DOTALL)
        layers = []
        for ft in feature_types:
            name_match = re.search(r'<Name>(.*?)</Name>', ft)
            if name_match:
                layers.append(name_match.group(1))

        self.description = (
            ("layer_name", None, None, None, None, None, None),
        )
        self._results = [(l,) for l in layers]
        self.rowcount = len(layers)

    def fetchmany(self, size: Optional[int] = None):
        if self._closed:
            raise InterfaceError("Cursor is closed")
        if size is None:
            size = self.arraysize
        res = self._results[self._ptr:self._ptr+size]
        self._ptr += size
        return res

    def fetchone(self):
        res = self.fetchmany(1)
        if res:
            return res[0]
        return None

    def fetchall(self):
        if self._closed:
            raise InterfaceError("Cursor is closed")
        res = self._results[self._ptr:]
        self._ptr = len(self._results)
        return res

    def executemany(self, operation: str, seq_of_parameters: List[Dict]):
        for parameters in seq_of_parameters:
            self.execute(operation, parameters)
