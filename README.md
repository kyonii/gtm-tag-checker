# GTM Tag Checker

Google OAuthでサインインしてGTMコンテナの健全性を監査するWebアプリ。

## チェック内容

| ID | 内容 | 重要度 |
|----|------|--------|
| FIRE-001 | トリガーのないタグ | Error |
| FIRE-002 | 一時停止中のタグ | Warning |
| FIRE-003 | GA4タグのMeasurement ID欠落 | Error |
| UNUSED-001 | 未使用のトリガー | Warning |
| UNUSED-002 | GA4設定タグの重複 | Error |
| UNUSED-003 | test/tempなど放置タグの疑い | Warning |
| DUP-001 | 同一タイプ・同一トリガーの重複発火 | Error |
| DUP-002 | UA と GA4 の共存 | Warning |

## セットアップ

```bash
poetry install
cp .env.example .env
# .envにGOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET_KEYを記入
poetry run uvicorn app.main:app --reload
```

Google Cloud ConsoleでOAuthクライアントを作成し、リダイレクトURIに `http://localhost:8000/auth/callback` を追加してください。

## テスト

```bash
poetry run pytest tests/ -v
```
