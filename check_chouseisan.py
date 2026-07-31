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

            # 行のテキストを取得
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
    """テーブルの行データから日付と◯△✕の数を抽出"""
    # テーブルの各マス(セル)はタブ(\t)や改行(\n)で区切られているため分割する
    cols = re.split(r'[\t\n]+', row_text.strip())
    
    # 少なくとも「日程」「◯」「△」「✕」の4マスがない行は無視
    if len(cols) < 4:
        return None

    # 1列目（日程）から月と日を抽出
    date_match = re.search(
       r"(\d{1,2})[/月](\d{1,2})日?\s*[（(]?([月火水木金土日])?[）)]?",
        cols[0],
    )

    if not date_match:
        return None

    try:
        # 列のインデックスは0から始まるため、2列目は[1]、3列目は[2]、4列目は[3]
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        circle = int(cols[1])     # ◯の数 (2列目)
        triangle = int(cols[2])   # △の数 (3列目)
        cross = int(cols[3])      # ✕の数 (4列目)
        
        return (month, day, circle, triangle, cross)
        
    except ValueError:
        # ヘッダー行など、数字に変換できない行は無視
        return None


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
    # 19:30実行 (GitHubの遅延を考慮して19〜20時台を許容)
    # 今日が○8なら通知
    # -----------------------------
    if 19 <= hour <= 20:
        print("19〜20時台チェック")
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
    # 21:30実行 (GitHubの遅延を考慮して21〜22時台を許容)
    # 明日が○7△1なら通知
    # -----------------------------
    elif 21 <= hour <= 22:
        print("21〜22時台チェック")
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
