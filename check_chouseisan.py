"""
調整さんの出欠表をチェックして、
「◯が7個」または「◯が6個かつ△が1個」の候補日が"今日"だったら
Discordに通知を送るスクリプト。

GitHub ActionsなどでJST 20:30に毎日実行する想定。
（実行時刻そのものが「20:30通知」を意味するので、スクリプト内では時刻判定はしない）

必要な環境変数:
  CHOUSEISAN_URL       : 調整さんのイベントURL (例 https://chouseisan.com/s?h=xxxx)
  DISCORD_WEBHOOK_URL   : DiscordのWebhook URL
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta

import requests
from playwright.sync_api import sync_playwright

JST = timezone(timedelta(hours=9))

# ---- 条件はここで変更可能 ----
def match_status(circle: int, triangle: int) -> str | None:
    """
    通知条件を判定し、状態を表す文字列を返す。該当しなければNone。
      "確定": ◯が7個 -> 全員参加なので固定
      "仮確定": ◯が6個かつ△が1個 -> ほぼ全員なので固定かも
    """
    if circle == 7:
        return "確定"
    if circle == 6 and triangle == 1:
        return "仮確定"
    return None


def fetch_rows(url: str) -> list[str]:
    """調整さんのページをレンダリングして、候補日の行ごとのテキストを返す"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        # 候補日テーブルの行を丸ごとテキストで取得する
        # (調整さんのDOM構造が変わっても壊れにくいよう、
        #  "候補日らしき行"をtrベースで総当たりして拾う)
        rows = page.locator("table tr").all_inner_texts()
        browser.close()
        return rows


def parse_row(row_text: str):
    """
    1行分のテキストから (日付文字列, ◯の数, △の数, ×の数) を抜き出す。
    調整さんは各候補日の行に集計(◯n △n ×n)が出るのでそれを利用する。
    見つからなければ None を返す。
    """
    # 日付らしきパターン: 8/1(土) 20:00〜 や 8月1日(土)20:00 など
    date_match = re.search(r"(\d{1,2})[/月](\d{1,2})日?\s*[（(]?([月火水木金土日])?[）)]?", row_text)
    if not date_match:
        return None

    circle_match = re.search(r"○\s*(\d+)", row_text) or re.search(r"◯\s*(\d+)", row_text)
    triangle_match = re.search(r"△\s*(\d+)", row_text)
    cross_match = re.search(r"[×✕]\s*(\d+)", row_text)

    if not circle_match:
        return None

    month = int(date_match.group(1))
    day = int(date_match.group(2))
    circle = int(circle_match.group(1))
    triangle = int(triangle_match.group(1)) if triangle_match else 0
    cross = int(cross_match.group(1)) if cross_match else 0

    return (month, day, circle, triangle, cross)


def send_discord_notification(webhook_url: str, title: str, month: int, day: int, circle: int, triangle: int, status: str):
    if status == "確定":
        headline = "固定です！"
    else:  # "仮確定"
        headline = "固定かも？"

    content = (
        f"📅 **{title}**\n"
        f"本日 {month}/{day} は **{headline}**\n"
        f"◯ {circle} / △ {triangle}\n"
        f"よければ確認してください。"
    )
    resp = requests.post(webhook_url, json={"content": content}, timeout=15)
    resp.raise_for_status()


def main():
    url = os.environ.get("CHOUSEISAN_URL")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url or not webhook_url:
        print("CHOUSEISAN_URL と DISCORD_WEBHOOK_URL を環境変数にセットしてください", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(JST)

    rows = fetch_rows(url)

    matched_any = False
    for row in rows:
        parsed = parse_row(row)
        if not parsed:
            continue
        month, day, circle, triangle, cross = parsed

        status = match_status(circle, triangle)
        if month == today.month and day == today.day and status is not None:
            send_discord_notification(webhook_url, "調整さん通知", month, day, circle, triangle, status)
            matched_any = True

    if not matched_any:
        print(f"{today.month}/{today.day} は条件に一致する候補日ではありませんでした。通知はスキップします。")


if __name__ == "__main__":
    main()
