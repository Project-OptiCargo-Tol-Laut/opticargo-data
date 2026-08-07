from opticargo_data.security import hash_password

def test_argon2_hash_is_not_plaintext():
    value=hash_password("OptiCargoDemo123!","argon2")
    assert value != "OptiCargoDemo123!"
    assert value.startswith("$argon2")
