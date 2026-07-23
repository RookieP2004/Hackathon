from app.vision.persistence import DEFAULT_REQUIRED_CONSECUTIVE, PersistenceGate


def test_single_frame_does_not_confirm():
    gate = PersistenceGate(required_consecutive=3)
    result = gate.observe(("zone-1", "fire"), detected=True)
    assert result.is_confirmed is False
    assert result.just_crossed_threshold is False
    assert 0 < result.persistence_factor < 1


def test_confirms_only_after_required_consecutive_ticks():
    gate = PersistenceGate(required_consecutive=3)
    key = ("zone-1", "fire")

    r1 = gate.observe(key, detected=True)
    r2 = gate.observe(key, detected=True)
    r3 = gate.observe(key, detected=True)

    assert r1.is_confirmed is False
    assert r2.is_confirmed is False
    assert r3.is_confirmed is True
    assert r3.just_crossed_threshold is True
    assert r3.persistence_factor == 1.0


def test_just_crossed_threshold_fires_exactly_once_per_episode():
    gate = PersistenceGate(required_consecutive=2)
    key = ("zone-1", "gas_leak")

    gate.observe(key, detected=True)
    r2 = gate.observe(key, detected=True)
    r3 = gate.observe(key, detected=True)  # still detected, third consecutive tick

    assert r2.just_crossed_threshold is True
    assert r3.just_crossed_threshold is False  # already confirmed -- must not re-fire every tick
    assert r3.is_confirmed is True


def test_gap_resets_the_counter():
    gate = PersistenceGate(required_consecutive=3)
    key = ("zone-1", "smoke")

    gate.observe(key, detected=True)
    gate.observe(key, detected=True)
    r_gap = gate.observe(key, detected=False)
    r_after_gap = gate.observe(key, detected=True)

    assert r_gap.consecutive_ticks == 0
    assert r_gap.is_confirmed is False
    assert r_after_gap.consecutive_ticks == 1
    assert r_after_gap.is_confirmed is False


def test_can_re_arm_after_episode_ends():
    """A detection that clears and later reoccurs must be able to alert again --
    the just_crossed_threshold flag isn't a one-shot-forever latch."""
    gate = PersistenceGate(required_consecutive=2)
    key = ("zone-1", "fire")

    gate.observe(key, detected=True)
    r_first_confirm = gate.observe(key, detected=True)
    assert r_first_confirm.just_crossed_threshold is True

    gate.observe(key, detected=False)  # fire goes out

    gate.observe(key, detected=True)
    r_second_confirm = gate.observe(key, detected=True)
    assert r_second_confirm.just_crossed_threshold is True


def test_independent_keys_do_not_interfere():
    gate = PersistenceGate(required_consecutive=2)
    gate.observe(("zone-1", "fire"), detected=True)
    gate.observe(("zone-1", "fire"), detected=True)
    r_other = gate.observe(("zone-2", "fire"), detected=True)

    assert r_other.is_confirmed is False


def test_reset_clears_specific_key_only():
    gate = PersistenceGate(required_consecutive=3)
    gate.observe(("zone-1", "fire"), detected=True)
    gate.observe(("zone-2", "smoke"), detected=True)

    gate.reset(("zone-1", "fire"))

    assert ("zone-1", "fire") not in gate._counters
    assert gate._counters[("zone-2", "smoke")] == 1


def test_default_required_consecutive_is_reasonable():
    assert DEFAULT_REQUIRED_CONSECUTIVE >= 2
