# عیب‌یابی باجه

اول همیشه این دو را ببین:

```bash
systemctl status chiz-kiosk chiz-admin
journalctl -u chiz-kiosk -b --no-pager | tail -60
```

## صفحه و نمایش

| علامت | علت محتمل | راه‌حل |
|---|---|---|
| بعد از نصب کامل، صفحه سیاه است یا فقط کنسول دیده می‌شود | دسکتاپ هنوز صفحه را گرفته، یا کاربر به `/dev/dri` دسترسی ندارد | `systemctl get-default` باید `multi-user.target` باشد؛ `groups` باید `video render input` داشته باشد؛ `sudo reboot` |
| در لاگ: `kmsdrm not available` / `No available video device` | SDL درایور kmsdrm را پیدا نکرد | `bash scripts/install_pi.sh` را دوباره اجرا کن (بسته‌ی `libsdl2-2.0-0`)؛ روی Pi 3 در `config.txt` باید `dtoverlay=vc4-kms-v3d` فعال باشد (پیش‌فرض Bookworm) |
| تصویر خوابیده یا ۹۰ درجه چرخیده | پنل افقی نصب شده | در `booth.toml`: `screen_rotate = 90` (یا `270` اگر برعکس شد) |
| تصویر کوچک یا با حاشیه‌ی سیاه | رزولوشن مانیتور با ۴۸۰×۸۰۰ فرق دارد | عادی است؛ نسبت حفظ می‌شود (`SCALED`) |
| حروف فارسی مربع مربع | فونت نیست | `ls assets/fonts` باید Vazirmatn و Lalezar را نشان بدهد؛ `make fonts` |
| تیترها با فونت سینا نیستند | فایل `SSINABD.TTF` کپی نشده | [setup-pi.md](setup-pi.md) بخش ۳ |
| صفحه بعد از چند دقیقه خاموش می‌شود | خاموش شدن خودکار کنسول | `grep consoleblank /boot/firmware/cmdline.txt` باید `consoleblank=0` بدهد |

## دکمه‌ها

| علامت | راه‌حل |
|---|---|
| هیچ دکمه‌ای کار نمی‌کند (در حالت کیوسک) | کاربر باید در گروه `input` باشد (`groups`)؛ بعد از نصب `sudo reboot` |
| هیچ دکمه‌ای کار نمی‌کند ولی کیبورد کار می‌کند | انکودر مثل دسته‌ی بازی است: `make factory-test` ← اسم‌ها (`joy0` …) ← `[booth.keymap]` ([wiring.md](wiring.md) بخش ۱) |
| factory-test باز نمی‌شود (در حالت کیوسک) | باجه صفحه را گرفته: `sudo systemctl stop chiz-kiosk`، بعد از تست `start` |
| دکمه‌ای کالای اشتباه را برمی‌دارد | `make factory-test` → ببین هر دکمه چه کلیدی می‌فرستد → `[booth.keymap]` را در `booth.toml` درست کن |
| با کیبورد کار می‌کند ولی با انکودر نه | انکودر را جدا امتحان کن: `sudo evtest` (با `sudo apt install evtest`) |

## قفل، سنسور در، نورها

| علامت | راه‌حل |
|---|---|
| قفل برعکس کار می‌کند (همیشه باز است) | ماژول رله Low-trigger است: `lock_active_high = false` |
| قفل باز نمی‌شود | `make factory-test` → دکمه‌ی قرمز رله را ۱ ثانیه می‌زند. صدای «تق» رله را بشنو. پایه‌ی `lock_gpio` و `lock_active_high` (قطبیت برد رله) را چک کن |
| شمارش معکوس شروع نمی‌شود | سنسور در: در factory-test وضعیت «باز / بسته» باید عوض شود. اگر برعکس است: `door_open_when_high = false` |
| نورها کم و زیاد نمی‌شوند | ماسفت باید **logic-level** باشد (مثل IRLZ44N)؛ پایه‌ها ۱۲ و ۱۳ (پیش‌فرض)؛ زمین (GND) رزبری و منبع ۱۲ ولت باید مشترک باشد |
| در لاگ: `gpiozero … falling back` یا هیچ کار سخت‌افزاری نمی‌کند | `python3-lgpio` نصب نیست، یا venv بدون `--system-site-packages` ساخته شده → `rm -rf .venv && bash scripts/install_pi.sh` |
| نوار LED رنگی (WS2812) روشن نمی‌شود | این نوار دسترسی root می‌خواهد و روی Pi 5 کار نمی‌کند؛ اگر نداری، `led_enabled = false` |

## صدا

| علامت | راه‌حل |
|---|---|
| هیچ صدایی نیست | `sudo raspi-config` → System Options → Audio؛ بلندی صدا: `alsamixer` |
| صدا هست ولی باجه نه | کاربر در گروه `audio` باشد؛ `sound = true` در `booth.toml` |

## پرداخت

| علامت | راه‌حل |
|---|---|
| کیوآر نمی‌آید یا «اتصال به درگاه برقرار نشد» | اینترنت: `ping -c3 payment.zarinpal.com`؛ مرچنت‌کد در `booth.toml` |
| پرداخت با کیوآر انجام شد ولی باجه موفق نزد | تا ۳ ثانیه صبر کن (`payment_poll_seconds`)؛ اگر نشد، از پنل «تأیید پرداخت (دستی)» |
| کارتخوان: «کارتخوان جواب نداد» | `pos_driver` در `booth.toml`؛ تا درایور واقعی نیامده، `sim` است ([card-reader.md](card-reader.md)) |
| موجودی کالا کم شده ولی فروشی نیست | سفارش‌های نیمه‌کاره بعد از ۳۰ دقیقه خودکار لغو می‌شوند؛ یا از پنل لغو کن |

## پنل مدیریت

راهنمای کامل پنل: [admin-panel.md](admin-panel.md)

| علامت | راه‌حل |
|---|---|
| `chiz.local:8000` باز نمی‌شود | IP: `hostname -I` → `http://IP:8000/admin`؛ `systemctl status chiz-admin` |
| PIN را فراموش کردم | `admin_pin` در `booth.toml` → `sudo systemctl restart chiz-admin` |

## داغ شدن و خاموشی

- دما: `vcgencmd measure_temp` (بالای ۸۰ درجه پردازنده کند می‌شود). باجه‌ی خیابانی **فن** و **سوراخ تهویه** لازم دارد.
- علامت صاعقه‌ی زرد گوشه‌ی صفحه یا `vcgencmd get_throttled` ≠ `0x0` یعنی **برق کم**: آداپتور یا مبدل باتری ضعیف است.
- همیشه با `sudo poweroff` خاموش کن، نه با کشیدن برق؛ کارت حافظه خراب می‌شود.
