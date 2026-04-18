CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dwh;

DROP TABLE IF EXISTS stg.travel_intelligence_raw;

CREATE TABLE stg.travel_intelligence_raw (
    site_id           text,
    destination       text,
    name              text,
    lat_hotel         text,
    lon_hotel         text,
    url               text,
    hotel_id          text,
    review_score      text,
    description       text,
    address           text,
    lat_site          text,
    lon_site          text,
    avg_temp_c        text,
    expected_rain_mm  text,
    nice_score        text
);

-- Example import from S3 (credentials should be managed securely outside the SQL script)
SELECT aws_s3.table_import_from_s3(
    'stg.travel_intelligence_raw',
    '',
    '(FORMAT csv, HEADER true)',
    aws_commons.create_s3_uri(
        'your-bucket-name',
        'travel_intelligence_final.csv',
        'your-region'
    )
);

DROP TABLE IF EXISTS dwh.fact_hotel;
DROP TABLE IF EXISTS dwh.dim_site;

CREATE TABLE dwh.dim_site (
    site_id          integer PRIMARY KEY,
    site_name        text,
    lat_site         double precision,
    lon_site         double precision,
    avg_temp_c       double precision,
    expected_rain_mm double precision,
    nice_score       double precision
);

INSERT INTO dwh.dim_site (
    site_id,
    site_name,
    lat_site,
    lon_site,
    avg_temp_c,
    expected_rain_mm,
    nice_score
)
SELECT
    site_id::integer,
    MIN(destination) AS site_name,
    MIN(lat_site::double precision) AS lat_site,
    MIN(lon_site::double precision) AS lon_site,
    MIN(avg_temp_c::double precision) AS avg_temp_c,
    MIN(expected_rain_mm::double precision) AS expected_rain_mm,
    MIN(nice_score::double precision) AS nice_score
FROM stg.travel_intelligence_raw
GROUP BY site_id::integer;

CREATE TABLE dwh.fact_hotel (
    hotel_sk     bigserial PRIMARY KEY,
    site_id      integer NOT NULL,
    hotel_id     text NOT NULL,
    name         text,
    lat_hotel    double precision,
    lon_hotel    double precision,
    url          text,
    review_score numeric(3,1),
    description  text,
    address      text,
    CONSTRAINT fk_fact_hotel_site
        FOREIGN KEY (site_id) REFERENCES dwh.dim_site(site_id)
);

INSERT INTO dwh.fact_hotel (
    site_id,
    hotel_id,
    name,
    lat_hotel,
    lon_hotel,
    url,
    review_score,
    description,
    address
)
SELECT
    site_id::integer,
    hotel_id,
    name,
    lat_hotel::double precision,
    lon_hotel::double precision,
    url,
    review_score::numeric(3,1),
    description,
    address
FROM stg.travel_intelligence_raw;

-- Sample check
SELECT *
FROM dwh.fact_hotel
LIMIT 10;