import os
import re
from datetime import datetime, timedelta
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

    # タブや改行で列を分割
    cols = re.split(r'[\t\n]+', row_text.strip())

    print(f"行データ解析中: {cols}")

    # 日付 + ○ + △ + × の4列が必要
    if len(cols) < 4:
        print(" -> 列数が不足しています")
        return None

    # 日付の抽出
    # 例:
    # 7/31
    # 07/31
    # 7月31日
    # 7/31(木)
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

        # 「7人」「1人」「0人」から数字だけを取り出す
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

        return (
            month,
            day,
            circle,
            triangle,
            cross
        )

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
    minute = now.minute

    print(
        f"現在時刻 (JST): "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # --------------------------------
    # 実行時間の判定
    #
    # 19時台:
    # 翌日の予定を確認
    #
    # 20〜21時台:
    # 当日の予定を確認
    # --------------------------------

    if 19 <= hour <= 19:
        target_date = today + timedelta(days=1)
        check_type = "翌日"

    elif 20 <= hour <= 21:
        target_date = today
        check_type = "当日"

    else:
        print(
            f"現在時刻は{hour}時のため、"
            "チェック対象時間外です。"
        )
        return

    print(
        f"{check_type}の予定を確認します。"
    )

    print(
        f"確認対象日: "
        f"{target_date.strftime('%Y-%m-%d')}"
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

        # テーブルが読み込まれるまで最大10秒待機
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
    # 取得した全行を解析
    # --------------------------------

    for row in rows:

        parsed = parse_row(row)

        if parsed is None:
            continue

        month, day, circle, triangle, cross = parsed

        # --------------------------------
        # 対象日と一致するか確認
        # --------------------------------

        if (
            month != target_date.month
            or day != target_date.day
        ):
            continue

        print(
            f"対象日のデータを発見: "
            f"{month}/{day}"
        )

        print(
            f"○:{circle} "
            f"△:{triangle} "
            f"×:{cross}"
        )

        # --------------------------------
        # パターン1
        # ○8人
        # --------------------------------

        if circle >= 8:

            if check_type == "翌日":

                message = (
                    "📢 **明日は固定あります！**"
                )

            else:

                message = (
                    "📢 **今日は固定あります！**"
                )

            print(
                f"○{circle}人なので通知します"
            )

            send_discord_notification(
                webhook_url,
                message
            )

            return

        # --------------------------------
        # パターン2
        # ○7人 + △1人
        # --------------------------------

        if circle == 7 and triangle == 1:

            message = (
                "△の人は分かり次第連絡して♡"
            )

            print(
                "○7人 + △1人を確認しました"
            )

            send_discord_notification(
                webhook_url,
                message
            )

            return

        # --------------------------------
        # それ以外
        # --------------------------------

        print(
            "通知条件に一致しませんでした"
        )

        return

    print(
        f"{target_date.month}/{target_date.day} "
        "のデータが見つかりませんでした。"
    )


if __name__ == "__main__":
    check_and_notify()
