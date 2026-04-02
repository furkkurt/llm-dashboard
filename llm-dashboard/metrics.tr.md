# Büyük Dil Modelleri için Kod Kalitesi Metrikleri

## Genel bakış

Kotlin ve Flutter/Dart ekosistemlerinde Büyük Dil Modelleri (LLM) tarafından üretilen kodun kalitesini değerlendirmek için, nesnel olarak ölçülebilen, yazılım mühendisliği literatüründe yerleşik ve mevcut statik analiz araçlarımızdan (Kotlin için Detekt, Flutter için Dart analyzer) elde edilebilen, diller arası yazılım metrikleri kullanıyoruz. Bu metrikler, mevcut sadakat (faithfulness) değerlendirme bileşenlerini korurken LLM çıktılarını karşılaştırmak için hafif ama akademik olarak tutarlı bir temel sunar.

## Seçilen metrikler

Diller arası karşılaştırılabilirlik, akademik geçerlilik ve düşük uygulama maliyeti gereksinimlerini karşılayan beş temel metrik seçtik:

### 1. Ortalama döngüsel karmaşıklık (cyclomatic complexity)
**Tanım**: Program kaynak kodundaki doğrusal olarak bağımsız yolların sayısını ölçer; kod karmaşıklığı, test edilebilirlik ve olası hata eğilimi için bir göstergedir.
**Uygulama**: Üretilen kodda tüm fonksiyon/metotlar üzerinden ortalama döngüsel karmaşıklık olarak hesaplanır. Kotlin için Detekt’in `cyclomaticComplexity` metriğinden ve Flutter/Dart için Dart analyzer’ın eşdeğer ölçümünden türetilir. Düşük değerler daha basit, daha test edilebilir kod anlamına gelir.

### 2. Kod satırı (LOC) ve yorum oranı
**Tanım**: LOC kod boyutunu ölçer; yorum oranı ise yorum satırlarının toplam satıra bölünmesiyle dokümantasyon çabasını yansıtır.
**Uygulama**: Ham LOC diğer metrikler için boyut normalizasyonu sağlar. Yorum oranı sürdürülebilirlik ve okunabilirlik yatırımını gösterir. Her iki metrik de Detekt ve Dart analyzer çıktılarından lexer/AST işlemiyle çıkarılabilir.

### 3. Halstead hacmi ve zorluğu
**Tanım**: Hacim, benzersiz ve toplam işlemci/işlenen sayısına dayalı program boyutunu tahmin eder; zorluk kodu anlama veya yazma için gereken zihinsel çabayı tahmin eder.
**Uygulama**: İşlemciler (+, -, if, for vb.) ve işlenenler (değişkenler, sabitler) için jeton sayımlarından türetilir. Her iki metrik Detekt’ten alınabilir; Dart için tokenizer ile hesaplanabilir. Hacim kod boyutunu; zorluk geliştirme sırasındaki bilişsel yük ile ilişkilidir.

### 4. Sürdürülebilirlik indeksi (MI)
**Tanım**: LOC, döngüsel karmaşıklık ve Halstead hacmini birleştiren bileşik bir metrik (daha yüksek değer daha iyi sürdürülebilirlik).
**Uygulama**: Standart formül ile hesaplanır: MI = 171 - 5.2 * ln(Volume) - 0.23 * (Cyclomatic Complexity) - 16.2 * ln(LOC) + 50 * sin(sqrt(2.4 * perCM)); burada perCM yorum satırlarının yüzdesidir. Bu indeks hem endüstri araçlarında hem akademik çalışmalarda yaygın tek sayılı sürdürülebilirlik vekilidir.

### 5. Ortalama iç içe geçme derinliği
**Tanım**: İç içe kontrol yapılarının (if/for/while/try blokları) maksimum derinliğini ölçer; bilişsel karmaşıklık ve okunabilirlik zorluğu için vekil görevi görür.
**Uygulama**: Soyut sözdizim ağacı üzerinde iç içe seviyeler izlenerek, fonksiyon/metot başına maksimum derinliklerin ortalaması alınır. Detekt’in `nestedBlockDepth` metriğinden ve Dart analyzer için AST gezintisiyle uygulanabilir. Daha düşük değerler daha düz, daha okunabilir yapı anlamına gelir.

## Uygulama yaklaşımı

Bu metrikler mevcut değerlendirme hattına minimum kesintiyle entegre edilmiştir:

1. **Araç kullanımı**: Projede zaten bulunan statik analiz yardımcıları (`run_detekt.py`, `run_dart_analyze.py`) kullanılır; hedef metrikleri çıkarmak için hafif son işleme eklenir.

2. **Veri çıkarımı**: Araç çıktıları (Detekt XML, Dart analyzer JSON/metrikleri) standart sayısal değerlere dönüştüren metrik özgü ayrıştırıcılar eklenir.

3. **Model genişletmesi**: Mevcut sadakat alanları ve puanlama mekanizmaları korunarak `PaperScores` veri modeli yeni alanlarla genişletilir.

4. **Sonuç saklama**: Yeni metrikler mevcut analiz verisiyle birleştirilerek veritabanına yazılır. Panoda **kazanan**, eski **`composite_default_0_100`** yerine **`quality_composite_0_100`** ile seçilir. Uygulama: `backend/paper_scoring.py` içinde `attach_quality_composite`: **Sürdürülebilirlik İndeksi** [0, 100] kırpılır (yoksa nötr **50**), **iç içe geçme** `max(0, min(100, 100 − 15 × ortalama_derinlik))` (yoksa **50**), **analizör temizliği** (statik sağlık ile aynı ceza: 12×hata + 3,5×uyarı + 0,8×bilgi, 0–100), **sadakat** yalnızca **dereceli** ise; derecesizse ilk üç ağırlık (**0,30 / 0,10 / 0,30**) yeniden normalize edilir.

5. **Sezgisel diller arası çıkarım**: `AnalysisMetrics` oluşturulurken `backend/metrics_util.py`, kaynak metin üzerinde `backend/cross_language_metrics.compute_cross_language_metrics` çağırarak LOC, yorum satırları, Halstead tarzı ölçümler, döngüsel karmaşıklık, iç içe geçme ve MI’yi Detekt / Dart analyzer çıktılarıyla tutarlı biçimde tamamlar.

6. **Kotlin platform notu**: Tek dosyalı **kotlinc**, Android çerçevesi içe aktarmayan JVM Kotlin için çalıştırılır (`android.*`, `androidx.*`, `com.google.android.*` içeren parçalarda geçici ortamda SDK olmadığı için JVM derlemesi atlanır). **Detekt** yine çalışır. Mobil odaklı parçalar için “derlenebilirlik” anlamı buna göre sınırlıdır (`manual.md` §1).

## Akademik gerekçe

Bu metrik seçimi yazılım mühendisliği araştırmasında değer verilen kod kalitesi boyutlarını hedefler:

- **Doğruluk vekili**: Döngüsel karmaşıklık ve iç içe geçme derinliği test çabası ve hata yoğunluğu ile ilişkilidir.
- **Sürdürülebilirlik**: LOC, yorum oranı, Halstead metrikleri ve Sürdürülebilirlik İndeksi uzun vadeli kod sağlığını birlikte değerlendirir.
- **Bilişsel boyutlar**: İç içe geçme derinliği ve Halstead zorluğu okunabilirlik ve zihinsel çabayı yansıtır.
- **Çapraz platform geçerliliği**: Tüm metrikler dil özgü deyimlerden bağımsız tanımlara sahiptir; Kotlin/Dart adil karşılaştırmasına olanak verir.
- **Araştırma tekrarlanabilirliği**: İyi belgelenmiş, araç üretimi metrikler kullanımı çalışmalar arası tekrarlanabilirliği destekler.

Bu yaklaşım sadakat değerlendirmesini ayrı, ortogonal bir boyut olarak korurken akademik yayınlarda ampirik analiz için uygun, araç tabanlı nicel kod kalitesi ölçümleri ekler. Bu metrikler ikili başarı/başarısızlık oranlarının ötesinde eyleme dönük içgörüler sunar; farklı modeller, istem stratejileri ve sıcaklık ayarları arasında LLM üretimi kod kalitesinin incelikli karşılaştırmasına imkân verir.
