# Discord人狼サーバー

## 実行方法
---
### Discord Botを作成
  - https://discord.com/developers/applications にアクセスしてBotを作成する
    - Oauth2 -> URL Generatorにて、botのadmin権限を付与する
    - bot -> Privileged Gateway Intentsを有効にす
      - PRESENCE INTENT
      - SERVER MEMBERS INTENT
  - この際に、tokenを取得しておくこと
  - 使用したいサーバーに参加させる
---
### 資材を持ってくる
```
$ git clone https://github.com/YukiMurakami/discord_werewolf_server.git

$ cd discord_werewolf_server
```
---
### 接続情報を設定する
```
// 本番用の設定ファイルにシンボリックリンクを張り替える
$ ln -sf config.ini.prod config.ini

// 接続情報を編集
$ vim config.ini.prod
// HOST, PORTにサーバーで公開する情報を入れる（後程clientに設定が必要）
// TOKENに、Discord Botを作成した時のtokenを入力
// TLS対応が必要であれば証明書ファイルをSSL_FILEに設定
```
---
### ライブラリのインストール
```
$ pip install -r requirements.txt
```
---
### Discordの準備
- 下記Voice Channelをプライベートで作成
  - 大広間
  - 人狼
  - 共有
  - 妖狐
  - 個人部屋0
  - 個人部屋1
  ...
  - 個人部屋14 (必要な人数分だけ)
  - 霊界
- 下記Voice Channelをパブリックで作成
  - 玄関

- なお、これらの名前は設定ファイルで変更可能
---
### 起動
```
$ python server.py
```
