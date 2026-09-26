<div align="center">

```
   █████╗ ██████╗ ██╗  ██╗ █████╗
  ██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗
  ███████║██████╔╝█████╔╝ ███████║
  ██╔══██║██╔══██╗██╔═██╗ ██╔══██║
  ██║  ██║██║  ██║██║  ██╗██║  ██║
  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
```

# 🎬 Arka Downloader

**Universal Premium Downloader Bot**

⚡ Fast · Smart · Powerful

Made with ❤️ by @AMIRALI_IRX

</div>

---

## 🚀 نصب سریع

### گام ۱ — آپلود به سرور

از کامپیوتر خودت:

```bash
scp arka_downloader.zip root@SERVER_IP:/root/
```

### گام ۲ — اتصال به سرور

```bash
ssh root@SERVER_IP
```

### گام ۳ — نصب — فقط یک دستور!

```bash
cd /root && (unzip -o arka_downloader.zip 2>/dev/null || true); cd arka_downloader && sed -i 's/\r$//' install.sh && bash install.sh install
```

بعدش:

- Create .env now? (y/N): → y
- BOT_TOKEN: → توکن رباتت (از @BotFather)
- OWNER_IDS (numeric): → آیدی عددی‌ت (از @userinfobot)

بعدش ۲-۳ دقیقه صبر کن تا ربات آنلاین شه. ✅

---

## 📋 پیش‌نیازها

| مورد | از کجا | ضروری |
|------|--------|:-----:|
| 🔑 BOT_TOKEN | @BotFather | ✅ |
| 👤 OWNER_ID | @userinfobot | ✅ |
| 📦 arka_downloader.zip | توی /root/ بذار | ✅ |
| 🖥 سرور Ubuntu 22.04+ | هر VPS (KVM) | ✅ |
| 💾 حداقل ۱GB RAM | - | ✅ |
| 💿 حداقل ۱۰GB دیسک | - | ✅ |

---

## 📖 نصب کامل — قدم به قدم

### گام ۱ — آپلود ZIP

از کامپیوتر خودت:

```bash
scp arka_downloader.zip root@SERVER_IP:/root/
```

جای SERVER_IP آی‌پی سرورت رو بذار

### گام ۲ — اتصال به سرور

```bash
ssh root@SERVER_IP
```

### گام ۳ — باز کردن ZIP

```bash
cd /root
unzip -o arka_downloader.zip
cd arka_downloader
```

### گام ۴ — نصب

```bash
bash install.sh install
```

### گام ۵ — پاسخ به سوالات

| سوال | جواب |
|------|------|
| Create .env now? (y/N): | y |
| BOT_TOKEN: | توکن رباتت |
| OWNER_IDS (numeric): | آیدی عددیت |

### گام ۶ — انتظار

منتظر بمون تا این پیام بیاد:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✓ ONLINE — Bot started successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

بعد برو توی تلگرام و /start بزن 🎉

---

## 📂 ساختار پروژه

```
/root/arka_downloader/
├── bot.py              ← کد اصلی ربات
├── install.sh          ← نصب + مدیریت
├── README.md           ← همین فایل
├── .env                ← توکن + آیدی‌ها (خودکار)
├── data/               ← دیتابیس
├── downloads/          ← فایل‌های دانلود شده
├── logs/               ← لاگ‌ها
├── backups/            ← بکاپ‌ها
└── updates/            ← آپدیت‌ها
```

---

## 🛠 دستورات مدیریت

| دستور | کار |
|--------|------|
| bash install.sh restart | 🔄 ری‌استارت |
| bash install.sh stop | ⏸ توقف |
| bash install.sh start | ▶️ استارت |
| bash install.sh status | 📊 وضعیت سرویس |
| bash install.sh logs | 📜 لاگ زنده |
| bash install.sh health | 🏥 چک سلامت |
| bash install.sh backup | 💾 بکاپ دیتابیس |
| bash install.sh update | ⬆️ آپدیت پکیج‌ها |
| bash install.sh cleanup | 🧹 پاک‌سازی conflicts |
| bash install.sh uninstall | 🗑 حذف سرویس |

### دستورات systemd مستقیم

| دستور | کار |
|--------|------|
| systemctl restart arkabot | 🔄 ری‌استارت |
| systemctl stop arkabot | ⏸ توقف |
| systemctl start arkabot | ▶️ استارت |
| systemctl status arkabot | 📊 وضعیت |

---

## 🔄 آپدیت ربات

### حالت ۱ — فقط bot.py عوض شده

از کامپیوتر خودت:

```bash
scp bot.py root@SERVER_IP:/root/arka_downloader/
```

روی سرور:

```bash
cd /root/arka_downloader
bash install.sh restart
```

### حالت ۲ — ZIP کامل جدید

از کامپیوتر خودت:

```bash
scp arka_downloader.zip root@SERVER_IP:/root/
```

روی سرور:

```bash
cd /root
unzip -o arka_downloader.zip
cd arka_downloader
bash install.sh restart
```

---

## 🆘 عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| ربات جواب نمی‌ده | bash install.sh logs |
| unzip: command not found | apt install -y unzip |
| Permission denied | با sudo اجرا کن |
| BOT_TOKEN invalid | از @BotFather دوباره بگیر |
| Conflict errors | bash install.sh cleanup |
| install.sh not found | مطمئن شو کنار bot.py هست |
| Docker not working | سرورت باید KVM باشه نه OpenVZ |
| Bot connection timed out | docker logs telegram-bot-api --tail 30 |
| Killed / code 137 | swap بساز (پایین رو ببین) |

### ساخت swap (اگه رم کم داری)

اگه سرورت ۱GB رم داره و ربات با code 137 کشته می‌شه، این رو بزن:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -h
```

باید ببینی: Swap: 2.0Gi

### ریست کامل از صفر

```bash
bash install.sh uninstall
rm -rf /root/arka_downloader
cd /root
unzip -o arka_downloader.zip
cd arka_downloader
bash install.sh install
```

---

## ⚙️ ویژگی‌های ربات

- 📥 دانلود از YouTube, Instagram, TikTok, Twitter, Pinterest, ...
- 🎞 انتخاب کیفیت (1080p / 720p / 480p / 360p / MP3)
- 📊 نوار پیشرفت زنده + سرعت + ETA
- 📜 تاریخچه دانلود (۱۰ تا در هر صفحه)
- ⭐ علاقه‌مندی‌ها
- 🎫 سیستم تیکت پشتیبانی
- 💎 ایموجی پریمیوم (Custom Emoji)
- 🎨 پنل ادمین کامل
- 🌐 دوزبانه (فارسی / انگلیسی)
- ⏱ حذف خودکار فایل‌ها
- 🔒 کانال اجباری (Force Join)
- 🚦 محدودیت نرخ (ساعتی / روزانه)
- 👑 ادمین‌های فرعی
- 🔄 دانلود مجدد + ارسال مجدد فایل
- 💾 بکاپ خودکار
- 🔧 حالت تعمیر (Maintenance)
- 🎛 سفارشی‌سازی دکمه‌های منو
- 📝 متن‌های سفارشی
- 🌐 مینی‌اپ (Mini App)
- 📣 اطلاع‌رسانی در کانال

---

## 🔧 پنل ادمین

ربات یه پنل ادمین کامل داره که با /admin یا دکمه «🛠 پنل مدیریت» باز می‌شه:

- 📈 آمار و گزارش‌ها
- 👥 مدیریت کاربران (بلاک / VIP)
- 📦 مدیریت دانلودها
- 📢 پیام همگانی (Broadcast)
- 🎫 مدیریت تیکت‌ها
- ⚙️ تنظیمات ربات
- 🚦 محدودیت‌ها
- 🔒 کانال اجباری
- 🎞 مدیریت کیفیت‌ها
- 🎨 استایل و ایموجی
- 🧰 ابزارهای مدیریتی
- 🔄 آپدیت ربات (از داخل تلگرام!)
- 📣 اطلاع‌رسانی
- 🌐 مینی‌اپ
- 📜 لاگ‌های سیستم
- 🔘 مدیریت دکمه‌ها
- 📝 مدیریت متن‌ها
- 📖 مدیریت راهنما
- 👑 ادمین‌های فرعی

---

## 💡 نکات مهم

- ✅ ربات با systemd بالا میاد — بعد از ری‌استارت سرور خودکار روشن می‌شه
- ✅ لاگ‌ها هر ۷ روز rotate می‌شن (logrotate)
- ✅ یک بار نصب کافیه — بعدش فقط restart
- ✅ فایل‌های تا ۲GB پشتیبانی می‌شن (Local Telegram API)
- ✅ Auto-recovery: اگه ربات کرش کنه، دانلودهای نیمه‌کاره ادامه پیدا می‌کنن
- ⚠️ bot.py و install.sh رو همیشه کنار هم نگه دار
- ⚠️ بعد از آپدیت bot.py، حتماً install.sh restart بزن
- ⚠️ سرورت باید KVM باشه (نه OpenVZ) برای Docker

---

## 🖥 پیشنهاد سرور

| منابع | حداقل | پیشنهاد |
|-------|:-----:|:-------:|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 10 GB SSD | 20 GB SSD |
| OS | Ubuntu 22.04 | Ubuntu 24.04 |
| Virtualization | KVM | KVM |

سرویس‌دهنده‌های تست‌شده:

- Hetzner Cloud
- DigitalOcean
- Vultr
- Contabo
- Linode

---

## 📞 پشتیبانی

**Owner:** @AMIRALI_IRX

---

<div align="center">

⭐ اگه ربات بهت کمک کرد، یه ستاره بده

</div>