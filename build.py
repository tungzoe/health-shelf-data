#!/usr/bin/env python3
"""把 work/ 裡抓回來的素材整理成 App 會下載的資料集，並重寫 manifest.json。

用法：在 repo 根目錄執行 `python3 build.py`；只想重寫 manifest（例如 rules.json 剛換版）就加 `--manifest-only`。
- rules.json 不歸這裡管（Swift 是唯一原始來源，由 App repo 的 tools/export-rules.sh 產出），
  但 manifest 會把它一起列進去。
- 其他資料集的 version 記在下面 VERSIONS；資料改了就把對應版本 +1。

資料集格式全部是 {"schema": 1, "version": n, "updatedAt": "...", "source": "...", "license": "...", ...內容}。
App 只認 kind，同 kind 的新資料集或新版本不用重 build。
"""
import json, re, os, hashlib, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "work")
RAW = "https://raw.githubusercontent.com/tungzoe/health-shelf-data/main/"
TODAY = datetime.date.today().isoformat()

# 資料改了就 +1。schema 是格式版本，App 不認識的格式會整份略過。
VERSIONS = {"drugs-tw": 1, "tcm-formulas": 1, "herb-drug-tw": 1, "tcm-products": 1}


def dump(name, obj):
    path = os.path.join(ROOT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"{name}: {os.path.getsize(path):,} bytes")
    return path


# ---------------------------------------------------------------- 西藥許可證

# 主成分字串裡不算「藥名」的字：鹽類、離子、前綴。token 取第一個不在這裡面的字。
STOP = {"SODIUM", "POTASSIUM", "CALCIUM", "MAGNESIUM", "SILVER", "ZINC", "FERROUS", "FERRIC",
        "ALUMINUM", "ALUMINIUM", "DL", "D", "L", "ANHYDROUS", "MONOHYDRATE", "DIHYDRATE"}


def generic_tokens(g):
    """'ACETAMINOPHEN (EQ TO PARACETAMOL)' → ['ACETAMINOPHEN', 'PARACETAMOL']"""
    out = []
    m = re.search(r"\(\s*EQ\.?\s*TO\s+([A-Z][A-Z\- ]+)", g)
    base = re.sub(r"\(.*?\)", "", g)
    for w in re.split(r"[\s,/]+", base.upper()):
        w = w.strip("-")
        if not w or w in STOP or len(w) < 4:
            continue
        out.append(w)
        break
    if m:
        w = m.group(1).split()[0].strip("-")
        if len(w) >= 4 and w not in STOP and w not in out:
            out.append(w)
    return out


# 中文品名尾巴的劑型字，去掉才是使用者口中的名字。長的先比。
FORM_SUFFIX = sorted(["持續性藥效膜衣錠", "持續性藥效錠", "持續性膜衣錠", "腸溶微粒膠囊", "腸溶膜衣錠", "口溶膜衣錠",
                      "口崩錠", "口溶錠", "咀嚼錠", "發泡錠", "膜衣錠", "腸溶錠", "長效錠", "糖衣錠", "舌下錠", "陰道錠", "泡騰錠",
                      "軟膠囊", "液劑", "膠囊", "錠劑", "錠", "凍晶注射劑", "凍晶", "注射液", "注射劑", "注射筆", "糖漿", "懸液", "口服液", "內服液",
                      "乳膏", "軟膏", "凝膠", "眼藥水", "點眼液", "噴鼻液", "噴液", "滴劑", "栓劑", "貼片", "散劑", "顆粒", "散", "粉"],
                     key=len, reverse=True)


def strip_form(tok):
    """去掉尾巴的劑型字（最多兩層：「腸溶膜衣錠」→「」、「安心平錠」→「安心平」）"""
    for _ in range(2):
        for suf in FORM_SUFFIX:
            if tok.endswith(suf) and len(tok) > len(suf):
                tok = tok[: -len(suf)]
                break
    return tok.strip("-－ ")


def is_form_word(cand):
    """「持續性藥效」「膜衣」這種是劑型的一部分，不是名字"""
    return any(cand in suf for suf in FORM_SUFFIX) or cand in {"持續性", "持續性藥效", "持續性釋放", "凍晶", "長效", "速效", "緩釋", "控釋", "口服", "外用", "注射", "小兒", "兒童", "成人"}


def chinese_aliases(n):
    """'華興 施普寧錠（樂耐平）' → ['施普寧', '樂耐平']；'安心平錠0.5毫克' → ['安心平']"""
    out = []
    parens = re.findall(r"[（(]([^()（）]*)[)）]", n)
    head = re.split(r"[（(]", n)[0]
    m = re.search(r"[0-9０-９]", head)
    if m:
        head = head[:m.start()]
    head = head.strip()
    # 「華興 施普寧錠」：空白前是廠牌，名字在後面。「速糖淨 持續性藥效錠」：最後一段只是劑型，要往前找。
    parts = head.split() or [head]
    head = ""
    for tok in reversed(parts):
        cand = strip_form(tok)
        if len(cand) >= 2 and not is_form_word(cand):
            head = cand
            break
    if len(head) >= 2 and re.search(r"[一-鿿]", head):
        out.append(head)
    for p in parens:
        p = p.strip()
        if 2 <= len(p) <= 8 and re.fullmatch(r"[一-鿿]+", p) and p not in out:
            out.append(p)
    return out


def build_drugs():
    src = json.load(open(os.path.join(WORK, "drugs-tw.json"), encoding="utf-8"))
    records = []
    for d in src:
        tokens = []
        for g in d["g"]:
            for t in generic_tokens(g):
                if t not in tokens:
                    tokens.append(t)
        rec = {"n": d["n"], "e": d["e"], "g": d["g"], "t": tokens, "nb": chinese_aliases(d["n"]),
               "f": d["f"], "c": d["c"], "lic": d["lic"]}
        records.append(rec)
    obj = {"schema": 1, "version": VERSIONS["drugs-tw"], "updatedAt": TODAY,
           "source": "衛生福利部食品藥物管理署 全部藥品許可證資料集（data.fda.gov.tw 資料集 36）",
           "license": "政府資料開放授權條款",
           "note": "只留有效許可證的製劑；已排除註銷、原料藥、體外診斷試劑、衛生材料。t 是比對用的學名字、nb 是中文品名去掉廠牌與劑型後的名字。",
           "records": records}
    dump("drugs-tw.json", obj)
    return records


# ---------------------------------------------------------------- 中藥基準方

# 基準方的組成寫的是炮製名（炙甘草、煨薑、熟地黃），交互作用資料庫寫的是藥名（甘草、薑、地黃）。
# 只去掉炮製字，不去掉會變成另一味藥的字（大黃≠黃、川芎≠芎）。
HERB_PROCESS = re.compile(r"^(炙|煨|炒|酒|醋|蜜|鹽|製|煅|焦|黑|麩|清|淡|生|熟)")
HERB_ALIAS = {"白芍": ["芍藥"], "赤芍": ["芍藥", "赤芍藥"], "黃柏": ["黃蘗"], "枸杞子": ["枸杞"], "辛夷": ["辛夷花"],
              "川牛膝": ["牛膝"], "懷牛膝": ["牛膝"], "生薑皮": ["薑"], "乾薑": ["薑"], "薑黃": ["薑黃", "鬱金"]}


def herb_keys(raw, known):
    """一味藥在比對時算哪幾個名字。原名一定在；去炮製字後的名字夠長、或是資料庫認得的名字也算。"""
    out = []
    for p in raw.split("/"):
        p = p.strip()
        if not p:
            continue
        for k in [p] + HERB_ALIAS.get(p, []):
            if k not in out:
                out.append(k)
        q = HERB_PROCESS.sub("", p)
        if q != p and (len(q) >= 2 or q in known) and q not in out:
            out.append(q)
        for k in HERB_ALIAS.get(q, []):
            if k not in out:
                out.append(k)
    return out


def build_tcm(known_herbs=frozenset()):
    src = json.load(open(os.path.join(WORK, "tcm-formulas.json"), encoding="utf-8"))
    formulas = []
    for f in src:
        hk = []
        for h in f["h"]:
            for k in herb_keys(h, known_herbs):
                if k not in hk:
                    hk.append(k)
        formulas.append({"n": f["n"], "a": [a for a in f.get("a", []) if a != f["n"]], "h": f["h"], "hk": hk,
                         "fx": f.get("fx", ""), "ind": f.get("ind", ""), "warn": f.get("warn", ""),
                         "src": f["src"], "url": f["url"]})
    herbs = sorted({h for f in formulas for h in f["hk"]})
    obj = {"schema": 1, "version": VERSIONS["tcm-formulas"], "updatedAt": TODAY,
           "source": "衛生福利部中醫藥司 中藥基準方 200 方",
           "license": "政府網站資料開放宣告",
           "formulas": formulas, "herbs": herbs}
    dump("tcm-formulas.json", obj)
    return formulas, set(herbs)


# ---------------------------------------------------------------- 中西藥交互作用

# 資料庫裡的西藥欄位 → App 的 token。學名一律 generic:<大寫第一個字>；中文類別對 drug:<class>。
# 一筆可以對到多個 token（複方、或同一個藥有兩種登記名）。
DRUG_TOKENS = {
    "Deprenyl": ["generic:SELEGILINE"], "Taxol": ["generic:PACLITAXEL"], "rt-PA": ["generic:ALTEPLASE"],
    "Cyclosporin": ["generic:CICLOSPORIN", "generic:CYCLOSPORINE"], "Cyclosporine": ["generic:CICLOSPORIN", "generic:CYCLOSPORINE"],
    "Methotrexate (MTX)": ["generic:METHOTREXATE"], "Nifedipne": ["generic:NIFEDIPINE"], "Phenylzine": ["generic:PHENELZINE"],
    "Ciproﬂoxacin": ["generic:CIPROFLOXACIN"], "Kanamicin": ["generic:KANAMYCIN"], "Mytomycin C": ["generic:MITOMYCIN"],
    "Valproic acid": ["generic:VALPROIC", "generic:VALPROATE", "generic:DIVALPROEX"],
    "Ursodeoxycholic Acid": ["generic:URSODEOXYCHOLIC"], "Azidothymidine": ["generic:ZIDOVUDINE"],
    "Interferon-α": ["generic:INTERFERON"], "Silver sulfadiazine": ["generic:SULFADIAZINE"],
    "Baktar (TMP+SMX)": ["generic:TRIMETHOPRIM", "generic:SULFAMETHOXAZOLE"], "Aggrenox": ["generic:DIPYRIDAMOLE"],
    "Risperidone Quetiapine Quetiapine": ["generic:RISPERIDONE", "generic:QUETIAPINE"],
    "Busulphan": ["generic:BUSULFAN"], "Tirofibin": ["generic:TIROFIBAN"], "Rapamycin": ["generic:SIROLIMUS"],
    "Estrogen": ["drug:estrogen"], "Progesterone": ["generic:PROGESTERONE"], "Insulin": ["generic:INSULIN"],
    "Ephedra": ["herb:麻黃"], "Vitamin C": ["vitC"], "Thiazide": ["drug:diuretic"],
    "抗凝血劑": ["drug:antithrombotic"], "降血糖藥": ["drug:hypoglycemic"], "降血壓藥": ["drug:antihypertensive"],
    "MAO 抑制劑": ["drug:maoi"], "MAO抑制劑": ["drug:maoi"], "抗生素": ["drug:antibiotic"], "類固醇": ["drug:corticosteroid"],
    "利尿劑": ["drug:diuretic"], "擬交感興奮劑": ["drug:decongestant"], "NSAID類": ["drug:nsaid"],
    "抗癌藥": ["drug:antineoplastic"], "口服避孕藥": ["drug:contraceptive"],
    "膽鹼類": [],  # 太籠統，對不到任何類別，這幾筆不收
}

GENERIC_ADVICE = re.compile(r"^(無|無。|由醫師調整用藥。?|不須特別處理[，,。]?.*由醫師調整用藥。?|觀察用藥的反應，由醫師調整用藥。?|"
                            r"由醫師調整用藥，並觀察治療的反應。?|臨床意義及治療可能性還沒被確立，建議由醫師處方用藥。?)$")
UNKNOWN_SUMMARY = re.compile(r"^(機制未明|無交互作用|本項研究無描述機轉|本篇無描述機轉)|未達顯著")


def evidence_of(studies):
    s = studies or ""
    if re.search(r"個案|臨床|人體|病患|患者|受試者|藥動學|健保資料庫", s):
        return "clinical"
    if "動物" in s:
        return "animal"
    if re.search(r"體外|細胞|HPLC", s):
        return "invitro"
    return "review"


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\r", "")).strip()


def build_herb_drug(formula_names, herb_names):
    lst = json.load(open(os.path.join(WORK, "cmdhi_list.json"), encoding="utf-8"))
    det = json.load(open(os.path.join(WORK, "cmdhi_detail.json"), encoding="utf-8"))
    rules, dropped, unmapped = [], 0, set()
    for it in lst:
        d = det.get(str(it["id"]), {})
        summary, advice = clean(it["summary"]), clean(d.get("advice", ""))
        # 大批「機制未明＋由醫師調整用藥」是研究計畫的篩選結果，沒有可以告訴使用者的內容
        if UNKNOWN_SUMMARY.search(summary) and (not advice or GENERIC_ADVICE.match(advice)):
            dropped += 1
            continue
        herb = re.sub(r"《.*?》|（丸）|\(丸\)|\s", "", it["herb"])
        if herb in formula_names or re.search(r"(湯|散|丸|飲|丹|膏|方|煎)$", herb):
            kind = "formula"
        elif herb in herb_names or re.search(r"[一-鿿]", herb) and not re.search(r"(鹼|苷|素)$", herb):
            kind = "herb"
        else:
            kind = "compound"
        drug = it["drug"].strip()
        if drug in DRUG_TOKENS:
            tokens = DRUG_TOKENS[drug]
        elif re.fullmatch(r"[A-Za-z][A-Za-z\- ]*", drug):
            tokens = ["generic:" + drug.split()[0].upper().strip("-")]
        else:
            unmapped.add(drug)
            tokens = []
        if not tokens:
            dropped += 1
            continue
        rules.append({
            "id": f"cmdhi-{it['id']}",
            "herb": herb, "herbKind": kind, "drugName": drug, "drugTokens": tokens,
            "summary": summary, "advice": advice, "evidence": evidence_of(d.get("studies", "")),
            "refs": [clean(r) for r in d.get("refs", [])][:4],
            "url": f"https://www.cmdhi.mohw.gov.tw/Interactions/Detail?id={it['id']}",
        })
    if unmapped:
        print("對不到 token 的西藥名：", sorted(unmapped))
    obj = {"schema": 1, "version": VERSIONS["herb-drug-tw"], "updatedAt": TODAY,
           "source": "衛生福利部 中西藥交互作用資料庫（cmdhi.mohw.gov.tw）",
           "disclaimer": "本資料庫內容僅供藥師參考",
           "note": f"原始 {len(lst)} 筆；略過 {dropped} 筆只有「機制未明／由醫師調整用藥」的篩選結果。",
           "rules": rules}
    dump("herb-drug-tw.json", obj)
    print(f"herb-drug: kept {len(rules)} of {len(lst)}")



# ---------------------------------------------------------------- 中藥許可證（產品層級）

# 衛福部中醫藥司「中藥許可證查詢」網站的匯出檔（要驗證碼，使用者自己匯出後放 work/tcm-licenses.xls）。
# 每列：許可證字號、藥品名稱、劑型與類別、適應症及效能、處方成分、注意事項、有效期限。
TCM_HERB_RE = re.compile(r"([一-鿿][一-鿿、]{0,14}?)\s*[\(（]\s*([\d\.]+)\s*(mg|gm|g|公克|毫克|ml|mL|克)\s*[\)）]", re.I)
# 賦形劑、副料、單位字，不是藥
TCM_EXCIPIENT = {"澱粉", "蜂蜜", "砂糖", "白糖", "蔗糖", "乳糖", "糊精", "玉米澱粉", "馬鈴薯澱粉", "麥芽糊精", "滑石粉", "硬脂酸鎂", "微晶纖維素",
                 "羧甲基纖維素鈣", "羧甲基纖維素鈉", "二氧化矽", "滑石", "蜜", "煉蜜", "酒精", "乙醇", "水", "純水", "精製水", "食用色素", "香料", "每丸", "每包", "每錠", "每粒"}
TCM_ORAL_FORMS = ("顆粒", "散", "丸", "錠", "膠囊", "液", "膏", "飲", "糖漿", "酒", "露", "丹", "煎")
TCM_NAME_SUFFIX = sorted(["濃縮顆粒劑", "濃縮顆粒", "濃縮散劑", "濃縮散", "濃縮錠劑", "濃縮錠", "濃縮膠囊", "濃縮細粒", "顆粒劑", "顆粒", "細粒", "散劑", "丸劑", "錠劑", "膠囊劑", "膠囊",
                          "內服液劑", "口服液", "液劑", "糖漿", "膏劑", "煎劑", "水丸", "蜜丸", "糊丸", "小丸", "大丸"], key=len, reverse=True)


def tcm_base_name(raw):
    """'“順天堂”洗肝明目散顆粒' → '洗肝明目散'；'滋陽顆粒（茯菟丹）' → '滋陽'（括號別名另外回）"""
    n = raw.replace("\r\n", "\n").split("\n")[0].strip()
    # 廠牌寫在各種引號裡：“順天堂”、〝津村〞、''三才堂"、"科達"
    Q = "“”\"〝〞「」『』‘’'"
    n = re.sub(rf"^[{Q}]+[^{Q}]{{1,14}}[{Q}]+\s*", "", n)
    n = re.sub(rf"[{Q}]", "", n)
    n = n.replace("﹙", "(").replace("﹚", ")")
    aliases = [a for a in re.findall(r"[（(]([一-鿿]{2,12})[)）]", n)]
    n = re.sub(r"[（(].*?[)）]", "", n).strip()
    for _ in range(2):
        for suf in TCM_NAME_SUFFIX:
            if n.endswith(suf) and len(n) > len(suf) + 1:
                n = n[: -len(suf)]
                break
    n = re.sub(r"[\s\-－]+$", "", n)
    return n, aliases


def build_tcm_products(known_herbs=frozenset()):
    path = os.path.join(WORK, "tcm-licenses.xls")
    if not os.path.exists(path):
        print("沒有 work/tcm-licenses.xls，跳過 tcm-products")
        return
    import xlrd
    sh = xlrd.open_workbook(path).sheets()[0]
    groups = {}
    skipped = 0
    for r in range(1, sh.nrows):
        lic, name, formcat, ind, rx, warn, exp = [str(x) for x in sh.row_values(r)]
        parts = [x.strip() for x in formcat.replace("\r\n", "\n").split("\n") if x.strip()]
        form, cat = (parts[0], parts[-1]) if parts else ("", "")
        # 外用（藥膠布、油膏、外用液）與原料藥不會出現在藥袋裡
        if cat == "原料藥" or not any(k in form for k in TCM_ORAL_FORMS) or "外用" in form or "膠布" in form or "油膏" in form:
            skipped += 1
            continue
        herbs = []
        for h, a, u in TCM_HERB_RE.findall(rx):
            h = h.strip("、 ")
            if not h or h in TCM_EXCIPIENT or h.startswith("每"):
                continue
            if h not in herbs:
                herbs.append(h)
        if not herbs:
            skipped += 1
            continue
        base, aliases = tcm_base_name(name)
        if len(base) < 2:
            skipped += 1
            continue
        key = (base, tuple(herbs))
        g = groups.setdefault(key, {"n": base, "a": [], "h": herbs, "f": [], "c": [], "ind": "", "fx": "", "warn": "", "lic": [], "licCount": 0})
        for al in aliases:
            if al not in g["a"] and al != base:
                g["a"].append(al)
        if form and form not in g["f"]:
            g["f"].append(form)
        if cat and cat not in g["c"]:
            g["c"].append(cat)
        text = ind.replace("\r\n", "\n")
        m_ind = re.search(r"適應症[：:]\s*(.+)", text)
        m_fx = re.search(r"效能[：:]\s*(.+)", text)
        if not g["ind"] and m_ind:
            g["ind"] = clean(m_ind.group(1))[:120]
        if not g["fx"] and m_fx:
            g["fx"] = clean(m_fx.group(1))[:80]
        if not g["warn"] and warn.strip():
            g["warn"] = clean(warn)[:160]
        if len(g["lic"]) < 3:
            g["lic"].append(lic)
        g["licCount"] += 1
    products = []
    for g in groups.values():
        hk = []
        for h in g["h"]:
            for k in herb_keys(h, known_herbs):
                if k not in hk:
                    hk.append(k)
        g["hk"] = hk
        g["f"] = "、".join(g["f"][:3])
        g["c"] = "、".join(g["c"][:2])
        products.append(g)
    products.sort(key=lambda g: (g["n"], -g["licCount"]))
    obj = {"schema": 1, "version": VERSIONS["tcm-products"], "updatedAt": TODAY,
           "source": "衛生福利部中醫藥司 中藥許可證查詢（2026-09-05 匯出）",
           "license": "政府網站資料開放宣告",
           "note": f"同名、同組成的許可證合併成一筆；略過外用劑、原料藥、沒有處方成分的 {skipped} 筆。h 是處方成分（去賦形劑）、hk 是比對用藥名。",
           "products": products}
    dump("tcm-products.json", obj)
    print(f"tcm-products: {len(products)} 筆（原 {sh.nrows - 1} 張許可證）")

# ---------------------------------------------------------------- manifest

KINDS = {"rules": "rules", "drugs-tw": "drugIndex", "tcm-formulas": "tcmFormulas", "herb-drug-tw": "herbDrugInteractions", "tcm-products": "tcmProducts"}


def build_manifest():
    datasets = []
    for name, kind in KINDS.items():
        path = os.path.join(ROOT, name + ".json")
        if not os.path.exists(path):
            print(f"缺 {name}.json，manifest 不列")
            continue
        obj = json.load(open(path, encoding="utf-8"))
        data = open(path, "rb").read()
        datasets.append({"id": name, "kind": kind, "schema": obj["schema"], "version": obj["version"],
                         "updatedAt": obj.get("updatedAt", ""), "url": RAW + name + ".json",
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                         "source": obj.get("source", "")})
    dump("manifest.json", {"schema": 1, "generatedAt": TODAY, "datasets": datasets})


if __name__ == "__main__":
    import sys
    if "--manifest-only" in sys.argv:
        build_manifest()
        sys.exit(0)
    build_drugs()
    # 交互作用表裡的單味藥名先看一眼，方劑組成去炮製字時才知道「薑」這種單字名可以留
    cmdhi_herbs = {re.sub(r"《.*?》|（丸）|\(丸\)|\s", "", it["herb"]) for it in json.load(open(os.path.join(WORK, "cmdhi_list.json"), encoding="utf-8"))}
    formulas, herbs = build_tcm(frozenset(cmdhi_herbs))
    build_herb_drug({f["n"] for f in formulas} | {a for f in formulas for a in f["a"]}, herbs)
    build_tcm_products(frozenset(cmdhi_herbs))
    build_manifest()
