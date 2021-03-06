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

---
### バージョン履歴

#### 1.0.2
- 別の狩人の守り先が表示されてしまうバグを修正
- 死亡した霊媒師に結果が表示されないよう、死亡者にアクション結果を通知しないように変更
- 役職（闇騎士）を追加

#### 1.0.1
- 投票時の挙手を２人までに
- 時間停止条件のバグを修正
- 役職（女王、名探偵）を追加
- ソケット切断時の回避処理バグを修正

#### 1.0
- 基本役職（村人、人狼、占い師、霊媒師、狩人、狂人、共有者、妖狐、狂信者、猫又、背徳者、パン屋）を追加
- 役かけ、連続護衛、初日占いのルール設定を追加

