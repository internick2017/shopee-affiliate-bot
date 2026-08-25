from src.user_credentials_store import UserCredentialsStore


def test_get_sin_registrar_es_none(tmp_path):
    store = UserCredentialsStore(tmp_path / "creds.db")
    assert store.get(123) is None


def test_save_y_get_devuelve_las_credenciales(tmp_path):
    store = UserCredentialsStore(tmp_path / "creds.db")
    store.save(123, "mi_app_id", "mi_secret")

    assert store.get(123) == ("mi_app_id", "mi_secret")


def test_save_sobrescribe_credenciales_previas(tmp_path):
    store = UserCredentialsStore(tmp_path / "creds.db")
    store.save(123, "viejo_app_id", "viejo_secret")
    store.save(123, "nuevo_app_id", "nuevo_secret")

    assert store.get(123) == ("nuevo_app_id", "nuevo_secret")


def test_credenciales_por_usuario_no_se_mezclan(tmp_path):
    store = UserCredentialsStore(tmp_path / "creds.db")
    store.save(123, "app_123", "secret_123")
    store.save(456, "app_456", "secret_456")

    assert store.get(123) == ("app_123", "secret_123")
    assert store.get(456) == ("app_456", "secret_456")


def test_remove_borra_las_credenciales(tmp_path):
    store = UserCredentialsStore(tmp_path / "creds.db")
    store.save(123, "app_id", "secret")

    store.remove(123)

    assert store.get(123) is None


def test_remove_sin_registrar_no_falla(tmp_path):
    store = UserCredentialsStore(tmp_path / "creds.db")
    store.remove(999)  # no debe lanzar
