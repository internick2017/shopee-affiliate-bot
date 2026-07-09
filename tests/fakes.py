"""Dobles de test compartidos."""


class FakeDedup:
    """DedupStore en memoria con la misma semántica que el real.

    `claim` es atómico y devuelve False si la clave ya estaba: es el contrato del que
    dependen los handlers para no publicar la misma oferta dos veces.
    """

    def __init__(self):
        self.keys = {}

    def claim(self, key):
        if key in self.keys:
            return False
        self.keys[key] = True
        return True

    def release(self, key):
        self.keys.pop(key, None)

    def seen(self, key):
        return key in self.keys

    def mark(self, key):
        self.keys[key] = True
