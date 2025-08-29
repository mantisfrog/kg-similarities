#!/usr/bin/env python3
"""
Build node & relationship CSVs from ./data/processed/Deposits_spatial.csv

Nodes (exact headers):
- node_Commodity.csv: commodityID:ID, commoditySymbol:string, commodityName:string, :LABEL
- node_Company.csv:   companyID:ID,  companyName:string, :LABEL
- node_Name.csv:      nameID:ID,     nameText:string,    :LABEL
- node_Deposit.csv:   depositID:ID, ENO:int, STATE:string, LOCATION:string,
                      OPERATING_STATUS:string, GEOLOGIC_AGE:string,
                      DEPOSIT_MODEL_ENVIRONMENT:string, DEPOSIT_MODEL_GROUP:string,
                      DEPOSIT_MODEL_TYPE:string, PROVINCES:string, IGNEOUS:string,
                      METALLOGENIC:string, SEDIMENTARY:string, TECTONIC:string, :LABEL

Relationships (exact headers):
- rel_Refers_to.csv  (:Name -> :Deposit)        :START_ID,:END_ID,:TYPE
- rel_Has.csv        (:Deposit -> :Commodity)   :START_ID,:END_ID,:TYPE,ROLE:string  (ROLE = Primary|Secondary)
- rel_Owns.csv       (:Company -> :Deposit)     :START_ID,:END_ID,:TYPE

Special in SYNONYMS: treat "2, 3, 4, 5, 6/7, 9" and "2, 3" as single names (do not split by comma).
"""
import csv
import re
from pathlib import Path
import pandas as pd

SRC = Path("./data/processed/Deposits_spatial.csv")

COLS = [
    "ENO","DEPOSIT_NAME","SYNONYMS","STATE","LONG_GDA94","LAT_GDA94",
    "OPERATING_STATUS","COMMODITY_PRIMARY","COMMODITY_SECONDARY","COMMODITY_NAMES",
    "COMPANIES","GEOLOGIC_AGE","DEPOSIT_MODEL_ENVIRONMENT","DEPOSIT_MODEL_GROUP",
    "DEPOSIT_MODEL_TYPE","PROVINCES","IGNEOUS","METALLOGENIC","SEDIMENTARY","TECTONIC"
]

SPECIAL_SYNONYMS = [
    "2, 3, 4, 5, 6/7, 9",
    "2, 3",
]

def clean(s):
    if s is None:
        return ""
    t = str(s).strip()
    return "" if t.lower() in {"", "nan", "none", "null", "n/a", "na"} else t

def split_commas(s):
    s = clean(s)
    return [] if not s else [p.strip() for p in s.split(",") if clean(p)]

def split_names_cell(s, is_synonyms=False):
    """Comma-split; in SYNONYMS, keep special phrases as single tokens."""
    s_clean = clean(s)
    if not s_clean:
        return []
    if is_synonyms:
        tmp = s_clean
        placeholders = {}
        # replace each special phrase with a placeholder token
        for idx, sp in enumerate(sorted(SPECIAL_SYNONYMS, key=len, reverse=True), 1):
            if sp in tmp:
                ph = f"__SPECIAL_{idx}__"
                placeholders[ph] = sp
                tmp = tmp.replace(sp, ph)
        parts = [p.strip() for p in tmp.split(",") if clean(p)]
        return [placeholders.get(p, p) for p in parts]
    return [p.strip() for p in s_clean.split(",") if clean(p)]

def norm_key(s):
    return re.sub(r"\s+", " ", clean(s)).strip().lower()

def write_csv(path, rows, header):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"✔ wrote {Path(path).name} ({len(rows)} rows)")

def main():
    df = pd.read_csv(SRC, dtype=str).fillna("")
    miss = [c for c in COLS if c not in df.columns]
    if miss:
        raise ValueError(f"Missing columns: {miss}")

    # Names
    name_vals = set()
    for _, r in df.iterrows():
        for n in split_names_cell(r["DEPOSIT_NAME"], is_synonyms=False):
            name_vals.add((norm_key(n), n))
        for n in split_names_cell(r["SYNONYMS"], is_synonyms=True):
            name_vals.add((norm_key(n), n))
    name_sorted = [orig for _, orig in sorted(name_vals, key=lambda x: x[0])]
    name_id = {v: f"name_{i:04d}" for i, v in enumerate(name_sorted, 1)}

    # Companies
    comp_vals = set()
    for _, r in df.iterrows():
        for c in split_commas(r["COMPANIES"]):
            comp_vals.add((norm_key(c), c))
    comp_sorted = [orig for _, orig in sorted(comp_vals, key=lambda x: x[0])]
    comp_id = {v: f"company_{i:04d}" for i, v in enumerate(comp_sorted, 1)}

    # Commodity symbols and names
    sym_keys = {}
    for _, r in df.iterrows():
        for s in split_commas(r["COMMODITY_PRIMARY"]) + split_commas(r["COMMODITY_SECONDARY"]):
            k = norm_key(s)
            if k not in sym_keys:
                sym_keys[k] = s
    sym2name = {k: "" for k in sym_keys}
    for _, r in df.iterrows():
        syms = split_commas(r["COMMODITY_PRIMARY"]) + split_commas(r["COMMODITY_SECONDARY"])
        names = split_commas(r["COMMODITY_NAMES"])
        if not syms or not names:
            continue
        if len(names) == len(syms):
            for s, n in zip(syms, names):
                k = norm_key(s)
                if k in sym2name and not sym2name[k] and clean(n):
                    sym2name[k] = n
        elif len(names) == 1:
            n = names[0]
            for s in syms:
                k = norm_key(s)
                if k in sym2name and not sym2name[k] and clean(n):
                    sym2name[k] = n
    sym_sorted = sorted(sym_keys.keys())
    sym_id = {k: f"commodity_{i:04d}" for i, k in enumerate(sym_sorted, 1)}

    # node_Name.csv
    write_csv(
        "./data/graph/node_Name.csv",
        [[name_id[v], v, "Name"] for v in name_sorted],
        header=["nameID:ID", "nameText:string", ":LABEL"]
    )

    # node_Company.csv
    write_csv(
        "./data/graph/node_Company.csv",
        [[comp_id[v], v, "Company"] for v in comp_sorted],
        header=["companyID:ID", "companyName:string", ":LABEL"]
    )

    # node_Commodity.csv
    node_commodity_rows = []
    for k in sym_sorted:
        symbol = sym_keys[k]
        cname = sym2name.get(k, "")
        node_commodity_rows.append([sym_id[k], symbol, cname, "Commodity"])
    write_csv(
        "./data/graph/node_Commodity.csv",
        node_commodity_rows,
        header=["commodityID:ID", "commoditySymbol:string", "commodityName:string", ":LABEL"]
    )

    # node_Deposit.csv
    dep_rows = []
    dep_id = {}
    for i, r in df.iterrows():
        did = f"deposit_{i+1:04d}"
        dep_id[i] = did
        eno_raw = clean(r["ENO"])
        try:
            eno_val = str(int(float(eno_raw))) if eno_raw else ""
        except ValueError:
            eno_val = ""
        lon, lat = clean(r["LONG_GDA94"]), clean(r["LAT_GDA94"])
        location = f"{lon},{lat}" if lon and lat else ""
        dep_rows.append([
            did,
            eno_val,
            clean(r["STATE"]),
            location,
            clean(r["OPERATING_STATUS"]),
            clean(r["GEOLOGIC_AGE"]),
            clean(r["DEPOSIT_MODEL_ENVIRONMENT"]),
            clean(r["DEPOSIT_MODEL_GROUP"]),
            clean(r["DEPOSIT_MODEL_TYPE"]),
            clean(r["PROVINCES"]),
            clean(r["IGNEOUS"]),
            clean(r["METALLOGENIC"]),
            clean(r["SEDIMENTARY"]),
            clean(r["TECTONIC"]),
            "Deposit",
        ])
    write_csv(
        "./data/graph/node_Deposit.csv",
        dep_rows,
        header=[
            "depositID:ID","ENO:int","STATE:string","LOCATION:string",
            "OPERATING_STATUS:string","GEOLOGIC_AGE:string",
            "DEPOSIT_MODEL_ENVIRONMENT:string","DEPOSIT_MODEL_GROUP:string",
            "DEPOSIT_MODEL_TYPE:string","PROVINCES:string","IGNEOUS:string",
            "METALLOGENIC:string","SEDIMENTARY:string","TECTONIC:string",":LABEL"
        ]
    )

    # rel_Refers_to.csv
    rel_refers = set()
    for i, r in df.iterrows():
        did = dep_id[i]
        for n in split_names_cell(r["DEPOSIT_NAME"], is_synonyms=False):
            rel_refers.add((name_id[n], did))
        for n in split_names_cell(r["SYNONYMS"], is_synonyms=True):
            rel_refers.add((name_id[n], did))
    write_csv(
        "./data/graph/rel_Refers_to.csv",
        [[a, b, "REFERS_TO"] for (a, b) in sorted(rel_refers)],
        header=[":START_ID", ":END_ID", ":TYPE"]
    )

    # rel_Has.csv
    rel_has = set()
    for i, r in df.iterrows():
        did = dep_id[i]
        for s in split_commas(r["COMMODITY_PRIMARY"]):
            k = norm_key(s)
            if k in sym_id:
                rel_has.add((did, sym_id[k], "HAS", "Primary"))
        for s in split_commas(r["COMMODITY_SECONDARY"]):
            k = norm_key(s)
            if k in sym_id:
                rel_has.add((did, sym_id[k], "HAS", "Secondary"))
    write_csv(
        "./data/graph/rel_Has.csv",
        [list(t) for t in sorted(rel_has)],
        header=[":START_ID", ":END_ID", ":TYPE", "ROLE:string"]
    )

    # rel_Owns.csv
    rel_owns = set()
    for i, r in df.iterrows():
        did = dep_id[i]
        for c in split_commas(r["COMPANIES"]):
            rel_owns.add((comp_id[c], did, "OWNS"))
    write_csv(
        "./data/graph/rel_Owns.csv",
        [[a, b, t] for (a, b, t) in sorted(rel_owns)],
        header=[":START_ID", ":END_ID", ":TYPE"]
    )

    print("✅ Done.")

def _remove_unmatched_parens(t: str) -> str:
    """移除所有落单括号，仅处理 ()。"""
    s = str(t)
    out = []
    opens = 0
    for ch in s:
        if ch == "(":
            opens += 1
            out.append(ch)
        elif ch == ")":
            if opens > 0:           # 只有有未配对的 '(' 时才保留 ')'
                opens -= 1
                out.append(ch)
            else:
                continue            # 落单的 ')' 丢弃
        else:
            out.append(ch)
    # 现在如果 opens > 0，说明有多余的 '('，从右往左删掉对应数量
    if opens > 0:
        rev = []
        for ch in reversed(out):
            if ch == "(" and opens > 0:
                opens -= 1          # 丢弃多余 '('
                continue
            rev.append(ch)
        out = list(reversed(rev))
    return "".join(out)

def _strip_outer_single_pair(t: str) -> str:
    """
    若整格字符串在去空白后仅在首尾各有一个括号，且总计只有这一对，则去掉它们。
    例："(Gold, Silver)" -> "Gold, Silver"
    """
    s = str(t).strip()
    if len(s) >= 2 and s[0] == "(" and s[-1] == ")" and s.count("(") == 1 and s.count(")") == 1:
        return s[1:-1].strip()
    return s

def _normalize_parens_simple(t: str) -> str:
    """先去落单括号，再尝试去掉仅包裹在首尾的一对括号。"""
    s = _remove_unmatched_parens(t)
    s = _strip_outer_single_pair(s)
    return s.strip()

def split_commas(s):
    """
    通用逗号切分 + 括号清洗：
    - 对整格先做括号清洗（按规则1/2）
    - 再按逗号切分
    - 对每个分片再次做括号清洗（处理像 'Gold)' / '(Silver' 这类边界残留）
    """
    s = clean(s)
    if not s:
        return []
    s = _normalize_parens_simple(s)  # 先在字段级清洗（可去掉包裹一对括号）
    parts = [p.strip() for p in s.split(",")]
    parts = [_normalize_parens_simple(p) for p in parts]
    return [p for p in parts if clean(p)]


if __name__ == "__main__":
    main()
