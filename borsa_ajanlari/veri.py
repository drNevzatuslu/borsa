"""Veri kaynakları. Her kaynak bir metin bloğu döndürür; anahtar ya da paket yoksa
kısa bir 'atlandı' notu döner ve sistem çalışmaya devam eder."""
from __future__ import annotations

import datetime as dt
import os
from typing import Callable

import requests

ZAMAN_ASIMI = 20


def _anahtar(ad: str) -> str | None:
    deger = os.getenv(ad, "").strip()
    return deger or None


def _atlandi(kaynak: str, neden: str) -> str:
    return f"[{kaynak}] atlandı: {neden}"


# ---------------------------------------------------------------- fiyat + teknik
def _teknik_ozet(sembol: str) -> str:
    import yfinance as yf  # isteğe bağlı bağımlılık

    df = yf.Ticker(sembol).history(period="1y", interval="1d", auto_adjust=True)
    if df.empty:
        return f"{sembol}: veri yok"
    k = df["Close"]
    son = k.iloc[-1]

    def degisim(gun: int) -> str:
        return f"{(son / k.iloc[-gun - 1] - 1) * 100:+.1f}%" if len(k) > gun else "-"

    delta = k.diff()
    kazanc = delta.clip(lower=0).rolling(14).mean()
    kayip = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + kazanc / kayip)
    ema12, ema26 = k.ewm(span=12).mean(), k.ewm(span=26).mean()
    macd = ema12 - ema26
    sinyal = macd.ewm(span=9).mean()
    tr = (df["High"] - df["Low"]).rolling(14).mean()
    hacim_orani = df["Volume"].iloc[-1] / df["Volume"].rolling(20).mean().iloc[-1] if df["Volume"].iloc[-1] else 0
    goa = {n: k.rolling(n).mean().iloc[-1] for n in (20, 50, 200)}
    return (
        f"{sembol}: son={son:.2f} | 1g {degisim(1)} 1h {degisim(5)} 1a {degisim(21)} 3a {degisim(63)} 1y {degisim(len(k) - 1)}"
        f" | GOA20={goa[20]:.2f} GOA50={goa[50]:.2f} GOA200={goa[200]:.2f}"
        f" | RSI14={rsi.iloc[-1]:.0f} MACD={macd.iloc[-1]:.2f}/sinyal {sinyal.iloc[-1]:.2f}"
        f" | ATR14~{tr.iloc[-1]:.2f} | hacim/20g ort={hacim_orani:.1f}x"
        f" | 52h yüksek={k.max():.2f} düşük={k.min():.2f}"
    )


def fiyat_listesi(semboller: list[str], etiket: str) -> str:
    try:
        import yfinance  # noqa: F401
    except ImportError:
        return _atlandi(etiket, "yfinance kurulu değil (pip install yfinance)")
    satirlar = []
    for s in semboller:
        try:
            satirlar.append(_teknik_ozet(s))
        except Exception as e:  # tek sembol hatası tüm paketi bozmasın
            satirlar.append(f"{s}: hata ({e.__class__.__name__})")
    return f"[{etiket} – Yahoo Finance, günlük, gecikmeli]\n" + "\n".join(satirlar)


# ---------------------------------------------------------------- Türkiye
EVDS_SERILER = {
    "TP.DK.USD.A.YTL": "USD/TRY alış",
    "TP.FG.J0": "TÜFE (2003=100)",
    "TP.PY.P02.1HI": "TCMB 1 hafta repo (politika faizi)",
}


def tcmb_evds(_: dict) -> str:
    anahtar = _anahtar("TCMB_EVDS_API_KEY")
    if not anahtar:
        return _atlandi("TCMB EVDS", "TCMB_EVDS_API_KEY tanımlı değil")
    bitis = dt.date.today()
    bas = bitis - dt.timedelta(days=120)
    url = (
        "https://evds2.tcmb.gov.tr/service/evds/series=" + "-".join(EVDS_SERILER)
        + f"&startDate={bas:%d-%m-%Y}&endDate={bitis:%d-%m-%Y}&type=json"
    )
    try:
        r = requests.get(url, headers={"key": anahtar}, timeout=ZAMAN_ASIMI)
        r.raise_for_status()
        kalemler = r.json().get("items", [])
    except Exception as e:
        return _atlandi("TCMB EVDS", f"istek hatası ({e.__class__.__name__})")
    satirlar = []
    for kod, ad in EVDS_SERILER.items():
        alan = kod.replace(".", "_")
        degerler = [(i["Tarih"], i.get(alan)) for i in kalemler if i.get(alan)]
        if degerler:
            satirlar.append(f"{ad}: son {degerler[-1][1]} ({degerler[-1][0]}); ilk {degerler[0][1]} ({degerler[0][0]})")
    return "[TCMB EVDS]\n" + ("\n".join(satirlar) or "seri bulunamadı")


def _rss(url: str, etiket: str, adet: int = 15) -> str:
    try:
        import feedparser
    except ImportError:
        return _atlandi(etiket, "feedparser kurulu değil")
    try:
        akis = feedparser.parse(url)
        basliklar = [f"- {e.get('published', '')[:16]} {e.get('title', '').strip()}" for e in akis.entries[:adet]]
    except Exception as e:
        return _atlandi(etiket, f"hata ({e.__class__.__name__})")
    return f"[{etiket}]\n" + ("\n".join(basliklar) or "kayıt yok")


def kap(_: dict) -> str:
    # KAP'ın resmi bir açık API'si yok; Google News üzerinden KAP haberleri ve web araması ile tamamlanır.
    return _rss("https://news.google.com/rss/search?q=KAP+bildirimi&hl=tr&gl=TR&ceid=TR:tr", "KAP haberleri (Google News)")


def haberler_tr(_: dict) -> str:
    return _rss("https://news.google.com/rss/search?q=borsa+istanbul+OR+BIST&hl=tr&gl=TR&ceid=TR:tr", "Türkiye piyasa haberleri (Google News)")


def haberler_global(_: dict) -> str:
    anahtar = _anahtar("NEWSAPI_KEY")
    if not anahtar:
        return _rss("https://news.google.com/rss/search?q=stock+market+OR+fed&hl=en-US&gl=US&ceid=US:en", "Global piyasa haberleri (Google News)")
    try:
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": "business", "language": "en", "pageSize": 20},
            headers={"X-Api-Key": anahtar}, timeout=ZAMAN_ASIMI,
        )
        r.raise_for_status()
        return "[NewsAPI iş haberleri]\n" + "\n".join(f"- {a['title']}" for a in r.json().get("articles", []))
    except Exception as e:
        return _atlandi("NewsAPI", f"hata ({e.__class__.__name__})")


# ---------------------------------------------------------------- ABD
def fred(_: dict) -> str:
    anahtar = _anahtar("FRED_API_KEY")
    if not anahtar:
        return _atlandi("FRED", "FRED_API_KEY tanımlı değil")
    seriler = {"FEDFUNDS": "Fed fonlama faizi", "CPIAUCSL": "ABD TÜFE", "UNRATE": "İşsizlik", "DGS10": "ABD 10y getiri", "T10Y2Y": "10y-2y farkı"}
    satirlar = []
    for kod, ad in seriler.items():
        try:
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": kod, "api_key": anahtar, "file_type": "json", "sort_order": "desc", "limit": 2},
                timeout=ZAMAN_ASIMI,
            )
            r.raise_for_status()
            g = r.json()["observations"]
            satirlar.append(f"{ad}: {g[0]['value']} ({g[0]['date']}), önceki {g[1]['value']}")
        except Exception as e:
            satirlar.append(f"{ad}: hata ({e.__class__.__name__})")
    return "[FRED]\n" + "\n".join(satirlar)


def finnhub_haber(ayar: dict) -> str:
    anahtar = _anahtar("FINNHUB_API_KEY")
    if not anahtar:
        return haberler_global(ayar)
    try:
        r = requests.get("https://finnhub.io/api/v1/news", params={"category": "general", "token": anahtar}, timeout=ZAMAN_ASIMI)
        r.raise_for_status()
        return "[Finnhub piyasa haberleri]\n" + "\n".join(f"- {h['headline']} ({h.get('source', '')})" for h in r.json()[:20])
    except Exception as e:
        return _atlandi("Finnhub", f"hata ({e.__class__.__name__})")


def _sec_get(url: str):
    ua = _anahtar("SEC_USER_AGENT")
    if not ua:
        return None
    r = requests.get(url, headers={"User-Agent": ua}, timeout=ZAMAN_ASIMI)
    r.raise_for_status()
    return r


def sec_edgar(ayar: dict) -> str:
    if not _anahtar("SEC_USER_AGENT"):
        return _atlandi("SEC EDGAR", "SEC_USER_AGENT tanımlı değil")
    try:
        cikler = _sec_get("https://www.sec.gov/files/company_tickers.json").json()
        harita = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in cikler.values()}
        satirlar = []
        for t in ayar.get("izleme_listesi", {}).get("abd", []):
            cik = harita.get(t)
            if not cik:
                continue
            son = _sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()["filings"]["recent"]
            kayit = [f"{son['form'][i]} {son['filingDate'][i]}" for i in range(min(6, len(son["form"])))]
            satirlar.append(f"{t}: " + ", ".join(kayit))
        return "[SEC EDGAR son dosyalar]\n" + "\n".join(satirlar)
    except Exception as e:
        return _atlandi("SEC EDGAR", f"hata ({e.__class__.__name__})")


def sec_form4(ayar: dict) -> str:
    if not _anahtar("SEC_USER_AGENT"):
        return _atlandi("SEC Form 4", "SEC_USER_AGENT tanımlı değil")
    return _rss(
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&count=40&output=atom",
        "SEC Form 4 (içeriden alım-satım) son bildirimler", 25,
    )


# ---------------------------------------------------------------- sosyal medya
def stocktwits(ayar: dict) -> str:
    try:
        r = requests.get("https://api.stocktwits.com/api/2/trending/symbols.json", timeout=ZAMAN_ASIMI)
        r.raise_for_status()
        semboller = [s["symbol"] for s in r.json().get("symbols", [])[:20]]
        return "[StockTwits trend semboller]\n" + ", ".join(semboller)
    except Exception as e:
        return _atlandi("StockTwits", f"hata ({e.__class__.__name__})")


def reddit(_: dict) -> str:
    kimlik, sir = _anahtar("REDDIT_CLIENT_ID"), _anahtar("REDDIT_CLIENT_SECRET")
    if not (kimlik and sir):
        return _atlandi("Reddit", "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET tanımlı değil")
    try:
        ua = {"User-Agent": "borsa-ajanlari/0.1"}
        tok = requests.post("https://www.reddit.com/api/v1/access_token", auth=(kimlik, sir),
                            data={"grant_type": "client_credentials"}, headers=ua, timeout=ZAMAN_ASIMI).json()["access_token"]
        satirlar = []
        for sub in ("wallstreetbets", "stocks", "borsaistanbul"):
            r = requests.get(f"https://oauth.reddit.com/r/{sub}/hot", params={"limit": 10},
                             headers={**ua, "Authorization": f"bearer {tok}"}, timeout=ZAMAN_ASIMI)
            for p in r.json()["data"]["children"]:
                satirlar.append(f"- r/{sub} ({p['data']['score']}↑): {p['data']['title']}")
        return "[Reddit sıcak başlıklar]\n" + "\n".join(satirlar)
    except Exception as e:
        return _atlandi("Reddit", f"hata ({e.__class__.__name__})")


def x_twitter(ayar: dict) -> str:
    token = _anahtar("X_BEARER_TOKEN")
    if not token:
        return _atlandi("X/Twitter", "X_BEARER_TOKEN tanımlı değil (web araması ile tamamlanır)")
    sorgu = "(BIST OR borsaistanbul OR $SPY OR $NVDA) lang:tr OR lang:en -is:retweet"
    try:
        r = requests.get("https://api.x.com/2/tweets/search/recent",
                         params={"query": sorgu, "max_results": 50, "tweet.fields": "public_metrics,created_at"},
                         headers={"Authorization": f"Bearer {token}"}, timeout=ZAMAN_ASIMI)
        r.raise_for_status()
        tw = sorted(r.json().get("data", []), key=lambda t: -t["public_metrics"]["like_count"])[:20]
        return "[X son tweetler]\n" + "\n".join(f"- ({t['public_metrics']['like_count']}♥) {t['text'][:200]}" for t in tw)
    except Exception as e:
        return _atlandi("X/Twitter", f"hata ({e.__class__.__name__})")


KAYNAKLAR: dict[str, Callable[[dict], str]] = {
    "fiyat_bist": lambda a: fiyat_listesi(a["izleme_listesi"]["bist"], "BIST fiyat ve teknik"),
    "fiyat_abd": lambda a: fiyat_listesi(a["izleme_listesi"]["abd"], "ABD fiyat ve teknik"),
    "fiyat_global": lambda a: fiyat_listesi(a["izleme_listesi"]["global"], "Global endeks, emtia, kur"),
    "tcmb_evds": tcmb_evds,
    "kap": kap,
    "haberler_tr": haberler_tr,
    "haberler_global": haberler_global,
    "fred": fred,
    "finnhub_haber": finnhub_haber,
    "sec_edgar": sec_edgar,
    "sec_form4": sec_form4,
    "stocktwits": stocktwits,
    "reddit": reddit,
    "x_twitter": x_twitter,
}


class VeriToplayici:
    """Aynı çalıştırmada her kaynağı yalnızca bir kez çeker (önbellek)."""

    def __init__(self, ayar: dict, cevrimdisi: bool = False):
        self.ayar = ayar
        self.cevrimdisi = cevrimdisi
        self._onbellek: dict[str, str] = {}

    def getir(self, ad: str) -> str:
        if ad not in self._onbellek:
            if self.cevrimdisi:
                self._onbellek[ad] = _atlandi(ad, "çevrimdışı mod")
            elif ad not in KAYNAKLAR:
                self._onbellek[ad] = _atlandi(ad, "bilinmeyen kaynak")
            else:
                self._onbellek[ad] = KAYNAKLAR[ad](self.ayar)
        return self._onbellek[ad]

    def paket(self, adlar: list[str]) -> str:
        return "\n\n".join(self.getir(a) for a in adlar)
