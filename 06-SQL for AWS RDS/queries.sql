CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dwh;

CREATE TABLE stg.kayak_final_raw (
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

SELECT aws_s3.table_import_from_s3(
    'stg.kayak_final_raw',
    '',  -- toutes les colonnes, dans l'ordre de la table
    '(FORMAT csv, HEADER true)',
    aws_commons.create_s3_uri(
        'jedha-kayak-sandra-margot',  -- bucket
        'Kayak_final.csv',            -- objet dans le bucket
        'eu-north-1'                  -- région
    ),
    aws_commons.create_aws_credentials(
        'KEY',
        'TOKEN',
        ''  -- session token (vide si non utilisé)
    )
);

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
SELECT DISTINCT
    site_id::integer,
    destination AS site_name,
    lat_site::double precision,
    lon_site::double precision,
    avg_temp_c::double precision,
    expected_rain_mm::double precision,
    nice_score::double precision
FROM stg.kayak_final_raw;


DROP TABLE IF EXISTS dwh.fact_hotel;

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
    review_score::numeric,
    description,
    address
FROM stg.kayak_final_raw;

Voir quelques lignes:
SELECT *
FROM dwh.fact_hotel
LIMIT 10;
