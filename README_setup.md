# Three Lab 工具管理システム - セットアップ手順

## ファイル構成
```
tool-manager/
├── backend/
│   ├── main.py          # FastAPI バックエンド
│   └── requirements.txt
└── tool-manager-frontend.html  # フロントエンド（ブラウザで開くだけ）
```

## セットアップ

### 1. バックエンド起動
```bash
# バックエンドフォルダに移動
cd backend

# ライブラリインストール（初回のみ）
pip install fastapi uvicorn qrcode pillow python-multipart

# サーバー起動
py -m uvicorn main:app --reload --port 8000
```

### 2. フロントエンド起動
`tool-manager-frontend.html` をブラウザで開くだけ！
（Chromeでローカルファイルを開いてください）

### 3. 動作確認
- バックエンド: http://localhost:8000/docs でAPIドキュメント確認可能
- フロントエンド: htmlファイルをChromeで開く

## 機能一覧
- 📊 ダッシュボード - 工具・依頼の概要
- ⚙ 工具一覧 - 全工具の一覧・検索・フィルタ
- ▣ QRスキャン - カメラでQR読み取り or ID直接入力
- ↺ 再研磨依頼 - 依頼の一覧・完了管理
- ＋ 工具登録 - 新規工具登録・QRコード発行

## デモデータ（初期データ）
- エンドミル φ10（OSG）- 稼働中
- エンドミル φ6（MITSUBISHI）- 研磨待ち
- ドリル φ5（NACHI）- 稼働中
- ボールエンドミル R3（KYOCERA）- 稼働中
- フェイスミル φ50（SUMITOMO）- 非稼働

## APIエンドポイント
- GET  /api/tools         - 工具一覧
- POST /api/tools         - 工具登録
- GET  /api/tools/{id}    - 工具詳細
- GET  /api/tools/{id}/qr - QRコード生成
- GET  /api/sharpening-requests        - 依頼一覧
- POST /api/sharpening-requests        - 依頼作成
- PATCH /api/sharpening-requests/{id}/complete - 依頼完了
- GET  /api/stats         - 統計情報
