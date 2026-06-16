---
description: AWS AI-DLC アダプティブ開発ワークフローを起動する（opt-in）
argument-hint: [開発依頼の内容]
---

このタスクに限り、AWS AI-DLC（AI-Driven Development Lifecycle）のアダプティブ開発ワークフローに従って作業してください。

## 手順

1. まず `.aidlc/aidlc-rules/aws-aidlc-rules/core-workflow.md` を読み込み、その指示に厳密に従う。
2. ルール詳細ディレクトリは `.aidlc/aidlc-rules/aws-aidlc-rule-details/`（core-workflow が解決パス #1 として最初に探す場所）。
   `common/`・`inception/`・`construction/`・`extensions/` 配下のファイル参照は、すべてこのディレクトリからの相対パスとして解決する。
3. core-workflow.md の MANDATORY 指示（共通ルールの先読み、welcome message 表示、content validation、question format、audit ログ）を遵守する。

## このリポ固有の制約（core-workflow より優先）

- 本コマンドは **opt-in**。`/aidlc` で明示的に起動したこのタスクの間のみ AI-DLC ワークフローを適用し、以後の通常依頼を恒久的に上書きしない。
- 生成ドキュメントは `aidlc-docs/` 配下に作成する。`aidlc-state.md` の `Workspace Root` などに**絶対パスを書かない**（リポの Git ルール: 絶対パスを commit しない）。必要なら `.`（リポジトリルート）など相対表現にする。
- commit / push はユーザーの明示指示があるまで行わない（AGENTS.md の Git 運用ルールに従う）。
- 第三者サービスのコード・UI・文言・トレードドレスを複製・翻案・移植しない（クリーンルーム原則）。

## 今回の依頼

$ARGUMENTS
