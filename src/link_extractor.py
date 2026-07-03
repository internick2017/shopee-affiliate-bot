import re
from typing import List, Optional

_SHORTLINK_RE = re.compile(r"https?://s\.shopee\.com\.br/[A-Za-z0-9]+")


def extract_shopee_links(text: Optional[str]) -> List[str]:
    """Devuelve todos los shortlinks de Shopee (s.shopee.com.br/...) en el texto."""
    if not text:
        return []
    return _SHORTLINK_RE.findall(text)
