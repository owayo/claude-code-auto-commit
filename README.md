# claude-code-auto-commit

Claude Codeのhook機能と連携して、変更内容に基づいて自動的にGitコミットを実行するツールです。Gemini APIを使用してコミットメッセージを生成し、Conventional Commitsの形式でコミットを作成します。

## 機能

- 変更内容を自動検出してGitコミットを実行
- Gemini APIを使用した適切なコミットメッセージの自動生成
- Conventional Commits形式のサポート
- 環境変数による言語とデフォルトメッセージのカスタマイズ
- 大きな変更に対するタイムアウトとサイズ制限

## 必要条件

- Python 3.6以上
- Gitがインストールされていること
- [gemini CLI](https://github.com/reugn/gemini-cli)がインストールされていること

## 環境変数

| 環境変数 | 説明 | デフォルト値 |
|---------|------|-------------|
| `CLAUDE_CODE_COMMIT_LANGUAGE` | コミットメッセージの言語 | `日本語` |
| `CLAUDE_CODE_DEFAULT_COMMIT_MESSAGE` | gemini失敗時のデフォルトメッセージ | `chore: Claude Codeによる自動修正` |

## 設定方法

### 基本設定

Claude Codeの設定ファイル(`~/.claude/settings.json`)でStopフックとして設定します：

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/claude-code-auto-commit/auto-git-commit.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 日本語でデフォルトメッセージを変更する場合

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_CODE_DEFAULT_COMMIT_MESSAGE='chore: 自動修正' python3 /path/to/claude-code-auto-commit/auto-git-commit.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 英語でコミットメッセージを生成する場合

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_CODE_COMMIT_LANGUAGE='English' CLAUDE_CODE_DEFAULT_COMMIT_MESSAGE='chore: auto commit by Claude Code' python3 /path/to/claude-code-auto-commit/auto-git-commit.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## 動作の仕組み

1. Claude Codeが停止時にhookを実行
2. Gitリポジトリかどうかをチェック
3. 変更があるかを確認
4. 変更内容を取得してgeminiでコミットメッセージを生成
5. 生成されたメッセージでGitコミットを実行

## 終了コード

- `0`: 正常終了（変更なしまたはgemini成功でコミット完了）
- `1`: エラー終了（Gitリポジトリでない、geminiコマンドがない、gemini失敗など）

## トラブルシューティング

### スクリプトがハングする場合

大きな変更がある場合、geminiの処理に時間がかかることがあります。以下の対策が実装されています：

- geminiコマンドのタイムアウト（20秒）
- 変更内容の詳細を最大5000文字に制限
- デバッグ出力による進行状況の確認

### geminiが失敗する場合

- gemini CLIが正しくインストールされているか確認
- `gemini --version`でバージョンを確認

## ライセンス

MIT License
