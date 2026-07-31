import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
import urllib.request
import json


def send_discord_notification(webhook_url, message):
    """DiscordのWebhookに通知を送信する"""
    if not webhook_url:
        print("Discord Webhook URLが設定されていません。")
        return

    payload = {"content": message}
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        with urllib.request.urlopen(req) as res:
            print(f"Discord通知成功: ステータス {res.status}")
    except Exception as e:
        print(f"Discord通知失敗: {e}")


def parse_row(row_text):
    """テーブルの行データから日付と◯△✕の数を抽出"""
    cols = re.split(r'[\t\n]+', row_text.strip())
    print(f"行データ解析中: {cols}")

    if len(cols) < 4:
        print(" -> 列数が不足しています")
        return None

    # 日付の抽出
    # 例:
    # 7/31
    # 07/31
    # 7月31日
    # 7/31(金)
    date_match = re.search(
        r"(\d{1,2})[/月](\d{1,2})日?\s*[（(]?([月火水木金土日])?[）)]?",
        cols[0]
    )

    if not date_match:
        print(f" -> 日付がマッチしませんでした: {cols[0]}")
        return None

    try:
        month = int(date_match.group(1))
        day = int(date_match.group(2))

        circle = int(cols[1])
        triangle = int(cols[2])
        cross = int(cols[3])

        print(
            f" -> 抽出成功: "
            f"{month}月{day}日 "
            f"(◯:{circle}, △:{triangle}, ✕:{cross})"
        )

        return (month, day, circle, triangle, cross)

    except ValueError as e:
        print(f" -> 数値変換エラー: {e}")
        return None


def check_and_notify():
    url = os.environ.get("CHOUSEISAN_URL")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not url:
        print("エラー: CHOUSEISAN_URL が設定されていません。")
        return

    # 日本時間を取得
    jst = ZoneInfo("Asia/Tokyo")
    now = datetime.now(jst)
    today = now.date()
    hour = now.hour

    print(f"現在時刻 (JST): {now.strftime('%Y-%m-%d %H:%M:%S')}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"ページにアクセス中: {url}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        # ページのテーブルが読み込まれるまで最大10秒待機
        try:
            page.wait_for_selector("table", timeout=10000)
            print("テーブルの読み込みを確認しました")
        except Exception as e:
            print(f"テーブルの待機タイムアウト: {e}")

        # 調整さんのテーブル行を取得
        rows = page.locator("table tr").all_inner_texts()

        print(f"取得した行の数: {len(rows)}")

        browser.close()

    if not rows:
        print("テーブルの行が見つかりませんでした。")
        return

    # -----------------------------
    # 19〜21時台に実行
    # GitHub Actionsの遅延を考慮
    # -----------------------------
    if 19 <= hour <= 21:
        print("19〜21時台チェック開始")

        for row in rows:

            # ここが重要
            # rowをparse_row()に渡して解析する
            parsed = parse_row(row)

            if parsed is None:
                continue

            month, day, circle, triangle, cross = parsed

            # 今日の日付かつ○が8人の場合
            if (
                month == today.month
                and day == today.day
                and circle == 8
            ):
                print("○8を発見しました")

                send_discord_notification(
                    webhook_url,
                    "📢 **今日は固定あります！**"
                )

                return

        print("条件に一致しませんでした")

    else:
        print(
            f"現在時刻は{hour}時のため、"
            "19〜21時台チェックの対象外です"
        )


if __name__ == "__main__":
    check_and_notify()
