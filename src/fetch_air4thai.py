
"""
โปรแกรมดึงข้อมูลคุณภาพอากาศจาก Air4Thai
และบันทึกข้อมูล JSON ดิบลงใน data/raw/
"""

import logging
import sys
import time

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# รองรับใบรับรอง SSL ของระบบ
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


# ==========================================
# 1. ตั้งค่าพื้นฐาน
# ==========================================

URL = URL = URL = "http://air4thai.pcd.go.th/services/getNewAQI_JSON.php"

HEADERS = {
    "User-Agent": "pm25-explorer/0.1 (student project)"
}

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

TZ = ZoneInfo("Asia/Bangkok")

RETRIES = 3
WAIT = 5

RETRY_STATUS = {429, 500, 502, 503, 504}


# ==========================================
# 2. สร้างโฟลเดอร์และตั้งค่า Logging
# ==========================================

RAW_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            RAW_DIR / "fetch.log",
            encoding="utf-8"
        ),
    ],
)

log = logging.getLogger("fetch_air4thai")


# ==========================================
# 3. ฟังก์ชันดึงข้อมูลจาก API พร้อม Retry
# ==========================================

def fetch(url: str) -> requests.Response:

    for attempt in range(1, RETRIES + 1):

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=(10, 60)
            )

            if response.status_code not in RETRY_STATUS:
                response.raise_for_status()
                return response

            reason = f"HTTP Status {response.status_code}"

        except (requests.ConnectionError, requests.Timeout) as error:
            reason = str(error)

        log.warning(
            "ครั้งที่ %d/%d ล้มเหลว: %s",
            attempt,
            RETRIES,
            reason
        )

        if attempt == RETRIES:
            raise RuntimeError(
                f"ดึงข้อมูลไม่สำเร็จหลังลอง {RETRIES} ครั้ง: {reason}"
            )

        time.sleep(WAIT * attempt)


# ==========================================
# 4. ตรวจสอบรูปแบบข้อมูล JSON
# ==========================================

def validate(response: requests.Response) -> int:

    data = response.json()

    stations = (
        data.get("stations")
        if isinstance(data, dict)
        else None
    )

    if not isinstance(stations, list) or not stations:
        raise ValueError(
            "รูปแบบข้อมูลไม่ถูกต้อง หรือไม่พบรายการสถานี"
        )

    return len(stations)


# ==========================================
# 5. ฟังก์ชันหลักของโปรแกรม
# ==========================================

def main() -> int:

    fetched_at = datetime.now(TZ)

    try:
        # ดึงข้อมูลจาก API
        response = fetch(URL)

        # ตรวจสอบข้อมูลก่อนบันทึก
        station_count = validate(response)

    except Exception as error:
        log.error("ดึงข้อมูลไม่สำเร็จ: %s", error)
        return 1

    # สร้างชื่อไฟล์ตามวันที่และเวลาประเทศไทย
    filename = f"air4thai_{fetched_at:%Y%m%dT%H%M%S}.json"

    filepath = RAW_DIR / filename

    try:
        # บันทึกข้อมูล JSON ดิบ
        filepath.write_bytes(response.content)

        log.info(
            "บันทึก %s สำเร็จ (%d สถานี, %d bytes)",
            filename,
            station_count,
            len(response.content)
        )

    except OSError as error:
        log.error("บันทึกไฟล์ไม่สำเร็จ: %s", error)
        return 1

    return 0


# ==========================================
# 6. เริ่มทำงานเมื่อเรียกใช้ไฟล์โดยตรง
# ==========================================

if __name__ == "__main__":
    sys.exit(main())
