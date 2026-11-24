"""Kullanım:  python -m borsa_ajanlari [--gorev "..."] [--ajan id ...] [--deneme]"""
from __future__ import annotations

import argparse
import json

from .ekip import LLM, Koordinator, ayar_yukle, kaydet
from .veri import VeriToplayici

VARSAYILAN_GOREV = (
    "Borsa İstanbul ve ABD borsaları için güncel durum değerlendirmesi yap; "
    "izleme listesindeki varlıklar için görüş ve önümüzdeki 1-4 hafta için öneriler ver."
)


class _DenemeIstemci:
    """API çağırmadan uçtan uca akışı test etmek için sahte istemci."""

    class messages:  # noqa: N801
        @staticmethod
        def create(**kw):
            from types import SimpleNamespace as NS

            ajan = "koordinator" if "Koordinatör" in kw["system"] else kw["system"].split("\n")[0]
            ozet = {"ajan": ajan, "genel_gorus": "notr", "guven": 50,
                    "oneriler": [{"varlik": "XU100.IS", "yon": "TUT", "vade": "hafta", "guven": 50, "gerekce": "deneme"}],
                    "riskler": [], "izlenecekler": []}
            metin = f"(DENEME) {ajan}\n\n```json\n{json.dumps(ozet, ensure_ascii=False)}\n```"
            return NS(content=[NS(type="text", text=metin)], stop_reason="end_turn")


def main() -> None:
    p = argparse.ArgumentParser(description="Yedi ajanlı borsa araştırma ekibi")
    p.add_argument("--gorev", default=VARSAYILAN_GOREV)
    p.add_argument("--ajan", nargs="*", help="yalnızca bu ajan id'lerini çalıştır")
    p.add_argument("--config", default=None)
    p.add_argument("--deneme", action="store_true", help="API ve ağ çağrısı yapmadan akışı dene")
    a = p.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ayar = ayar_yukle(a.config) if a.config else ayar_yukle()
    llm = LLM(ayar, istemci=_DenemeIstemci() if a.deneme else None)
    koord = Koordinator(ayar, llm, VeriToplayici(ayar, cevrimdisi=a.deneme))
    raporlar, sentez = koord.calistir(a.gorev, a.ajan)
    hedef = kaydet(raporlar, sentez, ayar["cikti"]["klasor"])
    print(sentez)
    print(f"\nRaporlar kaydedildi: {hedef}")


if __name__ == "__main__":
    main()
