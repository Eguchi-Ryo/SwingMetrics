# SwingMetrics AI

SwingMetrics AI は、ゴルフや野球などのスイング動画を解析し、フォームの定量評価と改善ポイントを可視化するためのアプリケーションです。

本プロジェクトは、バックエンドを Python / Flask で構築しながら、UI とロジックを責務ごとに分離することを最重要方針としています。Flask を学習しながら実装を進めることで、Web アプリケーションの基本設計、ルーティング、テンプレート、サービス層の分離を体験できるようにします。

## 1. 実装方針

- Python をバックエンドの中心言語として使用する
- Flask を使ってルート定義、テンプレート表示、データ連携を実装する
- ビジネスロジックは `app/services` に切り出す
- 画面表示は `app/templates` に分離する
- ユーザーアカウント、お手本、解析履歴は MySQL に保存し、所有者ごとにアクセス制御する

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
- 画面選択肢は `app/data/options.py` で管理し、お手本動画は MySQL に保存する
- 解析情報とユーザーアカウントも MySQL に保存し、動画ファイルは `data/uploads` に保存する
- 画面に直接依存しないデータモデルを意識する

## 3. ルーティング構成

- `/` : ランディングページ
- `/register`・`/login` : 任意のアカウント登録・ログイン
- `/dashboard` : このブラウザー（またはログインアカウント）の解析履歴
- `/upload` : ゲストまたはログイン中ユーザーの動画アップロード
- `/models` : 公式お手本と、自分用に登録したお手本のライブラリ
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
│   │   └── options.py
│   ├── security.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── services/
│   │   ├── benchmark_service.py
│   │   ├── database.py
│   │   ├── swing_service.py
│   │   └── user_service.py
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   └── templates/
│       ├── base.html
│       ├── user_login.html
│       ├── user_register.html
│       ├── index.html
│       ├── dashboard.html
│       ├── upload.html
│       ├── models.html
│       └── analysis.html
└── .gitignore
```

## 5. Flask での開発ルール

- ルーティングは `app/routes` で管理する
- DBの読み書きは `app/services` に閉じ込め、フォーム選択肢のみ `app/data` で管理する
- 計算や整形は `app/services` に閉じ込める
- HTML はテンプレートで描き、条件分岐は Jinja2 に寄せる
- テンプレートファイルは責務ごとに分割し、base.html を共通レイアウトとする

## 6. 開発手順

### 依存関係のインストール

```bash
python -m pip install -r requirements.txt
```

### Docker Compose で起動（推奨）

```bash
docker compose up --build
```

Web アプリと MySQL が起動し、MySQL のデータは `mysql_data` ボリューム、アップロード動画はホスト側の `data/uploads` に保持されます。DB 接続情報は環境変数 `MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD` で変更できます。ローカル開発用の既定値は本番環境では必ず変更してください。

アカウント登録なしのゲストでも動画解析、履歴閲覧、公式お手本との比較ができます。ゲストのデータは署名付きブラウザーCookieの所有キーで分離され、ログイン画面を通してアカウントを作成・ログインすると、そのブラウザーの解析履歴をアカウントへ引き継ぎます。ログイン後は自分用のお手本動画を登録でき、別端末でもアカウントのデータを利用できます。ユーザー名は英数字と `.` `_` `-` の3〜32文字、パスワードは12文字以上です。

ログインしていないゲストのデータは同じブラウザーからのみ利用できます。ゲストCookieは180日間有効ですが、Cookieの削除・期限切れやブラウザープロファイルの変更で復旧できなくなるため、履歴を保持したい場合はログインしてください。`.env` に `SECRET_KEY` を設定するときは、再起動後も同じランダム値を使ってください。未設定時はアプリが `data/.flask_secret_key` に署名鍵を作成し、再起動後も再利用します。この鍵ファイルはGit管理対象外です。秘密鍵を削除・変更すると、ログイン前のゲストデータを引き継げなくなります。解析動画・履歴・自分用お手本は所有キーでアクセス制御し、他のゲストやアカウントには見えません。管理者が公式として登録したお手本だけは全員に公開されます。

### 管理者としてお手本動画を管理する

一般ユーザーが登録したお手本はそのユーザーだけに公開され、管理者が登録した公式お手本は全ユーザーに公開されます。どちらもアップロード後に自動でYOLO-Pose解析され、解析完了後は骨格を重ねた動画とフレームごとの体幹角度データを動画・グラフ比較に使えます。解析中はライブラリに状態が表示され、完了すると比較候補に反映されます。

公式お手本の追加・削除は管理者のみ可能です。管理者ログインへのリンクは公開画面に表示されません。次の手順で、管理者専用の推測困難なURLを設定してください。

1. プロジェクト直下の `.env` を作成または編集し、次の値を設定します。ユーザー名・パスワード・URLの例は、実際の環境で必ず別の値に置き換えてください。

		```dotenv
		ADMIN_USERNAME=your-admin-name
		ADMIN_PASSWORD=replace-with-a-unique-long-password
		ADMIN_LOGIN_PATH=/replace-this-with-your-own-random-private-path
		SECRET_KEY=replace-with-a-persistent-random-secret
		```

		`.env` の例は必ず置き換え、`ADMIN_LOGIN_PATH` には先頭の `/` を含めて25文字以上（`/` の後に24文字以上）の推測困難な文字列を設定します。パスワードマネージャーなどでランダムな値を生成してください。末尾の `/`、クエリ文字列（`?`）、フラグメント（`#`）は使えません。

2. 設定を反映するためアプリを再起動します。Docker Composeを使っている場合は、通常の起動手順で再度 `docker compose up -d` を実行します。
3. ブラウザーで `http://localhost:5001` の後ろに設定した `ADMIN_LOGIN_PATH` を付けたURLを開きます。たとえば、`ADMIN_LOGIN_PATH=/your-private-path` なら `http://localhost:5001/your-private-path` です。実際には例の文字列を使わず、自分で生成した値を使ってください。
4. `.env` に設定した管理者ユーザー名とパスワードでログインします。ログイン後は「お手本ライブラリ」から動画を追加・削除できます。操作が終わったら、ナビゲーションの「管理者ログアウト」を押してください。

3つの `ADMIN_*` 設定のいずれかが空欄の場合、ログインURLは登録されません（設定が一部だけの場合はアプリ起動時にエラーになります）。設定した秘密URL以外の `/admin/login` は利用できません。隠しURLは認証の代わりではなく、追加の防御層です。`SECRET_KEY` は再起動後も同じ値を保つようにし、HTTPS環境では `SESSION_COOKIE_SECURE=true` を設定してください。`.env` は秘密情報を含むため、リポジトリへコミットしないでください。

Docker を使わず起動する場合は、MySQL 8.4 を別途起動し、`MYSQL_HOST` などの接続環境変数を設定してから `python app.py` を実行してください。動画アップロードの既定上限は 500 MB で、`MAX_CONTENT_LENGTH` で変更できます。

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

- Flask の Blueprint を増やした機能分割
- アカウントへのゲストデータ引き継ぎの改善
- AI 推論 API との連携
- 解析データの保存と履歴管理
- 比較モデルの追加・削除・カテゴリ管理

## 9. 実務上のメモ

このプロジェクトは、UI のモックアップをベースにしながら、Python / Flask を使って実際に動く Web アプリへと成長させる段階を目指しています。バックエンドを必須としている今回の前提に合わせ、責務分離と拡張性を担保しながら、Flask の理解を深めることを優先しています。
