-- ============================================================
-- FORMULA 1 DATABASE SCHEMA
-- ============================================================
-- Source CSVs use camelCase headers (raceId, positionOrder). Columns
-- here are snake_case so generated SQL needs no quoted identifiers;
-- COPY maps columns by position, so the CSV headers are not used.


-- ============================================================
-- LOOKUP TABLES
-- ============================================================

CREATE TABLE seasons (
    year INTEGER PRIMARY KEY,
    url TEXT NOT NULL
);

CREATE TABLE circuits (
    circuit_id INTEGER PRIMARY KEY,
    circuit_ref TEXT NOT NULL,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    country TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    alt INTEGER NOT NULL,
    url TEXT NOT NULL
);

CREATE TABLE drivers (
    driver_id INTEGER PRIMARY KEY,
    driver_ref TEXT NOT NULL,
    number INTEGER,
    code VARCHAR(3),
    forename TEXT NOT NULL,
    surname TEXT NOT NULL,
    dob DATE,
    nationality TEXT,
    url TEXT
);

CREATE TABLE constructors (
    constructor_id INTEGER PRIMARY KEY,
    constructor_ref TEXT NOT NULL,
    name TEXT NOT NULL,
    nationality TEXT NOT NULL,
    url TEXT NOT NULL
);

CREATE TABLE status (
    status_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL
);


-- ============================================================
-- RACES
-- ============================================================

CREATE TABLE races (
    race_id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL REFERENCES seasons(year),
    round INTEGER NOT NULL,
    circuit_id INTEGER NOT NULL REFERENCES circuits(circuit_id),
    name TEXT NOT NULL,
    date DATE NOT NULL,
    time TIME,
    url TEXT NOT NULL,
    fp1_date DATE,
    fp1_time TIME,
    fp2_date DATE,
    fp2_time TIME,
    fp3_date DATE,
    fp3_time TIME,
    quali_date DATE,
    quali_time TIME,
    sprint_date DATE,
    sprint_time TIME
);


-- ============================================================
-- RESULTS
-- ============================================================

CREATE TABLE results (
    result_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    constructor_id INTEGER NOT NULL REFERENCES constructors(constructor_id),
    number INTEGER,
    grid INTEGER NOT NULL,
    position INTEGER,
    position_text TEXT NOT NULL,
    position_order INTEGER NOT NULL,
    points NUMERIC NOT NULL,
    laps INTEGER NOT NULL,
    time TEXT,
    milliseconds INTEGER,
    fastest_lap INTEGER,
    rank INTEGER,
    fastest_lap_time TEXT,
    fastest_lap_speed NUMERIC,
    status_id INTEGER NOT NULL REFERENCES status(status_id)
);

CREATE TABLE sprint_results (
    result_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    constructor_id INTEGER NOT NULL REFERENCES constructors(constructor_id),
    number INTEGER NOT NULL,
    grid INTEGER NOT NULL,
    position INTEGER,
    position_text TEXT NOT NULL,
    position_order INTEGER NOT NULL,
    points NUMERIC NOT NULL,
    laps INTEGER NOT NULL,
    time TEXT,
    milliseconds INTEGER,
    fastest_lap INTEGER,
    fastest_lap_time TEXT,
    status_id INTEGER NOT NULL REFERENCES status(status_id)
);

CREATE TABLE qualifying (
    qualify_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    constructor_id INTEGER NOT NULL REFERENCES constructors(constructor_id),
    number INTEGER NOT NULL,
    position INTEGER NOT NULL,
    q1 TEXT,
    q2 TEXT,
    q3 TEXT
);


-- ============================================================
-- LAP-LEVEL DATA
-- ============================================================

CREATE TABLE lap_times (
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    lap INTEGER NOT NULL,
    position INTEGER NOT NULL,
    time TEXT NOT NULL,
    milliseconds INTEGER NOT NULL,
    PRIMARY KEY (race_id, driver_id, lap)
);

CREATE TABLE pit_stops (
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    stop INTEGER NOT NULL,
    lap INTEGER NOT NULL,
    time TIME NOT NULL,
    duration TEXT,
    milliseconds INTEGER NOT NULL,
    PRIMARY KEY (race_id, driver_id, stop)
);


-- ============================================================
-- CHAMPIONSHIP STANDINGS (cumulative, after each race)
-- ============================================================

CREATE TABLE driver_standings (
    driver_standings_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    points NUMERIC NOT NULL,
    position INTEGER NOT NULL,
    position_text TEXT NOT NULL,
    wins INTEGER NOT NULL
);

CREATE TABLE constructor_standings (
    constructor_standings_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    constructor_id INTEGER NOT NULL REFERENCES constructors(constructor_id),
    points NUMERIC NOT NULL,
    position INTEGER NOT NULL,
    position_text TEXT NOT NULL,
    wins INTEGER NOT NULL
);

CREATE TABLE constructor_results (
    constructor_results_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    constructor_id INTEGER NOT NULL REFERENCES constructors(constructor_id),
    points NUMERIC NOT NULL,
    status TEXT
);


-- ============================================================
-- 2025-2026 ONLY (added by the dataset extension)
-- ============================================================

CREATE TABLE practice_results (
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    session TEXT NOT NULL,
    position INTEGER NOT NULL,
    best_lap_time INTERVAL NOT NULL,
    laps INTEGER NOT NULL,
    PRIMARY KEY (race_id, driver_id, session)
);

CREATE TABLE tire_stints (
    race_id INTEGER NOT NULL REFERENCES races(race_id),
    driver_id INTEGER NOT NULL REFERENCES drivers(driver_id),
    stint INTEGER NOT NULL,
    compound TEXT,
    start_lap INTEGER NOT NULL,
    end_lap INTEGER NOT NULL,
    laps_on_tire INTEGER NOT NULL,
    PRIMARY KEY (race_id, driver_id, stint)
);

CREATE TABLE weather (
    race_id INTEGER PRIMARY KEY REFERENCES races(race_id),
    air_temp_avg NUMERIC NOT NULL,
    air_temp_min NUMERIC NOT NULL,
    air_temp_max NUMERIC NOT NULL,
    track_temp_avg NUMERIC NOT NULL,
    track_temp_min NUMERIC NOT NULL,
    track_temp_max NUMERIC NOT NULL,
    humidity_avg NUMERIC NOT NULL,
    wind_speed_avg NUMERIC NOT NULL,
    wind_speed_max NUMERIC NOT NULL,
    rainfall BOOLEAN NOT NULL
);


-- ============================================================
-- INDEXES (foreign keys of the larger tables)
-- ============================================================

CREATE INDEX idx_results_race_id ON results(race_id);
CREATE INDEX idx_results_driver_id ON results(driver_id);
CREATE INDEX idx_results_constructor_id ON results(constructor_id);
CREATE INDEX idx_lap_times_driver_id ON lap_times(driver_id);
CREATE INDEX idx_driver_standings_race_id ON driver_standings(race_id);
CREATE INDEX idx_constructor_standings_race_id ON constructor_standings(race_id);
CREATE INDEX idx_qualifying_race_id ON qualifying(race_id);
CREATE INDEX idx_races_year ON races(year);
