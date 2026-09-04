# health-shelf-data

保健櫃（HealthShelf）App 用的對照表：營養素上限、化學形式、藥物別名、搭配規則。

- 這個 repo **只有對照表，沒有任何使用者資料**。公開是為了讓 App 不用登入就能拉。
- `rules.json` 是由 App 原始碼 `tools/export-rules.sh` 產生的，**不要手改**；要改資料回 App repo 改 Swift，
  把 `Rules.builtinVersion` +1，重新產出再 commit 這裡。
- App 啟動時從 `https://raw.githubusercontent.com/tungzoe/health-shelf-data/main/rules.json` 整份拉回來，
  `version` 比手機上的大、`schema` 相同、過了驗證才套用。請求不帶任何參數。

資料來源寫在每一筆的 `note`／`reference`／`source` 欄位。上限主要依衛福部國健署「國人膳食營養素參考攝取量」第八版。
