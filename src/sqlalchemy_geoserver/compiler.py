import json
import re
from sqlalchemy.sql.compiler import SQLCompiler, IdentifierPreparer
from sqlalchemy.sql import elements

class GeoServerIdentifierPreparer(IdentifierPreparer):
    # CQL identifiers do not need quoting unless they have special chars
    # We'll just strip quotes for safety
    def __init__(self, dialect, **kwargs):
        super().__init__(dialect, initial_quote="", final_quote="", escape_quote="", **kwargs)

    def format_column(self, column, use_table=False, name=None, table_name=None):
        return name or column.name

    def format_table(self, table, use_schema=False, name=None):
        return name or table.name


class GeoServerCompiler(SQLCompiler):

    def _strip_table_prefix(self, cql_filter, layer):
        """Remove table-name prefixes from column references in CQL.
        GeoServer CQL expects bare column names, not table.column."""
        if not cql_filter or not layer:
            return cql_filter
        # Remove "layer." prefix (e.g. "ne:countries.SOVEREIGNT" -> "SOVEREIGNT")
        cql_filter = cql_filter.replace(f"{layer}.", "")
        # Also handle case where only the short name is used as prefix
        short_name = layer.split(":")[-1] if ":" in layer else layer
        cql_filter = cql_filter.replace(f"{short_name}.", "")
        return cql_filter

    def visit_select(self, select_stmt, asfrom=False, **kwargs):
        # We need to compile the WHERE clause to CQL
        kwargs["literal_binds"] = True

        whereclause = select_stmt._whereclause
        cql_filter = self.process(whereclause, **kwargs) if whereclause is not None else None

        # Extract table/layer name
        froms = select_stmt.get_final_froms()
        layer = froms[0].name if froms else None

        # Strip table prefix from CQL filter — GeoServer expects bare column names
        cql_filter = self._strip_table_prefix(cql_filter, layer)

        # Extract columns
        columns = [c.name for c in select_stmt.inner_columns] if select_stmt.inner_columns else []

        limit = select_stmt._limit_clause
        offset = select_stmt._offset_clause

        limit_val = self.process(limit, **kwargs) if limit is not None else None
        offset_val = self.process(offset, **kwargs) if offset is not None else None

        instruction = {
            "command": "GetFeatures",
            "layer": layer,
            "cql_filter": cql_filter,
            "columns": columns
        }
        if limit_val is not None:
            instruction["limit"] = int(str(limit_val).strip("'"))
        if offset_val is not None:
            instruction["offset"] = int(str(offset_val).strip("'"))

        return json.dumps(instruction)

    def visit_bindparam(self, bindparam, within_columns_clause=False, **kwargs):
        # Enforce all bound parameters to be rendered as literals (CQL doesn't support parameterized queries)
        return self.render_literal_bindparam(bindparam, within_columns_clause=within_columns_clause, **kwargs)

    def render_literal_value(self, value, type_):
        if isinstance(value, str):
            val = value.replace("'", "''")
            return f"'{val}'"
        elif value is None:
            return "NULL"
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        return super().render_literal_value(value, type_)

    # --- Comparison operators (=, <>, <, >, <=, >=) ---
    # Handled by SQLAlchemy's default visit_binary — produces valid CQL output

    # --- LIKE / NOT LIKE ---
    def visit_like_op_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} LIKE {self.process(binary.right, **kw)}"

    def visit_not_like_op_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} NOT LIKE {self.process(binary.right, **kw)}"

    # --- ILIKE / NOT ILIKE (case-insensitive LIKE, GeoServer extension) ---
    def visit_ilike_op_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} ILIKE {self.process(binary.right, **kw)}"

    def visit_not_ilike_op_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} NOT ILIKE {self.process(binary.right, **kw)}"

    # --- BETWEEN ---
    def visit_between_op_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} BETWEEN {self.process(binary.right, **kw)}"

    def visit_not_between_op_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} NOT BETWEEN {self.process(binary.right, **kw)}"

    # --- IN / NOT IN ---
    def visit_in_op_binary(self, binary, operator, **kw):
        left = self.process(binary.left, **kw)
        right = self.process(binary.right, **kw)
        # Ensure parentheses wrap the value list
        if not right.startswith("("):
            right = f"({right})"
        return f"{left} IN {right}"

    def visit_not_in_op_binary(self, binary, operator, **kw):
        left = self.process(binary.left, **kw)
        right = self.process(binary.right, **kw)
        if not right.startswith("("):
            right = f"({right})"
        return f"{left} NOT IN {right}"

    # --- IS NULL / IS NOT NULL ---
    # SQLAlchemy's default rendering produces "col IS NULL" / "col IS NOT NULL" which is valid CQL

    # --- AND / OR / NOT ---
    # SQLAlchemy's default boolean logic rendering produces valid CQL

    # --- Spatial functions ---
    # Used via sqlalchemy.text() or sqlalchemy.func which pass through the compiler as-is.
    # Supported CQL spatial predicates:
    #   CONTAINS(geom, POINT(x y))
    #   CROSSES(geom, LINESTRING(x1 y1, x2 y2))
    #   INTERSECTS(geom, POINT(x y))
    #   BBOX(geom, x1, y1, x2, y2)
    #   DWITHIN(geom, POINT(x y), distance, units)
    #   WITHIN(geom, POLYGON(...))
    #   OVERLAPS(geom, POLYGON(...))
    #   DISJOINT(geom, POLYGON(...))
    #   TOUCHES(geom, POLYGON(...))

    # --- Temporal predicates ---
    # Used via sqlalchemy.text() because they use non-SQL syntax:
    #   ATTR BEFORE 2006-11-30T01:30:00Z
    #   ATTR AFTER 2006-11-30T01:30:00Z
    #   ATTR DURING 2006-11-30T01:30:00Z/2006-12-31T01:30:00Z

    # --- Not-Equal: CQL uses <> not != ---
    def visit_ne_binary(self, binary, operator, **kw):
        return f"{self.process(binary.left, **kw)} <> {self.process(binary.right, **kw)}"

    def visit_binary(self, binary, override_operator=None, eager_grouping=False, **kw):
        from sqlalchemy.sql import operators
        # Intercept != and rewrite to <>
        if binary.operator is operators.ne:
            return f"{self.process(binary.left, **kw)} <> {self.process(binary.right, **kw)}"
        return super().visit_binary(binary, override_operator, eager_grouping, **kw)
