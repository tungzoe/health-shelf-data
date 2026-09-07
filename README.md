# health-shelf-data

保健櫃（HealthShelf）App 用的對照表與公開資料。**只有對照表與政府公開資料，沒有任何使用者資料**；公開是為了讓 App 不用登入就能拉。

App 啟動時從 `https://raw.githubusercontent.com/tungzoe/health-shelf-data/main/manifest.json` 拿清單，每種資料集（`kind`）
版本比手機上的大、`schema` 相同、sha256 對得上、過了驗證才整份下載套用。請求不帶任何參數；藥名比對全部在手機上做。

| 檔 | kind | 來源 | 怎麼產 |
| --- | --- | --- | --- |
| `rules.json` | `rules` | App 內建的營養素（含國健署 DRIs 第八版分族群參考值）、成分名排除名單、化學形式、藥物類別、搭配規則、健康狀況、健檢項目 | App repo `tools/export-rules.sh`（Swift 是唯一原始來源，**不要手改**；改資料回 App 改 Swift、`Rules.builtinVersion` +1） |
| `drugs-tw.json` | `drugIndex` | 食藥署「全部藥品許可證資料集」（data.fda.gov.tw 資料集 36，政府資料開放授權） | `python3 build.py`，素材在 `work/`（不進 git） |
| `tcm-formulas.json` | `tcmFormulas` | 衛福部中醫藥司 中藥基準方 200 方 | 同上 |
| `tcm-products.json` | `tcmProducts` | 衛福部中醫藥司 中藥許可證查詢（要驗證碼，使用者自己匯出 `work/tcm-licenses.xls`） | 同上；同名同組成的許可證合併、去賦形劑、略過外用與原料藥 |
| `herb-drug-tw.json` | `herbDrugInteractions` | 衛福部 中西藥交互作用資料庫（cmdhi.mohw.gov.tw），**僅供藥師參考** | 同上；只留有實質內容的筆數 |
| `manifest.json` | — | 以上每份的 kind、schema、version、url、bytes、sha256 | `build.py`（`--manifest-only` 只重寫這份） |

資料改了把 `build.py` 裡 `VERSIONS` 對應項 +1 再重產。各檔的來源、授權、備註寫在檔頭的 `source`／`license`／`note`。
