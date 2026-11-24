from app.fingerprint import make_fingerprint


def test_same_message_same_fingerprint():
    assert make_fingerprint('Hello there', 'web') == make_fingerprint('Hello there', 'web')


def test_case_and_spacing_are_ignored():
    assert make_fingerprint('Hello   THERE', 'web') == make_fingerprint('hello there', 'web')


def test_different_source_gives_different_fingerprint():
    assert make_fingerprint('Hello there', 'web') != make_fingerprint('Hello there', 'email')


def test_different_message_gives_different_fingerprint():
    assert make_fingerprint('Hello there', 'web') != make_fingerprint('Goodbye', 'web')