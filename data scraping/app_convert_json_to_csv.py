import pandas as pd

INPUT_JSONL = "converted_test.jsonl"
OUTPUT_CSV = "schools.csv"
CHUNKSIZE = 50_000  # 按需调整；越大越快但更占内存


def flatten_df(df: pd.DataFrame) -> pd.DataFrame:
    # grade_level: {"from": "...", "to": "..."} -> "from-to"
    if "grade_level" in df.columns:
        def _gl(x):
            if isinstance(x, dict):
                a = (x or {}).get("from", "") or ""
                b = (x or {}).get("to", "") or ""
                s = f"{a}-{b}".strip("-")
                return s
            return x
        df["grade_level"] = df["grade_level"].apply(_gl)

    # student_teacher_ratio: {"raw": "13:1", ...} -> "13:1"
    if "student_teacher_ratio" in df.columns:
        df["student_teacher_ratio"] = df["student_teacher_ratio"].apply(
            lambda d: (d or {}).get("raw") if isinstance(d, dict) else d
        )

    # flatten source_meta into separate columns
    if "source_meta" in df.columns:
        df["source_page"] = df["source_meta"].apply(
            lambda d: (d or {}).get("page") if isinstance(d, dict) else None
        )
        df["source_raw_school_name"] = df["source_meta"].apply(
            lambda d: (d or {}).get("raw_school_name") if isinstance(d, dict) else None
        )
        df = df.drop(columns=["source_meta"])

    return df


def jsonl_to_csv(input_path: str, output_path: str, chunksize: int = 0) -> None:
    if chunksize and chunksize > 0:
        first = True
        for chunk in pd.read_json(input_path, lines=True, chunksize=chunksize):
            chunk = flatten_df(chunk)
            chunk.to_csv(
                output_path,
                mode="w" if first else "a",
                header=first,
                index=False,
                encoding="utf-8",
            )
            first = False
    else:
        df = pd.read_json(input_path, lines=True)
        df = flatten_df(df)
        df.to_csv(output_path, index=False, encoding="utf-8")


if __name__ == "__main__":
    jsonl_to_csv(INPUT_JSONL, OUTPUT_CSV, CHUNKSIZE)
