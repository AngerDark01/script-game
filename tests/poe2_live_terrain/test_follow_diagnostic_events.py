import logging
import pickle

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.diagnostic_events import DiagnosticJournal, DiagnosticRelay


def test_events_survive_latest_only_drop_and_parent_deduplicates(caplog):
    journal = DiagnosticJournal(capacity=4)
    journal.record("local", "p1", "conflict", sequence=1, distance=88)
    journal.record("local", "p1", "accepted", sequence=2, distance=1)
    packet = pickle.loads(pickle.dumps(journal.snapshot()))
    relay = DiagnosticRelay(logging.getLogger("diagnostic_test"))
    with caplog.at_level(logging.INFO):
        relay.consume("control", 1, packet)
        relay.consume("control", 1, packet)
    assert caplog.text.count("reason=conflict") == 1
    assert caplog.text.count("reason=accepted") == 1
    assert "distance" in caplog.text


def test_journal_samples_repeated_state_and_reports_overflow(caplog):
    journal = DiagnosticJournal(capacity=2)
    for i in range(20):
        journal.record("visual", "p1", "accepted", now_ms=100, sequence=i)
    assert len(journal.snapshot()) == 1
    journal.record("visual", "p1", "rejected", now_ms=101)
    journal.record("visual", "p1", "accepted", now_ms=102)
    relay = DiagnosticRelay(logging.getLogger("diagnostic_test"))
    with caplog.at_level(logging.INFO):
        relay.consume("vision", 1, journal.snapshot())
    assert "diagnostic_gap" in caplog.text
    assert "dropped=1" in caplog.text
