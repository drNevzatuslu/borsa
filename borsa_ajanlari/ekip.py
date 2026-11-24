"""Ajanlar ve koordinatör: yedi ajanı paralel çalıştırır, raporları birleştirir."""
from __future__ import annotations

import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .veri import VeriToplayici

KOK = Path(__file__).resolve().parent
PROMPT_KLASORU = KOK / "prompts"


def ayar_yukle(yol: str | Path = KOK.parent / "config.yaml") -> dict:
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f)


def prompt_oku(dosya: str) -> str:
    return (PROMPT_KLASORU / dosya).read_text(encoding="utf-8")


def json_ayikla(metin: str) -> dict | None:
    """Rapor sonundaki ```json ... ``` bloğunu okur."""
    bloklar = re.findall(r"```json\s*(\{.*?\})\s*```", metin, flags=re.S)
    for b in reversed(bloklar):
        try:
            return json.loads(b)
        except json.JSONDecodeError:
            continue
    return None


@dataclass
class Rapor:
    ajan_id: str
    ad: str
    metin: str
    ozet: dict | None = field(default=None)


class LLM:
    """Anthropic Messages API çevresinde ince bir sarmalayıcı."""

    def __init__(self, ayar: dict, istemci=None):
        self.ayar = ayar["model"]
        if istemci is None:
            import anthropic  # ANTHROPIC_API_KEY ortam değişkeninden okunur

            istemci = anthropic.Anthropic()
        self.istemci = istemci

    def sor(self, model: str, sistem: str, kullanici: str, web_arama: bool) -> str:
        araclar = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}] if web_arama else []
        mesajlar = [{"role": "user", "content": kullanici}]
        parcalar: list[str] = []
        for _ in range(4):  # sunucu aracı uzun sürerse "pause_turn" ile devam edilir
            yanit = self.istemci.messages.create(
                model=model, max_tokens=self.ayar.get("max_tokens", 2000),
                system=sistem, messages=mesajlar, **({"tools": araclar} if araclar else {}),
            )
            parcalar += [b.text for b in yanit.content if getattr(b, "type", "") == "text"]
            if yanit.stop_reason != "pause_turn":
                break
            mesajlar = mesajlar + [{"role": "assistant", "content": yanit.content}]
        return "".join(parcalar).strip()


class Koordinator:
    def __init__(self, ayar: dict, llm: LLM, veri: VeriToplayici):
        self.ayar, self.llm, self.veri = ayar, llm, veri
        self.ortak = prompt_oku("_ortak.md")

    def _ajan_calistir(self, tanim: dict, gorev: str, tarih: str) -> Rapor:
        sistem = prompt_oku(tanim["prompt"]) + "\n\n" + self.ortak.replace("<ajan_id>", tanim["id"])
        kullanici = (
            f"Tarih: {tarih}\nGÖREV: {gorev}\n\n"
            f"İZLEME LİSTESİ: {json.dumps(self.ayar['izleme_listesi'], ensure_ascii=False)}\n\n"
            f"VERİ PAKETİ:\n{self.veri.paket(tanim.get('veri', []))}"
        )
        try:
            metin = self.llm.sor(self.ayar["model"]["ajan"], sistem, kullanici, self.ayar["model"].get("web_arama", False))
        except Exception as e:
            metin = f"Ajan çalışamadı: {e.__class__.__name__}: {e}"
        return Rapor(tanim["id"], tanim["ad"], metin, json_ayikla(metin))

    def calistir(self, gorev: str, sadece: list[str] | None = None) -> tuple[list[Rapor], str]:
        tarih = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        ajanlar = [a for a in self.ayar["ajanlar"] if not sadece or a["id"] in sadece]

        # 1) Veriyi önce topla (her kaynak bir kez)
        gerekli = sorted({k for a in ajanlar for k in a.get("veri", [])})
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(self.veri.getir, gerekli))

        # 2) Yedi ajan paralel
        with ThreadPoolExecutor(max_workers=len(ajanlar) or 1) as ex:
            raporlar = list(ex.map(lambda a: self._ajan_calistir(a, gorev, tarih), ajanlar))

        # 3) Koordinatör sentezi
        birlesik = "\n\n".join(f"===== {r.ad} ({r.ajan_id}) =====\n{r.metin}" for r in raporlar)
        konsensus = json.dumps(konsensus_tablosu(raporlar), ensure_ascii=False, indent=1)
        sentez = self.llm.sor(
            self.ayar["model"]["koordinator"], prompt_oku("koordinator.md"),
            f"Tarih: {tarih}\nGÖREV: {gorev}\n\nOTOMATİK KONSENSÜS (JSON bloklarından):\n{konsensus}\n\nAJAN RAPORLARI:\n{birlesik}",
            web_arama=False,
        )
        return raporlar, sentez


def konsensus_tablosu(raporlar: list[Rapor]) -> dict:
    """Varlık bazında AL/SAT oylarını güvenle ağırlıklandırarak toplar."""
    puan = {"AL": 1, "TUT": 0, "IZLE": 0, "SAT": -1}
    tablo: dict[str, dict] = {}
    for r in raporlar:
        for o in (r.ozet or {}).get("oneriler", []):
            v = o.get("varlik")
            if not v:
                continue
            satir = tablo.setdefault(v, {"oylar": {}, "skor": 0.0})
            yon = str(o.get("yon", "IZLE")).upper()
            satir["oylar"][r.ajan_id] = yon
            satir["skor"] += puan.get(yon, 0) * float(o.get("guven", 50)) / 100
    for satir in tablo.values():
        satir["skor"] = round(satir["skor"], 2)
    return dict(sorted(tablo.items(), key=lambda kv: -abs(kv[1]["skor"])))


def kaydet(raporlar: list[Rapor], sentez: str, klasor: str | Path) -> Path:
    hedef = Path(klasor) / dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    hedef.mkdir(parents=True, exist_ok=True)
    for r in raporlar:
        (hedef / f"{r.ajan_id}.md").write_text(f"# {r.ad}\n\n{r.metin}\n", encoding="utf-8")
    (hedef / "00_koordinator_raporu.md").write_text(sentez + "\n", encoding="utf-8")
    (hedef / "konsensus.json").write_text(
        json.dumps(konsensus_tablosu(raporlar), ensure_ascii=False, indent=2), encoding="utf-8")
    return hedef
