import pytest

from src.vetados import vetado


@pytest.mark.parametrize("titulo", [
    "Cerveja Pilsen Lata 350ml Caixa com 12",
    "Vinho Tinto Seco 750ml",
    "Whisky 12 Anos 1 Litro",
    "Cigarro Eletrônico Vape",
    "Arma de Brinquedo Realista",
    "Pistola de Gel Automática",
    "Canivete Tático",
])
def test_veta(titulo):
    assert vetado(titulo)


@pytest.mark.parametrize("titulo", [
    "Copo Garrafa Térmico Cerveja C/ Canudo Personalizado 1200ml",
    "Jogo 6 Copos Baixos De Vidro Lapidado - Whisky, Água, Drinks",
    "Abridor de Vinho Elétrico",
    "Organizador De Armazenamento Pendurado Grande",
    "Perfume Arabe Armaf Club De Nuit",
    "Pistola Cola Quente 20w",
    "Afiador de Facas 3 Estágios",
    "Jogo 6 Taças De Vidro 330ml Cristal Suco",
    "Saco de Lixo Lavanda 10L",
    "Seladora à Vácuo Armazena Alimentos",
])
def test_no_veta(titulo):
    assert not vetado(titulo)
