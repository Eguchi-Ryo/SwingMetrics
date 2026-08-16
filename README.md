# SwingMetrics AI

SwingMetrics AI は、ゴルフや野球などのスイング動画を解析し、フォームの定量評価と改善ポイントを可視化するためのアプリケーションです。

本プロジェクトは、バックエンドを Python / Flask で構築しながら、UI とロジックを責務ごとに分離することを最重要方針としています。Flask を学習しながら実装を進めることで、Web アプリケーションの基本設計、ルーティング、テンプレート、サービス層の分離を体験できるようにします。

## 1. 実装方針

- Python をバックエンドの中心言語として使用する
- Flask を使ってルート定義、テンプレート表示、データ連携を実装する
- ビジネスロジックは `app/services` に切り出す
- 画面表示は `app/templates` に分離する
- モックデータは `app/data` で管理し、将来的に DB や API に置き換えやすい構造にする

## 2. 責務の分離

### 2.1 Presentation Layer
- 画面 HTML は `app/templates` に書く
- HTML にはロジックを埋め込まず、Flask の render_template で値を渡す
- CSS は `app/static/css` に分離し、共通レイアウトとページごとの差分を整理する

### 2.2 Application / Service Layer
- `app/services/swing_service.py` に計算ロジックや整形処理を置く
- 画面やルートに直接ロジックを書くことを避ける
- 将来の AI 推論や外部 API 連携を追加しやすいように抽象化する

### 2.3 Data Layer
- `app/data/mock_data.py` にダミーデータを置く
- 実運用時は DB や API クライアントに置換できるように、データ構造を明確にする
- 画面に直接依存しないデータモデルを意識する

## 3. ルーティング構成

- `/` : ランディングページ
- `/dashboard` : 解析履歴と成長トラッキング
- `/upload` : 動画アップロードと設定
- `/models` : お手本スイングライブラリ
- `/analysis` : 解析詳細と時系列比較

## 4. ディレクトリ構成

```text
.
├── README.md
├── requirements.txt
├── app.py
├── app/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   └── mock_data.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── services/
│   │   └── swing_service.py
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── dashboard.html
│       ├── upload.html
│       ├── models.html
│       └── analysis.html
└── .gitignore
```

## 5. Flask での開発ルール

- ルーティングは `app/routes` で管理する
- データの読み書きは `app/data` に閉じ込める
- 計算や整形は `app/services` に閉じ込める
- HTML はテンプレートで描き、条件分岐は Jinja2 に寄せる
- テンプレートファイルは責務ごとに分割し、base.html を共通レイアウトとする

## 6. 開発手順

### 依存関係のインストール

```bash
python -m pip install -r requirements.txt
```

### 開発サーバー起動

```bash
python app.py
```

ブラウザで以下にアクセスします。

- http://localhost:5001/
- http://localhost:5001/dashboard
- http://localhost:5001/upload
- http://localhost:5001/models
- http://localhost:5001/analysis

## 7. 共同開発を見据えた設計

- ルーティングとビジネスロジックが混在しない
- データの変更が UI に直接影響しない
- 機能追加時に対応するファイルが明確になる
- Flask の学習を進めながら、ウェブアプリの構成理解を深められる

## 8. 今後の展望

- PostgreSQL / SQLite への接続
- Flask の Blueprint を増やした機能分割
- ユーザー認証とセッション管理
- AI 推論 API との連携
- 解析データの保存と履歴管理
- 比較モデルの追加・削除・カテゴリ管理

## 9. 実務上のメモ

このプロジェクトは、UI のモックアップをベースにしながら、Python / Flask を使って実際に動く Web アプリへと成長させる段階を目指しています。バックエンドを必須としている今回の前提に合わせ、責務分離と拡張性を担保しながら、Flask の理解を深めることを優先しています。
