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
    """調整さんのテーブル行から日付と◯△✕の人数を抽出"""

    cols = re.split(r'[\t\n]+', row_text.strip())

    print(f"行データ解析中: {cols}")

    if len(cols) < 4:
        print(" -> 列数が不足しています")
        return None

    # 日付を抽出
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

        # 「7人」「1人」「0人」から数字だけを抽出
        circle_match = re.search(r"\d+", cols[1])
        triangle_match = re.search(r"\d+", cols[2])
        cross_match = re.search(r"\d+", cols[3])

        if not circle_match or not triangle_match or not cross_match:
            print(" -> 人数の解析に失敗しました")
            return None

        circle = int(circle_match.group())
        triangle = int(triangle_match.group())
        cross = int(cross_match.group())

        print(
            f" -> 抽出成功: "
            f"{month}月{day}日 "
            f"(◯:{circle}, △:{triangle}, ✕:{cross})"
        )

        return month, day, circle, triangle, cross

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

    print(
        f"現在時刻 (JST): "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # --------------------------------
    # 当日の予定だけをチェック
    # --------------------------------

    print("当日の予定を確認します。")

    print(
        f"確認対象日: "
        f"{today.strftime('%Y-%m-%d')}"
    )

    # --------------------------------
    # 調整さんへアクセス
    # --------------------------------

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        print(
            f"ページにアクセス中: {url}"
        )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        try:
            page.wait_for_selector(
                "table",
                timeout=10000
            )

            print(
                "テーブルの読み込みを確認しました"
            )

        except Exception as e:

            print(
                f"テーブルの待機タイムアウト: {e}"
            )

        # 調整さんのテーブル行を取得
        rows = page.locator(
            "table tr"
        ).all_inner_texts()

        print(
            f"取得した行の数: {len(rows)}"
        )

        browser.close()

    if not rows:

        print(
            "テーブルの行が見つかりませんでした。"
        )

        return

    # --------------------------------
    # 今日の日付の行を探す
    # --------------------------------

    for row in rows:

        parsed = parse_row(row)

        if parsed is None:
            continue

        month, day, circle, triangle, cross = parsed

        # 今日の日付ではない場合はスキップ
        if (
            month != today.month
            or day != today.day
        ):
            continue

        print(
            f"今日のデータを発見: "
            f"{month}/{day}"
        )

        print(
            f"○:{circle} "
            f"△:{triangle} "
            f"×:{cross}"
        )

        # --------------------------------
        # ○8人以上
        # --------------------------------

        if circle >= 8:

            print(
                f"○{circle}人なので通知します"
            )

            send_discord_notification(
                webhook_url,
                "📢 **今日は固定あります！**"
            )

            return

        # --------------------------------
        # ○7人 + △1人
        # --------------------------------

        if circle == 7 and triangle == 1:

            print(
                "○7人 + △1人なので通知します"
            )

            send_discord_notification(
                webhook_url,
                "📢 **固定あるかも？（わかったら連絡して）**"
            )

            return

        # --------------------------------
        # その他
        # --------------------------------

        print(
            "通知条件に一致しませんでした"
        )

        return

    print(
        f"{today.month}/{today.day} "
        "のデータが見つかりませんでした。"
    )


if __name__ == "__main__":
    check_and_notify()
