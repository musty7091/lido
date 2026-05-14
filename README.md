# Lido Masa Takip Sistemi

Lido Masa Takip Sistemi, Kuzey Kıbrıs'ta bulunan Lido isimli plaj/bar işletmesi için geliştirilecek web tabanlı masa doluluk, müşteri yönlendirme ve süre takip uygulamasıdır.

Uygulama internet üzerinden çalışacak şekilde tasarlanacaktır ve ilk hedef yayın ortamı PythonAnywhere olacaktır.

Bu proje sadece Lido işletmesine özel olarak geliştirilecektir.

---

## 1. Projenin Amacı

Bu uygulamanın amacı, Lido işletmesinde kapıdan gelen müşterilerin mevcut masa durumuna göre hızlı, doğru ve kullanıcı dostu şekilde uygun masalara yönlendirilmesini sağlamaktır.

Sistem aşağıdaki temel ihtiyaçları karşılayacaktır:

- Alt Bar, Üst Bar ve Ana Bar alanlarının canlı doluluk durumunu göstermek
- Boş, dolu, uzun süreli ve pasif masa durumlarını görsel olarak ayırmak
- Müşteri bilgisiyle birlikte masa ataması yapmak
- Müşterinin giriş saatini kaydetmek
- Müşteri masadan kalktığında masayı tekrar boşa almak
- Çıkış saatini ve toplam kalış süresini hesaplamak
- Günlük operasyon raporları oluşturmak
- Tablet uyumlu, sade ve hızlı bir kullanım deneyimi sunmak

---

## 2. İşletme Yapısı

Başlangıçta sistemde 3 ana alan olacaktır:

| Alan | Masa Kodları | Başlangıç Masa Sayısı |
|---|---|---:|
| Alt Bar | A1 - A100 | 100 |
| Üst Bar | U1 - U60 | 60 |
| Ana Bar | M1 - M50 | 50 |

Masa sayıları ve masa kapasiteleri yönetici tarafından güncellenebilir olacaktır.

---

## 3. Masa Kapasitesi

Her masa için kapasite bilgisi tutulacaktır.

Başlangıç kapasite seçenekleri:

- 2 kişilik
- 4 kişilik
- 6 kişilik
- Özel kapasite

Masa kapasitesi sonradan yönetici panelinden değiştirilebilir olmalıdır.

---

## 4. Müşteri Bilgileri

Masa ataması yapılırken aşağıdaki bilgiler tutulacaktır:

| Bilgi | Durum |
|---|---|
| Kişi sayısı | Zorunlu |
| Müşteri adı | Opsiyonel |
| Telefon | Opsiyonel |
| Not | Opsiyonel |
| Giriş saati | Sistem tarafından otomatik |
| Çıkış saati | Masa boşaltıldığında otomatik |
| Toplam süre | Sistem tarafından hesaplanır |

---

## 5. Kullanıcı Rolleri

İlk sürümde aşağıdaki kullanıcı rolleri hedeflenmektedir:

### Yönetici

- Tüm alanları görebilir
- Masa oluşturabilir
- Masa kapasitelerini güncelleyebilir
- Kullanıcıları yönetebilir
- Raporları görebilir
- Sistem ayarlarını düzenleyebilir

### Kapı Personeli

- Tüm alanları görebilir
- Boş ve dolu masaları takip edebilir
- Müşteriyi masaya yönlendirebilir
- Masa ataması yapabilir

### Bar Personeli

- Tüm alanları görebilir
- Uygun masaya müşteri yönlendirebilir
- Dolu masaları takip edebilir
- Müşteri masadan kalkınca masayı boşa alabilir

Not: İlk değerlendirmede bar personelinin sadece kendi alanını görmesi düşünülmüş olsa da son karar olarak bar personeli tüm alanları görebilecek ve yönlendirme yapabilecektir.

---

## 6. Teknik Kararlar

Başlangıç teknik kararları:

| Konu | Karar |
|---|---|
| Backend | Flask |
| Veritabanı | SQLite ile başlanacak |
| ORM | SQLAlchemy |
| Arayüz | HTML, CSS, Bootstrap |
| Yayın ortamı | PythonAnywhere |
| Kullanım cihazı | Tablet öncelikli |
| Canlı güncelleme | İlk aşamada periyodik otomatik yenileme |
| İşletme yapısı | Sadece Lido'ya özel |

İlk sürüm SQLite ile geliştirilecektir.

İleride eş zamanlı kullanım, veri hacmi veya performans ihtiyacı artarsa MySQL geçişi ayrıca değerlendirilecektir.

---

## 7. Çalışma Kuralları

Bu projede aşağıdaki çalışma kuralları geçerlidir:

- Önce kod yazılmaz.
- Önce repo ve mevcut durum analiz edilir.
- Dosya isimleri tahmin edilmez.
- Gerçek dosya yolları repodan kontrol edilir.
- Patch veya diff verilmez.
- Kod değişikliği gerekiyorsa her zaman kısaltmasız tam nihai dosya verilir.
- Büyük refactor yapılmaz.
- Fonksiyon, sınıf, dosya ve mevcut mimari isimleri gereksiz yere değiştirilmez.
- Her değişiklik küçük, kontrollü ve test edilebilir olur.
- Her adımda önce analiz ve plan verilir.
- Kullanıcı “onaylıyorum” demeden tam kod verilmez.
- Her öneride etkilenecek dosyalar açıkça belirtilir.
- Migration gerekip gerekmediği her adımda belirtilir.
- Test komutları ve beklenen sonuçlar her adımda yazılır.
- Teknik dil sade tutulur.
- Eksik, riskli veya hatalı görülen konular net ve dürüst şekilde belirtilir.

---

## 8. Geliştirme Disiplini

Her geliştirme adımı aşağıdaki sırayla ilerleyecektir:

1. Mevcut durum analizi
2. Etkilenecek dosyaların listesi
3. Migration gerekip gerekmediği
4. Plan
5. Kullanıcı onayı
6. Tam nihai dosya içeriği
7. Test komutları
8. Beklenen sonuç
9. Commit önerisi

---

## 9. Satış Öncesi Kalite Hedefi

Bu proje sadece çalışan bir demo olarak değil, gerçek işletmede kullanılabilecek güvenilir bir ürün olarak geliştirilecektir.

Bu nedenle geliştirme sürecinde aşağıdaki başlıklar dikkate alınacaktır:

- Güvenlik
- Kullanıcı girişi
- Rol ve yetki kontrolü
- CSRF koruması
- İşlem kayıtları
- Kurulum kolaylığı
- PythonAnywhere uyumluluğu
- Yedekleme
- Restore
- Raporlama
- Kullanıcı deneyimi
- Tablet uyumluluğu
- Hata yönetimi
- Satış öncesi sunuma uygun görünüm

---

## 10. İlk MVP Kapsamı

İlk çalışan sürümde hedeflenen özellikler:

- Kullanıcı giriş sistemi
- Yönetici, kapı personeli ve bar personeli rolleri
- Alt Bar, Üst Bar ve Ana Bar alanları
- Masa oluşturma
- Masa kapasitesi yönetimi
- Canlı masa doluluk ekranı
- Boş, dolu, uzun süreli ve pasif masa görünümleri
- Müşteri bilgisiyle masa atama
- Masa boşaltma
- Giriş saati, çıkış saati ve süre takibi
- Günlük temel raporlar
- Tablet uyumlu arayüz

---

## 11. Şimdilik Kapsam Dışı

İlk sürümde aşağıdaki özellikler yapılmayacaktır:

- Online ödeme
- POS entegrasyonu
- WhatsApp/SMS bildirimi
- Gelişmiş rezervasyon sistemi
- Çok işletmeli SaaS yapı
- Mobil uygulama
- WebSocket ile tam gerçek zamanlı canlılık
- Gelişmiş muhasebe entegrasyonu

Bu özellikler ihtiyaç doğarsa ileriki aşamalarda ayrıca değerlendirilecektir.

---

## 12. Onay Akışı

Bu projede her teknik değişiklikten önce analiz ve plan paylaşılır.

Kullanıcı “onaylıyorum” demeden tam kod veya dosya değişikliği uygulanmaz.

Amaç, küçük ve kontrollü adımlarla ilerleyerek projenin güvenli, anlaşılır ve sürdürülebilir şekilde geliştirilmesidir.