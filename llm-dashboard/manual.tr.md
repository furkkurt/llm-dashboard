# LLM Dashboard — kullanıcı kılavuzu

**Proje kökü:** `setup.sh` / `setup.bat`, `backend/` ve `frontend/` klasörlerini içeren dizin. Bu depoda bu yol `llm-eval/llm-dashboard/` şeklindedir.

Bu belge **ana kullanıcı kılavuzudur**: aracın amacı, yapısı, **Linux** ve **Windows** üzerinde kurulum ve çalıştırma, kullanılan teknolojiler. **Puan formülleri ve API ayrıntıları** [§ Metrik tanımları](#metrik-tanımları-araştırma-özeti-hizalaması) bölümünde başlar. Çalışma tasarımı, veri ve değerlendirme prosedürünü Türkçe anlatan metodoloji özeti için **`yontem.md`** dosyasına bakın.

---

## Bu projenin amacı

Panel, farklı **LLM** çıktılarını (ör. ChatGPT, Claude, Gemini) **aynı istem** üzerinden karşılaştırmanıza yardımcı olur:

- **Gerçek araç zincirleri** mümkün olduğunda: Kotlin ve Flutter/Dart, yalnızca metin benzerliği değil derleme/analiz tarzı adımlarla işlenir.
- **Yapılandırılmış puanlar**: derlenebilirlik, statik analiz sağlığı, araç verimliliği ve istem sadakati (manuel ve/veya isteğe bağlı yapay zekâ destekli).
- **Kalıcılık**: yerel SQLite veritabanında; tekrarlanabilir ve denetlenebilir çalışma (`snippet_id` paylaşımı, geçmiş, isteğe bağlı “kazanan” görünümleri).

**Bu, zemin gerçekliği etiketli bir kıyaslama değildir.** Sayılar **sezgisel** (ayarlanabilir kurallar, öznel sadakat). Amaç **pratik bir iş akışı**: istem + kod yapıştır, analiz çalıştır, modelleri karşılaştır, sonuçları dışa aktar veya sonra tekrar aç.

**Kapsam dışı:** üstünlüğün istatistiksel kanıtı, güvenlik sertifikasyonu veya isteğe bağlı yapay zekâ yorumunu mutlak hakem saymak.

---

## Nasıl çalışır (özet)

1. **Streamlit** web arayüzü (`frontend/app.py`) ile **hedef dil** (**Kotlin**, **Flutter** veya **Her ikisi — Both**), **snippet kimliği**, **istem** ve her modelin **kodu** girilir (**Both** seçiliyse Flutter satırı + Kotlin satırı, toplam altı kutu; yalnızca seçilen dil satırı analiz edilir).
2. Arayüz **`POST /analyze`** isteğini **FastAPI** arka ucuna (`backend/main.py`) gönderir.
3. **Analyzer** (`backend/analyzer.py`) geçici proje oluşturur, ilgili araçları çalıştırır (Dart analyzer, düz JVM Kotlin için **kotlinc**, **Detekt**, Flutter **pub get** döngüleri). **`android.*` / `androidx.*` içeren** Kotlin parçalarında tek dosyalı **kotlinc** **atlanır** (geçici ortamda Android SDK yok); **Detekt** yine çalışır. Arka uç çalışmayı **puanlar** (`backend/paper_scoring.py`), **Compare/History kazananı** için **`quality_composite_0_100`** dahil.
4. İsteğe bağlı **yapay zekâ yorumu** (`backend/commentary.py`, **OpenRouter**) yapılandırıldığında sadakat tarzı puan ve metin ekleyebilir.
5. Sonuçlar **`results/`** altında (varsayılan SQLite) saklanır ve arayüzde gösterilir; **History & winner** aynı API’yi kullanır.

| Bileşen | Rol |
|---------|-----|
| **FastAPI** (`backend/main.py`) | REST API: `/analyze`, `/results`, `/health/commentary`, vb. |
| **Streamlit** (`frontend/app.py`) | **LLM Dashboard** arayüzü: modelleri karşılaştır, metrik tabloları, grafikler, geçmiş; snippet JSON **Ayarlar** (sol sütun). |
| **SQLite** (`backend/database.py`) | Çalışmaları saklar; aynı mantıksal anahtar **mevcut satırı günceller**, çoğaltmaz. |
| **Analyzer** (`backend/analyzer.py`) | Kotlin / Flutter geçici projeleri, derleme ve statik analiz, metrik JSON; Android içe aktaran Kotlin’de JVM `kotlinc` atlanır. |
| **Kotlin derleyici** (`tools/kotlin/`, `setup.sh` / `setup.bat`) | Paketlenmiş **kotlinc**; **`KOTLIN_HOME`** ile geçersiz kılınabilir. **JDK** `PATH`’te olmalı. |
| **Detekt** (`tools/detekt-cli.jar`) | Kotlin statik analizi (JAR ayrı indirilir; önkoşullara bakın). |
| **OpenRouter** (isteğe bağlı) | `OPENROUTER_API_KEY` tanımlıyken `auto_commentary` ve sağlık kontrolleri için sohbet tamamlamaları. |

Arayüz API ile HTTP üzerinden konuşur. Varsayılan taban URL: **`http://127.0.0.1:8000`** (ortamda `API_BASE_URL`). API çalışmıyorsa analiz eylemleri API yeniden ayağa kalkana kadar başarısız olur.

---

## Streamlit arayüz düzeni

Uygulamayı açtığınızda (varsayılan **http://localhost:8501**):

1. **Başlık** — **LLM Dashboard** **sekmelerin üstünde, sol üstte** görünür; kısa bir alt başlık eşlik eder. Tarayıcı sekmesi başlığı da **LLM Dashboard**’dur. Başlık ve alt başlık renkleri **Streamlit temasına** (Ayarlar → Theme) uyar: **karanlık** modda başlık **açık renkli metin** kullanır; **açık** modda koyu metin.
2. **Sekmeler** — Başlığın hemen altında **Compare models** ve **History & winner** bulunur.
3. **Compare models** üç sütun kullanır:
   - **Sol — Ayarlar:** hedef dil (**Kotlin** / **Flutter** / **Both**), **Snippet ID**, **Snippet bundle**, isteğe bağlı **Use AI for task faithfulness & commentary**, etkinse salt okunur yapay zekâ çıktı alanı.
   - **Orta — Prompt and model outputs:** paylaşılan istem; ayara göre **Flutter (Dart)** satırı (üç sütun: ChatGPT, Claude, Gemini) ve/veya **Kotlin** satırı; **COMPARE MODELS**.
   - **Sağ — Live analysis results:** karşılaştırma tablosu, **Altair** çubuk grafikleri (**Both** modunda **Flutter = mavi**, **Kotlin = turuncu**), her çalıştırma anahtarı için genişletilebilir rapor (ör. `ChatGPT (Kotlin)`).

Snippet JSON varsayılan olarak **sürüm 2**: `version`, `snippet_id`, `target_language` (**`Both`** dahil), `prompt`, `code_flutter_*`, `code_kotlin_*`. Eski **sürüm 1** (`code_chatgpt`, …) dosyaları yüklenmeye devam eder. **İndir** davranışı **manual.md** ile aynıdır.

---

## Teknolojiler

| Katman | Teknoloji |
|--------|-----------|
| Dil | **Python** 3.10+ (3.12+ önerilir) |
| Web API | **FastAPI**, **Uvicorn** |
| Arayüz | **Streamlit** |
| Veri / tablolar | **Pandas** (arayüz tabloları), **SQLite** (kalıcılık) |
| Grafikler (Compare) | **Altair** (**Both** karşılaştırmasında dile göre gruplanmış çubuklar) |
| HTTP istemcisi | **Requests** (arayüz → API) |
| İsteğe bağlı yapay zekâ | **OpenRouter** (OpenAI uyumlu HTTP API; model `OPENROUTER_MODEL`) |
| Kotlin analizi | **kotlinc** (`setup` sonrası `tools/kotlin` veya `KOTLIN_HOME` / `PATH`), **Detekt** (JAR), **JDK** |
| Flutter analizi | **Flutter / Dart** SDK, `PATH` üzerinde `flutter`, `dart` |

---

## Önkoşullar

- **Python** 3.10+ ve `pip` (Windows’ta `setup.bat` genelde `python` kullanır).
- **Git** (depoyu klonlamak için) — kaynak zaten elinizdeyse isteğe bağlı.
- **Kotlin yolu:** **`./setup.sh`** veya **`setup.bat`** ile **Kotlin derleyicisini** **`tools/kotlin/`** altına kurun (Linux/macOS’ta isteğe bağlı **`KOTLIN_VERSION`**). **`java` (JDK 17+)** `PATH`’te olmalı. **`detekt-cli.jar`** dosyasını `tools/` içine koyun veya **`DETEKT_JAR`** ayarlayın. İsteğe bağlı **`KOTLIN_HOME`** paketlenmiş yolu geçersiz kılar.
- **Flutter yolu:** **Flutter/Dart** kurulu olsun; Flutter parçalarını analiz ederken `flutter` ve `dart` **PATH**’te olsun.
- **İsteğe bağlı:** yapay zekâ yorumu ve `/health/commentary` için **[OpenRouter](https://openrouter.ai)** API anahtarı.

---

## Kurulum — Linux ve macOS

```bash
cd /path/to/llm-eval/llm-dashboard
chmod +x setup.sh start.sh stop.sh   # gerekirse
./setup.sh
source .venv/bin/activate
```

`setup.sh`: `backend/main.py` varlığını doğrular, **`.venv`** oluşturur ve **`requirements.txt`** yükler, **`tools/`**, **`results/`**, **`temp/runs/`**, **`scripts/`** vb. oluşturur; eksikse **Kotlin `kotlinc`** indirip **`tools/kotlin/`** içine yerleştirir. **`.env`** / **`local.env`** dosyalarını oluşturmaz veya değiştirmez.

```bash
cp .env.example .env
cp local.env.example local.env   # sırlar için önerilir (gitignore)
```

Yükleyici sırası: önce **`.env`**, sonra **`local.env`** (çakışan anahtarlarda ikinci dosya kazanır). Dosyaları **diske kaydedin**; çalışan süreçler yalnızca diskteki dosyaları görür.

---

## Kurulum — Windows

1. **Komut İstemi** veya **PowerShell** açın.
2. `backend\main.py` ve `setup.bat` içeren klasöre `cd` yapın.

```bat
setup.bat
```

`.venv` oluşturur, bağımlılıkları yükler. `python` bulunamazsa [python.org](https://www.python.org/downloads/) üzerinden kurun ve **PATH**’e ekleyin.

```bat
.venv\Scripts\activate
```

```bat
copy .env.example .env
copy local.env.example local.env
```

Kotlin analizi için **`detekt-cli.jar`** dosyasını **`tools\`** içine indirin.

---

## Çalıştırma — Linux ve macOS

**Seçenek A — tek komut (API + arayüz)**

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
./start.sh
```

**Başka bir terminalde** gerektiğinde:

```bash
./stop.sh
```

**Seçenek B — iki terminal**

Terminal 1 — API:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — arayüz:

```bash
streamlit run frontend/app.py --server.port 8501
```

Arayüz: **http://localhost:8501**. API belgeleri: **http://127.0.0.1:8000/docs**.

---

## Çalıştırma — Windows

```bat
start.bat
```

**http://localhost:8501** adresini açın. Streamlit kapandıktan sonra arka planda **Uvicorn** çalışıyor olabilir; **8000** portu meşgalse Görev Yöneticisi veya:

```bat
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

---

## Arayüzde tipik iş akışı

1. **LLM Dashboard** başlığının altındaki **Compare models** sekmesini açın.
2. **Sol Ayarlar** sütununda **Kotlin**, **Flutter** veya **Both** ve **Snippet ID** seçin/girin.
3. **Snippet bundle** ile JSON indirin/yükleyin (v2: altı kod alanı; v1 uyumluluğu sürer).
4. **Orta** sütunda **istem** ve etkin dil satır(lar)ındaki kodları yapıştırın; **COMPARE MODELS** (seçilen dil başına dolu her kutu için bir **`POST /analyze`**).
5. İsterseniz Ayarlarda **Use AI for task faithfulness & commentary (OpenRouter)** seçeneğini açın (API anahtarı gerekir).
6. **History & winner** ile geçmişi yükleyin; kazanan **araştırma birleşik puanı** (`quality_composite_0_100`) ile belirlenir (**manual.md** §5).

Metrik anlamları ve formüller için bu dosyanın devamına bakın. Kısa özet ve sorun giderme için **`README.md`**. İngilizce ana kılavuz **`manual.md`**; metrik tanımlarının Türkçesi **`metrics.tr.md`**. Makale odaklı Türkçe metodoloji: **`yontem.md`**.

---

## Testler ve sağlık kontrolleri

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
pytest
```

API açıkken: **GET** `http://127.0.0.1:8000/health/commentary` OpenRouter yapılandırmasını doğrular. CLI: `python -m backend.openrouter_check`.

---

## Güvenlik ve veri

- **`.env`** ve **`local.env`** gitignore’dadır; sırlar için **`local.env`** tercih edin.
- Veritabanı ve geçici çalışmalar varsayılan olarak **`results/`** ve **`temp/`** altındadır.

---

# Metrik tanımları (araştırma özeti hizalaması)

Bu bölümün geri kalanı **puanların nasıl hesaplandığını** ve API / depolama ile ilişkisini tanımlar. Formüller **sezgisel** araştırma yardımcılarıdır, istatistiksel test değildir.

## 1. Derlenebilirlik (0–100)

İkili: araç zinciri parçayı geçerli kabul ediyorsa veya derleme başarılıysa **100**, aksi halde **0**. “Kodun derlenebilirliği” geçit olarak eşlenir.

**Android / AndroidX Kotlin:** Parça **`android.*`**, **`androidx.*`** veya **`com.google.android.*`** içe aktarıyorsa tek dosyalı **kotlinc** **çalıştırılmaz**. Bir **bilgi** statik bayrağı (`kotlin_pipeline`) kaydedilir; **`compilable`** hat için **true** sayılabilir ancak bu, tam bir **Gradle/cihaz** derlemesini doğrulamaz. **Detekt** kaynak dosyada çalışmaya devam eder.

## 2. Statik analiz sağlığı (0–100)

100 ile başlar; analizör çıktısından cezalar uygulanır:

- Mümkünse yapılandırılmış sayımlar (`analyzer_errors`, `analyzer_warnings`, `analyzer_infos`).
- Aksi halde ayrıştırılmış hata günlüğü ve statik bayraklardan yaklaşım; `flutter_scaffold` gürültüsü hariç.

Örnek ceza: `100 − 12×hata − 3.5×uyarı − 0.8×bilgi`, `[0, 100]` içinde kırpılır.

## 3. Araç verimliliği (0–100)

Toplam duvar süresi, üst sınıra (varsayılan **300_000 ms**) göre: `100 × (1 − min(1, duration_ms / cap_ms))`. Süre yoksa **50** (nötr). Süre sıfırsa **100**.

## 4. İstem sadakati (manuel veya isteğe bağlı yapay zekâ, 1–5 → 0–100)

Arayüzde **1 (zayıf)** … **5 (güçlü)** derecelendirilebilir; veritabanında `faithfulness_score`, 0–100 eşlemesi `puan × 20`.

Derecelendirme yoksa `faithfulness_rated: false`; sadakat ağırlığı **devreye girmez** ve diğer üç eksen yeniden normalize edilir (**manual.md** §5).

### İsteğe bağlı yapay zekâ yorumu — OpenRouter (`auto_commentary`)

`auto_commentary: true` ve **`OPENROUTER_API_KEY`** ile API **[OpenRouter](https://openrouter.ai)** üzerinden **`POST /v1/chat/completions`** çağırır. JSON: **`faithfulness_score_0_100`**, **`faithfulness_note`**, **`metrics_comment`**. Anahtar **`local.env`** ve/veya **`.env`** içinde; `.env` sonra **`local.env`** (ikincisi kazanır). **Uvicorn’u** düzenlemeden sonra yeniden başlatın.

Yapay zekâ mutlak hakem değildir; eksik anahtar veya ayrıştırma hataları `ai_commentary.error` alanını doldurur, analiz isteğini düşürmez.

`COMMENTARY_TIMEOUT_SEC` ile zaman aşımı (varsayılan 60). Yorum `metrics_json.ai_commentary` altında saklanır.

## 5. Compare / History kazananı: araştırma birleşik puanı (`quality_composite_0_100`)

**Compare models** ve **History & winner**, kazananı **`paper_scores.quality_composite_0_100`** (0–100, yüksek iyi) ile belirler. Dört 0–100 bileşenin ağırlıklı ortalamasıdır; **sadakat dereceli değilse** o eksen devreye girmez ve diğer üç ağırlık yeniden normalize edilir:

| Bileşen | Anlam | Varsayılan ağırlık |
|--------|--------|---------------------|
| **MI** | **metrics.md** §4 Sürdürülebilirlik İndeksi, [0, 100] kırpılır; yoksa nötr **50** | 0,30 |
| **İç içe geçme** | Düşük **avg_nesting_depth** iyi: `max(0, min(100, 100 − 15×derinlik))`; yoksa **50** | 0,10 |
| **Analizör temizliği** | §2 ile aynı ceza yapısı: `100 − 12×hata − 3,5×uyarı − 0,8×bilgi` | 0,30 |
| **Sadakat** | Dereceli **faithfulness_0_100**; derecesizse eksen **hariç** | 0,30 |

Uygulama: **`backend/paper_scoring.py`** (`QUALITY_COMPOSITE_WEIGHTS`, `attach_quality_composite`).

## 6. Eski `paper_scores` boyutları (API / dışa aktarım)

API hâlâ **`composite_default_0_100`** ve diğer 0–100 boyutlarını üretir; pano kazanan için **yeni araştırma birleşik** puanını kullanır.

## API ve depolama

- `GET /health/commentary` — OpenRouter duman testi. Eski takma ad: `GET /health/gemini`.
- `POST /analyze` — isteğe bağlı `faithfulness_score_1_5`, `faithfulness_notes`, `auto_commentary`.
- `PATCH /results/{id}` — sadakat güncellemesi; `metrics_json` içinde `paper_scores` yeniden hesaplanır.
- `GET /results`, `GET /results/{id}` — `metrics.paper_scores` dahil.
- Aynı `(llm_source, language, snippet_id, prompt, code)` ile yeniden gönderim **aynı `id`** ile satırı günceller.

## Sınırlamalar

- Sadakat özneldir; denetim için notlar kullanın.
- Statik cezalar ayarlanabilir sabitlerdir, etiketli veri setine göre kalibre edilmemiştir.
- Verimlilik, statik analizin yakaladıkları ötesinde doğruluğu koşullandırmadan hızı ödüllendirir.
- **JVM Kotlin** derlemesi Android sınıf yolu olmadan yapılır; Android bağımlı parçalarda bu adım atlanır (§1).
- **Kazanan** metriği sezgisel bir bileşiktir; istatistiksel üstünlük kanıtı değildir.

---

## Belge haritası

| Belge | İçerik |
|-------|--------|
| **`manual.md`** | Bu kılavuzun İngilizce sürümü |
| **Bu dosya (`manual.tr.md`)** | Kullanıcı kılavuzu (Türkçe) |
| **`metrics.md`** | Çapraz dil kod kalitesi metrikleri (İngilizce) |
| **`metrics.tr.md`** | **metrics.md** Türkçe çevirisi |
| **`metricguide.md`** | Geliştiriciler için uygulama ipuçları |
| **`README.md`** | Hızlı özet ve sorun giderme |
| **`yontem.md`** | Metodoloji (Türkçe): mimari, veri, yöntem, değerlendirme |
