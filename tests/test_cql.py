"""
Tests for all CQL functions and operators supported by GeoServer.
Reference: http://udig.refractions.net/confluence/display/EN/Constraint+Query+Language.html

These tests verify that SQLAlchemy expressions compile into correct CQL filter strings.
They use mocked HTTP responses so no live GeoServer is required.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Integer, Float,
    select, text, and_, or_, not_, between, func
)


def _make_engine_and_table():
    """Create a mocked engine and a simple table for CQL compilation tests."""
    engine = create_engine("geoserver+http://localhost:8080/geoserver/test/ows")
    metadata = MetaData()
    t = Table("test_layer", metadata,
        Column("name", String),
        Column("city", String),
        Column("population", Integer),
        Column("area", Float),
        Column("geom", String),
        Column("date_col", String),
    )
    return engine, t


def _extract_cql(stmt, engine):
    """Compile a SQLAlchemy statement and extract the CQL filter from the JSON instruction."""
    compiled = stmt.compile(dialect=engine.dialect)
    instruction = json.loads(str(compiled))
    return instruction.get("cql_filter")


def _extract_instruction(stmt, engine):
    """Compile a SQLAlchemy statement and return the full JSON instruction."""
    compiled = stmt.compile(dialect=engine.dialect)
    return json.loads(str(compiled))


# ============================================================
# Comparison Operators: =, <>, <, >, <=, >=
# ============================================================

class TestComparisons:

    def test_equal(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.city == "Nelson")
        cql = _extract_cql(stmt, engine)
        assert cql == "city = 'Nelson'"

    def test_not_equal(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.city != "Nelson")
        cql = _extract_cql(stmt, engine)
        assert cql == "city <> 'Nelson'"

    def test_less_than(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.population < 10)
        cql = _extract_cql(stmt, engine)
        assert cql == "population < 10"

    def test_greater_than(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.population > 10)
        cql = _extract_cql(stmt, engine)
        assert cql == "population > 10"

    def test_less_equal(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.population <= 10)
        cql = _extract_cql(stmt, engine)
        assert cql == "population <= 10"

    def test_greater_equal(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.population >= 10)
        cql = _extract_cql(stmt, engine)
        assert cql == "population >= 10"


# ============================================================
# Text: LIKE, NOT LIKE, ILIKE
# ============================================================

class TestTextOperators:

    def test_like(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name.like("abc%"))
        cql = _extract_cql(stmt, engine)
        assert cql == "name LIKE 'abc%'"

    def test_not_like(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name.not_like("abc%"))
        cql = _extract_cql(stmt, engine)
        assert "NOT LIKE" in cql
        assert "'abc%'" in cql

    def test_ilike(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name.ilike("abc%"))
        cql = _extract_cql(stmt, engine)
        assert cql == "name ILIKE 'abc%'"

    def test_not_ilike(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name.not_ilike("abc%"))
        cql = _extract_cql(stmt, engine)
        assert "NOT ILIKE" in cql
        assert "'abc%'" in cql


# ============================================================
# Null: IS NULL, IS NOT NULL
# ============================================================

class TestNullChecks:

    def test_is_null(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name == None)
        cql = _extract_cql(stmt, engine)
        assert cql == "name IS NULL"

    def test_is_not_null(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name != None)
        cql = _extract_cql(stmt, engine)
        assert cql == "name IS NOT NULL"

    def test_is_null_explicit(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name.is_(None))
        cql = _extract_cql(stmt, engine)
        assert cql == "name IS NULL"

    def test_is_not_null_explicit(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name.is_not(None))
        cql = _extract_cql(stmt, engine)
        assert cql == "name IS NOT NULL"


# ============================================================
# Between
# ============================================================

class TestBetween:

    def test_between(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.population.between(10, 20))
        cql = _extract_cql(stmt, engine)
        assert "BETWEEN" in cql
        assert "10" in cql
        assert "20" in cql

    def test_not_between(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(~t.c.population.between(10, 20))
        cql = _extract_cql(stmt, engine)
        assert "NOT" in cql
        assert "BETWEEN" in cql


# ============================================================
# IN
# ============================================================

class TestIn:

    def test_in_list(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.city.in_(["Nelson", "Richmond", "Norfolk"]))
        cql = _extract_cql(stmt, engine)
        assert "IN" in cql
        assert "'Nelson'" in cql
        assert "'Richmond'" in cql
        assert "'Norfolk'" in cql

    def test_not_in_list(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.city.not_in(["Nelson", "Richmond"]))
        cql = _extract_cql(stmt, engine)
        assert "NOT IN" in cql
        assert "'Nelson'" in cql


# ============================================================
# Boolean Logic: AND, OR, NOT
# ============================================================

class TestBooleanLogic:

    def test_and(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(and_(t.c.population < 10, t.c.area > 100))
        cql = _extract_cql(stmt, engine)
        assert "population < 10" in cql
        assert "AND" in cql
        assert "area > 100" in cql

    def test_or(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(or_(t.c.city == "Nelson", t.c.city == "Norfolk"))
        cql = _extract_cql(stmt, engine)
        assert "city = 'Nelson'" in cql
        assert "OR" in cql
        assert "city = 'Norfolk'" in cql

    def test_not(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(not_(t.c.city == "Nelson"))
        cql = _extract_cql(stmt, engine)
        assert "city" in cql
        assert "Nelson" in cql
        # SQLAlchemy may render NOT(...) or city != 'Nelson'

    def test_compound_and_or(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(
            and_(
                t.c.population < 10,
                or_(
                    t.c.city == "Nelson",
                    t.c.area > 100
                )
            )
        )
        cql = _extract_cql(stmt, engine)
        assert "AND" in cql
        assert "OR" in cql


# ============================================================
# Spatial Relationships (via text())
# CQL spatial predicates: CONTAINS, CROSSES, INTERSECTS,
#   BBOX, DWITHIN, WITHIN, OVERLAPS, DISJOINT, TOUCHES
# ============================================================

class TestSpatialFunctions:

    def test_contains(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("CONTAINS(geom, POINT(1 2))"))
        cql = _extract_cql(stmt, engine)
        assert cql == "CONTAINS(geom, POINT(1 2))"

    def test_crosses(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("CROSSES(geom, LINESTRING(1 2, 10 15))"))
        cql = _extract_cql(stmt, engine)
        assert cql == "CROSSES(geom, LINESTRING(1 2, 10 15))"

    def test_intersects(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("INTERSECTS(geom, POINT(1 2))"))
        cql = _extract_cql(stmt, engine)
        assert cql == "INTERSECTS(geom, POINT(1 2))"

    def test_bbox(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("BBOX(geom, 10, 20, 30, 40)"))
        cql = _extract_cql(stmt, engine)
        assert cql == "BBOX(geom, 10, 20, 30, 40)"

    def test_dwithin(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("DWITHIN(geom, POINT(1 2), 10, kilometers)"))
        cql = _extract_cql(stmt, engine)
        assert cql == "DWITHIN(geom, POINT(1 2), 10, kilometers)"

    def test_within(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("WITHIN(geom, POLYGON((0 0, 10 0, 10 10, 0 10, 0 0)))"))
        cql = _extract_cql(stmt, engine)
        assert "WITHIN" in cql
        assert "POLYGON" in cql

    def test_overlaps(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("OVERLAPS(geom, POLYGON((0 0, 10 0, 10 10, 0 10, 0 0)))"))
        cql = _extract_cql(stmt, engine)
        assert "OVERLAPS" in cql

    def test_disjoint(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("DISJOINT(geom, POINT(1 2))"))
        cql = _extract_cql(stmt, engine)
        assert cql == "DISJOINT(geom, POINT(1 2))"

    def test_touches(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("TOUCHES(geom, POINT(1 2))"))
        cql = _extract_cql(stmt, engine)
        assert cql == "TOUCHES(geom, POINT(1 2))"

    def test_spatial_with_and(self):
        """Spatial filter combined with attribute filter."""
        engine, t = _make_engine_and_table()
        stmt = select(t).where(
            and_(
                text("INTERSECTS(geom, POINT(-76.28 36.84))"),
                t.c.city == "Norfolk"
            )
        )
        cql = _extract_cql(stmt, engine)
        assert "INTERSECTS" in cql
        assert "city = 'Norfolk'" in cql
        assert "AND" in cql


# ============================================================
# Temporal Predicates (via text())
#   BEFORE, AFTER, DURING
# ============================================================

class TestTemporalPredicates:

    def test_before(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("date_col BEFORE 2006-11-30T01:30:00Z"))
        cql = _extract_cql(stmt, engine)
        assert cql == "date_col BEFORE 2006-11-30T01:30:00Z"

    def test_after(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("date_col AFTER 2006-11-30T01:30:00Z"))
        cql = _extract_cql(stmt, engine)
        assert cql == "date_col AFTER 2006-11-30T01:30:00Z"

    def test_during(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("date_col DURING 2006-11-30T01:30:00Z/2006-12-31T01:30:00Z"))
        cql = _extract_cql(stmt, engine)
        assert cql == "date_col DURING 2006-11-30T01:30:00Z/2006-12-31T01:30:00Z"

    def test_before_period(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("date_col BEFORE 2006-11-30T01:30:00Z/2006-12-31T01:30:00Z"))
        cql = _extract_cql(stmt, engine)
        assert "BEFORE" in cql
        assert "2006-11-30" in cql

    def test_after_with_duration(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(text("date_col AFTER 2006-11-30T01:30:00Z/P10D"))
        cql = _extract_cql(stmt, engine)
        assert "AFTER" in cql
        assert "P10D" in cql


# ============================================================
# Limit and Offset
# ============================================================

class TestLimitOffset:

    def test_limit(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).limit(10)
        instruction = _extract_instruction(stmt, engine)
        assert instruction["limit"] == 10

    def test_offset(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).limit(10).offset(20)
        instruction = _extract_instruction(stmt, engine)
        assert instruction["limit"] == 10
        assert instruction["offset"] == 20


# ============================================================
# String Escaping
# ============================================================

class TestStringEscaping:

    def test_single_quote_in_value(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name == "O'Brien")
        cql = _extract_cql(stmt, engine)
        assert cql == "name = 'O''Brien'"

    def test_empty_string(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.name == "")
        cql = _extract_cql(stmt, engine)
        assert cql == "name = ''"


# ============================================================
# Table prefix stripping
# ============================================================

class TestTablePrefixStripping:

    def test_no_table_prefix_in_cql(self):
        """Verify that CQL filters don't contain table.column prefixes."""
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.city == "Nelson")
        cql = _extract_cql(stmt, engine)
        assert "test_layer." not in cql
        assert cql == "city = 'Nelson'"


# ============================================================
# Instruction structure
# ============================================================

class TestInstructionStructure:

    def test_basic_instruction(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).where(t.c.city == "Nelson").limit(5)
        instruction = _extract_instruction(stmt, engine)
        assert instruction["command"] == "GetFeatures"
        assert instruction["layer"] == "test_layer"
        assert instruction["cql_filter"] == "city = 'Nelson'"
        assert instruction["limit"] == 5
        assert "name" in instruction["columns"]

    def test_no_filter(self):
        engine, t = _make_engine_and_table()
        stmt = select(t).limit(1)
        instruction = _extract_instruction(stmt, engine)
        assert instruction["cql_filter"] is None
        assert instruction["limit"] == 1
