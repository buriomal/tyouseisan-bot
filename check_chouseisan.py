import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from playwright.sync_api import sync_playwright, TimeoutError

JST = timezone(timedelta(hours=9))


def fetch_rows(url: str) -> list[str]:
    """調整さんの候補日一覧を取得"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            )
        )

        try:
            print("ページを開いています...")

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(3000)

            page.wait_for_selector("table", timeout=30000)

            rows = page.locator("table tr").all_inner_texts()

            print(f"{len(rows)}件取得")

            browser.close()

            return rows

        except TimeoutError:

            print("ページの読み込みに失敗しました")
            print(page.url)

            try:
                print(page.content()[:2000])
            except Exception:
                pass

            browser.close()
            sys.exit(1)


def parse_row(row_text):

    date_match = re.search(
       r"(\d{1,2})[/月](\d{1,2})日?\s*[（(]?([月火水木金土日])?[）)]?",
        row_text,
    )

    if not date_match:
        return None

    circle_match = (
       re.search(r"○\s*(\d+)", row_text)
        or re.search(r"◯\s*(\d+)", row_text)
    )

    triangle_match = re.search(r"△\s*(\d+)", row_text)

    cross_match = re.search(r"[×✕]\s*(\d+)", row_text)

    if not circle_match:
        return None

    return (
        int(date_match.group(1)),
        int(date_match.group(2)),
        int(circle_match.group(1)),
        int(triangle_match.group(1)) if triangle_match else 0,
        int(cross_match.group(1)) if cross_match else 0,
    )


def send_discord_notification(webhook_url: str, message: str):

    requests.post(
        webhook_url,
        json={
            "content": message
        },
        timeout=15,
    ).raise_for_status()

def check_and_notify(rows, webhook_url):

    now = datetime.now(JST)

    today = now.date()
    tomorrow = today + timedelta(days=1)

    hour = now.hour
    minute = now.minute

    print(f"現在時刻 {hour}:{minute:02d}")

    # -----------------------------
    # 19:30実行
    # 今日が○8なら通知
    # -----------------------------
    if hour == 19:

        print("19時台チェック")

        for row in rows:

            parsed = parse_row(row)

            if parsed is None:
                continue

            month, day, circle, triangle, cross = parsed

            if (
                month == today.month
                and day == today.day
                and circle == 8
            ):

                print("○8を発見")

                send_discord_notification(
                    webhook_url,
                    "📢 **今日は固定あります！**"
                )

                return

        print("条件に一致しませんでした")

    # -----------------------------
    # 21:30実行
    # 明日が○7△1なら通知
    # -----------------------------
    elif hour == 21:

        print("21時台チェック")

        for row in rows:

            parsed = parse_row(row)

            if parsed is None:
                continue

            month, day, circle, triangle, cross = parsed

            if (
                month == tomorrow.month
                and day == tomorrow.day
                and circle == 7
                and triangle == 1
            ):

                print("○7△1を発見")

                send_discord_notification(
                    webhook_url,
                    "📢 **△の人はわかり次第連絡お願い♡**"
                )

                return

        print("条件に一致しませんでした")

    else:

        print("通知時間外なので終了")

def main():

    url = os.environ.get("CHOUSEISAN_URL")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not url:
        print("CHOUSEISAN_URL が設定されていません")
        sys.exit(1)

    if not webhook_url:
        print("DISCORD_WEBHOOK_URL が設定されていません")
        sys.exit(1)

    rows = fetch_rows(url)

    check_and_notify(rows, webhook_url)


if __name__ == "__main__":
    main()
