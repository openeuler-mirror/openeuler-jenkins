from src.ac.acl.wittyhub_audit.license_access import (
    STATUS_ALLOWED,
    STATUS_BLACK,
    STATUS_CONFLICT,
    STATUS_MISSING,
    STATUS_RESTRICTED,
    STATUS_UNKNOWN,
    LicenseAccessList,
    LicenseScanner,
    normalize_expression,
)

LICENSE_LIST = """\
Software Licenses:
  Nonstandard Licenses:
  - alias:
    - Apache
    identifier: Apache
    fsfApproved: 'N'
    osiApproved: 'N'
    oeApproved: 'N'
    ohApproved: 'N'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'N'
  Licenses:
  - alias:
    - MIT License
    - MIT
    identifier: MIT
    fsfApproved: 'Y'
    osiApproved: 'Y'
    oeApproved: 'Y'
    ohApproved: 'Y'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'Y'
  - alias:
    - Apache License 2.0
    - Apache-2.0
    identifier: Apache-2.0
    fsfApproved: 'Y'
    osiApproved: 'Y'
    oeApproved: 'Y'
    ohApproved: 'Y'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'Y'
  - alias:
    - GNU General Public License v3.0 only
    - GPL-3.0
    identifier: GPL-3.0-only
    fsfApproved: 'Y'
    osiApproved: 'Y'
    oeApproved: 'Y'
    ohApproved: 'N'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'Y'
  - alias:
    - Server Side Public License, v 1
    - SSPL-1.0
    identifier: SSPL-1.0
    fsfApproved: 'N'
    osiApproved: 'N'
    oeApproved: 'N'
    ohApproved: 'N'
    lowRisk: 'N'
    black: 'Y'
    blackReason: 不建议引入，对云厂商不友好
    exception: 'N'
    review: 'Y'
  - alias:
    - CC-BY-NC-4.0
    identifier: CC-BY-NC-4.0
    fsfApproved: 'N'
    osiApproved: 'N'
    oeApproved: 'N'
    ohApproved: 'N'
    lowRisk: 'Y'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'Y'
  - alias:
    - Classpath-exception-2.0
    identifier: Classpath-exception-2.0
    fsfApproved: 'N'
    osiApproved: 'N'
    oeApproved: 'N'
    ohApproved: 'N'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'Y'
    review: 'Y'
  - alias:
    - Mulan PSL v2
    identifier: MulanPSL-2.0
    fsfApproved: 'Y'
    osiApproved: 'Y'
    oeApproved: 'Y'
    ohApproved: 'Y'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'Y'
  - alias:
    - PostgreSQL License
    identifier: PostgreSQL
    fsfApproved: 'Y'
    osiApproved: 'Y'
    oeApproved: 'Y'
    ohApproved: 'N'
    lowRisk: 'N'
    black: 'N'
    blackReason: ''
    exception: 'N'
    review: 'Y'
"""

MIT_TEXT = """MIT License

Copyright (c) 2024 Example

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""

GPL_TEXT = """GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (C) 2007 Free Software Foundation, Inc.
"""

APACHE_TEXT = """Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/
"""


def _access(tmp_path):
    path = tmp_path / "Licenses_Access_List.yaml"
    path.write_text(LICENSE_LIST, encoding="utf-8")
    return LicenseAccessList(source=str(path)).load()


def _skill_dir(tmp_path):
    repo = tmp_path / "repo"
    skill = repo / "skills" / "demo"
    skill.mkdir(parents=True)
    return repo, skill


def test_classify_whitelist_black_and_restricted(tmp_path):
    access = _access(tmp_path)
    assert access.classify("MIT") == (STATUS_ALLOWED, "")
    status, reason = access.classify("SSPL-1.0")
    assert status == STATUS_BLACK
    assert "云厂商" in reason
    assert access.classify("CC-BY-NC-4.0")[0] == STATUS_RESTRICTED
    assert access.classify("Elastic-2.0")[0] == STATUS_UNKNOWN


def test_expression_and_or_with(tmp_path):
    access = _access(tmp_path)
    assert access.evaluate("MIT OR SSPL-1.0").status == STATUS_ALLOWED
    assert access.evaluate("MIT AND SSPL-1.0").status == STATUS_BLACK
    assert access.evaluate("GPL-3.0 WITH Classpath-exception-2.0").status == STATUS_ALLOWED
    assert access.evaluate("GPL-3.0 WITH Unknown-exception").status == STATUS_UNKNOWN
    assert access.evaluate("MIT AND").status == STATUS_UNKNOWN
    assert normalize_expression(["MIT", "Apache-2.0"]) == "MIT AND Apache-2.0"
    assert access.evaluate(["MIT", "Apache-2.0"]).status == STATUS_ALLOWED


def test_alias_and_ambiguous_name(tmp_path):
    access = _access(tmp_path)
    assert access.resolve("MIT License") == ("MIT", "")
    assert access.resolve("apache") == ("Apache", "")
    identifier, error = access.resolve("not-in-list")
    assert identifier is None
    assert "未在" in error


def test_scanner_frontmatter_license(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    (skill / "SKILL.md").write_text("---\nname: demo\nlicense: MIT\n---\n", encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill, "MIT")
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "MIT"


def test_scanner_license_file_and_repo_root_fallback(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    scanner = LicenseScanner(_access(tmp_path))
    verdict = scanner.scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "MIT"
    assert "LICENSE" in verdict.sources

    (skill / "LICENSES").mkdir()
    (skill / "LICENSES" / "Apache-2.0.txt").write_text(APACHE_TEXT, encoding="utf-8")
    verdict = scanner.scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert "Apache-2.0" in verdict.expression


def test_scanner_filename_nonstandard_alias_falls_back_to_content(tmp_path):
    """LICENSE-APACHE 这类文件名不能解析成非标准的 Apache，应按正文识别为 Apache-2.0."""
    repo, skill = _skill_dir(tmp_path)
    (skill / "LICENSE-APACHE").write_text(APACHE_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "Apache-2.0"


def test_scanner_finds_parent_directory_license(tmp_path):
    """skill 目录没有 LICENSE 时，向上查找父目录（如 skills/LICENSE）."""
    repo = tmp_path / "repo"
    skill = repo / "skills" / "demo"
    skill.mkdir(parents=True)
    (repo / "skills" / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert verdict.sources == ["skills/LICENSE"]


def test_scanner_black_and_restricted(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    (skill / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    scanner = LicenseScanner(_access(tmp_path))
    assert scanner.scan(repo, skill, "SSPL-1.0").status == STATUS_BLACK
    assert scanner.scan(repo, skill, "CC-BY-NC-4.0").status == STATUS_RESTRICTED


def test_scanner_missing_and_unknown_file(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    scanner = LicenseScanner(_access(tmp_path))
    assert scanner.scan(repo, skill).status == STATUS_MISSING

    (skill / "LICENSE").write_text("Some custom license text.", encoding="utf-8")
    verdict = scanner.scan(repo, skill)
    assert verdict.status == STATUS_UNKNOWN
    assert "无法从 license 文件识别" in verdict.reasons[0]


def test_scanner_conflict_between_declared_and_file(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    (skill / "LICENSE").write_text(GPL_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill, "MIT")
    assert verdict.status == STATUS_CONFLICT
    assert "不一致" in verdict.reasons[0]


def test_license_list_load_failure(tmp_path):
    missing = tmp_path / "missing.yaml"
    access = LicenseAccessList(source=str(missing), timeout=0.01)
    try:
        access.load()
    except Exception as exc:
        assert "拉取失败" in str(exc) or "解析失败" in str(exc)
    else:
        raise AssertionError("missing license list should fail")


CANN_TEXT = """CANN Open Software License Agreement Version 2.0

This CANN Open Software License Agreement Version 2.0 is a legal agreement
between you and Huawei, and it governs your use, modification, or distribution
of CANN Open Software.
"""


def _access_with_extra(tmp_path, extra_allow):
    path = tmp_path / "Licenses_Access_List.yaml"
    path.write_text(LICENSE_LIST, encoding="utf-8")
    return LicenseAccessList(source=str(path), extra_allow=extra_allow).load()


def test_extra_allow_classifies_unknown_license(tmp_path):
    """清单未收录的生态许可可通过 license_extra_allow 放行."""
    access = _access_with_extra(tmp_path, ["CANN-2.0"])
    assert access.resolve("cann-2.0") == ("CANN-2.0", "")
    assert access.classify("CANN-2.0") == (STATUS_ALLOWED, "")
    assert access.evaluate("CANN-2.0").status == STATUS_ALLOWED
    # 未列入 extra_allow 的仍然未知
    assert access.classify("Unknown-1.0")[0] == STATUS_UNKNOWN


def test_extra_allow_never_overrides_black(tmp_path):
    """补充放行不能覆盖清单的 black 判定."""
    access = _access_with_extra(tmp_path, ["SSPL-1.0"])
    assert access.classify("SSPL-1.0")[0] == STATUS_BLACK


def test_scanner_detects_cann_and_extra_allow(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(CANN_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access_with_extra(tmp_path, ["CANN-2.0"])).scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "CANN-2.0"


def test_scanner_placeholder_declared_falls_back_to_file(tmp_path):
    """frontmatter 占位声明解析不出 license 时，以 LICENSE 文件为准."""
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path)).scan(
        repo, skill, "Complete terms in LICENSE.txt"
    )
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "MIT"


def test_scanner_prefer_file_when_declared_restricted(tmp_path):
    """声明受限但文件明确允许时，prefer_file 以文件为准."""
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")

    strict = LicenseScanner(_access(tmp_path)).scan(repo, skill, "CC-BY-NC-4.0")
    assert strict.status == STATUS_RESTRICTED

    prefer = LicenseScanner(_access(tmp_path), prefer_file=True).scan(
        repo, skill, "CC-BY-NC-4.0"
    )
    assert prefer.status == STATUS_ALLOWED
    assert prefer.expression == "MIT"
    assert "不一致" in prefer.reasons[0]


def test_scanner_prefer_file_keeps_black(tmp_path):
    """black 声明不因 prefer_file 被文件许可覆盖."""
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path), prefer_file=True).scan(
        repo, skill, "SSPL-1.0"
    )
    assert verdict.status == STATUS_BLACK


def test_scanner_detects_mulan_psl_v2_and_postgresql(tmp_path):
    repo, skill = _skill_dir(tmp_path)
    (skill / "LICENSE").write_text(
        "Copyright (c) 2023 openEuler Embedded\n"
        "oebuild is licensed under Mulan PSL v2.\n",
        encoding="utf-8",
    )
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "MulanPSL-2.0"

    (skill / "LICENSE").write_text(
        "PostgreSQL License\n\nCopyright (c) 2025, Example\n", encoding="utf-8"
    )
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill)
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "PostgreSQL"


VENDOR_LICENSE_TEXTS = {
    "SUL-1.0": "Sustainable Use License\n\nYou may use the software only for internal purposes.\n",
    "FSL-1.1-Apache-2.0": (
        "Functional Source License, Version 1.1, Apache 2.0 Future License\n\n"
        "Copyright (c) 2025 Example\n"
    ),
    "Convex-CPL": "Convex Public License\n\nCopyright (c) 2025 Example\n",
}


def test_scanner_detects_vendor_source_available_licenses(tmp_path):
    """厂商/源码可见许可按正文识别，并可经 extra_allow 放行."""
    repo, skill = _skill_dir(tmp_path)
    for expected, text in VENDOR_LICENSE_TEXTS.items():
        (repo / "LICENSE").write_text(text, encoding="utf-8")
        access = _access_with_extra(tmp_path, list(VENDOR_LICENSE_TEXTS))
        verdict = LicenseScanner(access).scan(repo, skill)
        assert verdict.expression == expected, text
        assert verdict.status == STATUS_ALLOWED, text


def test_scanner_detects_sspl_as_black(tmp_path):
    """SSPL 正文可识别为 SSPL-1.0，并保留清单 black 结论."""
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(
        "Server Side Public License\nVersion 1\n\nCopyright (c) 2025 Example\n",
        encoding="utf-8",
    )
    verdict = LicenseScanner(_access(tmp_path)).scan(repo, skill)
    assert verdict.expression == "SSPL-1.0"
    assert verdict.status == STATUS_BLACK


def test_extra_allow_overrides_listed_restricted_entry(tmp_path):
    """已收录但未获 oE 认可的许可可经 extra_allow 放行（black 除外）."""
    access = _access_with_extra(tmp_path, ["CC-BY-NC-4.0"])
    assert access.classify("CC-BY-NC-4.0") == (STATUS_ALLOWED, "")


def test_scanner_prefer_file_when_declared_unknown(tmp_path):
    """声明无法识别但文件明确允许时，prefer_file 以文件为准."""
    repo, skill = _skill_dir(tmp_path)
    (repo / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    verdict = LicenseScanner(_access(tmp_path), prefer_file=True).scan(
        repo, skill, "Unknown-1.0"
    )
    assert verdict.status == STATUS_ALLOWED
    assert verdict.expression == "MIT"
