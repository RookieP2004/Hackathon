from aegis_agents.envelope import AgentMessage, ConfidenceBand, MessageType, confidence_band


def test_confidence_band_high():
    assert confidence_band(0.9) == ConfidenceBand.HIGH
    assert confidence_band(0.86) == ConfidenceBand.HIGH


def test_confidence_band_medium():
    assert confidence_band(0.85) == ConfidenceBand.MEDIUM
    assert confidence_band(0.5) == ConfidenceBand.MEDIUM
    assert confidence_band(0.6) == ConfidenceBand.MEDIUM


def test_confidence_band_low():
    assert confidence_band(0.49) == ConfidenceBand.LOW
    assert confidence_band(0.0) == ConfidenceBand.LOW


def test_confidence_band_none_when_no_score():
    assert confidence_band(None) is None


def test_agent_message_round_trip():
    msg = AgentMessage(
        agent_id="test-agent", agent_version="v1", message_type=MessageType.ASSERTION,
        payload={"foo": "bar"}, confidence=0.7, evidence_refs=["1", "2"], reasoning="because X",
    )
    d = msg.to_dict()
    assert d["message_type"] == "assertion"

    restored = AgentMessage.from_dict(d)
    assert restored.agent_id == "test-agent"
    assert restored.message_type == MessageType.ASSERTION
    assert restored.payload == {"foo": "bar"}
    assert restored.confidence == 0.7
    assert restored.evidence_refs == ["1", "2"]
    assert restored.reasoning == "because X"
    assert restored.correlation_id == msg.correlation_id


def test_agent_message_default_correlation_id_is_unique():
    msg1 = AgentMessage(agent_id="a", agent_version="v1", message_type=MessageType.HEALTH, payload={})
    msg2 = AgentMessage(agent_id="a", agent_version="v1", message_type=MessageType.HEALTH, payload={})
    assert msg1.correlation_id != msg2.correlation_id
