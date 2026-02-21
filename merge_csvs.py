import os
import glob
import pandas as pd
import csv

folder_path = r"C:\Users\daans\PycharmProjects\Tiktok\Merge"
out_path = os.path.join(folder_path, "merged_clean_shared_columns.csv")

def detect_delimiter(file_path: str) -> str:
    """Detect delimiter between ';' and ',' based on first non-empty line."""
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # simple heuristic
            if line.count(";") >= line.count(","):
                return ";"
            return ","
    return ";"  # fallback

def fix_header_line(line: str, delim: str) -> str:
    """
    Fix common header issue: 'bio_links,__source_file' where comma sneaks into a ; delimited header.
    """
    if delim == ";" and "bio_links,__source_file" in line:
        return line.replace("bio_links,__source_file", "bio_links;__source_file")
    return line

def repair_multiline_records(in_file: str, out_file: str) -> None:
    """
    Repairs broken multiline records by buffering lines until quotes are balanced.
    This helps when fields contain newlines and quoting is messy.
    """
    fixed_rows = []
    buffer = ""

    with open(in_file, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for raw_line in f:
            line = raw_line.rstrip("\r\n")

            if buffer == "":
                buffer = line
            else:
                buffer += "\n" + line

            # Balanced quotes => record complete
            if buffer.count('"') % 2 == 0:
                fixed_rows.append(buffer)
                buffer = ""

    if buffer:
        fixed_rows.append(buffer)

    with open(out_file, "w", encoding="utf-8-sig", errors="replace", newline="") as f:
        for row in fixed_rows:
            f.write(row + "\n")

def read_csv_robust(file_path: str) -> pd.DataFrame:
    """
    Reads CSV robustly:
    - detects delimiter (; or ,)
    - repairs multiline/quote issues into a temp file
    - reads with QUOTE_NONE so stray " doesn't break parsing
    """
    delim = detect_delimiter(file_path)

    # repair file into temp
    tmp_path = file_path + ".__tmp_fixed__.csv"
    repair_multiline_records(file_path, tmp_path)

    # Fix header line if needed
    with open(tmp_path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    if lines:
        lines[0] = fix_header_line(lines[0], delim)
    with open(tmp_path, "w", encoding="utf-8-sig", errors="replace") as f:
        f.writelines(lines)

    # read
    df = pd.read_csv(
        tmp_path,
        sep=delim,
        engine="python",
        encoding="utf-8-sig",
        quoting=csv.QUOTE_NONE,   # ignore stray quotes
        escapechar="\\",
        on_bad_lines="skip"
    )

    # cleanup temp
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    # normalize column names
    df.columns = [c.strip().replace("\ufeff", "") for c in df.columns]

    return df

# ---- Load all files
files = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
if not files:
    raise SystemExit(f"No .csv files found in: {folder_path}")

dfs = []
for f in files:
    try:
        df = read_csv_robust(f)
        df["__source_file"] = os.path.basename(f)  # keep trace
        dfs.append(df)
        print("OK  ", os.path.basename(f), "shape:", df.shape)
    except Exception as e:
        print("FAIL", os.path.basename(f), "=>", repr(e))

if not dfs:
    raise SystemExit("All files failed to parse. Paste the FAIL lines here.")

# ---- Keep ONLY shared columns across all files (intersection)
shared_cols = set(dfs[0].columns)
for df in dfs[1:]:
    shared_cols &= set(df.columns)

# Make sure 'keyword' stays included if present in most files
# (If some files miss it, you can choose to add it instead of dropping.)
if "keyword" not in shared_cols:
    # if keyword exists in any file, we force it in and fill missing with NaN
    if any("keyword" in d.columns for d in dfs):
        for d in dfs:
            if "keyword" not in d.columns:
                d["keyword"] = pd.NA
        shared_cols.add("keyword")

# Always keep __source_file
if "__source_file" not in shared_cols:
    shared_cols.add("__source_file")

shared_cols = list(shared_cols)

# Align and concat
aligned = [d.reindex(columns=shared_cols) for d in dfs]
merged = pd.concat(aligned, ignore_index=True)

# Optional: remove totally empty rows
merged = merged.dropna(how="all")

# Save
merged.to_csv(out_path, index=False, encoding="utf-8-sig")
print("\nSaved:", out_path)
print("Final shape:", merged.shape)
print("Columns:", merged.columns.tolist())