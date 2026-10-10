from hotel.services.passwords import PasswordHasher, ScryptParams

FAST = ScryptParams(n=2**10)


def test_hash_and_verify():
    hasher = PasswordHasher(FAST)
    encoded = hasher.hash("cognac and cedar wood")
    assert encoded.startswith("scrypt$1024$8$1$")
    assert hasher.verify("cognac and cedar wood", encoded)
    assert not hasher.verify("cognac and cedar woods", encoded)


def test_same_password_gets_different_salts():
    hasher = PasswordHasher(FAST)
    assert hasher.hash("same password here") != hasher.hash("same password here")


def test_malformed_hashes_never_verify():
    hasher = PasswordHasher(FAST)
    for bad in ["", "plain", "bcrypt$1$2$3$4$5", "scrypt$x$8$1$aaaa$bbbb", "scrypt$1024$8$1$!!$!!"]:
        assert not hasher.verify("anything", bad)


def test_needs_rehash_when_cost_changes():
    old = PasswordHasher(FAST).hash("cognac and cedar wood")
    stronger = PasswordHasher(ScryptParams(n=2**11))
    assert stronger.needs_rehash(old)
    assert stronger.verify("cognac and cedar wood", old)  # old hashes keep working
    assert not PasswordHasher(FAST).needs_rehash(old)
