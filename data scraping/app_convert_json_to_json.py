import json
import re
from pathlib import Path

def normalize_school(item: dict) -> dict:
    if not isinstance(item, dict):
        raise TypeError(f"normalize_school expects dict, got {type(item)}")

    raw = item.get("raw_text_list", [])

    def after(label: str):
        """Return the first token after the first occurrence of label in raw."""
        try:
            i = raw.index(label)
        except ValueError:
            return None
        return raw[i + 1] if i + 1 < len(raw) else None

    grade = after("Grade Level")
    enrollment = after("Enrollment")
    ratio = after("Student-Teacher Ratio")

    # Rank: pattern '#', '1', 'in', 'Texas Elementary Schools'
    rank = None
    for i in range(len(raw) - 3):
        if raw[i] == "#" and raw[i + 2] == "in" and re.fullmatch(r"\d+", str(raw[i + 1])):
            rank = int(raw[i + 1])
            break

    # School name: concatenate starting tokens until a location token or label token is reached
    name_tokens = []
    for tok in raw:
        if isinstance(tok, str) and re.search(r",\s*TX$", tok):
            break
        if tok in {"#", "Grade Level", "Enrollment", "Student-Teacher Ratio", "Read More"}:
            break
        name_tokens.append(tok)
    name = " ".join(name_tokens).strip() or item.get("school_name")

    # City/state: 'Midland, TX'
    city_state = None
    for tok in raw:
        if isinstance(tok, str) and re.search(r",\s*TX$", tok):
            city_state = tok
            break

    # District: token ending with 'School District'
    district = None
    for tok in raw:
        if isinstance(tok, str) and tok.endswith("School District"):
            district = tok
            break

    # Description: first longer token containing ' is a '
    description = None
    for tok in raw:
        if isinstance(tok, str) and " is a " in tok:
            description = tok
            break

    # Grade parse: '1-6' / 'PK-5'
    grade_parsed = None
    if grade:
        m = re.fullmatch(r"([A-Za-z]{1,2}|\d+)-([A-Za-z]{1,2}|\d+)", str(grade))
        grade_parsed = {"from": m.group(1), "to": m.group(2)} if m else {"value": grade}

    # Ratio parse: '17:1'
    ratio_parsed = None
    if ratio and re.fullmatch(r"\d+\s*:\s*\d+", str(ratio)):
        a, b = [int(x.strip()) for x in str(ratio).split(":")]
        ratio_parsed = {"students": a, "teacher": b, "raw": str(ratio)}
    elif ratio:
        ratio_parsed = {"raw": str(ratio)}

    # Enrollment parse
    if isinstance(enrollment, str) and enrollment.isdigit():
        enrollment_val = int(enrollment)
    else:
        enrollment_val = enrollment

    return {
        "school_name": name,
        "city_state": city_state,
        "district": district,
        "rank_state_elementary": rank,
        "grade_level": grade_parsed,
        "enrollment": enrollment_val,
        "student_teacher_ratio": ratio_parsed,
        "description": description,
        "source_meta": {
            "page": item.get("page"),
            "raw_school_name": item.get("school_name"),
        },
    }


def normalize_all(schools: list[dict]) -> list[dict]:
    if not isinstance(schools, list):
        raise TypeError(f"Input JSON must be a list of objects, got {type(schools)}")
    return [normalize_school(x) for x in schools]

def load_records(in_path: str) -> list[dict]:
    p = Path(in_path)
    if p.suffix.lower() in {".jsonl", ".ndjson"}:
        records = []
        with p.open("r", encoding="utf-8") as f:
            for ln, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON on line {ln}: {p}") from e
                records.append(obj)
        return records
    else:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容：如果意外读到单个 dict，也包成 list
        return data if isinstance(data, list) else [data]


def write_records(records: list[dict], out_path: str) -> None:
    p = Path(out_path)
    if p.suffix.lower() in {".jsonl", ".ndjson"}:
        with p.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        with p.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)


def main(in_path: str = "test.jsonl", out_path: str = "converted_test.jsonl"):
    data = load_records(in_path)
    converted = normalize_all(data)
    write_records(converted, out_path)
    print(f"Wrote {out_path} ({len(converted)} records)")


if __name__ == "__main__":
    main()
