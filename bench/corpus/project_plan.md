# Veri platformu göçü — 2026 H2

Eski Hadoop kümesinden bulut tabanlı lakehouse mimarisine geçiş planı. Sahibi: Veri Platformu ekibi.
Hedef tarih: 15 Aralık 2026. Bütçe: 420.000 €.

## Keşif ve envanter
- [x] Mevcut iş akışlarının envanteri
  Toplam 312 Airflow DAG'i, 48 Spark işi ve 17 Hive veritabanı tespit edildi.
- [x] Veri sahipleriyle görüşmeler
  - [x] Pazarlama analitiği
  - [x] Finans raporlama
  - [x] Ürün analitiği
  - [ ] Hukuk ve uyum
    KVKK kapsamındaki tablolar için ayrı onay gerekiyor.
- [x] Maliyet modeli
  Mevcut küme aylık 38.000 €; hedef mimari tahmini aylık 21.500 €.
- [/] Bağımlılık grafiğinin çıkarılması
  DAG'ler arası bağımlılıkların %70'i otomatik çıkarıldı, kalanı elle.

## Mimari
- [x] Depolama formatı seçimi (Iceberg vs Delta)
  Iceberg seçildi: çoklu motor desteği ve gizli bölümleme.
- [x] Katalog: AWS Glue yerine Nessie
- [/] Ağ ve güvenlik tasarımı
  - [x] VPC ve özel uç noktalar
  - [/] IAM rol modeli
  - [ ] Şifreleme anahtarlarının rotasyonu
- [ ] Felaket kurtarma planı
  RPO 1 saat, RTO 4 saat. Bölgeler arası kopya: eu-central-1 → eu-west-1.

## Göç dalgaları
### Dalga 1 — düşük riskli tablolar
- [x] 120 boyut tablosunun kopyalanması
- [x] Doğrulama betikleri
  ```sql
  SELECT count(*), sum(hash(*)) FROM eski.tablo
  EXCEPT
  SELECT count(*), sum(hash(*)) FROM yeni.tablo;
  ```
- [x] Okuyucuların yeni kataloğa yönlendirilmesi
### Dalga 2 — olay tabloları
- [/] Günlük olay tablolarının yeniden bölümlenmesi
  Bölümleme: gün + ülke kodu. Tahmini süre 3 hafta.
- [ ] Geçmiş verinin (2019–2023) arşiv katmanına taşınması
- [ ] Akış işlerinin (Kafka → Iceberg) devreye alınması
  - [ ] Şema kayıt defteri entegrasyonu
  - [ ] Tam olarak bir kez (exactly-once) yazım testi
### Dalga 3 — finans ve uyum
- [ ] Finans tablolarının göçü
  Ay sonu kapanışı sırasında göç yapılmayacak (her ayın son 3 iş günü).
- [ ] Hukuk onayı
- [-] Eski raporlama sunucusunun taşınması
  İptal: sunucu Ocak'ta tamamen kapatılacak.

## Doğrulama ve performans
- [ ] Sorgu performansı karşılaştırması (en yoğun 50 sorgu)
- [ ] Maliyet izleme panoları
- [ ] Veri kalitesi kuralları (Great Expectations)
  - [ ] Boş değer oranları
  - [ ] Benzersizlik kısıtları
  - [ ] Referans bütünlüğü

## Kapanış
- [ ] Eski kümenin salt okunur moda alınması
- [ ] Eski kümenin kapatılması
- [ ] Ekip eğitimi ve dokümantasyon
- [ ] Proje retrospektifi
