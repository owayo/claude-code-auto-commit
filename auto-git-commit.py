#!/usr/bin/env python3
"""Claude Code用の自動Gitコミットツール

Claude Codeのhook機能と連携して、変更内容に基づいて自動的にGitコミットを実行します。
Gemini APIを使用してコミットメッセージを生成し、Conventional Commitsの形式で
コミットを作成します。

使用方法:
    Claude Codeの設定ファイル(~/.claude/settings.json)でStopフックとして設定します。

    設定例:
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

環境変数:
    CLAUDE_CODE_COMMIT_LANGUAGE: コミットメッセージの言語（デフォルト: 日本語）
    CLAUDE_CODE_DEFAULT_COMMIT_MESSAGE: gemini失敗時のデフォルトメッセージ
                                       （デフォルト: chore: Claude Codeによる自動修正）

終了コード:
    0: 正常終了（変更なしまたはgemini成功でコミット完了）
    1: エラー終了（Gitリポジトリでない、geminiコマンドがない、gemini失敗など）
"""

import json
import os
import shlex
import subprocess
import sys

# 定数
# Conventional Commitsのプレフィックス一覧
CONVENTIONAL_PREFIXES = [
    "build:",  # ビルド
    "chore:",  # 雑務
    "ci:",  # 継続的インテグレーション
    "debug:",  # デバッグ
    "docs:",  # ドキュメント
    "feat:",  # 新機能
    "fix:",  # バグ修正
    "perf:",  # パフォーマンス改善
    "refactor:",  # リファクタリング
    "style:",  # コードスタイル
    "test:",  # テスト
]

# デフォルト言語設定
DEFAULT_LANGUAGE = "日本語"  # 例: "日本語", "English"

# コミットメッセージ生成用プロンプトテンプレート
COMMIT_MESSAGE_PROMPT = """修正内容からConventional Commits形式のgit commit messageを作って。{language}で1行で簡潔に。

Conventional Commits形式の規則:
- 必ず{prefixes}のいずれかのプレフィックスで始める
- プレフィックスの後にコロン(:)とスペースを付ける
- メッセージは小文字で始める（日本語の場合を除く）
- 1行で簡潔に変更内容を説明する
- 現在形・命令形で記述する

<修正内容>
{changes}

<詳細>
{detailed_changes}
</修正内容>"""

# デフォルト設定
DEFAULT_COMMIT_MESSAGE = "chore: Claude Codeによる自動修正"
DEFAULT_MODEL = "gemini-2.5-flash"


def run_command(cmd, cwd=None, capture_output=True, shell=True):
    """シェルコマンドを実行して結果を返す

    Args:
        cmd (str): 実行するコマンド文字列
        cwd (str, optional): 作業ディレクトリ。デフォルトはNone
        capture_output (bool, optional): 出力をキャプチャするか。デフォルトはTrue
        shell (bool, optional): シェル経由で実行するか。デフォルトはTrue

    Returns:
        tuple: (success: bool, stdout: str, stderr: str)
            - success: コマンドが正常終了したか（returncode == 0）
            - stdout: 標準出力の内容（capture_output=Trueの場合）
            - stderr: 標準エラー出力の内容（capture_output=Trueの場合）
    """
    try:
        if capture_output:
            result = subprocess.run(
                cmd,
                shell=shell,
                cwd=cwd,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        else:
            result = subprocess.run(cmd, shell=shell, cwd=cwd)
            return result.returncode == 0, "", ""
    except Exception as e:
        return False, "", str(e)


def main():
    """メイン処理

    Claude Codeから渡された情報を基に、以下の処理を実行:
    1. Gitリポジトリかチェック
    2. 変更があるかチェック
    3. geminiコマンドの存在確認
    4. 変更内容を取得してgeminiでコミットメッセージ生成
    5. Gitコミット実行

    終了コード:
        0: 正常終了（変更なしまたはgemini成功でコミット完了）
        1: エラー終了（各種チェック失敗またはgemini失敗）
    """
    # 言語設定を環境変数から取得（デフォルトはDEFAULT_LANGUAGE）
    language = os.environ.get("CLAUDE_CODE_COMMIT_LANGUAGE", DEFAULT_LANGUAGE)

    # デフォルトコミットメッセージを環境変数から取得（デフォルトはDEFAULT_COMMIT_MESSAGE）
    default_commit_msg = os.environ.get(
        "CLAUDE_CODE_DEFAULT_COMMIT_MESSAGE", DEFAULT_COMMIT_MESSAGE
    )

    # 入力データを読み込む
    input_data_str = sys.stdin.read()

    try:
        input_data = json.loads(input_data_str)
        cwd = input_data.get("cwd", ".")
    except (json.JSONDecodeError, AttributeError):
        cwd = "."

    # 作業ディレクトリに移動
    os.chdir(cwd)

    # Git管理下かチェック
    success, _, _ = run_command("git rev-parse --git-dir")
    if not success:
        print("エラー: Gitリポジトリではありません", file=sys.stderr)
        sys.exit(1)

    # 変更があるかチェック
    success, output, _ = run_command("git status --porcelain")
    if not output:
        print("変更はありません。コミットをスキップします。", file=sys.stderr)
        sys.exit(0)

    # geminiコマンドが利用可能かチェック
    success, _, _ = run_command("command -v gemini")
    if not success:
        print(
            "エラー: geminiコマンドが見つかりません。geminiをインストールしてください。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 変更内容を取得
    success, changes, _ = run_command("git diff --cached --stat")
    if not changes:
        # ステージングされていない場合は、すべての変更をステージング
        run_command("git add -A", capture_output=False)
        success, changes, _ = run_command("git diff --cached --stat")

    print(f"changes: {changes}", file=sys.stderr)

    # 変更の詳細を取得
    print("git diff --cachedを実行中...", file=sys.stderr)
    success, detailed_changes, _ = run_command("git diff --cached")
    print(
        f"git diff --cached完了 (サイズ: {len(detailed_changes)}文字)", file=sys.stderr
    )

    # detailed_changesが大きすぎる場合は制限する（最大5000文字）
    if len(detailed_changes) > 5000:
        detailed_changes = detailed_changes[:5000] + "\n\n[... 以降省略 ...]"
        print(
            "警告: 変更内容が大きすぎるため、最初の5000文字のみを使用します",
            file=sys.stderr,
        )

    # プロンプトを作成
    prefixes_str = "、".join([f"`{p}`" for p in CONVENTIONAL_PREFIXES])
    prompt = COMMIT_MESSAGE_PROMPT.format(
        language=language,
        prefixes=prefixes_str,
        changes=changes,
        detailed_changes=detailed_changes,
    )
    print(f"プロンプトサイズ: {len(prompt)}文字", file=sys.stderr)

    # デフォルトのコミットメッセージ
    commit_message = default_commit_msg
    gemini_success = False  # geminiコマンドの成功フラグ

    try:
        print("geminiでコミットメッセージを生成中...", file=sys.stderr)
        # geminiコマンドでコミットメッセージを生成
        # shell=Falseでリスト形式で渡すことでエスケープの問題を回避
        # タイムアウトを20秒に設定
        result = subprocess.run(
            ["gemini", "-m", DEFAULT_MODEL, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=20,
        )

        if result.returncode == 0 and result.stdout.strip():
            commit_message = result.stdout.strip()
            gemini_success = True  # gemini成功
            print("geminiによるメッセージ生成成功", file=sys.stderr)
        else:
            if result.stderr:
                print(f"geminiエラー: {result.stderr}", file=sys.stderr)
            print(
                "警告: geminiコマンドが失敗しました。デフォルトメッセージを使用します。",
                file=sys.stderr,
            )

    except subprocess.TimeoutExpired:
        print("警告: geminiコマンドがタイムアウトしました（20秒）", file=sys.stderr)
        print(
            f"デフォルトメッセージを使用します: {default_commit_msg}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"警告: geminiコマンドが失敗しました: {e}", file=sys.stderr)
        print(
            f"デフォルトメッセージを使用します: {default_commit_msg}",
            file=sys.stderr,
        )

    # コミットを実行
    # shlex.quoteでシェルエスケープ
    escaped_message = shlex.quote(commit_message)
    success, output, error = run_command(f"git commit -m {escaped_message}")
    if success:
        print(f"✅ 自動コミット成功: {commit_message}")

        # コミット後の状態を表示
        print("")
        print("📊 コミット情報:")
        success, log_output, _ = run_command("git log -1 --oneline")
        if success:
            print(log_output)

        # まだステージングされていない変更があるかチェック
        success, remaining, _ = run_command("git status --porcelain")
        if remaining:
            print("")
            print("⚠️  まだコミットされていない変更があります:")
            run_command("git status --short", capture_output=False)

        # geminiが失敗した場合はexit 1
        if not gemini_success:
            print(
                "\n⚠️  geminiコマンドが失敗したため、終了コード1で終了します。",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print(f"エラー: コミットに失敗しました: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
