"""
調整さんの出欠表をチェックして、
「◯が7個」または「◯が6個かつ△が1個」の候補日が"今日"だったら
Discordに通知を送るスクリプト。
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta

import requests
from playwright.sync_api import sync_playwright, TimeoutError

JST = timezone(timedelta(hours=9))


def match_status(circle: int, triangle: int) -> str | None:
    if circle == 7:
        return "確定"
    if circle == 6 and triangle == 1:
        return "仮確定"
    return None


def fetch_rows(url: str) -> list[str]:
    """調整さんのページを取得して候補日一覧を返す"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
        )

        try:
            print("ページを開いています...")
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # JS描画待ち
            page.wait_for_timeout(3000)

            # テーブルが出るまで待つ
            page.wait_for_selector("table", timeout=30000)

            rows = page.locator("table tr").all_inner_texts()

            print(f"{len(rows)}件の行を取得しました")

            browser.close()
            return rows

        except TimeoutError:
            print("ページの読み込みがタイムアウトしました。")
            print("現在のURL:", page.url)

            try:
                print(page.content()[:2000])
            except Exception:
                pass

            browser.close()
            sys.exit(1)


def parse_row(row_text: str):
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


def send_discord_notification(
    webhook_url,
    title,
    month,
    day,
    circle,
    triangle,
    status,
):
    headline = "固定です！" if status == "確定" else "固定かも？"

    content = (
        f"📅 **{title}**\n"
        f"本日 {month}/{day} は **{headline}**\n"
        f"◯ {circle} / △ {triangle}\n"
        f"よければ確認してください。"
    )

    response = requests.post(
        webhook_url,
        json={"content": content},
        timeout=15,
    )

    response.raise_for_status()


def main():
    url = os.environ.get("CHOUSEISAN_URL")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not url or not webhook_url:
        print("環境変数が設定されていません")
        sys.exit(1)

    today = datetime.now(JST)

    rows = fetch_rows(url)

    matched = False

    for row in rows:
        parsed = parse_row(row)

        if not parsed:
            continue

        month, day, circle, triangle, cross = parsed

        status = match_status(circle, triangle)

        if (
            month == today.month
            and day == today.day
            and status is not None
        ):
            send_discord_notification(
                webhook_url,
                "調整さん通知",
                month,
                day,
                circle,
                triangle,
                status,
            )
            matched = True

    if not matched:
        print("今日は通知条件に一致しませんでした。")


if __name__ == "__main__":
    main()
