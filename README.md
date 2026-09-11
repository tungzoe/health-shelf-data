# health-shelf-data

保健櫃（HealthShelf）App 用的對照表與公開資料。**只有對照表與政府公開資料，沒有任何使用者資料**；公開是為了讓 App 不用登入就能拉。

App 啟動時從 `https://raw.githubusercontent.com/tungzoe/health-shelf-data/main/manifest.json` 拿清單，每種資料集（`kind`）
版本比手機上的大、`schema` 相同、sha256 對得上、過了驗證才整份下載套用。請求不帶任何參數；藥名比對全部在手機上做。

## 簽章（2026-09-11 起）

`manifest.json` 旁邊要有 `manifest.json.sig`：Ed25519 對 manifest.json **原始 bytes** 的簽章，base64 一行。
iOS 2026-09-11 之後的版本會先驗簽章再看清單，對不上就整份不套；build 14 以前的 App 不看 `.sig`，照舊只驗 sha256。

- 為什麼要簽：sha256 跟 manifest 在同一個 repo，只驗 sha256 等於只信 GitHub 帳號本身。帳號被盜或 token 外洩就能改 App 吃進去的
  營養素上限與交互作用建議，那是會影響用藥判斷的資料。簽章私鑰只在開發機，不在任何 repo。
- 私鑰在 `~/.healthshelf/manifest-signing.pem`。**第一次**：`python3 build.py --keygen`，把印出的公鑰貼進 App 的
  `Rules/DataUpdater.swift` 的 `manifestPublicKey`。之後 `build.py` 每次重寫 manifest 都會順手簽。
- **私鑰要備份到密碼管理器。** 弄丟就得重產一把、換 App 內建公鑰、出新 build；在那之前所有新版 App 都只會用手機上的舊資料。
- 只改 rules.json 也一樣：App repo 的 `tools/export-rules.sh` 會叫 `build.py --manifest-only`，簽章一起重產。
  `manifest.json` 跟 `manifest.json.sig` **要一起 commit**，分開推上去的那段時間 App 會驗不過。
- 資料集的 `url` 只准是這個 repo `main` 底下的固定檔名（App 也會擋別的 host、http、查詢字串）；
  `tcm-formulas.json`、`herb-drug-tw.json` 裡每筆的 `url` 只准 http(s)，App 用 `Link` 開它，別的 scheme 整份不套。

| 檔 | kind | 來源 | 怎麼產 |
| --- | --- | --- | --- |
| `rules.json` | `rules` | App 內建的營養素（含國健署 DRIs 第八版分族群參考值）、成分名排除名單、化學形式、藥物類別、搭配規則、健康狀況、健檢項目 | App repo `tools/export-rules.sh`（Swift 是唯一原始來源，**不要手改**；改資料回 App 改 Swift、`Rules.builtinVersion` +1） |
| `drugs-tw.json` | `drugIndex` | 食藥署「全部藥品許可證資料集」（data.fda.gov.tw 資料集 36，政府資料開放授權） | `python3 build.py`，素材在 `work/`（不進 git） |
| `tcm-formulas.json` | `tcmFormulas` | 衛福部中醫藥司 中藥基準方 200 方 | 同上 |
| `tcm-products.json` | `tcmProducts` | 衛福部中醫藥司 中藥許可證查詢（要驗證碼，使用者自己匯出 `work/tcm-licenses.xls`） | 同上；同名同組成的許可證合併、去賦形劑、略過外用與原料藥 |
| `herb-drug-tw.json` | `herbDrugInteractions` | 衛福部 中西藥交互作用資料庫（cmdhi.mohw.gov.tw），**僅供藥師參考** | 同上；只留有實質內容的筆數 |
| `manifest.json` | — | 以上每份的 kind、schema、version、url、bytes、sha256 | `build.py`（`--manifest-only` 只重寫這份） |

資料改了把 `build.py` 裡 `VERSIONS` 對應項 +1 再重產。各檔的來源、授權、備註寫在檔頭的 `source`／`license`／`note`。
