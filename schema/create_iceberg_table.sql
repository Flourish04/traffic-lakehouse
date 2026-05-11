-- Create Iceberg schema and table for traffic events
-- Run in Trino: docker exec -it trino trino -f /path/to/create_iceberg_table.sql

-- Create schema
CREATE SCHEMA IF NOT EXISTS iceberg.traffic 
WITH (location = 's3://warehouse/traffic/');

-- Create traffic events table with semi-structured schema
-- Speed: flatten aggregates + ARRAY for series
-- Weather: ROW (STRUCT)
CREATE TABLE IF NOT EXISTS iceberg.traffic.events (
    -- Base fields (flatten)
    camera_id VARCHAR NOT NULL,
    slot TIMESTAMP(6) NOT NULL,
    generated_at TIMESTAMP(6),
    duration_sec INTEGER,
    vehicles_count DOUBLE,
    
    -- Speed: Flatten aggregates
    speed_count INTEGER,
    speed_avg_kmh DOUBLE,
    speed_min_kmh DOUBLE,
    speed_max_kmh DOUBLE,
    
    -- Speed: ARRAY for time series data
    speed_series ARRAY(ROW(
        time TIMESTAMP(6),
        speed DOUBLE
    )),
    
    -- Weather: ROW (STRUCT) - from OpenWeather API
    weather ROW(
        id INTEGER,                 -- Weather condition ID (801, 500, etc.)
        main VARCHAR,               -- "Clouds", "Rain", "Clear"
        description VARCHAR,        -- "few clouds", "light rain"
        icon VARCHAR,               -- "02n", "10d"
        temp DOUBLE,                -- Temperature in Celsius
        feels_like DOUBLE,          -- Feels like temperature
        temp_min DOUBLE,            -- Minimum temperature
        temp_max DOUBLE,            -- Maximum temperature
        pressure INTEGER,           -- Pressure in hPa
        humidity INTEGER,           -- Humidity percentage
        sea_level INTEGER,          -- Sea level pressure in hPa
        grnd_level INTEGER,         -- Ground level pressure in hPa
        wind_speed DOUBLE,          -- Wind speed in m/s
        wind_deg INTEGER,           -- Wind direction in degrees
        clouds_all INTEGER          -- Cloud coverage percentage
    )
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['day(slot)', 'camera_id']
);

-- Example queries:

-- 1. Basic query
-- SELECT camera_id, slot, vehicles_count, speed_avg_kmh, weather.temp, weather.condition
-- FROM iceberg.traffic.events
-- WHERE weather.condition = 'Rain';

-- 2. Query with weather filter
-- SELECT camera_id, AVG(speed_avg_kmh) as avg_speed
-- FROM iceberg.traffic.events
-- WHERE weather.temp > 30 AND weather.humidity > 80
-- GROUP BY camera_id;

-- 3. Unnest speed series
-- SELECT e.camera_id, e.slot, s.time, s.speed
-- FROM iceberg.traffic.events e
-- CROSS JOIN UNNEST(e.speed_series) AS t(s)
-- WHERE e.camera_id = '5deb576d1dc17d7c5515acfb';

-- 4. Aggregation by weather condition
-- SELECT weather.condition, 
--        COUNT(*) as count,
--        AVG(speed_avg_kmh) as avg_speed,
--        AVG(vehicles_count) as avg_vehicles
-- FROM iceberg.traffic.events
-- GROUP BY weather.condition;
