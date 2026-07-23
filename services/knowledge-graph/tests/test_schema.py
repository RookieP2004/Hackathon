from app.graph.schema import apply_schema


async def test_apply_schema_is_idempotent(driver):
    first = await apply_schema(driver)
    second = await apply_schema(driver)
    assert first["applied"] > 0
    assert second["applied"] == first["applied"]


async def test_constraints_actually_exist_in_neo4j(driver):
    await apply_schema(driver)
    async with driver.session() as session:
        result = await session.run("SHOW CONSTRAINTS YIELD name RETURN collect(name) AS names")
        record = await result.single()
        names = record["names"]
    assert "equipment_id" in names
    assert "risk_id" in names
