"""
ICAO 9303 MRZ checksum validation — passport (TD3) format.

TD3 = two 44-character lines, standard for passports.
Reference: ICAO Doc 9303, Part 4.

Line 2 layout (0-indexed):
  0-8   passport number (9)
  9     check digit for passport number
  10-12 nationality (3)
  13-18 date of birth YYMMDD (6)
  19    check digit for DOB
  20    sex (1)
  21-26 expiry date YYMMDD (6)
  27    check digit for expiry
  28-41 personal number (14, optional, '<'-filled if unused)
  42    check digit for personal number
  43    composite check digit (over doc#, DOB, expiry, personal# fields)
"""

WEIGHTS = (7, 3, 1)


def _char_value(c: str) -> int:
    if c == "<":
        return 0
    if c.isdigit():
        return int(c)
    if c.isalpha():
        return ord(c.upper()) - ord("A") + 10
    raise ValueError(f"invalid MRZ character: {c!r}")


def check_digit(s: str) -> int:
    """Compute the ICAO 9303 check digit for a string."""
    total = 0
    for i, c in enumerate(s):
        total += _char_value(c) * WEIGHTS[i % 3]
    return total % 10


def validate_td3(line2: str) -> dict:
    """
    Validate all check digits in a TD3 line 2. Returns an explainable
    result: overall pass/fail plus per-field detail naming exactly
    what failed, not just a score.
    """
    line2 = line2.strip().upper()
    if len(line2) != 44:
        return {"valid": False, "error": f"line 2 must be 44 chars, got {len(line2)}"}

    fields = {
        "passport_number": (line2[0:9], line2[9]),
        "date_of_birth":   (line2[13:19], line2[19]),
        "expiry_date":     (line2[21:27], line2[27]),
        "personal_number": (line2[28:42], line2[42]),
    }

    checks = []
    for name, (value, given_check) in fields.items():
        expected = check_digit(value)
        actual = int(given_check) if given_check.isdigit() else _char_value(given_check)
        checks.append({
            "field": name,
            "value": value,
            "expected_check_digit": expected,
            "found_check_digit": actual,
            "passed": expected == actual,
        })

    composite_input = line2[0:10] + line2[13:20] + line2[21:43]
    composite_expected = check_digit(composite_input)
    composite_found = line2[43]
    composite_found_val = int(composite_found) if composite_found.isdigit() else _char_value(composite_found)
    checks.append({
        "field": "composite",
        "value": composite_input,
        "expected_check_digit": composite_expected,
        "found_check_digit": composite_found_val,
        "passed": composite_expected == composite_found_val,
    })

    return {
        "valid": all(c["passed"] for c in checks),
        "checks": checks,
    }


def demo():
    """Self-check: one genuine ICAO sample line, one tampered variant."""
    genuine = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    result = validate_td3(genuine)
    assert result["valid"], f"genuine MRZ should pass: {result}"
    print("Genuine sample: PASS (all checksums valid)")

    # tamper the date of birth (740812 -> 740813) without fixing its check digit
    tampered = "L898902C36UTO7408132F1204159ZE184226B<<<<<10"
    result = validate_td3(tampered)
    assert not result["valid"], "tampered MRZ should fail"
    failed = [c["field"] for c in result["checks"] if not c["passed"]]
    print(f"Tampered sample: FAIL — flagged field(s): {failed}")


if __name__ == "__main__":
    demo()