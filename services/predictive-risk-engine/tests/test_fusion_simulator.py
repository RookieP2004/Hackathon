from app.fusion.simulator import BASELINES, SensorSimulator

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


async def test_load_sensors_loads_real_seeded_sensors():
    simulator = SensorSimulator()
    count = await simulator.load_sensors(POSTGRES_DSN)
    assert count > 0
    assert count == len(simulator.states)


async def test_tick_produces_values_within_baseline_bounds():
    simulator = SensorSimulator()
    await simulator.load_sensors(POSTGRES_DSN)
    for _ in range(5):
        values = simulator.tick()
    for sensor_id, value in values.items():
        sensor_type = simulator.states[sensor_id].sensor_type
        baseline = BASELINES[sensor_type]
        assert baseline["min"] <= value <= baseline["max"]


async def test_injection_pulls_value_toward_target():
    simulator = SensorSimulator()
    await simulator.load_sensors(POSTGRES_DSN)
    sensor_id = next(iter(simulator.states))
    original_value = simulator.states[sensor_id].value
    target = original_value + 500

    simulator.inject_precursor_pattern(sensor_id, target=target, rate=0.5)
    for _ in range(10):
        simulator.tick()

    assert simulator.states[sensor_id].value > original_value + 100


async def test_clear_injection_stops_the_pull():
    simulator = SensorSimulator()
    await simulator.load_sensors(POSTGRES_DSN)
    sensor_id = next(iter(simulator.states))
    simulator.inject_precursor_pattern(sensor_id, target=simulator.states[sensor_id].value + 1000, rate=0.5)
    simulator.clear_injection(sensor_id)
    assert simulator.states[sensor_id].target_override is None


async def test_tick_and_persist_writes_real_rows():
    simulator = SensorSimulator()
    await simulator.load_sensors(POSTGRES_DSN)
    written = await simulator.tick_and_persist(POSTGRES_DSN)
    assert written == len(simulator.states)

    import asyncpg

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        count = await conn.fetchval("SELECT count(*) FROM sensor_readings WHERE recorded_at > now() - interval '1 minute'")
    finally:
        await conn.close()
    assert count >= written
