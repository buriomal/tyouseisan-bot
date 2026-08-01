# 調整さん → Discord 通知ボット

調整さんの候補日のうち、
- ◯（参加）が **8個** → 「固定です！」と通知
- または ◯が **7個** かつ △（未定）が **1個** → 「固定かも？」と通知

の日付が「今日」であれば、毎日 **20:30 (JST)** にDiscordへ通知します。

## セットアップ手順（GitHub Actionsで動かす場合）

1. このフォルダをGitHubの新しいリポジトリにpushする
   ```
   cd chouseisan-discord-bot
   git init
   git add .
   git commit -m "init"
   gh repo create your-repo-name --private --source=. --push
   ```

2. Discordで通知したいチャンネルの Webhook URL を発行する
   - チャンネル設定 → 連携サービス → ウェブフック → 新しいウェブフック → URLをコピー

3. GitHubリポジトリの Settings → Secrets and variables → Actions で以下を設定
   - **Secrets** タブ → `New repository secret`
     - Name: `DISCORD_WEBHOOK_URL`
     - Value: (コピーしたWebhook URL)
   - **Variables** タブ → `New repository variable`
     - Name: `CHOUSEISAN_URL`
     - Value: (調整さんのイベントURL、例 `https://chouseisan.com/s?h=xxxxxxxx`)

4. イベントを作り直してURLが変わったら、上記の `CHOUSEISAN_URL` の値を書き換えるだけでOK（コードは触らなくてよい）

5. 動作確認したい場合は、GitHubリポジトリの Actions タブ →
   「Chouseisan Discord Notify」→「Run workflow」で手動実行できます

## 通知条件を変えたい場合

`check_chouseisan.py` の `match_status()` 関数を編集してください。

## 注意点

- 調整さんのページのHTML構造が将来変わると、日付や集計の読み取りに失敗する可能性があります。その場合は `check_chouseisan.py` の `parse_row()` の正規表現を調整してください。
- 候補日の表記ゆれ（`8/1(土)` や `8月1日(土)` 等）にはある程度対応していますが、想定外の表記だと日付を拾えないことがあります。実際に動かして、GitHub Actionsのログ（Run check のステップ）で候補日が正しく読めているか確認することをおすすめします。
