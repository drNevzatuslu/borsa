from borsa_ajanlari.__main__ import _DenemeIstemci
from borsa_ajanlari.ekip import LLM, Koordinator, Rapor, ayar_yukle, json_ayikla, kaydet, konsensus_tablosu, prompt_oku
from borsa_ajanlari.veri import VeriToplayici


def test_config_yedi_ajan_ve_promptlar():
    ayar = ayar_yukle()
    assert len(ayar["ajanlar"]) == 7
    for a in ayar["ajanlar"]:
        assert prompt_oku(a["prompt"]).startswith("# Rol")


def test_json_ayikla():
    assert json_ayikla('x\n```json\n{"a": 1}\n```') == {"a": 1}
    assert json_ayikla("json yok") is None


def test_konsensus():
    r1 = Rapor("a", "A", "", {"oneriler": [{"varlik": "X", "yon": "AL", "guven": 80}]})
    r2 = Rapor("b", "B", "", {"oneriler": [{"varlik": "X", "yon": "SAT", "guven": 30}]})
    t = konsensus_tablosu([r1, r2])
    assert t["X"]["skor"] == 0.5 and t["X"]["oylar"] == {"a": "AL", "b": "SAT"}


def test_uctan_uca_deneme(tmp_path):
    ayar = ayar_yukle()
    k = Koordinator(ayar, LLM(ayar, istemci=_DenemeIstemci()), VeriToplayici(ayar, cevrimdisi=True))
    raporlar, sentez = k.calistir("deneme")
    assert len(raporlar) == 7 and all(r.ozet for r in raporlar)
    hedef = kaydet(raporlar, sentez, tmp_path)
    assert (hedef / "00_koordinator_raporu.md").exists()
    assert len(list(hedef.glob("*.md"))) == 8
