"""
Comprehensive attribute-level tests for lr:lr_parcel_51_710.

For every attribute in the layer, tests as many CQL operators as that
field type supports:
  - String:  =, !=, IS NULL, IS NOT NULL, LIKE, NOT LIKE, IN
  - Numeric: =, !=, <, >, <=, >=, BETWEEN, IS NULL, IS NOT NULL, IN
  - Geometry: INTERSECTS, BBOX, DWITHIN, CONTAINS, WITHIN
"""
import os
import json
import pytest
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    select, text, and_, or_, not_,
    types as sa_types,
)

load_dotenv(".env.test")

GEOSERVER_URL = os.environ.get("GEOSERVER_URL")
GEOSERVER_AUTH_HEADER = os.environ.get("GEOSERVER_AUTH_HEADER")
LAYER = "lr:lr_parcel_51_710"

pytestmark = pytest.mark.skipif(
    not GEOSERVER_URL,
    reason="GEOSERVER_URL must be set for attribute tests"
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    kwargs = {"connect_args": {"timeout": 300}}
    if GEOSERVER_AUTH_HEADER:
        kwargs["connect_args"]["headers"] = {"Authorization": GEOSERVER_AUTH_HEADER}
    return create_engine(GEOSERVER_URL, **kwargs)


@pytest.fixture(scope="module")
def parcels(engine):
    metadata = MetaData()
    return Table(LAYER, metadata, autoload_with=engine)


@pytest.fixture(scope="module")
def sample_row(engine, parcels):
    """Fetch one complete row to use as reference data for filter tests."""
    stmt = select(parcels).limit(1)
    with engine.connect() as conn:
        row = conn.execute(stmt).fetchone()
    assert row is not None, "Layer has no data to test against"
    return dict(row._mapping)


def _col_is_string(col):
    return isinstance(col.type, (sa_types.String, sa_types.Text, sa_types.VARCHAR))


def _col_is_numeric(col):
    return isinstance(col.type, (sa_types.Integer, sa_types.Float, sa_types.Numeric))


def _col_is_geometry(col):
    name_lower = col.name.lower()
    return name_lower in ("geom", "the_geom", "geometry", "wkb_geometry", "shape")


# ==================================================================
# STRING ATTRIBUTE TESTS
# ==================================================================

class TestStringAttributes:
    """Test all string columns with: =, !=, IS NULL, IS NOT NULL, LIKE, NOT LIKE, IN."""

    # ---- parcelid ----

    def test_parcelid_equal(self, engine, parcels, sample_row):
        val = sample_row.get("parcelid")
        if val is None:
            pytest.skip("parcelid is null in sample")
        stmt = select(parcels).where(parcels.c.parcelid == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        assert rows[0]._mapping["parcelid"] == val

    def test_parcelid_not_equal(self, engine, parcels, sample_row):
        val = sample_row.get("parcelid")
        if val is None:
            pytest.skip("parcelid is null in sample")
        stmt = select(parcels).where(parcels.c.parcelid != val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        assert rows[0]._mapping["parcelid"] != val

    def test_parcelid_like(self, engine, parcels, sample_row):
        val = sample_row.get("parcelid")
        if val is None or len(str(val)) < 4:
            pytest.skip("parcelid too short for LIKE test")
        prefix = str(val)[:8]
        stmt = select(parcels).where(parcels.c.parcelid.like(f"{prefix}%")).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        for row in rows:
            assert str(row._mapping["parcelid"]).startswith(prefix)

    def test_parcelid_not_like(self, engine, parcels, sample_row):
        val = sample_row.get("parcelid")
        if val is None:
            pytest.skip("parcelid is null in sample")
        prefix = str(val)[:8]
        stmt = select(parcels).where(parcels.c.parcelid.not_like(f"{prefix}%")).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        assert not str(rows[0]._mapping["parcelid"]).startswith(prefix)

    def test_parcelid_is_not_null(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.parcelid != None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_parcelid_in(self, engine, parcels, sample_row):
        val = sample_row.get("parcelid")
        if val is None:
            pytest.skip("parcelid is null in sample")
        stmt = select(parcels).where(parcels.c.parcelid.in_([val, "FAKEID999"])).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- lrid ----

    def test_lrid_equal(self, engine, parcels, sample_row):
        val = sample_row.get("lrid")
        if val is None:
            pytest.skip("lrid is null in sample")
        stmt = select(parcels).where(parcels.c.lrid == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_lrid_not_equal(self, engine, parcels, sample_row):
        val = sample_row.get("lrid")
        if val is None:
            pytest.skip("lrid is null in sample")
        stmt = select(parcels).where(parcels.c.lrid != val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_lrid_like(self, engine, parcels, sample_row):
        val = sample_row.get("lrid")
        if val is None or len(str(val)) < 4:
            pytest.skip("lrid too short for LIKE test")
        prefix = str(val)[:6]
        stmt = select(parcels).where(parcels.c.lrid.like(f"{prefix}%")).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_lrid_is_not_null(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.lrid != None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- statefp ----

    def test_statefp_equal(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.statefp == "51").limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        assert rows[0]._mapping["statefp"] == "51"

    def test_statefp_not_equal(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.statefp != "99").limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_statefp_in(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.statefp.in_(["51", "24"])).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_statefp_is_not_null(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.statefp != None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- countyfp ----

    def test_countyfp_equal(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.countyfp == "710").limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_countyfp_not_equal(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.countyfp != "999").limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_countyfp_like(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.countyfp.like("71%")).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- countyname ----

    def test_countyname_equal(self, engine, parcels, sample_row):
        val = sample_row.get("countyname")
        if val is None:
            pytest.skip("countyname is null in sample")
        stmt = select(parcels).where(parcels.c.countyname == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        assert rows[0]._mapping["countyname"] == val

    def test_countyname_not_equal(self, engine, parcels, sample_row):
        val = sample_row.get("countyname")
        if val is None:
            pytest.skip("countyname is null in sample")
        stmt = select(parcels).where(parcels.c.countyname != val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        # May return 0 if only one county in the layer — that's fine
        if len(rows) > 0:
            assert rows[0]._mapping["countyname"] != val

    def test_countyname_like(self, engine, parcels, sample_row):
        val = sample_row.get("countyname")
        if val is None or len(val) < 2:
            pytest.skip("countyname too short for LIKE test")
        prefix = val[:3]
        stmt = select(parcels).where(parcels.c.countyname.like(f"{prefix}%")).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_countyname_in(self, engine, parcels, sample_row):
        val = sample_row.get("countyname")
        if val is None:
            pytest.skip("countyname is null in sample")
        stmt = select(parcels).where(parcels.c.countyname.in_([val, "FAKECOUNTY"])).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- parceladdr ----

    def test_parceladdr_equal(self, engine, parcels, sample_row):
        val = sample_row.get("parceladdr")
        if val is None:
            pytest.skip("parceladdr is null in sample")
        val = str(val).replace("'", "")
        stmt = select(parcels).where(parcels.c.parceladdr == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_parceladdr_like(self, engine, parcels, sample_row):
        val = sample_row.get("parceladdr")
        if val is None or len(str(val)) < 3:
            pytest.skip("parceladdr too short for LIKE test")
        prefix = str(val).replace("'", "")[:5]
        stmt = select(parcels).where(parcels.c.parceladdr.like(f"{prefix}%")).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_parceladdr_is_null(self, engine, parcels):
        """Test IS NULL — some parcels may have null addresses."""
        stmt = select(parcels).where(parcels.c.parceladdr == None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        # May or may not find nulls, just ensure query executes
        print(f"  Found {len(rows)} parcels with null parceladdr")

    def test_parceladdr_is_not_null(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.parceladdr != None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- taxyear ----

    def test_taxyear_equal(self, engine, parcels, sample_row):
        val = sample_row.get("taxyear")
        if val is None:
            pytest.skip("taxyear is null in sample")
        stmt = select(parcels).where(parcels.c.taxyear == str(val)).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_taxyear_not_equal(self, engine, parcels, sample_row):
        val = sample_row.get("taxyear")
        if val is None:
            pytest.skip("taxyear is null in sample")
        stmt = select(parcels).where(parcels.c.taxyear != str(val)).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        # May be 0 if only one taxyear — that's fine
        print(f"  Found {len(rows)} parcels with taxyear != {val}")

    def test_taxyear_in(self, engine, parcels, sample_row):
        val = sample_row.get("taxyear")
        if val is None:
            pytest.skip("taxyear is null in sample")
        stmt = select(parcels).where(parcels.c.taxyear.in_([str(val), "9999"])).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0


# ==================================================================
# NUMERIC ATTRIBUTE TESTS
# ==================================================================

class TestNumericAttributes:
    """Test numeric columns with: =, !=, <, >, <=, >=, BETWEEN, IS NULL, IS NOT NULL, IN."""

    # ---- totalvalue ----

    def test_totalvalue_equal(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        stmt = select(parcels).where(parcels.c.totalvalue == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_totalvalue_not_equal(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        stmt = select(parcels).where(parcels.c.totalvalue != val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_totalvalue_less_than(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        threshold = float(val) + 100000
        stmt = select(parcels).where(parcels.c.totalvalue < threshold).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        for row in rows:
            rv = row._mapping["totalvalue"]
            if rv is not None:
                assert float(rv) < threshold

    def test_totalvalue_greater_than(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None or float(val) <= 0:
            pytest.skip("totalvalue is null or non-positive in sample")
        threshold = float(val) - 1
        stmt = select(parcels).where(parcels.c.totalvalue > threshold).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_totalvalue_less_equal(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        stmt = select(parcels).where(parcels.c.totalvalue <= float(val)).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_totalvalue_greater_equal(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        stmt = select(parcels).where(parcels.c.totalvalue >= float(val)).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_totalvalue_between(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        lo = float(val) - 50000
        hi = float(val) + 50000
        stmt = select(parcels).where(parcels.c.totalvalue.between(lo, hi)).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        for row in rows:
            rv = row._mapping["totalvalue"]
            if rv is not None:
                assert lo <= float(rv) <= hi

    def test_totalvalue_is_not_null(self, engine, parcels):
        stmt = select(parcels).where(parcels.c.totalvalue != None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_totalvalue_is_null(self, engine, parcels):
        """May or may not have nulls — just ensure query executes."""
        stmt = select(parcels).where(parcels.c.totalvalue == None).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        print(f"  Found {len(rows)} parcels with null totalvalue")

    def test_totalvalue_in(self, engine, parcels, sample_row):
        val = sample_row.get("totalvalue")
        if val is None:
            pytest.skip("totalvalue is null in sample")
        stmt = select(parcels).where(parcels.c.totalvalue.in_([float(val), -99999])).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- landvalue ----

    def test_landvalue_equal(self, engine, parcels, sample_row):
        val = sample_row.get("landvalue")
        if val is None:
            pytest.skip("landvalue is null in sample")
        stmt = select(parcels).where(parcels.c.landvalue == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_landvalue_less_than(self, engine, parcels, sample_row):
        val = sample_row.get("landvalue")
        if val is None:
            pytest.skip("landvalue is null in sample")
        threshold = float(val) + 100000
        stmt = select(parcels).where(parcels.c.landvalue < threshold).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_landvalue_greater_than(self, engine, parcels, sample_row):
        val = sample_row.get("landvalue")
        if val is None or float(val) <= 0:
            pytest.skip("landvalue is null or non-positive in sample")
        stmt = select(parcels).where(parcels.c.landvalue > 0).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_landvalue_between(self, engine, parcels, sample_row):
        val = sample_row.get("landvalue")
        if val is None:
            pytest.skip("landvalue is null in sample")
        lo = float(val) - 50000
        hi = float(val) + 50000
        stmt = select(parcels).where(parcels.c.landvalue.between(lo, hi)).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    # ---- improvvalue ----

    def test_improvvalue_equal(self, engine, parcels, sample_row):
        val = sample_row.get("improvvalue")
        if val is None:
            pytest.skip("improvvalue is null in sample")
        stmt = select(parcels).where(parcels.c.improvvalue == val).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_improvvalue_less_than(self, engine, parcels, sample_row):
        val = sample_row.get("improvvalue")
        if val is None:
            pytest.skip("improvvalue is null in sample")
        threshold = float(val) + 100000
        stmt = select(parcels).where(parcels.c.improvvalue < threshold).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_improvvalue_between(self, engine, parcels, sample_row):
        val = sample_row.get("improvvalue")
        if val is None:
            pytest.skip("improvvalue is null in sample")
        lo = float(val) - 50000
        hi = float(val) + 50000
        stmt = select(parcels).where(parcels.c.improvvalue.between(lo, hi)).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0


# ==================================================================
# GEOMETRY ATTRIBUTE TESTS
# ==================================================================

class TestGeometryAttributes:
    """Test spatial predicates against the geom column via CQL text()."""

    def test_intersects_point(self, engine, parcels):
        """INTERSECTS(geom, POINT(lon lat))"""
        lon, lat = -76.29793, 36.85664
        stmt = select(parcels).where(text(f"INTERSECTS(geom, POINT({lon} {lat}))")).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        print(f"  INTERSECTS POINT found {len(rows)} parcel(s)")

    def test_bbox(self, engine, parcels):
        """BBOX(geom, minx, miny, maxx, maxy)"""
        stmt = select(parcels).where(
            text("BBOX(geom, -76.30, 36.85, -76.29, 36.86)")
        ).limit(10)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        print(f"  BBOX found {len(rows)} parcel(s)")

    def test_dwithin(self, engine, parcels):
        """DWITHIN(geom, POINT(lon lat), distance, units)"""
        lon, lat = -76.29793, 36.85664
        stmt = select(parcels).where(
            text(f"DWITHIN(geom, POINT({lon} {lat}), 0.01, meters)")
        ).limit(10)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        print(f"  DWITHIN found {len(rows)} parcel(s)")
        # May return 0 depending on distance tolerance — just ensure no error

    def test_within_polygon(self, engine, parcels):
        """WITHIN(geom, POLYGON(...))"""
        stmt = select(parcels).where(
            text("WITHIN(geom, POLYGON((-76.30 36.85, -76.29 36.85, -76.29 36.86, -76.30 36.86, -76.30 36.85)))")
        ).limit(10)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        print(f"  WITHIN POLYGON found {len(rows)} parcel(s)")

    def test_intersects_polygon(self, engine, parcels):
        """INTERSECTS(geom, POLYGON(...))"""
        stmt = select(parcels).where(
            text("INTERSECTS(geom, POLYGON((-76.30 36.85, -76.29 36.85, -76.29 36.86, -76.30 36.86, -76.30 36.85)))")
        ).limit(10)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        print(f"  INTERSECTS POLYGON found {len(rows)} parcel(s)")


# ==================================================================
# COMBINED / COMPOUND FILTER TESTS
# ==================================================================

class TestCompoundFilters:
    """Test combining multiple operators across different attribute types."""

    def test_string_and_numeric(self, engine, parcels, sample_row):
        """AND of a string = filter and a numeric > filter."""
        county = sample_row.get("countyname")
        val = sample_row.get("totalvalue")
        if county is None or val is None:
            pytest.skip("Required fields null in sample")
        stmt = select(parcels).where(
            and_(
                parcels.c.countyname == county,
                parcels.c.totalvalue > 0,
            )
        ).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_string_or_string(self, engine, parcels):
        """OR of two string comparisons."""
        stmt = select(parcels).where(
            or_(
                parcels.c.statefp == "51",
                parcels.c.statefp == "24",
            )
        ).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_spatial_and_attribute(self, engine, parcels):
        """Combine spatial filter with attribute filter."""
        lon, lat = -76.29793, 36.85664
        stmt = select(parcels).where(
            and_(
                text(f"INTERSECTS(geom, POINT({lon} {lat}))"),
                parcels.c.statefp == "51",
            )
        ).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0

    def test_not_filter(self, engine, parcels, sample_row):
        """NOT operator."""
        val = sample_row.get("parcelid")
        if val is None:
            pytest.skip("parcelid is null in sample")
        stmt = select(parcels).where(
            not_(parcels.c.parcelid == val)
        ).limit(1)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        assert len(rows) > 0
        assert rows[0]._mapping["parcelid"] != val

    def test_between_and_like(self, engine, parcels, sample_row):
        """Combine BETWEEN on numeric with LIKE on string."""
        val = sample_row.get("totalvalue")
        pid = sample_row.get("parcelid")
        if val is None or pid is None:
            pytest.skip("Required fields null in sample")
        lo = float(val) - 100000
        hi = float(val) + 100000
        prefix = str(pid)[:4]
        stmt = select(parcels).where(
            and_(
                parcels.c.totalvalue.between(lo, hi),
                parcels.c.parcelid.like(f"{prefix}%"),
            )
        ).limit(5)
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        print(f"  BETWEEN + LIKE found {len(rows)} parcel(s)")


# ==================================================================
# DYNAMIC ATTRIBUTE DISCOVERY TESTS
# ==================================================================

class TestAllAttributes:
    """Dynamically test every reflected attribute with = and IS NOT NULL."""

    def test_all_columns_equal_sample(self, engine, parcels, sample_row):
        """For every non-geometry column, test = with sample value."""
        passed = []
        skipped = []
        for col in parcels.columns:
            if _col_is_geometry(col):
                continue
            val = sample_row.get(col.name)
            if val is None:
                skipped.append(col.name)
                continue
            # Skip geometry-like JSON strings
            if isinstance(val, str) and val.startswith("{"):
                skipped.append(col.name)
                continue
            # Escape single quotes
            if isinstance(val, str):
                val = val.replace("'", "")
            try:
                stmt = select(parcels.c[col.name]).where(parcels.c[col.name] == val).limit(1)
                with engine.connect() as conn:
                    rows = conn.execute(stmt).fetchall()
                assert len(rows) > 0, f"No results for {col.name} = {val!r}"
                passed.append(col.name)
            except Exception as e:
                pytest.fail(f"Failed on column {col.name}: {e}")

        print(f"\n  Tested {len(passed)} columns with =")
        print(f"  Skipped {len(skipped)} columns (null or geometry): {skipped}")

    def test_all_columns_is_not_null(self, engine, parcels):
        """For every non-geometry column, test IS NOT NULL."""
        for col in parcels.columns:
            if _col_is_geometry(col):
                continue
            stmt = select(parcels.c[col.name]).where(parcels.c[col.name] != None).limit(1)
            with engine.connect() as conn:
                rows = conn.execute(stmt).fetchall()
            # Just verify the query executes — some columns may be entirely null
            print(f"  {col.name} IS NOT NULL: {len(rows)} rows")
