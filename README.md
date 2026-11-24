# Borsa Ajanları – Yedi Ajanlı Araştırma Ekibi (BIST + ABD)

Borsa İstanbul ve ABD borsaları (NYSE/Nasdaq) için yedi uzman yapay zekâ ajanı ve onları yöneten bir koordinatör. Ajanlar paralel çalışır, her biri kendi veri paketini ve gerekirse web aramasını kullanır, koordinatör raporları karşılaştırıp tek bir strateji raporu yazar.

> Bu sistem bir araştırma aracıdır, yatırım tavsiyesi vermez ve emir göndermez.

## Ekip

| # | Ajan | Odak | Veri kaynakları |
|---|------|------|-----------------|
| 1 | Ekonomist 1 – Türkiye Makro | TCMB, enflasyon, kur, CDS, bütçe, BIST'e makro etki | TCMB EVDS, Türkçe haberler, global fiyatlar |
| 2 | Ekonomist 2 – Küresel Makro | Fed/ECB, ABD verileri, dolar, emtia, risk iştahı | FRED, Finnhub haberleri, global fiyatlar |
| 3 | Trader 1 – Kısa Vade / Teknik | GOA, RSI, MACD, ATR, kırılımlar; giriş/stop/hedef | BIST + ABD + global fiyat ve teknik göstergeler |
| 4 | Trader 2 – Pozisyon / Risk | Portföy dağılımı, pozisyon boyutu, risk limitleri, şeytanın avukatı | BIST + ABD + global fiyat ve teknik göstergeler |
| 5 | Analist 1 – Ulusal (BIST) | KAP, bilanço, değerleme, sektörler, temettü | KAP haberleri, BIST fiyatları, Türkçe haberler |
| 6 | Analist 2 – Uluslararası (ABD ağırlıklı) | ABD hisseleri, SEC dosyaları, bilanço sezonu, sektör rotasyonu | ABD fiyatları, SEC EDGAR, Finnhub, FRED |
| 7 | Sektör, Yönetici ve Sosyal Medya İstihbaratı | Yönetici değişiklikleri, içeriden alım-satım, söylentiler, sosyal medya duygusu, manipülasyon uyarısı | StockTwits, Reddit, X, KAP, SEC Form 4, haberler |
| ★ | Koordinatör | Raporları birleştirir, çelişkileri çözer, nihai önerileri yazar | Yedi ajan raporu + otomatik konsensüs tablosu |

Rol tanımları `borsa_ajanlari/prompts/` klasöründedir ve düz Markdown'dır; kod değiştirmeden düzenlenebilir.

## Nasıl çalışır

1. `config.yaml` içindeki her ajanın ihtiyaç duyduğu veri kaynakları bir kez çekilir.
2. Yedi ajan aynı anda çalışır (varsayılan model `claude-sonnet-5-5`, Anthropic web araması açık).
3. Her ajan raporunun sonuna makine tarafından okunabilir bir JSON bloğu ekler (görüş, güven, AL/TUT/SAT/IZLE önerileri).
4. Bu bloklardan güven ağırlıklı bir konsensüs tablosu hesaplanır.
5. Koordinatör (`claude-opus-5-5`) tüm raporları ve konsensüsü okuyup nihai raporu yazar.
6. Çıktılar `raporlar/YYYY-AA-GG_SSDD/` klasörüne kaydedilir: `00_koordinator_raporu.md`, her ajanın raporu ve `konsensus.json`.

## Kurulum

```bash
git clone https://github.com/drNevzatuslu/borsa && cd borsa
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # sonra .env dosyasını doldurun
```

### API anahtarları

Yalnızca `ANTHROPIC_API_KEY` zorunludur. Diğerleri boş kalırsa o kaynak atlanır ve ajan web aramasıyla tamamlar. Anahtarlar sadece `.env` dosyasında durur, `.env` git'e girmez.

| Değişken | Zorunlu | Ücret | Nereden alınır | Kullanan ajanlar |
|----------|---------|-------|----------------|------------------|
| `ANTHROPIC_API_KEY` | Evet | Kullanım başına | console.anthropic.com | Hepsi |
| `TCMB_EVDS_API_KEY` | Önerilir | Ücretsiz | evds2.tcmb.gov.tr → Profil → API anahtarı | Ekonomist 1 |
| `FRED_API_KEY` | Önerilir | Ücretsiz | fred.stlouisfed.org/docs/api/api_key.html | Ekonomist 2, Analist 2 |
| `FINNHUB_API_KEY` | Önerilir | Ücretsiz katman | finnhub.io | Ekonomist 2, Analist 2, İstihbarat |
| `SEC_USER_AGENT` | Önerilir | Ücretsiz | Anahtar değil; "Ad Soyad e-posta" yazılır (SEC kuralı) | Analist 2, İstihbarat |
| `NEWSAPI_KEY` | İsteğe bağlı | Ücretsiz katman | newsapi.org | Ekonomistler (yoksa Google News RSS) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | İsteğe bağlı | Ücretsiz | reddit.com/prefs/apps ("script" uygulama) | İstihbarat |
| `X_BEARER_TOKEN` | İsteğe bağlı | Ücretli (Basic+) | developer.x.com | İstihbarat |

Anahtar gerektirmeyen kaynaklar: Yahoo Finance (yfinance, BIST `.IS` ve ABD fiyatları, gecikmeli), Google News RSS (Türkçe ve İngilizce haber), StockTwits trend sembolleri.

## Çalıştırma

```bash
python -m borsa_ajanlari                       # tam ekip, varsayılan görev
python -m borsa_ajanlari --gorev "Bankacılık hisselerini PPK öncesi değerlendir"
python -m borsa_ajanlari --ajan analist_ulusal istihbarat_sosyal   # sadece seçili ajanlar
python -m borsa_ajanlari --deneme              # API ve ağ çağrısı yapmadan akışı dener
pytest -q                                      # testler
```

İzleme listesi (`config.yaml` → `izleme_listesi`) BIST için `.IS` uzantılı Yahoo sembolleri, ABD için düz semboller kullanır. Modeller ve token sınırı da `config.yaml` içindedir.

## Neden bu tasarım (hazır projelerin incelemesi)

Hazır açık kaynak çok ajanlı borsa projeleri incelendi:

- **TauricResearch/TradingAgents** (Apache-2.0): Analist ekibi → boğa/ayı tartışması → trader → risk yönetimi → nihai karar akışı. Bugün Tauric'in kendi API anahtarını isteyen bir TypeScript CLI'ya dönüştü ve ABD odaklıdır.
- **virattt/ai-hedge-fund** (MIT): Ünlü yatırımcı tarzlarında ajanlar, kâğıt üzerinde işlem ve geriye dönük test. Veri için ücretli Financial Datasets API'si gerekir, BIST desteği yoktur.

İkisi de istenen yedi rolü (iki ekonomist, iki trader, ulusal/uluslararası analist, sosyal medya istihbaratı) ve Borsa İstanbul verisini karşılamadığı için, bu depo TradingAgents'ın kanıtlanmış akışını (paralel uzman raporları → karşıt görüşler → risk süzgeci → koordinatör kararı) örnek alır ama kodu kopyalamaz; BIST (TCMB, KAP) ve ABD (FRED, SEC, Finnhub) veri kaynaklarını ekler. ABD hisselerinde ikinci görüş isteyenler bu iki aracı ayrıca kurup kullanabilir.

## Sınırlar ve güvenlik

- Fiyatlar gecikmeli ve günlüktür; gün içi işlem için uygun değildir.
- KAP'ın açık bir API'si olmadığından KAP verisi haber akışı ve web aramasıyla toplanır.
- İstihbarat ajanı yalnızca kamuya açık iş ve piyasa bilgisini kullanır; doğrulanmamış söylentiyi tek başına AL/SAT gerekçesi yapmaz.
- Sistem emir göndermez. Bir aracı kurum API'sine bağlamadan önce ayrıca risk kontrolleri eklenmelidir.

## Yapı

```
config.yaml                  ajanlar, modeller, izleme listesi, veri eşlemesi
.env.example                 API anahtarı şablonu (gerçek değerler .env'de)
borsa_ajanlari/
  prompts/*.md               7 rol + koordinatör + ortak kurallar
  veri.py                    veri kaynakları (yfinance, EVDS, FRED, SEC, Finnhub, Reddit, X, StockTwits, RSS)
  ekip.py                    LLM sarmalayıcı, paralel ajan çalıştırma, konsensüs, koordinatör
  __main__.py                komut satırı
tests/                       uçtan uca deneme testi dahil
```
