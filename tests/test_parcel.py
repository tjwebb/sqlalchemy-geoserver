import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, and_, or_, func, text

load_dotenv(".env.test")

GEOSERVER_URL = os.environ.get("GEOSERVER_URL")
GEOSERVER_AUTH_HEADER = os.environ.get("GEOSERVER_AUTH_HEADER")

LAYER = "lr:lr_parcel_51_710"

pytestmark = pytest.mark.skipif(
    not GEOSERVER_URL,
    reason="GEOSERVER_URL must be set for parcel integration tests"
)

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


def test_reflect_schema(parcels):
    """Verify layer reflection returns expected parcel columns."""
    col_names = [c.name for c in parcels.columns]
    print(f"\nReflected {len(col_names)} columns: {col_names}")
    assert len(col_names) > 0
    # Spot-check expected columns
    for expected in ["parcelid", "statefp", "countyfp", "countyname"]:
        assert expected in col_names, f"Expected column '{expected}' not found"


def test_select_limit_1(engine, parcels):
    """Fetch a single parcel record."""
    stmt = select(parcels).limit(1)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFetched {len(rows)} row(s)")
        if rows:
            print(dict(rows[0]._mapping))
        assert len(rows) == 1


def test_select_by_county(engine, parcels):
    """Query parcels filtered by county name."""
    # First get a valid county name
    stmt_sample = select(parcels.c.countyname).limit(1)
    with engine.connect() as conn:
        sample = conn.execute(stmt_sample).fetchone()

    if not sample or not sample[0]:
        pytest.skip("No county data available")

    county = sample[0]
    print(f"\nFiltering by countyname = '{county}'")

    stmt = select(parcels).where(parcels.c.countyname == county).limit(5)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"Found {len(rows)} parcels in {county}")
        assert len(rows) > 0
        for row in rows:
            assert row._mapping["countyname"] == county


def test_select_by_statefp(engine, parcels):
    """Query parcels filtered by state FIPS code (51 = Virginia)."""
    stmt = select(parcels).where(parcels.c.statefp == "51").limit(5)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFound {len(rows)} parcels with statefp = '51'")
        assert len(rows) > 0
        for row in rows:
            assert row._mapping["statefp"] == "51"


def test_select_specific_columns(engine, parcels):
    """Select only specific columns instead of all."""
    stmt = select(
        parcels.c.parcelid,
        parcels.c.countyname,
        parcels.c.parceladdr,
        parcels.c.totalvalue
    ).limit(5)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFetched {len(rows)} rows with selected columns")
        for row in rows:
            print(f"  parcelid={row[0]}, county={row[1]}, addr={row[2]}, value={row[3]}")
        assert len(rows) > 0


def test_select_by_countyfp(engine, parcels):
    """Query parcels by county FIPS code (710)."""
    stmt = select(parcels).where(parcels.c.countyfp == "710").limit(5)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFound {len(rows)} parcels with countyfp = '710'")
        assert len(rows) > 0


def test_select_with_multiple_filters(engine, parcels):
    """Query with multiple WHERE conditions (AND)."""
    stmt = (
        select(parcels)
        .where(
            and_(
                parcels.c.statefp == "51",
                parcels.c.countyfp == "710",
            )
        )
        .limit(5)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFound {len(rows)} parcels with statefp=51 AND countyfp=710")
        assert len(rows) > 0
        for row in rows:
            m = row._mapping
            assert m["statefp"] == "51"
            assert m["countyfp"] == "710"


def test_select_with_year_filter(engine, parcels):
    """Query parcels by tax year."""
    # Get a valid tax year first
    stmt_sample = select(parcels.c.taxyear).limit(1)
    with engine.connect() as conn:
        sample = conn.execute(stmt_sample).fetchone()

    if not sample or not sample[0]:
        pytest.skip("No taxyear data available")

    year = sample[0]
    print(f"\nFiltering by taxyear = '{year}'")

    stmt = select(parcels.c.parcelid, parcels.c.taxyear, parcels.c.totalvalue).where(
        parcels.c.taxyear == str(year)
    ).limit(5)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"Found {len(rows)} parcels for taxyear = {year}")
        assert len(rows) > 0


def test_select_by_parcelid(engine, parcels):
    """Query a specific parcel by parcelid."""
    stmt = select(parcels).where(parcels.c.parcelid == "14680097630000").limit(1)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFound {len(rows)} parcel(s) with parcelid = '14680097630000'")
        assert len(rows) > 0
        for row in rows:
            print(dict(row._mapping))
            assert row._mapping["parcelid"] == "14680097630000"


def test_search_by_parcelid(engine, parcels):
    """Search for parcels with a partial parcelid match using LIKE."""
    stmt = select(parcels).where(parcels.c.parcelid.like("14680097%")).limit(10)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFound {len(rows)} parcel(s) matching parcelid LIKE '14680097%'")
        assert len(rows) > 5
        for row in rows:
            pid = row._mapping["parcelid"]
            print(f"  parcelid: {pid}")
            assert pid.startswith("14680097")


def test_select_by_lrid(engine, parcels):
    """Return a single parcel by lrid."""
    # First get a valid lrid
    stmt_sample = select(parcels.c.lrid).limit(1)
    with engine.connect() as conn:
        sample = conn.execute(stmt_sample).fetchone()

    if not sample or not sample[0]:
        pytest.skip("No lrid data available")

    lrid = sample[0]
    print(f"\nLooking up parcel by lrid = '{lrid}'")

    stmt = select(parcels).where(parcels.c.lrid == lrid).limit(1)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"Found {len(rows)} parcel(s)")
        assert len(rows) == 1
        row = rows[0]
        print(dict(row._mapping))
        assert row._mapping["lrid"] == lrid


def test_point_in_polygon(engine, parcels):
    """Find parcels that contain a specific point (point-in-polygon spatial query)."""
    # Use a coordinate in Norfolk, VA (FIPS 51, county 710)
    lon, lat = -76.29793, 36.85664

    # GeoServer CQL spatial filter: INTERSECTS(geom, POINT(lon lat))
    spatial_filter = text(f"INTERSECTS(geom, POINT({lon} {lat}))")

    stmt = select(parcels).where(spatial_filter).limit(5)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        print(f"\nFound {len(rows)} parcel(s) containing POINT({lon} {lat})")
        assert len(rows) == 1
        for row in rows:
            m = row._mapping
            print(f"  parcelid={m.get('parcelid')}, addr={m.get('parceladdr')}, county={m.get('countyname')}")
