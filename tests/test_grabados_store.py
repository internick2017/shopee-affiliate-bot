import pytest

from src.grabados_store import GrabadosStore

_HOY = 1_700_000_000
_DIA = 86400


@pytest.fixture
def store(tmp_path):
    return GrabadosStore(tmp_path / "g.db")


def test_arranca_vacio(store):
    assert store.total() == 0
    assert store.ya_grabado(1) is False
    assert store.grabados_todos() == set()


def test_marcar_y_consultar(store):
    store.marcar(42, titulo="Kit Pastilha")
    assert store.ya_grabado(42) is True
    assert store.total() == 1


def test_marcar_dos_veces_no_duplica(store):
    """El usuario puede repetir /video sobre el mismo producto sin que falle."""
    store.marcar(42, titulo="Primera", now=_HOY)
    store.marcar(42, titulo="Segunda", now=_HOY + 100)
    assert store.total() == 1
    assert store.ultimos()[0].titulo == "Segunda"


def test_grabados_en_bloque(store):
    """Consulta unica al filtrar una lista, no una por producto."""
    store.marcar(1)
    store.marcar(3)
    assert store.grabados([1, 2, 3, 4]) == {1, 3}


def test_grabados_con_lista_vacia_no_consulta(store):
    assert store.grabados([]) == set()


def test_olvidar_permite_volver_a_grabar(store):
    store.marcar(7)
    assert store.olvidar(7) is True
    assert store.ya_grabado(7) is False


def test_olvidar_algo_que_no_estaba(store):
    assert store.olvidar(999) is False


def test_ultimos_ordena_por_mas_reciente(store):
    store.marcar(1, titulo="Viejo", now=_HOY - 5 * _DIA)
    store.marcar(2, titulo="Nuevo", now=_HOY)
    assert [g.titulo for g in store.ultimos()] == ["Nuevo", "Viejo"]


def test_ultimos_respeta_el_limite(store):
    for i in range(20):
        store.marcar(i)
    assert len(store.ultimos(5)) == 5


def test_no_caduca_solo(store):
    """A diferencia de DedupStore, un video grabado no se olvida con el tiempo:
    sigue existiendo. El olvido es explicito, con olvidar()."""
    store.marcar(1, now=_HOY - 400 * _DIA)
    assert store.ya_grabado(1) is True
